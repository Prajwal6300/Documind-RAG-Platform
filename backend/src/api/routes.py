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
from backend.src.utils.helpers import format_file_size, format_doc_response
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
from backend.src.vectordb import (
    add_chunks,
    remove_document,
    insert_document,
    update_document_status,
    get_document_by_id,
    get_document_by_name,
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
)
from backend.src.pipeline import answer_question, answer_question_stream
from backend.src.llm import get_llm_status

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

        chunks = create_chunks(
            pages=pages,
            source=original_filename,
            document_id=doc_id,
        )

        if not chunks:
            raise ValueError("Document was empty or could not be chunked.")

        log_pipeline_event("chunk_success", {"doc_id": doc_id, "chunks": len(chunks)})

        # Upsert chunks with embeddings into Supabase document_chunks
        add_chunks(chunks)

        log_pipeline_event("embed_success", {"doc_id": doc_id, "indexed_chunks": len(chunks)})

        # Update database with real page count and chunk count
        page_count = len(pages)
        chunk_count = len(chunks)
        update_document_status(doc_id, "indexed", pages=page_count, chunks=chunk_count)

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

    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    saved_filename = f"{doc_id}_{safe_name}"
    saved_path = UPLOAD_DIR / saved_filename

    try:
        # Reject exact duplicate uploads (same name) to avoid silent re-index conflicts
        existing = get_document_by_name(safe_name)
        if existing:
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
    }

    try:
        inserted = insert_document(doc_record)
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
    groundedness = result.get("groundedness") or {"score": 0.0, "confidence": "Low"}
    debug_info = result.get("debug")

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
    except Exception as exc:
        raise _handle_db_exception(exc) from exc

    target_doc_id = None
    if payload.scope and payload.scope != "All Documents":
        for d in indexed_docs:
            if d["name"].lower() == payload.scope.lower() or d["id"] == payload.scope:
                target_doc_id = d["id"]
                break

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
        questions.append({
            "id": "q-1",
            "title": f"Summarize key findings in {doc_names[0]}",
            "prompt": f"Summarize the key points, main conclusions, and findings from {doc_names[0]}."
        })

    if len(doc_names) >= 2:
        questions.append({
            "id": "q-2",
            "title": f"Compare {doc_names[0]} and {doc_names[1]}",
            "prompt": f"Compare the information and key differences between {doc_names[0]} and {doc_names[1]}."
        })
    else:
        questions.append({
            "id": "q-2",
            "title": "What are the main requirements and dates?",
            "prompt": f"Extract all important requirements, dates, deadlines, and milestone figures from the document."
        })

    questions.append({
        "id": "q-3",
        "title": "Extract all named entities and stakeholders",
        "prompt": "Extract all individuals, organizations, stakeholders, and referenced entities from the uploaded documents."
    })

    questions.append({
        "id": "q-4",
        "title": "Identify risks, exceptions, or liabilities",
        "prompt": "Identify any risks, exceptions, policy conditions, or liabilities mentioned in the uploaded documents."
    })

    return questions


@router.get("/api/logs")
def get_logs(lines: int = Query(60, ge=1, le=200)):
    """Observability endpoint returning recent pipeline telemetry."""
    return {
        "logs": get_recent_logs(lines)
    }


@router.get("/api/health")
@router.get("/api/status")
@router.get("/health")
def get_health():
    status = get_llm_status()
    try:
        active_docs = list_all_documents(include_archived=False)
        db_ok = True
        db_detail = "ok"
        indexed_count = sum(1 for d in active_docs if d.get("status") == "indexed")
        total_count = len(active_docs)
    except Exception as exc:
        db_ok = False
        db_detail = "unavailable"
        indexed_count = 0
        total_count = 0

    return {
        "status": "healthy" if db_ok else "degraded",
        "gemini": status,
        "database": {"status": db_detail},
        "indexed_documents_count": indexed_count,
        "total_documents_count": total_count,
    }