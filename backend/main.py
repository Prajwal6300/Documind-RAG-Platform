"""DocuMind Backend API (FastAPI)

Enterprise-grade RAG backend integrating:
- Google Gemini Generation & Embeddings
- ChromaDB Vector Store with Hybrid Search & Cross-Encoder Re-Ranking
- PyMuPDF / python-docx / openpyxl document parsing
- SQLite persistence for documents, chat history, and archive
- Server-Sent Events (SSE) Streaming & Observability Logs
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from rag.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, GEMINI_MODEL
from rag.document_loader import load_document
from rag.chunker import create_chunks
from rag.vector_store import add_chunks, remove_document
from rag.rag_pipeline import answer_question, answer_question_stream, NO_CONTEXT_MESSAGE
from rag.llm import get_llm_status
from rag.logger import log_pipeline_event, get_recent_logs
import backend.database as db

app = FastAPI(
    title="DocuMind RAG API",
    version="1.0.0",
    description="Full RAG Document Chatbot Backend powered by Google Gemini and ChromaDB",
)

# Enable CORS for Vite frontend development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _get_doc_icon_and_color(file_type: str):
    t = file_type.upper()
    if t == "PDF":
        return "picture_as_pdf", "text-coral-accent"
    elif t in ("DOCX", "DOC", "TXT", "MD"):
        return "article", "text-tertiary"
    elif t in ("XLSX", "XLS", "CSV"):
        return "table_chart", "text-secondary"
    elif t in ("PPTX", "PPT"):
        return "slideshow", "text-coral-accent"
    return "description", "text-secondary"


def _format_doc_response(doc: dict) -> dict:
    icon, color = _get_doc_icon_and_color(doc.get("type", "PDF"))
    created_at_str = doc.get("created_at", "")
    try:
        dt = datetime.fromisoformat(created_at_str)
        date_added = dt.strftime("%b %d, %Y")
    except Exception:
        date_added = "Recently"

    status_raw = doc.get("status", "processing")
    status_display = status_raw.capitalize() if status_raw else "Processing"

    return {
        "id": doc["id"],
        "name": doc["name"],
        "title": doc.get("title") or doc["name"],
        "type": doc.get("type", "PDF").upper(),
        "size": doc.get("size", "0 KB"),
        "pages": doc.get("pages", 0),
        "chunks": doc.get("chunks", 0),
        "dateAdded": date_added,
        "status": status_display,
        "icon": icon,
        "accentColor": color,
        "isArchived": bool(doc.get("is_archived", 0)),
        "errorMessage": doc.get("error_message", ""),
    }


def _process_document_pipeline(doc_id: str, file_path: str, original_filename: str):
    """Background task to extract, chunk, embed, and index document in ChromaDB."""
    try:
        log_pipeline_event("parse_start", {"doc_id": doc_id, "file": original_filename})
        db.update_document_status(doc_id, "processing")
        
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

        # Upsert chunks with embeddings into ChromaDB
        add_chunks(chunks)

        log_pipeline_event("embed_success", {"doc_id": doc_id, "indexed_chunks": len(chunks)})

        # Update database with real page count and chunk count
        page_count = len(pages)
        chunk_count = len(chunks)
        db.update_document_status(doc_id, "indexed", pages=page_count, chunks=chunk_count)

    except Exception as exc:
        err_msg = str(exc)
        log_pipeline_event("pipeline_error", {"doc_id": doc_id, "error": err_msg})
        db.update_document_status(doc_id, "failed", error_message=err_msg)


# ---------------------------------------------------------------------------
# Document Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/documents/upload")
@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
):
    original_filename = file.filename or "uploaded_file"
    ext = Path(original_filename).suffix.lower().lstrip(".")

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '.{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    saved_filename = f"{doc_id}_{original_filename}"
    saved_path = UPLOAD_DIR / saved_filename

    # Read and enforce file size limit
    content = await file.read()
    size_bytes = len(content)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB.",
        )

    with open(saved_path, "wb") as f:
        f.write(content)

    doc_title = (title or "").strip() or original_filename.rsplit(".", 1)[0]
    file_type = ext.upper()
    size_str = _format_file_size(size_bytes)

    doc_record = {
        "id": doc_id,
        "name": original_filename,
        "title": doc_title,
        "type": file_type,
        "size": size_str,
        "size_bytes": size_bytes,
        "pages": 0,
        "chunks": 0,
        "file_path": str(saved_path),
        "status": "processing",
    }

    inserted = db.insert_document(doc_record)

    log_pipeline_event("upload", {
        "doc_id": doc_id,
        "filename": original_filename,
        "size": size_str,
    })

    # Trigger indexing in background
    background_tasks.add_task(
        _process_document_pipeline,
        doc_id=doc_id,
        file_path=str(saved_path),
        original_filename=original_filename,
    )

    return _format_doc_response(inserted)


@app.get("/api/documents")
@app.get("/documents")
def get_documents(include_archived: bool = Query(False)):
    docs = db.list_all_documents(include_archived=include_archived)
    return [_format_doc_response(d) for d in docs]


@app.get("/api/documents/{doc_id}")
@app.get("/documents/{doc_id}")
def get_single_document(doc_id: str):
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _format_doc_response(doc)


@app.delete("/api/documents/{doc_id}")
@app.delete("/documents/{doc_id}")
def delete_or_archive_document(doc_id: str, permanent: bool = Query(False)):
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if permanent:
        remove_document(doc_id)
        db.delete_document_permanently(doc_id)
        try:
            if doc.get("file_path") and os.path.exists(doc["file_path"]):
                os.remove(doc["file_path"])
        except Exception:
            pass
        return {"success": True, "message": f"Document '{doc['name']}' permanently deleted."}
    else:
        db.set_document_archived(doc_id, True)
        return {"success": True, "message": f"Document '{doc['name']}' moved to archive."}


@app.post("/api/documents/{doc_id}/archive")
@app.post("/documents/{doc_id}/archive")
def archive_document(doc_id: str):
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.set_document_archived(doc_id, True)
    return {"success": True, "message": f"Document '{doc['name']}' archived."}


@app.post("/api/documents/{doc_id}/restore")
@app.post("/documents/{doc_id}/restore")
def restore_document(doc_id: str):
    doc = db.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.set_document_archived(doc_id, False)
    return {"success": True, "message": f"Document '{doc['name']}' restored to active library."}


@app.get("/api/documents/{doc_id}/download")
@app.get("/documents/{doc_id}/download")
def download_document(doc_id: str):
    doc = db.get_document_by_id(doc_id)
    if not doc or not doc.get("file_path") or not os.path.exists(doc["file_path"]):
        raise HTTPException(status_code=404, detail="Document file not found.")
    return FileResponse(doc["file_path"], filename=doc["name"])


# ---------------------------------------------------------------------------
# Archive Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/archive")
@app.get("/archive")
def get_archive():
    all_docs = db.list_all_documents(include_archived=True)
    archived_docs = [d for d in all_docs if d.get("is_archived")]

    all_sessions = db.list_chat_sessions(include_archived=True)
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
            "docData": _format_doc_response(d)
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
    message: str
    scope: Optional[str] = "All Documents"
    session_id: Optional[str] = None


@app.post("/api/chat")
@app.post("/chat")
def handle_chat(payload: ChatRequest):
    user_query = payload.message.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    active_docs = db.list_all_documents(include_archived=False)
    indexed_docs = [d for d in active_docs if d.get("status") == "indexed"]
    processing_docs = [d for d in active_docs if d.get("status") == "processing"]

    # Check if scoped document is currently processing
    if payload.scope and payload.scope != "All Documents":
        for pd in processing_docs:
            if pd["name"].lower() == payload.scope.lower() or pd["id"] == payload.scope:
                return {
                    "sessionId": payload.session_id or f"session-{uuid.uuid4().hex[:10]}",
                    "message": {
                        "id": f"msg-{uuid.uuid4().hex[:10]}",
                        "sender": "assistant",
                        "intro": f"Document '{pd['name']}' is currently being indexed. Please wait a moment until processing finishes.",
                        "text": f"Document '{pd['name']}' is currently being indexed. Please wait a moment until processing finishes.",
                        "sections": [],
                        "sources": [],
                        "evidences": [],
                        "noContext": True,
                        "groundedness": {"score": 0.0, "confidence": "Low"},
                        "timestamp": datetime.now().strftime("%I:%M %p"),
                    }
                }

    # Guardrail if no documents indexed
    if not indexed_docs:
        return {
            "sessionId": payload.session_id or f"session-{uuid.uuid4().hex[:10]}",
            "message": {
                "id": f"msg-{uuid.uuid4().hex[:10]}",
                "sender": "assistant",
                "intro": "I couldn't find that in your uploaded documents because no documents have been uploaded and indexed yet. Please upload a PDF, DOCX, or TXT document first.",
                "text": "I couldn't find that in your uploaded documents because no documents have been uploaded and indexed yet. Please upload a PDF, DOCX, or TXT document first.",
                "sections": [],
                "sources": [],
                "evidences": [],
                "noContext": True,
                "groundedness": {"score": 0.0, "confidence": "Low"},
                "timestamp": datetime.now().strftime("%I:%M %p"),
            }
        }

    # Resolve document scope
    target_doc_id = None
    if payload.scope and payload.scope != "All Documents":
        for d in indexed_docs:
            if d["name"].lower() == payload.scope.lower() or d["id"] == payload.scope or d["title"].lower() == payload.scope.lower():
                target_doc_id = d["id"]
                break

    # Get or create chat session
    session_id = payload.session_id
    session = db.get_chat_session(session_id) if session_id else None

    if not session:
        session_id = f"session-{uuid.uuid4().hex[:10]}"
        title = user_query[:50] + ("..." if len(user_query) > 50 else "")
        session = db.create_chat_session(
            session_id=session_id,
            title=title,
            doc_scope=payload.scope or "All Documents",
            snippet=user_query,
            doc_count=len(indexed_docs) if not target_doc_id else 1
        )

    prior_messages = db.get_session_messages(session_id)

    # Save user message
    user_msg_id = f"msg-{uuid.uuid4().hex[:10]}"
    db.insert_chat_message({
        "id": user_msg_id,
        "session_id": session_id,
        "sender": "user",
        "text": user_query,
        "timestamp": datetime.now().strftime("%I:%M %p"),
    })

    # Run RAG Pipeline
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
    db.insert_chat_message({
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
    db.update_chat_session(session_id, snippet=snippet, doc_count=len(indexed_docs) if not target_doc_id else 1)

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


@app.post("/api/chat/stream")
@app.post("/chat/stream")
def handle_chat_stream(payload: ChatRequest):
    user_query = payload.message.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    active_docs = db.list_all_documents(include_archived=False)
    indexed_docs = [d for d in active_docs if d.get("status") == "indexed"]

    target_doc_id = None
    if payload.scope and payload.scope != "All Documents":
        for d in indexed_docs:
            if d["name"].lower() == payload.scope.lower() or d["id"] == payload.scope:
                target_doc_id = d["id"]
                break

    session_id = payload.session_id or f"session-{uuid.uuid4().hex[:10]}"
    session = db.get_chat_session(session_id)
    if not session:
        title = user_query[:50] + ("..." if len(user_query) > 50 else "")
        db.create_chat_session(
            session_id=session_id,
            title=title,
            doc_scope=payload.scope or "All Documents",
            snippet=user_query,
            doc_count=len(indexed_docs) if not target_doc_id else 1
        )

    prior_messages = db.get_session_messages(session_id)

    db.insert_chat_message({
        "id": f"msg-{uuid.uuid4().hex[:10]}",
        "session_id": session_id,
        "sender": "user",
        "text": user_query,
        "timestamp": datetime.now().strftime("%I:%M %p"),
    })

    def event_generator():
        gen = answer_question_stream(
            question=user_query,
            document_id=target_doc_id,
            chat_history=prior_messages,
        )
        for item in gen:
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/chat/sessions")
@app.get("/chat/sessions")
def get_chat_sessions():
    sessions = db.list_chat_sessions(include_archived=False)
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


@app.get("/api/chat/{session_id}")
@app.get("/chat/{session_id}")
def get_chat_history(session_id: str):
    session = db.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    messages = db.get_session_messages(session_id)
    return {
        "session": dict(session),
        "messages": messages
    }


@app.delete("/api/chat/sessions/{session_id}")
@app.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str, permanent: bool = Query(False)):
    session = db.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    if permanent:
        db.delete_chat_session_permanently(session_id)
    else:
        db.set_chat_session_archived(session_id, True)
    return {"success": True, "message": "Chat session removed."}


# ---------------------------------------------------------------------------
# Suggested Questions & Observability Logs
# ---------------------------------------------------------------------------

@app.get("/api/suggested-questions")
@app.get("/suggested-questions")
def get_suggested_questions():
    active_docs = db.list_all_documents(include_archived=False)
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


@app.get("/api/logs")
def get_logs(lines: int = Query(60)):
    """Observability endpoint returning recent pipeline telemetry."""
    return {
        "logs": get_recent_logs(lines)
    }


@app.get("/api/health")
@app.get("/api/status")
@app.get("/health")
def get_health():
    status = get_llm_status()
    active_docs = db.list_all_documents(include_archived=False)
    indexed_count = sum(1 for d in active_docs if d.get("status") == "indexed")
    return {
        "status": "healthy",
        "gemini": status,
        "indexed_documents_count": indexed_count,
        "total_documents_count": len(active_docs),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
