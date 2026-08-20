"""Document ingestion and extraction module for DocuMind."""

from backend.src.ingestion.loader import (
    load_document,
    load_pdf,
    load_docx,
    load_txt,
    load_csv,
    load_xlsx,
    load_pptx,
)

__all__ = [
    "load_document",
    "load_pdf",
    "load_docx",
    "load_txt",
    "load_csv",
    "load_xlsx",
    "load_pptx",
]
