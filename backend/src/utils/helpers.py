"""General helper utilities for DocuMind backend and RAG processing."""

import hashlib
from datetime import datetime


def file_hash(content: bytes) -> str:
    """Generate SHA256 hex digest for binary content."""
    return hashlib.sha256(content).hexdigest()


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_doc_icon_and_color(file_type: str) -> tuple[str, str]:
    """Return UI icon identifier and accent color class for given document format."""
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


def format_doc_response(doc: dict) -> dict:
    """Format database document row into standardized frontend API JSON object."""
    icon, color = get_doc_icon_and_color(doc.get("type", "PDF"))
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
    }
