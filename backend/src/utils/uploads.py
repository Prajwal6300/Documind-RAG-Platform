"""Server-side upload validation for DocuMind.

Performs real content-based MIME detection (magic bytes), not just extension
checks, plus safe filename sanitization to prevent path traversal.
"""

import re
from pathlib import PurePosixPath, PureWindowsPath

from backend.src.utils.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, MAX_FILENAME_LENGTH
from backend.src.utils.errors import bad_request, too_large, unsupported_media, conflict

# ---------------------------------------------------------------------------
# Magic-byte signatures for supported formats
# ---------------------------------------------------------------------------

# (extension, magic check callable on bytes)
def _is_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF")


def _is_ooxml(data: bytes, marker: bytes) -> bool:
    # OOXML files (docx/xlsx/pptx) are ZIP archives containing a marker part
    return data.startswith(b"PK\x03\x04") and marker in data[:2048]


def _is_plain_text(data: bytes) -> bool:
    # Reject binary-looking content; allow UTF-8 / ASCII / common legacy encodings
    if not data:
        return False
    # NUL bytes almost always indicate binary
    if b"\x00" in data[:2048]:
        return False
    return True


def detect_extension_by_content(filename: str, data: bytes) -> str | None:
    """Return the canonical extension based on real file content, or None if unknown."""
    ext = _safe_extension(filename)

    if _is_pdf(data):
        return "pdf"
    if _is_ooxml(data, b"word/"):
        return "docx"
    if _is_ooxml(data, b"xl/"):
        return "xlsx"
    if _is_ooxml(data, b"ppt/"):
        return "pptx"

    if ext in ("xls",):
        # Legacy .xls is an OLE compound document (D0 CF 11 E0 A1 B1 1A E1)
        if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return "xls"
        return None

    if ext in ("ppt",):
        if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return "ppt"
        return None

    # Textual formats (txt, md, markdown, csv) — content-based check
    if ext in ("txt", "md", "markdown", "csv") and _is_plain_text(data):
        return ext

    return None


def _safe_extension(filename: str) -> str:
    base = _sanitize_filename(filename)
    suffix = PurePosixPath(base).suffix or PureWindowsPath(base).suffix or ""
    return suffix.lower().lstrip(".")


def _sanitize_filename(filename: str) -> str:
    """Strip path components, control characters, and enforce a length cap."""
    name = (filename or "").strip()
    # Remove any path prefixes (both *nix and Windows style)
    name = name.replace("\\", "/").split("/")[-1]
    # Strip control characters and reserved path separators
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name)
    name = name.strip()
    if not name or name in (".", ".."):
        return "uploaded_file"
    if len(name) > MAX_FILENAME_LENGTH:
        stem, _, ext = name.rpartition(".")
        name = f"{stem[:MAX_FILENAME_LENGTH - len(ext) - 1]}.{ext}" if ext else name[:MAX_FILENAME_LENGTH]
    return name


def sanitize_filename(filename: str) -> str:
    """Public helper: return a filesystem-safe basename."""
    return _sanitize_filename(filename)


def validate_upload(filename: str, data: bytes) -> tuple[str, str]:
    """Validate an uploaded file's content and size.

    Returns (safe_filename, detected_extension). Raises ApiError for any
    invalid upload (empty file, unsupported type, content/extension mismatch).
    """
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if len(data) == 0:
        raise bad_request("The uploaded file is empty. Please select a non-empty file.", "empty_file")

    if len(data) > max_bytes:
        raise too_large(
            f"File exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB.",
            "file_too_large",
        )

    safe_name = _sanitize_filename(filename)
    ext = _safe_extension(safe_name)

    if ext not in ALLOWED_EXTENSIONS:
        raise unsupported_media(
            f"Unsupported file format '.{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            "unsupported_file_type",
        )

    detected = detect_extension_by_content(safe_name, data)
    if detected is None:
        raise unsupported_media(
            "The file content does not match a supported document format. Please upload a valid PDF, DOCX, XLSX, TXT, CSV, or PPTX file.",
            "invalid_file_content",
        )

    if detected != ext:
        # Extension lies about the content — reject to prevent execution of mismatched files
        raise bad_request(
            f"File extension '.{ext}' does not match its actual content (looks like a {detected.upper()} file).",
            "extension_mismatch",
        )

    return safe_name, detected