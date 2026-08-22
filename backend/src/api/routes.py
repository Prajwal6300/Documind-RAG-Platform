"""FastAPI route handlers for DocuMind backend.

Defines REST and SSE endpoints for:
- Document management (Upload, List, Get, Delete, Archive, Restore, Download)
- Grounded chat & SSE token streaming (/api/chat, /api/chat/stream)
- Chat session management (/api/chat/sessions, /api/chat/{session_id})
- Archive overview (/api/archive)
- Suggested questions & observability telemetry (/api/suggested-questions, /api/logs)
- Health check & LLM readiness (/api/health, /api/status)

Error contract: every failure returns HTTPException with a clear JSON body of
the shape ``{"detail": "..."}`` and an appropriate status code
(400/404/409/413/415/422/429/500/503). No stack traces reach the client.
"""

import os
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Form, Query, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.src.utils.config import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    MAX_QUERY_LENGTH,
    UPLOAD_DIR,
    RATE_LIMIT_CHAT_LIMIT,
    RATE_LIMIT_CHAT_WINDOW,
    RATE_LIMIT_UPLOAD_LIMIT,
    RATE_LIMIT_UPLOAD_WINDOW,
)
from backend.src.utils.helpers import format_file_size, format_doc_response, file_hash
from backend.src.utils.logger import log_pipeline_event, get_recent_logs
from backend.src.utils.errors import (
    bad_request,
    not_found,
    conflict,
    database_unavailable,
)
from backend.src.utils.rate_limit import check_rate_limit
from backend.src.utils.uploads import validate_upload, sanitize_filename
from backend.src.ingestion import load_document
from backend.src.chunking import create_chunks
from backend.src.analysis import analyze_document_text
from backend.src.vectordb import (
    add_chunks,
    remove_document,
    insert_document,
    update_document_status,
    get_document_by_id,
    get_document_by_name,
    get_document_by_content_hash,
    DuplicateContentError,
    list_all_documents,
    set_document_archived,
    delete_document_permanently,
    create_chat_session,
    update_chat_session,
    get_chat_session,
    list_chat_sessions,
    set_chat_session_archived,
    delete_chat_session_permanently,
    insert_chat_message,
    get_session_messages,
    get_workspace_settings,
    update_workspace_settings,
    list_support_guides,
    create_support_ticket,
)
from backend.src.pipeline import answer_question, answer_question_stream
from backend.src.llm import get_llm_status
from backend.src.prompts.prompt_templates import NO_CONTEXT_MESSAGE

router = APIRouter()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Error mapping helpers
# ---------------------------------------------------------------------------

def _handle_db_exception(exc: Exception) -> HTTPException:
    """Map psycopg connection failures to a friendly 503."""
    from backend.src.utils.errors import is_database_error
    if is_database_error(exc):
        return database_unavailable()
    return HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")


def _safe_bool(value: bool) -> bool:
    return 1 if value else 0


