from pathlib import Path
import fitz
from docx import Document


def load_pdf(file_path):
    pages = []

    pdf = fitz.open(file_path)

    for page_number, page in enumerate(pdf):
        text = page.get_text()

        if text.strip():
            pages.append({
                "text": text,
                "page": page_number + 1
            })

    pdf.close()

    return pages


def load_docx(file_path):
    document = Document(file_path)

    text = "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )

    return [{
        "text": text,
        "page": None
    }]


def load_txt(file_path):
    text = Path(file_path).read_text(
        encoding="utf-8",
        errors="ignore"
    )

    return [{
        "text": text,
        "page": None
    }]


def load_document(file_path):
    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return load_pdf(file_path)

    if extension == ".docx":
        return load_docx(file_path)

    if extension == ".txt":
        return load_txt(file_path)

    raise ValueError(
        f"Unsupported file type: {extension}"
    )