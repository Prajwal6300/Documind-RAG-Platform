"""SQLite database management for DocuMind.

Handles persistence for:
- Uploaded & indexed document records
- Chat sessions and conversation history
- Grounded citations & evidence storage
- Archive states
"""

import os
import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime

DB_DIR = Path("data")
DB_PATH = DB_DIR / "documind.db"


def get_db_connection():
    """Get a thread-safe SQLite connection with dictionary-like row factory."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    """Initialize database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            size TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            pages INTEGER DEFAULT 0,
            chunks INTEGER DEFAULT 0,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'processing',
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            is_archived INTEGER DEFAULT 0,
            archived_at TEXT DEFAULT NULL
        );
    """)

    # Chat sessions table (used for Recent Analysis)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            snippet TEXT DEFAULT '',
            doc_scope TEXT DEFAULT 'All Documents',
            doc_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_archived INTEGER DEFAULT 0,
            archived_at TEXT DEFAULT NULL
        );
    """)

    # Chat messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            text TEXT DEFAULT '',
            intro TEXT DEFAULT '',
            sections_json TEXT DEFAULT '[]',
            sources_json TEXT DEFAULT '[]',
            evidences_json TEXT DEFAULT '[]',
            no_context INTEGER DEFAULT 0,
            timestamp TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );
    """)

    # Create indexes for fast lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_archived ON documents(is_archived, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at ASC);")

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------

def insert_document(doc_data: dict) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO documents (
            id, name, title, type, size, size_bytes, pages, chunks, file_path, status, error_message, created_at, is_archived
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_data["id"],
        doc_data["name"],
        doc_data["title"],
        doc_data["type"],
        doc_data["size"],
        doc_data["size_bytes"],
        doc_data.get("pages", 0),
        doc_data.get("chunks", 0),
        doc_data["file_path"],
        doc_data.get("status", "processing"),
        doc_data.get("error_message", ""),
        doc_data.get("created_at", datetime.now().isoformat()),
        0
    ))
    conn.commit()
    conn.close()
    return get_document_by_id(doc_data["id"])


def update_document_status(doc_id: str, status: str, pages: int = None, chunks: int = None, error_message: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["status = ?"]
    params = [status]

    if pages is not None:
        updates.append("pages = ?")
        params.append(pages)
    if chunks is not None:
        updates.append("chunks = ?")
        params.append(chunks)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)

    params.append(doc_id)
    cursor.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_document_by_id(doc_id: str) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_document_by_name(name: str) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE name = ? AND is_archived = 0", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def list_all_documents(include_archived: bool = False) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_archived:
        cursor.execute("SELECT * FROM documents ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM documents WHERE is_archived = 0 ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_document_archived(doc_id: str, is_archived: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    archived_at = datetime.now().isoformat() if is_archived else None
    cursor.execute(
        "UPDATE documents SET is_archived = ?, archived_at = ? WHERE id = ?",
        (1 if is_archived else 0, archived_at, doc_id)
    )
    conn.commit()
    conn.close()


def delete_document_permanently(doc_id: str) -> dict | None:
    doc = get_document_by_id(doc_id)
    if not doc:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return doc


# ---------------------------------------------------------------------------
# Chat Session & Message CRUD
# ---------------------------------------------------------------------------

def create_chat_session(session_id: str, title: str, doc_scope: str = "All Documents", snippet: str = "", doc_count: int = 0) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO chat_sessions (id, title, snippet, doc_scope, doc_count, created_at, updated_at, is_archived)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (session_id, title, snippet, doc_scope, doc_count, now, now))
    conn.commit()
    conn.close()
    return get_chat_session(session_id)


def update_chat_session(session_id: str, title: str = None, snippet: str = None, doc_count: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["updated_at = ?"]
    params = [datetime.now().isoformat()]

    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if snippet is not None:
        updates.append("snippet = ?")
        params.append(snippet)
    if doc_count is not None:
        updates.append("doc_count = ?")
        params.append(doc_count)

    params.append(session_id)
    cursor.execute(f"UPDATE chat_sessions SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_chat_session(session_id: str) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def list_chat_sessions(include_archived: bool = False) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_archived:
        cursor.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC")
    else:
        cursor.execute("SELECT * FROM chat_sessions WHERE is_archived = 0 ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_chat_session_archived(session_id: str, is_archived: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    archived_at = datetime.now().isoformat() if is_archived else None
    cursor.execute(
        "UPDATE chat_sessions SET is_archived = ?, archived_at = ? WHERE id = ?",
        (1 if is_archived else 0, archived_at, session_id)
    )
    conn.commit()
    conn.close()


def delete_chat_session_permanently(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def insert_chat_message(msg_data: dict) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_messages (
            id, session_id, sender, text, intro, sections_json, sources_json, evidences_json, no_context, timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        msg_data["id"],
        msg_data["session_id"],
        msg_data["sender"],
        msg_data.get("text", ""),
        msg_data.get("intro", ""),
        json.dumps(msg_data.get("sections", [])),
        json.dumps(msg_data.get("sources", [])),
        json.dumps(msg_data.get("evidences", [])),
        1 if msg_data.get("no_context") else 0,
        msg_data.get("timestamp", datetime.now().strftime("%I:%M %p")),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return msg_data


def get_session_messages(session_id: str) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()

    messages = []
    for r in rows:
        d = dict(r)
        messages.append({
            "id": d["id"],
            "sessionId": d["session_id"],
            "sender": d["sender"],
            "text": d["text"],
            "intro": d["intro"],
            "sections": json.loads(d["sections_json"] or "[]"),
            "sources": json.loads(d["sources_json"] or "[]"),
            "evidences": json.loads(d["evidences_json"] or "[]"),
            "noContext": bool(d["no_context"]),
            "timestamp": d["timestamp"]
        })
    return messages


# Initialize on import
init_db()