def _process_document_pipeline(doc_id: str, file_path: str, original_filename: str):
    """Background task to extract, chunk, embed, and index document in Supabase pgvector."""
    try:
        log_pipeline_event("parse_start", {"doc_id": doc_id, "file": original_filename})
        update_document_status(doc_id, "processing")

        pages = load_document(file_path)
        if not pages:
            raise ValueError("No text content could be extracted from this document.")

        log_pipeline_event("parse_success", {"doc_id": doc_id, "pages": len(pages)})

        # Detect low-text documents (e.g. certificates, image-heavy PDFs, scanned docs)
        total_text_chars = sum(len((p.get("text") or "").strip()) for p in pages)
        is_low_text = total_text_chars < 120
        warning_msg = ""
        if is_low_text:
            warning_msg = (
                f"This document appears to contain very little extractable text ({total_text_chars} characters). "
                "Answers to questions about image or certificate content may be limited."
            )
            log_pipeline_event("low_text_warning", {
                "doc_id": doc_id,
                "filename": original_filename,
                "total_chars": total_text_chars,
            })

        chunks = create_chunks(
            pages=pages,
            source=original_filename,
            document_id=doc_id,
        )

        if not chunks:
            raise ValueError("Document was empty or could not be chunked.")

        log_pipeline_event("chunk_success", {"doc_id": doc_id, "chunks": len(chunks)})

        log_pipeline_event("analysis_start", {"doc_id": doc_id, "filename": original_filename})
        analysis = analyze_document_text(pages, original_filename, is_low_text=is_low_text)
        log_pipeline_event("analysis_success", {
            "doc_id": doc_id,
            "status": analysis.get("analysis_status"),
            "document_type": analysis.get("document_type"),
            "entities": analysis.get("entities", [])[:8],
            "structure_count": len(analysis.get("structure", [])),
            "low_content": is_low_text,
        })

        # Upsert chunks with embeddings into Supabase document_chunks
        add_chunks(chunks)

        log_pipeline_event("embed_success", {"doc_id": doc_id, "indexed_chunks": len(chunks)})

        # Update database with real page count, chunk count, and low-text status
        page_count = len(pages)
        chunk_count = len(chunks)
        update_document_status(
            doc_id,
            "indexed",
            pages=page_count,
            chunks=chunk_count,
            warning_message=warning_msg,
            is_low_text=is_low_text,
            analysis=analysis,
        )

    except Exception as exc:
        err_msg = str(exc)
        log_pipeline_event("pipeline_error", {"doc_id": doc_id, "error": err_msg})
        try:
            update_document_status(doc_id, "failed", error_message=err_msg)
        except Exception:
            log_pipeline_event("pipeline_error", {"doc_id": doc_id, "error": "could not persist failure status"})


# ---------------------------------------------------------------------------
# Document Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/documents/upload")
@router.post("/documents/upload")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
):
    check_rate_limit(request, RATE_LIMIT_UPLOAD_LIMIT, RATE_LIMIT_UPLOAD_WINDOW, scope="upload")

    original_filename = file.filename or "uploaded_file"

    # Read full content once (bounded by size validation below)
    content = await file.read()

    # Server-side content validation: empty file, real size, MIME detection,
    # extension/content match, and safe filename (path-traversal safe).
    safe_name, detected_ext = validate_upload(original_filename, content)

    doc_title = (title or "").strip() or safe_name.rsplit(".", 1)[0]
    size_bytes = len(content)
    size_str = format_file_size(size_bytes)
    file_type = detected_ext.upper()
    c_hash = file_hash(content)

    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    saved_filename = f"{doc_id}_{safe_name}"
    saved_path = UPLOAD_DIR / saved_filename

    try:
        # Check 1: Reject duplicate uploads with identical content hash
        existing_hash = get_document_by_content_hash(c_hash)
        if existing_hash:
            raise conflict(
                f"A document with identical content ('{existing_hash['name']}') already exists in the library. "
                "Archive or delete it first, or use the existing document for questions.",
                "duplicate_content",
            )

        # Check 2: Reject duplicate uploads with exact same name
        existing_name = get_document_by_name(safe_name)
        if existing_name:
            raise conflict(
                f"A document named '{safe_name}' already exists in the library. "
                "Archive or delete it first, or rename the file before uploading.",
                "duplicate_document",
            )

        with open(saved_path, "wb") as f:
            f.write(content)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    doc_record = {
        "id": doc_id,
        "name": safe_name,
        "title": doc_title,
        "type": file_type,
        "size": size_str,
        "size_bytes": size_bytes,
        "pages": 0,
        "chunks": 0,
        "file_path": str(saved_path),
        "status": "processing",
        "content_hash": c_hash,
        "warning_message": "",
        "is_low_text": False,
        "doc_summary": "",
        "doc_category": "",
        "entities": [],
        "structure": [],
        "suggested_questions": [],
        "analysis_status": "pending",
        "analysis_warnings": [],
    }

    try:
        inserted = insert_document(doc_record)
    except DuplicateContentError as exc:
        if saved_path.exists():
            saved_path.unlink()
        raise conflict(
            f"A document with identical content ('{exc.existing['name']}') already exists in the library.",
            "duplicate_content",
        ) from exc
    except Exception as exc:
        # Clean up the orphaned file if DB write failed
        if saved_path.exists():
            try:
                saved_path.unlink()
            except Exception:
                pass
        raise _handle_db_exception(exc) from exc

    log_pipeline_event("upload", {
        "doc_id": doc_id,
        "filename": safe_name,
        "size": size_str,
        "content_hash": c_hash[:12],
    })

    # Trigger indexing in background
    background_tasks.add_task(
        _process_document_pipeline,
        doc_id=doc_id,
        file_path=str(saved_path),
        original_filename=safe_name,
    )

    return format_doc_response(inserted)


