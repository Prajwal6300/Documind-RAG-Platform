"""Supabase PostgreSQL database management for DocuMind.

Handles persistence for:
- Uploaded & indexed document records
- Chat sessions and conversation history
- Grounded citations & evidence storage
- Archive states
"""

import os
import json
import time
from datetime import datetime
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector

from backend.src.utils.config import DATABASE_URL, DB_CONNECT_TIMEOUT, DB_STATEMENT_TIMEOUT_MS
from backend.src.utils.logger import logger


class DuplicateContentError(Exception):
    """Raised when an upload races an existing active content hash."""

    def __init__(self, existing: dict):
        self.existing = existing
        super().__init__(f"Duplicate content: {existing.get('name', 'existing document')}")

_pool: Optional[psycopg.Connection] = None


def get_db_connection():
    """Get a PostgreSQL connection with dict_row factory and pgvector registered.

    Applies a connect timeout and a per-statement timeout so no database
    operation can hang the backend indefinitely.
    """
    db_url = os.getenv("DATABASE_URL", DATABASE_URL).strip()
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set.")

    conn = psycopg.connect(
        db_url,
        row_factory=dict_row,
        prepare_threshold=None,
        autocommit=True,
        connect_timeout=int(DB_CONNECT_TIMEOUT),
        options=f"-c statement_timeout={int(DB_STATEMENT_TIMEOUT_MS)}",
    )
    try:
        register_vector(conn)
    except Exception:
        pass
    return conn


