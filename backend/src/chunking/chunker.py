"""Heading-aware recursive text chunker for DocuMind RAG.

Splits multi-format documents along structural headings, table boundaries,
and sentence boundaries without severing entity names, amounts, or codes.
"""

import re
import hashlib
from backend.src.utils.config import CHUNK_SIZE, CHUNK_OVERLAP

# Sentence boundary split that keeps initials intact.
_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])"
    r"(?<![A-Z]\.)"   # do not split after an uppercase initial ("M. S. Yadav")
    r"\s+(?=[A-Z0-9\"'($])"
)

# Section heading detector (e.g. "EDUCATION", "1. Casual Leave", "### Skills", "Working Hours")
_HEADING_PATTERN = re.compile(
    r"^(?:#{1,4}\s+|[0-9]{1,2}\.\s+|[A-Z\s]{3,30}$|[A-Z][a-zA-Z\s]{2,25}:?$)"
)


def _detect_section(unit: str) -> str | None:
    """Detect if a text unit begins with a section title."""
    if not unit:
        return None
    first_line = unit.split("\n")[0].strip()
    if len(first_line) < 50 and _HEADING_PATTERN.match(first_line):
        return first_line.rstrip(":")
    return None


def _split_units(text: str) -> list[str]:
    """Split raw text into coherent paragraph and sentence units."""
    units = []

    for raw_line in re.split(r"\n{2,}|\n(?=[A-Z0-9#•\-\*])", text):
        line = raw_line.strip()

        if not line:
            continue

        # Keep table data blocks together as single units if possible
        if "TABLE DATA:" in line or " | " in line:
            units.append(line)
            continue

        sentences = _SENTENCE_BOUNDARY.split(line)

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                units.append(sentence)

    return units


def _chunk_id(document_id: str | None, source: str, page: int | None, chunk_index: int) -> str:
    key = f"{document_id}|{source}|{page}|{chunk_index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _split_long_unit(unit: str, chunk_size: int) -> list[str]:
    pieces = []
    for start in range(0, len(unit), chunk_size):
        piece = unit[start:start + chunk_size].strip()
        if piece:
            pieces.append(piece)
    return pieces


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Chunk text into overlapping, coherent windows."""
    if chunk_size is None:
        chunk_size = CHUNK_SIZE

    if overlap is None:
        overlap = CHUNK_OVERLAP

    text = text.strip()

    if not text:
        return []

    units = _split_units(text)

    if not units:
        return []

    chunks = []
    current = []
    current_len = 0

    for unit in units:
        if len(unit) > chunk_size:
            if current:
                chunks.append("\n".join(current) if any("\n" in u for u in current) else " ".join(current))
                current = []
                current_len = 0

            chunks.extend(_split_long_unit(unit, chunk_size))
            continue

        if current and current_len + len(unit) + 1 > chunk_size:
            chunks.append("\n".join(current) if any("\n" in u for u in current) else " ".join(current))

            tail = []
            tail_len = 0

            for tail_unit in reversed(current):
                if tail_len + len(tail_unit) + 1 <= overlap:
                    tail.append(tail_unit)
                    tail_len += len(tail_unit) + 1
                else:
                    break

            current = list(reversed(tail))
            current_len = sum(len(u) + 1 for u in current)

        current.append(unit)
        current_len += len(unit) + 1

    if current:
        chunks.append("\n".join(current) if any("\n" in u for u in current) else " ".join(current))

    return [chunk for chunk in chunks if chunk.strip()]


def create_chunks(
    pages: list[dict],
    source: str,
    document_id: str | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[dict]:
    """Convert extracted document pages into indexed chunks with rich metadata."""
    all_chunks = []
    current_section = None

    for page_data in pages:
        text = page_data.get("text", "")
        page = page_data.get("page")

        chunks = chunk_text(text, chunk_size, overlap)

        for index, chunk in enumerate(chunks):
            # Check for section headers in chunk
            detected = _detect_section(chunk)
            if detected:
                current_section = detected

            all_chunks.append({
                "text": chunk,
                "metadata": {
                    "source": source,
                    "page": page,
                    "chunk_id": _chunk_id(document_id, source, page, index),
                    "document_id": document_id,
                    "chunk_index": index,
                    "section": current_section or "",
                }
            })

    return all_chunks