@router.get("/api/documents")
@router.get("/documents")
def get_documents(include_archived: bool = Query(False)):
    try:
        docs = list_all_documents(include_archived=include_archived)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    return [format_doc_response(d) for d in docs]


@router.get("/api/documents/{doc_id}")
@router.get("/documents/{doc_id}")
def get_single_document(doc_id: str):
    try:
        doc = get_document_by_id(doc_id)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    if not doc:
        raise not_found("Document not found.")
    return format_doc_response(doc)


@router.delete("/api/documents/{doc_id}")
@router.delete("/documents/{doc_id}")
def delete_or_archive_document(doc_id: str, permanent: bool = Query(False)):
    try:
        doc = get_document_by_id(doc_id)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    if not doc:
        raise not_found("Document not found.")

    try:
        if permanent:
            remove_document(doc_id)
            try:
                if doc.get("file_path") and os.path.exists(doc["file_path"]):
                    os.remove(doc["file_path"])
            except Exception:
                pass
            return {"success": True, "message": f"Document '{doc['name']}' permanently deleted."}
        else:
            set_document_archived(doc_id, True)
            return {"success": True, "message": f"Document '{doc['name']}' moved to archive."}
    except Exception as exc:
        raise _handle_db_exception(exc) from exc


@router.post("/api/documents/{doc_id}/archive")
@router.post("/documents/{doc_id}/archive")
def archive_document(doc_id: str):
    try:
        doc = get_document_by_id(doc_id)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    if not doc:
        raise not_found("Document not found.")
    try:
        set_document_archived(doc_id, True)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    return {"success": True, "message": f"Document '{doc['name']}' archived."}


@router.post("/api/documents/{doc_id}/restore")
@router.post("/documents/{doc_id}/restore")
def restore_document(doc_id: str):
    try:
        doc = get_document_by_id(doc_id)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    if not doc:
        raise not_found("Document not found.")
    try:
        set_document_archived(doc_id, False)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    return {"success": True, "message": f"Document '{doc['name']}' restored to active library."}


@router.get("/api/documents/{doc_id}/download")
@router.get("/documents/{doc_id}/download")
def download_document(doc_id: str):
    try:
        doc = get_document_by_id(doc_id)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    if not doc or not doc.get("file_path") or not os.path.exists(doc["file_path"]):
        raise not_found("Document file not found.")
    return FileResponse(doc["file_path"], filename=doc["name"])


# ---------------------------------------------------------------------------
# Archive Endpoint
# ---------------------------------------------------------------------------

@router.get("/api/archive")
@router.get("/archive")
def get_archive():
    try:
        all_docs = list_all_documents(include_archived=True)
        all_sessions = list_chat_sessions(include_archived=True)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    archived_docs = [d for d in all_docs if d.get("is_archived")]
    archived_sessions = [s for s in all_sessions if s.get("is_archived")]

    items = []
    for d in archived_docs:
        try:
            dt = datetime.fromisoformat(d.get("archived_at") or d.get("created_at", ""))
            date_str = dt.strftime("%b %d, %Y")
        except Exception:
            date_str = "Recently"

        items.append({
            "id": f"arch-doc-{d['id']}",
            "rawId": d["id"],
            "type": "document",
            "title": d["name"],
            "context": f"{d.get('pages', 1)} pages • {d.get('size', '')} • Moved from active library.",
            "dateArchived": date_str,
            "icon": "description",
            "docData": format_doc_response(d)
        })

    for s in archived_sessions:
        try:
            dt = datetime.fromisoformat(s.get("archived_at") or s.get("updated_at", ""))
            date_str = dt.strftime("%b %d, %Y")
        except Exception:
            date_str = "Recently"

        items.append({
            "id": f"arch-chat-{s['id']}",
            "rawId": s["id"],
            "type": "chat",
            "title": s["title"],
            "context": f"Chat Session • {s.get('snippet', 'Past analysis session')}",
            "dateArchived": date_str,
            "icon": "forum",
        })

    return items