def _format_datetime(val) -> str:
    """Ensure datetime values are formatted as standard ISO strings."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _parse_json_field(val) -> list:
    """Parse JSON or JSONB field into python list/dict safely."""
    if val is None:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(str(val))
    except Exception:
        return []


def _json_dumps(value) -> str:
    return json.dumps(value if value is not None else [])


def init_db():
    """Verify database connection and initialize required tables if missing."""
    db_url = os.getenv("DATABASE_URL", DATABASE_URL).strip()
    if not db_url:
        return

    try:
        with psycopg.connect(db_url, prepare_threshold=None, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        title TEXT NOT NULL,
                        type TEXT NOT NULL,
                        size TEXT NOT NULL,
                        size_bytes BIGINT NOT NULL,
                        pages INTEGER DEFAULT 0,
                        chunks INTEGER DEFAULT 0,
                        file_path TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'processing',
                        error_message TEXT DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        is_archived BOOLEAN NOT NULL DEFAULT FALSE,
                        archived_at TIMESTAMPTZ DEFAULT NULL
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        snippet TEXT DEFAULT '',
                        doc_scope TEXT DEFAULT 'All Documents',
                        doc_count INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        is_archived BOOLEAN NOT NULL DEFAULT FALSE,
                        archived_at TIMESTAMPTZ DEFAULT NULL
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                        sender TEXT NOT NULL,
                        text TEXT DEFAULT '',
                        intro TEXT DEFAULT '',
                        sections_json JSONB DEFAULT '[]'::jsonb,
                        sources_json JSONB DEFAULT '[]'::jsonb,
                        evidences_json JSONB DEFAULT '[]'::jsonb,
                        no_context BOOLEAN NOT NULL DEFAULT FALSE,
                        timestamp TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        source TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        page INTEGER DEFAULT 1,
                        section TEXT DEFAULT '',
                        text TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        embedding vector NOT NULL
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS workspace_settings (
                        id TEXT PRIMARY KEY DEFAULT 'default',
                        name TEXT NOT NULL DEFAULT 'Local Workspace',
                        email TEXT DEFAULT '',
                        role TEXT DEFAULT 'Workspace User',
                        avatar_url TEXT DEFAULT '',
                        avatar_zoom INTEGER DEFAULT 110,
                        avatar_pos_json JSONB DEFAULT '{"x": 0, "y": 0}'::jsonb,
                        plan TEXT DEFAULT 'Self-hosted',
                        next_billing TEXT DEFAULT 'Not applicable',
                        notifications_json JSONB DEFAULT '{"documentSummaries": true, "productUpdates": false}'::jsonb,
                        privacy_json JSONB DEFAULT '{"aiTraining": false}'::jsonb,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS support_guides (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        category TEXT NOT NULL,
                        icon TEXT DEFAULT 'article',
                        sort_order INTEGER DEFAULT 0,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS support_tickets (
                        id TEXT PRIMARY KEY,
                        subject TEXT NOT NULL,
                        category TEXT NOT NULL,
                        message TEXT NOT NULL,
                        requester_email TEXT DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'open',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    INSERT INTO workspace_settings (id)
                    VALUES ('default')
                    ON CONFLICT (id) DO NOTHING;
                """)
                cur.executemany("""
                    INSERT INTO support_guides (id, title, summary, category, icon, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        category = EXCLUDED.category,
                        icon = EXCLUDED.icon,
                        sort_order = EXCLUDED.sort_order,
                        updated_at = NOW();
                """, [
                    (
                        "quickstart",
                        "Getting Started",
                        "Upload a supported document, wait for indexing and document analysis to complete, then ask grounded questions from the workspace.",
                        "Workspace",
                        "flag",
                        1,
                    ),
                    (
                        "retrieval-tips",
                        "Grounded Search Tips",
                        "Ask specific questions using names, dates, IDs, sections, or document scope to improve retrieval precision.",
                        "Retrieval",
                        "manage_search",
                        2,
                    ),
                    (
                        "library-management",
                        "Managing Documents",
                        "Archive documents to remove them from active retrieval while keeping their records available for restoration.",
                        "Library",
                        "folder_managed",
                        3,
                    ),
                ])
                cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_archived ON documents(is_archived, status);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at ASC);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(document_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_index ON document_chunks(document_id, chunk_index);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_created ON support_tickets(created_at DESC);")

                # Schema migrations for content hash and low-text warning fields
                try:
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT DEFAULT '';")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS warning_message TEXT DEFAULT '';")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_low_text BOOLEAN DEFAULT FALSE;")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_summary TEXT DEFAULT '';")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_category TEXT DEFAULT '';")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS entities_json JSONB DEFAULT '[]'::jsonb;")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS structure_json JSONB DEFAULT '[]'::jsonb;")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS suggested_questions_json JSONB DEFAULT '[]'::jsonb;")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS analysis_status TEXT DEFAULT 'pending';")
                    cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS analysis_warnings_json JSONB DEFAULT '[]'::jsonb;")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_content_hash ON documents(content_hash);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_category ON documents(doc_category);")
                except Exception as e:
                    logger.debug("Schema migration notice: %s", e)

                try:
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
                        ON document_chunks USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);
                    """)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Database init failed: %s", e)


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------

def _row_to_doc_dict(row: dict) -> dict:
    """Format row dictionary into document dictionary with clean types."""
    if not row:
        return None
    d = dict(row)
    d["is_archived"] = 1 if d.get("is_archived") else 0
    d["is_low_text"] = bool(d.get("is_low_text"))
    d["warning_message"] = d.get("warning_message") or ""
    d["content_hash"] = d.get("content_hash") or ""
    d["doc_summary"] = d.get("doc_summary") or ""
    d["doc_category"] = d.get("doc_category") or ""
    d["entities"] = _parse_json_field(d.get("entities_json"))
    d["structure"] = _parse_json_field(d.get("structure_json"))
    d["suggested_questions"] = _parse_json_field(d.get("suggested_questions_json"))
    d["analysis_status"] = d.get("analysis_status") or "pending"
    d["analysis_warnings"] = _parse_json_field(d.get("analysis_warnings_json"))
    d["created_at"] = _format_datetime(d.get("created_at"))
    d["archived_at"] = _format_datetime(d.get("archived_at")) if d.get("archived_at") else None
    return d


def insert_document(doc_data: dict) -> dict:
    created_at = doc_data.get("created_at") or datetime.now().isoformat()
    content_hash = doc_data.get("content_hash") or ""
    warning_message = doc_data.get("warning_message") or ""
    is_low_text = bool(doc_data.get("is_low_text", False))
    doc_summary = doc_data.get("doc_summary") or ""
    doc_category = doc_data.get("doc_category") or ""
    entities_json = _json_dumps(doc_data.get("entities", []))
    structure_json = _json_dumps(doc_data.get("structure", []))
    suggested_questions_json = _json_dumps(doc_data.get("suggested_questions", []))
    analysis_status = doc_data.get("analysis_status") or "pending"
    analysis_warnings_json = _json_dumps(doc_data.get("analysis_warnings", []))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # The API has a friendly preflight check, but concurrent uploads can
            # otherwise pass it together.  Serialize by hash within PostgreSQL
            # so duplicate protection works even before historical data is
            # cleaned sufficiently to add a unique index.
            if content_hash:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", (f"doc-content:{content_hash}",))
                cur.execute(
                    "SELECT id, name FROM documents WHERE content_hash = %s AND is_archived = FALSE LIMIT 1;",
                    (content_hash,),
                )
                existing = cur.fetchone()
                if existing and existing["id"] != doc_data["id"]:
                    raise DuplicateContentError(dict(existing))
            cur.execute("""
                INSERT INTO documents (
                    id, name, title, type, size, size_bytes, pages, chunks, file_path, status, error_message, created_at, is_archived, content_hash, warning_message, is_low_text,
                    doc_summary, doc_category, entities_json, structure_json, suggested_questions_json, analysis_status, analysis_warnings_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    title = EXCLUDED.title,
                    type = EXCLUDED.type,
                    size = EXCLUDED.size,
                    size_bytes = EXCLUDED.size_bytes,
                    pages = EXCLUDED.pages,
                    chunks = EXCLUDED.chunks,
                    file_path = EXCLUDED.file_path,
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    created_at = EXCLUDED.created_at,
                    is_archived = EXCLUDED.is_archived,
                    content_hash = EXCLUDED.content_hash,
                    warning_message = EXCLUDED.warning_message,
                    is_low_text = EXCLUDED.is_low_text,
                    doc_summary = EXCLUDED.doc_summary,
                    doc_category = EXCLUDED.doc_category,
                    entities_json = EXCLUDED.entities_json,
                    structure_json = EXCLUDED.structure_json,
                    suggested_questions_json = EXCLUDED.suggested_questions_json,
                    analysis_status = EXCLUDED.analysis_status,
                    analysis_warnings_json = EXCLUDED.analysis_warnings_json
                RETURNING *;
            """, (
                doc_data["id"],
                doc_data["name"],
                doc_data["title"],
                doc_data["type"],
                doc_data["size"],
                int(doc_data["size_bytes"]),
                int(doc_data.get("pages") or 0),
                int(doc_data.get("chunks") or 0),
                doc_data["file_path"],
                doc_data.get("status", "processing"),
                doc_data.get("error_message", ""),
                created_at,
                bool(doc_data.get("is_archived", False)),
                content_hash,
                warning_message,
                is_low_text,
                doc_summary,
                doc_category,
                entities_json,
                structure_json,
                suggested_questions_json,
                analysis_status,
                analysis_warnings_json,
            ))
            row = cur.fetchone()
            return _row_to_doc_dict(row)


def update_document_status(
    doc_id: str,
    status: str,
    pages: int = None,
    chunks: int = None,
    error_message: str = None,
    warning_message: str = None,
    is_low_text: bool = None,
    content_hash: str = None,
    analysis: dict = None,
):
    updates = ["status = %s"]
    params = [status]

    if pages is not None:
        updates.append("pages = %s")
        params.append(int(pages))
    if chunks is not None:
        updates.append("chunks = %s")
        params.append(int(chunks))
    if error_message is not None:
        updates.append("error_message = %s")
        params.append(error_message)
    if warning_message is not None:
        updates.append("warning_message = %s")
        params.append(warning_message)
    if is_low_text is not None:
        updates.append("is_low_text = %s")
        params.append(bool(is_low_text))
    if content_hash is not None:
        updates.append("content_hash = %s")
        params.append(content_hash)
    if analysis is not None:
        updates.extend([
            "doc_summary = %s",
            "doc_category = %s",
            "entities_json = %s",
            "structure_json = %s",
            "suggested_questions_json = %s",
            "analysis_status = %s",
            "analysis_warnings_json = %s",
        ])
        params.extend([
            analysis.get("summary") or "",
            analysis.get("document_type") or "",
            _json_dumps(analysis.get("entities", [])),
            _json_dumps(analysis.get("structure", [])),
            _json_dumps(analysis.get("suggested_questions", [])),
            analysis.get("analysis_status") or "pending",
            _json_dumps(analysis.get("analysis_warnings", [])),
        ])

    params.append(doc_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = %s;", params)


def get_document_by_id(doc_id: str) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE id = %s;", (doc_id,))
            row = cur.fetchone()
            return _row_to_doc_dict(row)


def get_document_by_name(name: str) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE name = %s AND is_archived = FALSE;", (name,))
            row = cur.fetchone()
            return _row_to_doc_dict(row)


def get_document_by_content_hash(content_hash: str) -> dict | None:
    if not content_hash:
        return None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM documents WHERE content_hash = %s AND is_archived = FALSE;", (content_hash,))
            row = cur.fetchone()
            return _row_to_doc_dict(row)


def list_all_documents(include_archived: bool = False) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if include_archived:
                cur.execute("SELECT * FROM documents ORDER BY created_at DESC;")
            else:
                cur.execute("SELECT * FROM documents WHERE is_archived = FALSE ORDER BY created_at DESC;")
            rows = cur.fetchall()
            return [_row_to_doc_dict(r) for r in rows]


def set_document_archived(doc_id: str, is_archived: bool):
    archived_at = datetime.now().isoformat() if is_archived else None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET is_archived = %s, archived_at = %s WHERE id = %s;",
                (bool(is_archived), archived_at, doc_id)
            )


def delete_document_permanently(doc_id: str) -> dict | None:
    doc = get_document_by_id(doc_id)
    if not doc:
        return None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s;", (doc_id,))
    return doc


# ---------------------------------------------------------------------------
# Chat Session & Message CRUD
# ---------------------------------------------------------------------------

def _row_to_session_dict(row: dict) -> dict:
    if not row:
        return None
    d = dict(row)
    d["is_archived"] = 1 if d.get("is_archived") else 0
    d["created_at"] = _format_datetime(d.get("created_at"))
    d["updated_at"] = _format_datetime(d.get("updated_at"))
    d["archived_at"] = _format_datetime(d.get("archived_at")) if d.get("archived_at") else None
    return d


def create_chat_session(session_id: str, title: str, doc_scope: str = "All Documents", snippet: str = "", doc_count: int = 0) -> dict:
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_sessions (id, title, snippet, doc_scope, doc_count, created_at, updated_at, is_archived)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    snippet = EXCLUDED.snippet,
                    doc_scope = EXCLUDED.doc_scope,
                    doc_count = EXCLUDED.doc_count,
                    updated_at = EXCLUDED.updated_at
                RETURNING *;
            """, (session_id, title, snippet, doc_scope, int(doc_count), now, now))
            row = cur.fetchone()
            return _row_to_session_dict(row)


