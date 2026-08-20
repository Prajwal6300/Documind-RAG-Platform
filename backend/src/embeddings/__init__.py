"""Embeddings module for DocuMind RAG."""

from backend.src.embeddings.embedder import (
    embed_documents,
    embed_query,
)

__all__ = [
    "embed_documents",
    "embed_query",
]