# ---------------------------------------------------------------------------
# Chat & Streaming Endpoints
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., description="User question.")
    scope: Optional[str] = "All Documents"
    session_id: Optional[str] = None


class WorkspaceSettingsUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    avatarUrl: Optional[str] = None
    avatarZoom: Optional[int] = Field(None, ge=100, le=200)
    avatarPos: Optional[dict] = None
    notifications: Optional[dict] = None
    privacy: Optional[dict] = None


class SupportTicketRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)
    requesterEmail: Optional[str] = None


def _validate_chat_message(message: str) -> str:
    user_query = (message or "").strip()
    if not user_query:
        raise bad_request("Question cannot be empty.", "empty_question")
    if len(user_query) > MAX_QUERY_LENGTH:
        raise bad_request(
            f"Question is too long (maximum {MAX_QUERY_LENGTH} characters).",
            "question_too_long",
        )
    # Strip control characters that can confuse prompt assembly
    cleaned = "".join(ch for ch in user_query if ord(ch) >= 32 or ch in "\t\r\n")
    return cleaned.strip()


def _no_context_response(session_id: str, message: str) -> dict:
    return {
        "sessionId": session_id,
        "message": {
            "id": f"msg-{uuid.uuid4().hex[:10]}",
            "sender": "assistant",
            "intro": message,
            "text": message,
            "sections": [],
            "sources": [],
            "evidences": [],
            "noContext": True,
            "groundedness": {"score": 0.0, "confidence": "Low"},
            "timestamp": datetime.now().strftime("%I:%M %p"),
        }
    }


