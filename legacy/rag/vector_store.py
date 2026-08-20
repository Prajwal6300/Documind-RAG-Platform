import hashlib
import time
from pathlib import Path
import chromadb

from rag.embeddings import embed_documents

CHROMA_PATH = "data/chroma"
Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(path=CHROMA_PATH)

collection = client.get_or_create_collection(name="rag_documents")
registry = client.get_or_create_collection(name="documents_registry")


def _chunk_id(document_id, source, page, chunk_index):
    key = f"{document_id}|{source}|{page}|{chunk_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_collection():
    global collection
    return collection


def add_chunks(chunks):
    global collection
    if not chunks:
        return

    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    ids = [
        _chunk_id(
            chunk.get("metadata", {}).get("document_id"),
            chunk.get("metadata", {}).get("source", ""),
            chunk.get("metadata", {}).get("page"),
            chunk.get("metadata", {}).get("chunk_index"),
        )
        for chunk in chunks
    ]

    embeddings = embed_documents(documents)

    try:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
    except Exception as exc:
        if "dimension" in str(exc).lower():
            print(f"[DocuMind VectorStore] Embedding dimension changed ({exc}), recreating Chroma collection.")
            try:
                client.delete_collection(name="rag_documents")
            except Exception:
                pass
            collection = client.get_or_create_collection(name="rag_documents")
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        else:
            raise exc


def get_document(doc_id):
    result = registry.get(ids=[doc_id])

    if not result.get("ids"):
        return None

    metadata = (result.get("metadatas") or [None])[0] or {}
    document = (result.get("documents") or [""])[0]

    return {
        "id": doc_id,
        "source": document or metadata.get("source", "Unknown"),
        "type": metadata.get("type", ""),
        "page_count": metadata.get("page_count"),
        "chunk_count": metadata.get("chunk_count"),
        "indexed_at": metadata.get("indexed_at"),
    }


def document_exists(doc_id):
    return get_document(doc_id) is not None


def register_document(doc_id, source, file_type, page_count, chunk_count):
    existing = get_document(doc_id)

    if existing:
        return existing

    same_name = registry.get(where={"source": source})

    for old_id in same_name.get("ids", []):
        if old_id != doc_id:
            _remove_document_by_id(old_id)

    registry.upsert(
        ids=[doc_id],
        documents=[source],
        metadatas=[{
            "source": source,
            "type": file_type,
            "page_count": page_count,
            "chunk_count": chunk_count,
            "indexed_at": time.time(),
        }]
    )

    return get_document(doc_id)


def list_documents():
    result = registry.get()

    documents = []

    for doc_id, name, metadata in zip(
        result.get("ids", []),
        result.get("documents", []),
        result.get("metadatas", []) or []
    ):
        metadata = metadata or {}

        documents.append({
            "id": doc_id,
            "source": name or metadata.get("source", "Unknown"),
            "type": metadata.get("type", ""),
            "page_count": metadata.get("page_count"),
            "chunk_count": metadata.get("chunk_count"),
            "indexed_at": metadata.get("indexed_at"),
        })

    documents.sort(key=lambda doc: doc["source"].lower())

    return documents


def _remove_document_by_id(doc_id):
    global collection
    try:
        collection.delete(where={"document_id": doc_id})
    except Exception:
        pass

    try:
        registry.delete(ids=[doc_id])
    except Exception:
        pass


def remove_document(doc_id):
    _remove_document_by_id(doc_id)


def clear_all_documents():
    global collection
    try:
        ids = collection.get().get("ids", [])
        if ids:
            collection.delete(ids=ids)
    except Exception:
        pass

    try:
        ids = registry.get().get("ids", [])
        if ids:
            registry.delete(ids=ids)
    except Exception:
        pass


def get_document_chunks(document_id, include_embeddings=False):
    """Return all stored chunks (text + metadata) for a given document."""
    global collection
    try:
        result = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )
    except Exception:
        return []

    ids = result.get("ids", []) or []
    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []

    chunks = []

    for chunk_id, text, metadata in zip(ids, documents, metadatas):
        chunks.append({
            "chunk_id": chunk_id,
            "text": text or "",
            "metadata": metadata or {},
        })

    return chunks


def get_all_chunks():
    """Return all stored chunks across all documents."""
    global collection
    try:
        result = collection.get(
            include=["documents", "metadatas"],
        )
    except Exception:
        return []

    ids = result.get("ids", []) or []
    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []

    chunks = []
    for chunk_id, text, metadata in zip(ids, documents, metadatas):
        chunks.append({
            "chunk_id": chunk_id,
            "text": text or "",
            "metadata": metadata or {},
        })

    return chunks


def get_adjacent_chunks(document_id, chunk_index, window=1):
    """Retrieve adjacent chunks for the same document to expand context."""
    if not document_id or chunk_index is None:
        return []

    doc_chunks = get_document_chunks(document_id)
    if not doc_chunks:
        return []

    # Map chunk_index -> chunk
    indexed = {}
    for c in doc_chunks:
        idx = c.get("metadata", {}).get("chunk_index")
        if idx is not None:
            indexed[idx] = c

    adjacent = []
    for offset in range(-window, window + 1):
        if offset == 0:
            continue
        target_idx = chunk_index + offset
        if target_idx in indexed:
            adjacent.append(indexed[target_idx])

    return adjacent
