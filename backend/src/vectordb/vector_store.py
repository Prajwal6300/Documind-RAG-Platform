"""Supabase PostgreSQL + pgvector Vector Store operations for DocuMind.

Manages vector embeddings, chunk storage, cosine similarity retrieval,
adjacent context expansion, and document lifecycle in PostgreSQL.
"""

import hashlib
import json
import time
from typing import Optional, List, Dict, Any

import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector

from backend.src.embeddings.embedder import embed_documents, embed_query
from backend.src.utils.config import DATABASE_URL
from backend.src.vectordb.database import get_db_connection, insert_document, get_document_by_id, list_all_documents, delete_document_permanently

# Dimension of the Gemini embedding model and of the HNSW halfvec expression index
HNSW_INDEX_DIM = 3072


def _chunk_id(document_id: str | None, source: str, page: int | None, chunk_index: int) -> str:
    """Generate deterministic hash for a document chunk."""
    key = f"{document_id}|{source}|{page}|{chunk_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class VectorCollectionCompat:
    """Compatibility wrapper providing count(), get(), query(), and delete() for tests & eval scripts."""

    def count(self) -> int:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS count FROM document_chunks;")
                    row = cur.fetchone()
                    return int(row["count"]) if row else 0
        except Exception:
            return 0

    def query(self, query_embeddings: list[list[float]], n_results: int = 5, where: dict | None = None) -> dict:
        if not query_embeddings or not query_embeddings[0]:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        query_emb = query_embeddings[0]
        doc_id = None
        if where and "document_id" in where:
            doc_id = where["document_id"]

        results = query_vector_store(query_emb, top_k=n_results, document_id=doc_id)

        ids = [r["chunk_id"] for r in results]
        documents = [r["text"] for r in results]
        metadatas = [r["metadata"] for r in results]
        distances = [r["distance"] for r in results]

        return {
            "ids": [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    def get(self, ids: list[str] | None = None, where: dict | None = None, include: list[str] | None = None) -> dict:
        chunks = []
        if where and "document_id" in where:
            chunks = get_document_chunks(where["document_id"])
        elif ids:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, text, metadata FROM document_chunks WHERE id = ANY(%s);", (ids,))
                    rows = cur.fetchall()
                    chunks = [{"chunk_id": r["id"], "text": r["text"], "metadata": r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}")} for r in rows]
        else:
            chunks = get_all_chunks()

        return {
            "ids": [c["chunk_id"] for c in chunks],
            "documents": [c["text"] for c in chunks],
            "metadatas": [c["metadata"] for c in chunks],
        }

    def delete(self, ids: list[str] | None = None, where: dict | None = None):
        if where and "document_id" in where:
            remove_document(where["document_id"])
        elif ids:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM document_chunks WHERE id = ANY(%s);", (ids,))


_collection_compat = VectorCollectionCompat()


def get_collection():
    """Return collection interface for backward compatibility."""
    return _collection_compat


def add_chunks(chunks: list[dict]):
    """Insert or upsert document chunks and their vector embeddings into Supabase."""
    if not chunks:
        return

    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk.get("metadata", {}) for chunk in chunks]

    # Check if embeddings are already present in chunk objects
    embeddings = [chunk.get("embedding") for chunk in chunks]
    if any(e is None for e in embeddings):
        computed = embed_documents(documents)
        embeddings = computed

    records = []
    for chunk, text, meta, emb in zip(chunks, documents, metadatas, embeddings):
        meta_dict = meta if isinstance(meta, dict) else {}
        doc_id = meta_dict.get("document_id") or chunk.get("document_id") or "unknown_doc"
        source = meta_dict.get("source") or chunk.get("source") or "Unknown"
        page = meta_dict.get("page") or chunk.get("page") or 1
        try:
            page = int(page)
        except Exception:
            page = 1
        chunk_idx = meta_dict.get("chunk_index") if meta_dict.get("chunk_index") is not None else chunk.get("chunk_index", 0)
        section = meta_dict.get("section") or chunk.get("section") or ""
        c_id = chunk.get("chunk_id") or _chunk_id(doc_id, source, page, chunk_idx)

        # Store chunk_id in metadata dict for consistency
        meta_dict["chunk_id"] = c_id
        meta_dict["document_id"] = doc_id
        meta_dict["source"] = source
        meta_dict["page"] = page
        meta_dict["chunk_index"] = chunk_idx

        records.append((
            c_id,
            doc_id,
            source,
            int(chunk_idx),
            page,
            section,
            text,
            json.dumps(meta_dict),
            emb,
        ))

    # Ensure parent document records exist in documents table to satisfy FK constraint
    unique_doc_ids = {r[1]: (r[2], r[7]) for r in records}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for d_id, (d_src, d_meta) in unique_doc_ids.items():
                cur.execute("SELECT id FROM documents WHERE id = %s;", (d_id,))
                if not cur.fetchone():
                    ext = d_src.rsplit(".", 1)[-1].upper() if "." in d_src else "DOC"
                    cur.execute("""
                        INSERT INTO documents (
                            id, name, title, type, size, size_bytes, pages, chunks, file_path, status, error_message, created_at, is_archived
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'indexed', '', NOW(), FALSE)
                        ON CONFLICT (id) DO NOTHING;
                    """, (d_id, d_src, d_src, ext, "0 KB", 0, 1, len(chunks), d_src))

            # Batch upsert chunks into document_chunks
            cur.executemany("""
                INSERT INTO document_chunks (
                    id, document_id, source, chunk_index, page, section, text, metadata, embedding
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    source = EXCLUDED.source,
                    chunk_index = EXCLUDED.chunk_index,
                    page = EXCLUDED.page,
                    section = EXCLUDED.section,
                    text = EXCLUDED.text,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding;
            """, records)


def get_document(doc_id: str) -> dict | None:
    """Fetch document metadata by id."""
    doc = get_document_by_id(doc_id)
    if doc:
        return {
            "id": doc["id"],
            "source": doc["name"],
            "type": doc["type"],
            "page_count": doc.get("pages", 0),
            "chunk_count": doc.get("chunks", 0),
            "indexed_at": doc.get("created_at"),
        }

    # Fallback: check chunks
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, metadata, COUNT(*) as count 
                FROM document_chunks 
                WHERE document_id = %s 
                GROUP BY source, metadata;
            """, (doc_id,))
            row = cur.fetchone()
            if not row:
                return None
            meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
            return {
                "id": doc_id,
                "source": row["source"],
                "type": meta.get("type", "PDF"),
                "page_count": meta.get("page_count", 1),
                "chunk_count": row["count"],
                "indexed_at": meta.get("indexed_at", time.time()),
            }


def document_exists(doc_id: str) -> bool:
    """Check if document or its chunks exist."""
    return get_document(doc_id) is not None


def register_document(doc_id: str, source: str, file_type: str, page_count: int, chunk_count: int) -> dict:
    """Register or update a document in the persistence layer."""
    existing = get_document_by_id(doc_id)
    if existing:
        return {
            "id": existing["id"],
            "source": existing["name"],
            "type": existing["type"],
            "page_count": existing.get("pages", 0),
            "chunk_count": existing.get("chunks", 0),
            "indexed_at": existing.get("created_at"),
        }

    # Clean up old documents with the same name if different id
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM documents WHERE name = %s AND id != %s;", (source, doc_id))
            old_docs = cur.fetchall()
            for old_doc in old_docs:
                _remove_document_by_id(old_doc["id"])

    doc_record = {
        "id": doc_id,
        "name": source,
        "title": source.rsplit(".", 1)[0].replace("_", " ").title(),
        "type": file_type,
        "size": f"{max(1, chunk_count * 2)} KB",
        "size_bytes": chunk_count * 2048,
        "pages": page_count,
        "chunks": chunk_count,
        "file_path": f"data/uploads/{doc_id}_{source}",
        "status": "indexed",
        "error_message": "",
    }
    inserted = insert_document(doc_record)
    return {
        "id": inserted["id"],
        "source": inserted["name"],
        "type": inserted["type"],
        "page_count": inserted.get("pages", 0),
        "chunk_count": inserted.get("chunks", 0),
        "indexed_at": inserted.get("created_at"),
    }


def list_documents() -> list[dict]:
    """List all registered indexed documents."""
    docs = list_all_documents(include_archived=False)
    results = []
    for d in docs:
        results.append({
            "id": d["id"],
            "source": d["name"],
            "type": d["type"],
            "page_count": d.get("pages", 0),
            "chunk_count": d.get("chunks", 0),
            "indexed_at": d.get("created_at"),
        })

    # If no documents in documents table, check distinct chunks
    if not results:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT document_id, source, COUNT(*) as chunks, MAX(page) as max_page 
                    FROM document_chunks 
                    GROUP BY document_id, source 
                    ORDER BY source ASC;
                """)
                rows = cur.fetchall()
                for r in rows:
                    results.append({
                        "id": r["document_id"],
                        "source": r["source"],
                        "type": r["source"].rsplit(".", 1)[-1].upper() if "." in r["source"] else "DOC",
                        "page_count": r["max_page"] or 1,
                        "chunk_count": r["chunks"],
                        "indexed_at": None,
                    })

    results.sort(key=lambda doc: doc["source"].lower())
    return results


def _remove_document_by_id(doc_id: str):
    """Delete chunks and document record for a document."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks WHERE document_id = %s;", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = %s;", (doc_id,))


def remove_document(doc_id: str):
    """Delete chunks and document records by doc_id.

    The document_chunks table has ON DELETE CASCADE FK to documents(id),
    so deleting from documents alone would cascade. We still explicitly
    remove chunks first for clarity and to ensure pgvector index entries
    are cleaned up predictably.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks WHERE document_id = %s;", (doc_id,))
    # This also deletes the document row; FK ON DELETE CASCADE ensures
    # any remaining chunk rows are cleaned up by the database.
    delete_document_permanently(doc_id)


def clear_all_documents():
    """Clear all document chunks from the vector store."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks;")
            cur.execute("DELETE FROM documents;")


def get_document_chunks(document_id: str, include_embeddings: bool = False) -> list[dict]:
    """Return all stored chunks (text + metadata) for a given document."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if include_embeddings:
                cur.execute("""
                    SELECT id, text, metadata, embedding 
                    FROM document_chunks 
                    WHERE document_id = %s 
                    ORDER BY chunk_index ASC;
                """, (document_id,))
            else:
                cur.execute("""
                    SELECT id, text, metadata 
                    FROM document_chunks 
                    WHERE document_id = %s 
                    ORDER BY chunk_index ASC;
                """, (document_id,))
            rows = cur.fetchall()

    chunks = []
    for r in rows:
        meta = r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}")
        item = {
            "chunk_id": r["id"],
            "text": r["text"] or "",
            "metadata": meta,
        }
        if include_embeddings and "embedding" in r:
            item["embedding"] = r["embedding"]
        chunks.append(item)
    return chunks


