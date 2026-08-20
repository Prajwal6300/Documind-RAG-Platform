"""Data migration script: Migrate local SQLite + ChromaDB data into Supabase (Postgres + pgvector).

Preserves:
- All documents, pages, chunk counts, and archive states from SQLite
- All chat sessions, analysis threads, and message histories from SQLite
- All chunk texts, metadata, and embeddings from ChromaDB (with automatic dimension alignment)
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from backend.src.embeddings.embedder import embed_documents
from backend.src.vectordb.database import get_db_connection
from backend.src.vectordb.vector_store import add_chunks

SQLITE_PATH = ROOT_DIR / "data" / "documind.db"
CHROMA_DIR = ROOT_DIR / "data" / "chroma"


def migrate_sqlite_data():
    """Migrate documents, chat sessions, and chat messages from local SQLite to Supabase."""
    if not SQLITE_PATH.exists():
        print(f"[SKIP] SQLite database not found at {SQLITE_PATH}")
        return 0, 0, 0

    print(f"\n[1/3] Reading SQLite records from {SQLITE_PATH}...")
    conn_sq = sqlite3.connect(str(SQLITE_PATH))
    conn_sq.row_factory = sqlite3.Row

    # 1. Documents
    cur = conn_sq.cursor()
    cur.execute("SELECT * FROM documents;")
    docs = [dict(r) for r in cur.fetchall()]

    # 2. Chat Sessions
    cur.execute("SELECT * FROM chat_sessions;")
    sessions = [dict(r) for r in cur.fetchall()]

    # 3. Chat Messages
    cur.execute("SELECT * FROM chat_messages;")
    messages = [dict(r) for r in cur.fetchall()]
    conn_sq.close()

    print(f"  Found {len(docs)} document(s), {len(sessions)} session(s), {len(messages)} message(s).")

    with get_db_connection() as conn_pg:
        with conn_pg.cursor() as cur_pg:
            # Insert Documents
            for doc in docs:
                cur_pg.execute("""
                    INSERT INTO documents (
                        id, name, title, type, size, size_bytes, pages, chunks, file_path, status, error_message, created_at, is_archived, archived_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                        archived_at = EXCLUDED.archived_at;
                """, (
                    doc["id"],
                    doc["name"],
                    doc["title"],
                    doc["type"],
                    doc["size"],
                    int(doc["size_bytes"]),
                    int(doc.get("pages") or 0),
                    int(doc.get("chunks") or 0),
                    doc["file_path"],
                    doc.get("status", "indexed"),
                    doc.get("error_message", ""),
                    doc.get("created_at") or datetime.now().isoformat(),
                    bool(doc.get("is_archived", 0)),
                    doc.get("archived_at"),
                ))

            # Insert Chat Sessions
            for s in sessions:
                cur_pg.execute("""
                    INSERT INTO chat_sessions (
                        id, title, snippet, doc_scope, doc_count, created_at, updated_at, is_archived, archived_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        snippet = EXCLUDED.snippet,
                        doc_scope = EXCLUDED.doc_scope,
                        doc_count = EXCLUDED.doc_count,
                        updated_at = EXCLUDED.updated_at,
                        is_archived = EXCLUDED.is_archived,
                        archived_at = EXCLUDED.archived_at;
                """, (
                    s["id"],
                    s["title"],
                    s.get("snippet", ""),
                    s.get("doc_scope", "All Documents"),
                    int(s.get("doc_count") or 0),
                    s.get("created_at") or datetime.now().isoformat(),
                    s.get("updated_at") or datetime.now().isoformat(),
                    bool(s.get("is_archived", 0)),
                    s.get("archived_at"),
                ))

            # Insert Chat Messages
            for m in messages:
                cur_pg.execute("""
                    INSERT INTO chat_messages (
                        id, session_id, sender, text, intro, sections_json, sources_json, evidences_json, no_context, timestamp, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        sender = EXCLUDED.sender,
                        text = EXCLUDED.text,
                        intro = EXCLUDED.intro,
                        sections_json = EXCLUDED.sections_json,
                        sources_json = EXCLUDED.sources_json,
                        evidences_json = EXCLUDED.evidences_json,
                        no_context = EXCLUDED.no_context;
                """, (
                    m["id"],
                    m["session_id"],
                    m["sender"],
                    m.get("text", ""),
                    m.get("intro", ""),
                    m.get("sections_json") or "[]",
                    m.get("sources_json") or "[]",
                    m.get("evidences_json") or "[]",
                    bool(m.get("no_context", 0)),
                    m.get("timestamp", ""),
                    m.get("created_at") or datetime.now().isoformat(),
                ))

    print("  [OK] Successfully migrated SQLite documents, sessions, and messages.")
    return len(docs), len(sessions), len(messages)


def migrate_chroma_data():
    """Migrate chunks and vector embeddings from local ChromaDB to Supabase."""
    chroma_sqlite = CHROMA_DIR / "chroma.sqlite3"
    if not chroma_sqlite.exists():
        print(f"[SKIP] ChromaDB data not found at {CHROMA_DIR}")
        return 0

    print(f"\n[2/3] Reading ChromaDB collections from {CHROMA_DIR}...")
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        rag_collection = client.get_collection("rag_documents")
        total_chunks = rag_collection.count()
        print(f"  Found {total_chunks} chunk(s) in ChromaDB collection 'rag_documents'.")

        if total_chunks == 0:
            return 0

        data = rag_collection.get(include=["documents", "metadatas", "embeddings"])
        ids = data.get("ids", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])
        embeddings = data.get("embeddings", [])

        # Check embedding dimensions against current embedding model
        chunks_to_add = []
        for c_id, text, meta, emb in zip(ids, documents, metadatas, embeddings):
            meta_dict = meta or {}
            chunk_obj = {
                "chunk_id": c_id,
                "text": text,
                "metadata": meta_dict,
                "embedding": emb if (emb is not None and len(emb) == 3072) else None,
            }
            chunks_to_add.append(chunk_obj)

        print(f"  Writing {len(chunks_to_add)} chunk(s) into Supabase document_chunks table...")
        add_chunks(chunks_to_add)
        print(f"  [OK] Successfully migrated {len(chunks_to_add)} chunk(s) into Supabase!")
        return len(chunks_to_add)

    except Exception as e:
        print(f"  [ERROR] ChromaDB migration error: {e}")
        return 0


def verify_supabase_data():
    """Verify total records migrated into Supabase."""
    print("\n[3/3] Verifying migrated data in Supabase...")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM documents;")
            doc_cnt = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM chat_sessions;")
            session_cnt = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM chat_messages;")
            msg_cnt = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM document_chunks;")
            chunk_cnt = cur.fetchone()["count"]

    print("=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"Documents in Supabase:        {doc_cnt}")
    print(f"Chat Sessions in Supabase:    {session_cnt}")
    print(f"Chat Messages in Supabase:    {msg_cnt}")
    print(f"Vector Chunks in Supabase:    {chunk_cnt}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("DOCUMIND STORAGE MIGRATION: SQLite + ChromaDB -> Supabase")
    print("=" * 70)
    migrate_sqlite_data()
    migrate_chroma_data()
    verify_supabase_data()


if __name__ == "__main__":
    main()