def update_chat_session(session_id: str, title: str = None, snippet: str = None, doc_count: int = None):
    updates = ["updated_at = %s"]
    params = [datetime.now().isoformat()]

    if title is not None:
        updates.append("title = %s")
        params.append(title)
    if snippet is not None:
        updates.append("snippet = %s")
        params.append(snippet)
    if doc_count is not None:
        updates.append("doc_count = %s")
        params.append(int(doc_count))

    params.append(session_id)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE chat_sessions SET {', '.join(updates)} WHERE id = %s;", params)


def get_chat_session(session_id: str) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM chat_sessions WHERE id = %s;", (session_id,))
            row = cur.fetchone()
            return _row_to_session_dict(row)


def list_chat_sessions(include_archived: bool = False) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if include_archived:
                cur.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC;")
            else:
                cur.execute("SELECT * FROM chat_sessions WHERE is_archived = FALSE ORDER BY updated_at DESC;")
            rows = cur.fetchall()
            return [_row_to_session_dict(r) for r in rows]


def set_chat_session_archived(session_id: str, is_archived: bool):
    archived_at = datetime.now().isoformat() if is_archived else None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET is_archived = %s, archived_at = %s WHERE id = %s;",
                (bool(is_archived), archived_at, session_id)
            )


def delete_chat_session_permanently(session_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_sessions WHERE id = %s;", (session_id,))


def insert_chat_message(msg_data: dict) -> dict:
    created_at = datetime.now().isoformat()
    sections_json = json.dumps(msg_data.get("sections", []))
    sources_json = json.dumps(msg_data.get("sources", []))
    evidences_json = json.dumps(msg_data.get("evidences", []))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_messages (
                    id, session_id, sender, text, intro, sections_json, sources_json, evidences_json, no_context, timestamp, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    sender = EXCLUDED.sender,
                    text = EXCLUDED.text,
                    intro = EXCLUDED.intro,
                    sections_json = EXCLUDED.sections_json,
                    sources_json = EXCLUDED.sources_json,
                    evidences_json = EXCLUDED.evidences_json,
                    no_context = EXCLUDED.no_context;
            """, (
                msg_data["id"],
                msg_data["session_id"],
                msg_data["sender"],
                msg_data.get("text", ""),
                msg_data.get("intro", ""),
                sections_json,
                sources_json,
                evidences_json,
                bool(msg_data.get("no_context", False)),
                msg_data.get("timestamp", datetime.now().strftime("%I:%M %p")),
                created_at
            ))
    return msg_data


def get_session_messages(session_id: str) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC;", (session_id,))
            rows = cur.fetchall()

    messages = []
    for r in rows:
        d = dict(r)
        messages.append({
            "id": d["id"],
            "sessionId": d["session_id"],
            "sender": d["sender"],
            "text": d["text"] or "",
            "intro": d["intro"] or "",
            "sections": _parse_json_field(d.get("sections_json")),
            "sources": _parse_json_field(d.get("sources_json")),
            "evidences": _parse_json_field(d.get("evidences_json")),
            "noContext": bool(d.get("no_context")),
            "timestamp": d.get("timestamp") or "",
        })
    return messages


# ---------------------------------------------------------------------------
# Workspace Settings & Support
# ---------------------------------------------------------------------------

def _row_to_settings_dict(row: dict) -> dict:
    if not row:
        return None
    d = dict(row)
    return {
        "name": d.get("name") or "Local Workspace",
        "email": d.get("email") or "",
        "role": d.get("role") or "Workspace User",
        "avatarUrl": d.get("avatar_url") or "",
        "avatarZoom": int(d.get("avatar_zoom") or 110),
        "avatarPos": _parse_json_field(d.get("avatar_pos_json")) or {"x": 0, "y": 0},
        "plan": d.get("plan") or "Self-hosted",
        "nextBilling": d.get("next_billing") or "Not applicable",
        "notifications": _parse_json_field(d.get("notifications_json")) or {
            "documentSummaries": True,
            "productUpdates": False,
        },
        "privacy": _parse_json_field(d.get("privacy_json")) or {"aiTraining": False},
        "updatedAt": _format_datetime(d.get("updated_at")),
    }


def get_workspace_settings() -> dict:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workspace_settings (id)
                VALUES ('default')
                ON CONFLICT (id) DO NOTHING;
            """)
            cur.execute("SELECT * FROM workspace_settings WHERE id = 'default';")
            return _row_to_settings_dict(cur.fetchone())


def update_workspace_settings(updates: dict) -> dict:
    current = get_workspace_settings()
    merged = {
        **current,
        **{k: v for k, v in (updates or {}).items() if v is not None},
    }
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workspace_settings SET
                    name = %s,
                    email = %s,
                    role = %s,
                    avatar_url = %s,
                    avatar_zoom = %s,
                    avatar_pos_json = %s,
                    plan = %s,
                    next_billing = %s,
                    notifications_json = %s,
                    privacy_json = %s,
                    updated_at = NOW()
                WHERE id = 'default'
                RETURNING *;
            """, (
                merged.get("name") or "Local Workspace",
                merged.get("email") or "",
                merged.get("role") or "Workspace User",
                merged.get("avatarUrl") or "",
                int(merged.get("avatarZoom") or 110),
                _json_dumps(merged.get("avatarPos") or {"x": 0, "y": 0}),
                merged.get("plan") or "Self-hosted",
                merged.get("nextBilling") or "Not applicable",
                _json_dumps(merged.get("notifications") or {}),
                _json_dumps(merged.get("privacy") or {}),
            ))
            return _row_to_settings_dict(cur.fetchone())


def list_support_guides() -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, summary, category, icon, sort_order, updated_at
                FROM support_guides
                ORDER BY sort_order ASC, title ASC;
            """)
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "summary": r["summary"],
            "category": r["category"],
            "icon": r.get("icon") or "article",
            "sortOrder": r.get("sort_order") or 0,
            "updatedAt": _format_datetime(r.get("updated_at")),
        }
        for r in rows
    ]


def create_support_ticket(ticket: dict) -> dict:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO support_tickets (id, subject, category, message, requester_email, status)
                VALUES (%s, %s, %s, %s, %s, 'open')
                RETURNING *;
            """, (
                ticket["id"],
                ticket["subject"],
                ticket["category"],
                ticket["message"],
                ticket.get("requester_email", ""),
            ))
            r = cur.fetchone()
    return {
        "id": r["id"],
        "subject": r["subject"],
        "category": r["category"],
        "message": r["message"],
        "requesterEmail": r.get("requester_email") or "",
        "status": r["status"],
        "createdAt": _format_datetime(r.get("created_at")),
    }


# Initialize database schema on module load
init_db()