def get_all_chunks() -> list[dict]:
    """Return all stored chunks across all non-archived documents."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dc.id, dc.text, dc.metadata
                FROM document_chunks dc
                JOIN documents doc ON doc.id = dc.document_id
                WHERE doc.is_archived = FALSE
                ORDER BY dc.document_id, dc.chunk_index ASC;
            """)
            rows = cur.fetchall()

    chunks = []
    for r in rows:
        meta = r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}")
        chunks.append({
            "chunk_id": r["id"],
            "text": r["text"] or "",
            "metadata": meta,
        })
    return chunks


def get_adjacent_chunks(document_id: str, chunk_index: int | None, window: int = 1) -> list[dict]:
    """Retrieve adjacent chunks for the same document to expand context."""
    if not document_id or chunk_index is None:
        return []

    min_idx = max(0, chunk_index - window)
    max_idx = chunk_index + window

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, text, metadata 
                FROM document_chunks 
                WHERE document_id = %s AND chunk_index >= %s AND chunk_index <= %s AND chunk_index != %s
                ORDER BY chunk_index ASC;
            """, (document_id, min_idx, max_idx, chunk_index))
            rows = cur.fetchall()

    adjacent = []
    for r in rows:
        meta = r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}")
        adjacent.append({
            "chunk_id": r["id"],
            "text": r["text"] or "",
            "metadata": meta,
        })
    return adjacent



def _vector_search_expr(dim: int) -> str:
    """Return the pgvector distance expression that matches the HNSW index.

    The HNSW index is built on the expression `(embedding::halfvec(3072))`, so the
    query operator must cast the column and parameter to the same halfvec dimension
    to remain index-compatible (pgvector 0.8.2+). For any other dimension the plain
    vector operator is used instead, keeping full compatibility with fallback
    embedding models of different dimensionality.
    """
    if dim == HNSW_INDEX_DIM:
        return "embedding::halfvec(3072) <=> %s::halfvec(3072)"
    return "embedding <=> %s::vector"


def query_vector_store(query_embedding: list[float], top_k: int, document_id: str | None = None) -> list[dict]:
    """Perform approximate cosine similarity search with pgvector (<=>).

    Calculates cosine distance $d_{cos} = 1 - \\cos(u, v) \\in [0, 2]$.
    Scales distance to squared L2 distance metric ($2 \\times d_{cos}$) for 100% calibration
    with DocuMind hybrid retrieval thresholds (RELEVANCE_THRESHOLD = 1.48).
    """
    if not query_embedding:
        return []

    if isinstance(query_embedding, str):
        from backend.src.embeddings import embed_query
        query_embedding = embed_query(query_embedding)
        if not query_embedding:
            return []

    dim = len(query_embedding)
    expr = _vector_search_expr(dim)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if document_id:
                cur.execute(f"""
                    SELECT dc.id, dc.text, dc.metadata, ({expr}) AS cos_dist
                    FROM document_chunks dc
                    JOIN documents doc ON doc.id = dc.document_id
                    WHERE doc.is_archived = FALSE AND dc.document_id = %s
                    ORDER BY {expr}
                    LIMIT %s;
                """, (query_embedding, document_id, query_embedding, int(top_k)))
            else:
                cur.execute(f"""
                    SELECT dc.id, dc.text, dc.metadata, ({expr}) AS cos_dist
                    FROM document_chunks dc
                    JOIN documents doc ON doc.id = dc.document_id
                    WHERE doc.is_archived = FALSE
                    ORDER BY {expr}
                    LIMIT %s;
                """, (query_embedding, query_embedding, int(top_k)))
            rows = cur.fetchall()

    chunks = []
    for r in rows:
        meta = r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"] or "{}")
        # Scale cosine distance (0..2) to squared L2 distance metric (0..2) for formula calibration
        cos_dist = float(r["cos_dist"]) if r.get("cos_dist") is not None else 0.0
        calibrated_distance = 2.0 * cos_dist

        chunks.append({
            "chunk_id": r["id"],
            "text": r["text"] or "",
            "metadata": meta,
            "distance": calibrated_distance,
        })
    return chunks