@router.post("/api/chat")
@router.post("/chat")
def handle_chat(request: Request, payload: ChatRequest):
    check_rate_limit(request, RATE_LIMIT_CHAT_LIMIT, RATE_LIMIT_CHAT_WINDOW, scope="chat")

    user_query = _validate_chat_message(payload.message)

    try:
        active_docs = list_all_documents(include_archived=False)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    indexed_docs = [d for d in active_docs if d.get("status") == "indexed"]
    processing_docs = [d for d in active_docs if d.get("status") == "processing"]

    # Check if scoped document is currently processing
    if payload.scope and payload.scope != "All Documents":
        for pd in processing_docs:
            if pd["name"].lower() == payload.scope.lower() or pd["id"] == payload.scope:
                return _no_context_response(
                    payload.session_id,
                    f"Document '{pd['name']}' is currently being indexed. Please wait a moment until processing finishes.",
                )

    # Guardrail if no documents indexed
    if not indexed_docs:
        return _no_context_response(
            payload.session_id,
            "I couldn't find that in your uploaded documents because no documents have been uploaded and indexed yet. "
            "Please upload a PDF, DOCX, or TXT document first.",
        )

    # Resolve document scope
    target_doc_id = None
    if payload.scope and payload.scope != "All Documents":
        for d in indexed_docs:
            if d["name"].lower() == payload.scope.lower() or d["id"] == payload.scope or d["title"].lower() == payload.scope.lower():
                target_doc_id = d["id"]
                break
        if target_doc_id is None:
            return _no_context_response(
                payload.session_id,
                f"I couldn't find an indexed document matching '{payload.scope}'. Please choose an indexed document from the scope selector.",
            )

    # Get or create chat session
    session_id = payload.session_id
    try:
        session = get_chat_session(session_id) if session_id else None

        if not session:
            session_id = f"session-{uuid.uuid4().hex[:10]}"
            title = user_query[:50] + ("..." if len(user_query) > 50 else "")
            session = create_chat_session(
                session_id=session_id,
                title=title,
                doc_scope=payload.scope or "All Documents",
                snippet=user_query,
                doc_count=len(indexed_docs) if not target_doc_id else 1
            )

        prior_messages = get_session_messages(session_id)

        # Save user message
        user_msg_id = f"msg-{uuid.uuid4().hex[:10]}"
        insert_chat_message({
            "id": user_msg_id,
            "session_id": session_id,
            "sender": "user",
            "text": user_query,
            "timestamp": datetime.now().strftime("%I:%M %p"),
        })
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    # Run RAG Pipeline (LLM errors are already converted to friendly messages)
    result = answer_question(
        question=user_query,
        document_id=target_doc_id,
        chat_history=prior_messages,
    )

    assistant_msg_id = f"msg-{uuid.uuid4().hex[:10]}"
    intro = result.get("intro") or result.get("answer") or ""
    sections = result.get("sections") or []
    sources = result.get("sources") or []
    evidences = result.get("evidences") or []
    no_context = result.get("no_context", False)
    groundedness = result.get("groundedness") or {"score": 0.0, "confidence": "Low", "is_grounded": False}
    debug_info = result.get("debug")

    if no_context or intro == NO_CONTEXT_MESSAGE:
        sections = []
        sources = []
        evidences = []
        no_context = True

    # Save assistant message
    try:
        insert_chat_message({
            "id": assistant_msg_id,
            "session_id": session_id,
            "sender": "assistant",
            "text": result.get("answer", ""),
            "intro": intro,
            "sections": sections,
            "sources": sources,
            "evidences": evidences,
            "no_context": no_context,
            "timestamp": datetime.now().strftime("%I:%M %p"),
        })

        # Update session snippet
        snippet = intro[:120] + ("..." if len(intro) > 120 else "")
        update_chat_session(session_id, snippet=snippet, doc_count=len(indexed_docs) if not target_doc_id else 1)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    return {
        "sessionId": session_id,
        "message": {
            "id": assistant_msg_id,
            "sender": "assistant",
            "intro": intro,
            "text": result.get("answer", ""),
            "sections": sections,
            "sources": sources,
            "evidences": evidences,
            "noContext": no_context,
            "groundedness": groundedness,
            "debug": debug_info,
            "timestamp": datetime.now().strftime("%I:%M %p"),
        }
    }


