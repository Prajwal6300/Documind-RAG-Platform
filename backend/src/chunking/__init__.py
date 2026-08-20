"""Chunking module for DocuMind RAG."""

from backend.src.chunking.chunker import (
    chunk_text,
    create_chunks,
)

__all__ = [
    "chunk_text",
    "create_chunks",
]