@router.post("/api/chat/stream")
@router.post("/chat/stream")
def handle_chat_stream(request: Request, payload: ChatRequest):
    check_rate_limit(request, RATE_LIMIT_CHAT_LIMIT, RATE_LIMIT_CHAT_WINDOW, scope="chat")

    user_query = _validate_chat_message(payload.message)

    try:
        active_docs = list_all_documents(include_archived=False)
        indexed_docs = [d for d in active_docs if d.get("status") == "indexed"]
        processing_docs = [d for d in active_docs if d.get("status") == "processing"]
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    if payload.scope and payload.scope != "All Documents":
        for pd in processing_docs:
            if pd["name"].lower() == payload.scope.lower() or pd["id"] == payload.scope:
                def processing_generator():
                    msg = f"Document '{pd['name']}' is currently being indexed. Please wait a moment until processing finishes."
                    yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'no_context': True})}\n\n"
                return StreamingResponse(processing_generator(), media_type="text/event-stream")

    if not indexed_docs:
        def no_docs_generator():
            msg = "I couldn't find that in your uploaded documents because no documents have been uploaded and indexed yet. Please upload a PDF, DOCX, or TXT document first."
            yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'no_context': True})}\n\n"
        return StreamingResponse(no_docs_generator(), media_type="text/event-stream")

    target_doc_id = None
    if payload.scope and payload.scope != "All Documents":
        for d in indexed_docs:
            if d["name"].lower() == payload.scope.lower() or d["id"] == payload.scope:
                target_doc_id = d["id"]
                break
        if target_doc_id is None:
            def missing_scope_generator():
                msg = f"I couldn't find an indexed document matching '{payload.scope}'. Please choose an indexed document from the scope selector."
                yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'no_context': True})}\n\n"
            return StreamingResponse(missing_scope_generator(), media_type="text/event-stream")

    session_id = payload.session_id or f"session-{uuid.uuid4().hex[:10]}"
    try:
        session = get_chat_session(session_id)
        if not session:
            title = user_query[:50] + ("..." if len(user_query) > 50 else "")
            create_chat_session(
                session_id=session_id,
                title=title,
                doc_scope=payload.scope or "All Documents",
                snippet=user_query,
                doc_count=len(indexed_docs) if not target_doc_id else 1
            )

        prior_messages = get_session_messages(session_id)

        insert_chat_message({
            "id": f"msg-{uuid.uuid4().hex[:10]}",
            "session_id": session_id,
            "sender": "user",
            "text": user_query,
            "timestamp": datetime.now().strftime("%I:%M %p"),
        })
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    def event_generator():
        try:
            gen = answer_question_stream(
                question=user_query,
                document_id=target_doc_id,
                chat_history=prior_messages,
            )
            for item in gen:
                yield f"data: {json.dumps(item)}\n\n"
        except Exception as exc:
            from backend.src.utils.errors import is_database_error
            if is_database_error(exc):
                message = "The database is temporarily unavailable. Please try again in a moment."
            else:
                message = "An unexpected error occurred while generating the answer. Please try again."
            yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'error': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/chat/sessions")
@router.get("/chat/sessions")
def get_chat_sessions():
    try:
        sessions = list_chat_sessions(include_archived=False)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    results = []
    for s in sessions:
        try:
            dt = datetime.fromisoformat(s.get("updated_at") or s.get("created_at", ""))
            date_str = dt.strftime("%b %d, %Y")
        except Exception:
            date_str = "Recently"

        results.append({
            "id": s["id"],
            "title": s["title"],
            "snippet": s.get("snippet", ""),
            "date": date_str,
            "docCount": s.get("doc_count", 0),
            "icon": "description",
            "query": s["title"]
        })
    return results


@router.get("/api/chat/{session_id}")
@router.get("/chat/{session_id}")
def get_chat_history(session_id: str):
    try:
        session = get_chat_session(session_id)
        if not session:
            raise not_found("Chat session not found.")
        messages = get_session_messages(session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    return {
        "session": dict(session),
        "messages": messages
    }


@router.delete("/api/chat/sessions/{session_id}")
@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str, permanent: bool = Query(False)):
    try:
        session = get_chat_session(session_id)
        if not session:
            raise not_found("Chat session not found.")
        if permanent:
            delete_chat_session_permanently(session_id)
        else:
            set_chat_session_archived(session_id, True)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    return {"success": True, "message": "Chat session removed."}


# ---------------------------------------------------------------------------
# Suggested Questions & Observability Logs
# ---------------------------------------------------------------------------

@router.get("/api/suggested-questions")
@router.get("/suggested-questions")
def get_suggested_questions():
    try:
        active_docs = list_all_documents(include_archived=False)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc
    indexed_docs = [d for d in active_docs if d.get("status") == "indexed"]

    if not indexed_docs:
        return []

    doc_names = [d["name"] for d in indexed_docs]
    questions = []

    if len(doc_names) >= 1:
        first_doc = indexed_docs[0]
        first_type = (first_doc.get("doc_category") or first_doc.get("documentType") or first_doc.get("type") or "document").replace("_", " ")
        first_suggested = first_doc.get("suggested_questions") or []
        if first_suggested:
            questions.append({
                "id": "q-1",
                "title": first_suggested[0],
                "prompt": first_suggested[0],
            })
        else:
            questions.append({
                "id": "q-1",
                "title": f"What are the key details in this {first_type}?",
                "prompt": f"What are the key details in {doc_names[0]}?",
            })

    if len(doc_names) >= 2:
        questions.append({
            "id": "q-2",
            "title": f"Compare {doc_names[0]} and {doc_names[1]}",
            "prompt": f"Compare the information and key differences between {doc_names[0]} and {doc_names[1]}."
        })

    for d in indexed_docs:
        for question in d.get("suggested_questions", []) or []:
            if len(questions) >= 4:
                break
            if question and all(q["prompt"].lower() != question.lower() for q in questions):
                questions.append({
                    "id": f"q-{len(questions) + 1}",
                    "title": question,
                    "prompt": question,
                })
        if len(questions) >= 4:
            break

    if len(questions) < 4 and len(doc_names) >= 2:
        questions.append({
            "id": f"q-{len(questions) + 1}",
            "title": "Which documents mention the same entities?",
            "prompt": "Which uploaded documents mention the same people, organizations, dates, or identifiers?"
        })

    if len(questions) < 4:
        questions.append({
            "id": f"q-{len(questions) + 1}",
            "title": "What entities and dates are present?",
            "prompt": "Extract the named entities, dates, IDs, and key terms present in the uploaded documents."
        })

    return questions[:4]


@router.get("/api/logs")
def get_logs(lines: int = Query(60, ge=1, le=200)):
    """Observability endpoint returning recent pipeline telemetry."""
    return {
        "logs": get_recent_logs(lines)
    }


# ---------------------------------------------------------------------------
# Settings & Support
# ---------------------------------------------------------------------------

@router.get("/api/settings")
@router.get("/settings")
def get_settings():
    try:
        return get_workspace_settings()
    except Exception as exc:
        raise _handle_db_exception(exc) from exc


@router.patch("/api/settings")
@router.patch("/settings")
def patch_settings(payload: WorkspaceSettingsUpdate):
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates:
        email = (updates.get("email") or "").strip()
        if email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", email):
            raise bad_request("Please enter a valid email address.", "invalid_email")
        updates["email"] = email
    try:
        return update_workspace_settings(updates)
    except Exception as exc:
        raise _handle_db_exception(exc) from exc


@router.get("/api/support/guides")
@router.get("/support/guides")
def get_support_guides():
    try:
        return list_support_guides()
    except Exception as exc:
        raise _handle_db_exception(exc) from exc


@router.post("/api/support/tickets")
@router.post("/support/tickets")
def submit_support_ticket(payload: SupportTicketRequest):
    subject = payload.subject.strip()
    message = payload.message.strip()
    category = payload.category.strip()
    requester_email = (payload.requesterEmail or "").strip()
    if not subject or not message:
        raise bad_request("Please provide both a subject and an inquiry message.", "invalid_support_ticket")
    if requester_email and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", requester_email):
        raise bad_request("Please enter a valid requester email address.", "invalid_email")
    try:
        ticket = create_support_ticket({
            "id": f"ticket-{uuid.uuid4().hex[:12]}",
            "subject": subject,
            "category": category,
            "message": message,
            "requester_email": requester_email,
        })
        return {"success": True, "ticket": ticket}
    except Exception as exc:
        raise _handle_db_exception(exc) from exc


@router.get("/api/health")
@router.get("/api/status")
@router.get("/health")
def get_health():
    # Check database connectivity first
    db_ok = True
    db_detail = "ok"
    try:
        active_docs = list_all_documents(include_archived=False)
        indexed_count = sum(1 for d in active_docs if d.get("status") == "indexed")
        total_count = len(active_docs)
    except Exception as exc:
        db_ok = False
        db_detail = "unavailable"
        indexed_count = 0
        total_count = 0

    # Check LLM status
    status = get_llm_status()
    gemini_ready = status.get("ready", False)

    # Overall status: healthy only if both DB and LLM are available
    overall_healthy = db_ok and gemini_ready

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "gemini": status,
        "database": {"status": db_detail},
        "indexed_documents_count": indexed_count,
        "total_documents_count": total_count,
    }
