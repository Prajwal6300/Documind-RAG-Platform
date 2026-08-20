# Pre-React Streamlit prototype. Kept for reference only, not used in the running app.
import hashlib
import html as html_module
import os
import tempfile

# Must run before NumPy/SciPy/streamlit are imported on Windows.
for _threading_var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_threading_var, "1")
del _threading_var

import streamlit as st
from dotenv import load_dotenv

from backend.src.chunking import create_chunks
from backend.src.utils.config import CHUNK_SIZE, CHUNK_OVERLAP, RAG_DEBUG
from backend.src.ingestion import load_document
from backend.src.llm import get_llm_status
from backend.src.pipeline import answer_question
from backend.src.prompts import NO_CONTEXT_MESSAGE
from backend.src.vectordb import (
    add_chunks,
    clear_all_documents,
    document_exists,
    get_document_chunks,
    list_documents,
    register_document,
    remove_document,
)

load_dotenv()

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "md", "markdown", "xlsx", "xls", "pptx", "ppt"}
FILE_TYPE_LABELS = {
    "pdf": "PDF",
    "docx": "DOCX",
    "txt": "TXT",
    "csv": "CSV",
    "md": "MD",
    "markdown": "MD",
    "xlsx": "XLSX",
    "xls": "XLS",
    "pptx": "PPTX",
    "ppt": "PPT",
}

esc = html_module.escape

st.set_page_config(
    page_title="DocuMind — Document Assistant",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Warm Editorial Design System
# ---------------------------------------------------------------------------

STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-canvas: #faf9f5;
  --surface-soft: #f5f0e8;
  --surface-card: #efe9de;
  --surface-cream-strong: #e8e0d2;
  
  --dark: #181715;
  --dark-elevated: #252320;
  --dark-soft: #1f1e1b;
  
  --ink: #141413;
  --body: #3d3d3a;
  --muted: #6c6a64;
  --muted-soft: #8e8b82;
  --border: #e6dfd8;
  --border-subtle: #ede7df;
  --border-strong: #d8cfc4;
  
  --primary-coral: #cc785c;
  --primary-active: #a9583e;
  --primary-coral-soft: #faf0eb;
  --primary-coral-border: #f0d5ca;
  
  --success: #5db872;
  --success-soft: #edf7f0;
  --warning: #d4a017;
  --error: #c64545;
  
  --font-serif: 'Cormorant Garamond', Georgia, serif;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 12px;
  --radius-full: 9999px;
  
  --shadow-subtle: 0 1px 3px rgba(24, 23, 21, 0.04);
  --shadow-card: 0 2px 8px rgba(24, 23, 21, 0.05);
  --shadow-pop: 0 8px 24px rgba(24, 23, 21, 0.08);
}

/* Global Reset */
html, body, .stApp {
  background-color: var(--bg-canvas) !important;
  color: var(--body) !important;
  font-family: var(--font-sans) !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
  display: none !important;
}

header[data-testid="stHeader"] {
  background: transparent !important;
  height: 0px !important;
  display: none !important;
}

/* Central Stage Container */
[data-testid="stMainBlockContainer"] {
  max-width: 880px !important;
  margin: 0 auto !important;
  padding-top: 14px !important;
  padding-bottom: 130px !important;
  padding-left: 20px !important;
  padding-right: 20px !important;
}

/* Sidebar Editorial Styling */
[data-testid="stSidebar"] {
  background-color: var(--surface-soft) !important;
  border-right: 1px solid var(--border) !important;
  box-shadow: none !important;
}

[data-testid="stSidebar"] > div:first-child {
  padding: 18px 16px 24px 16px !important;
}

.sidebar-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 2px 14px 2px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
}

.brand-mark {
  font-size: 22px;
  color: var(--primary-coral);
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.brand-name {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 500;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.brand-badge {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--muted);
  background: var(--surface-card);
  padding: 2px 7px;
  border-radius: var(--radius-full);
  margin-left: auto;
  border: 1px solid var(--border);
}

.sidebar-section-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--muted-soft);
  text-transform: uppercase;
  margin-top: 18px;
  margin-bottom: 8px;
  padding-left: 2px;
}

/* Upload Workspace Card */
.upload-card-wrapper {
  background: var(--surface-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 14px 12px 8px 12px;
  margin-bottom: 10px;
  text-align: center;
}

.upload-icon-mark {
  font-size: 18px;
  color: var(--primary-coral);
  display: inline-block;
  margin-bottom: 2px;
  line-height: 1;
}

.upload-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 2px;
}

.upload-card-subtitle {
  font-size: 11.5px;
  color: var(--muted);
  margin-bottom: 8px;
}

.upload-card-formats {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--muted-soft);
  background: var(--bg-canvas);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  padding: 2px 8px;
  display: inline-block;
  margin-bottom: 8px;
}

/* File Uploader Dropzone Styling */
[data-testid="stFileUploader"] {
  padding-bottom: 0px !important;
}

[data-testid="stFileUploaderDropzone"] {
  border: 1.5px dashed var(--border-strong) !important;
  border-radius: var(--radius-md) !important;
  background: var(--bg-canvas) !important;
  padding: 10px 10px !important;
  transition: all 0.15s ease !important;
}

[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--primary-coral) !important;
  background: var(--primary-coral-soft) !important;
}

[data-testid="stFileUploaderDropzone"] button {
  border-radius: var(--radius-sm) !important;
  font-size: 12px !important;
  padding: 4px 10px !important;
  background: var(--surface-card) !important;
  border: 1px solid var(--border) !important;
  color: var(--ink) !important;
}

[data-testid="stFileUploaderDropzone"] button:hover {
  border-color: var(--primary-coral) !important;
  color: var(--primary-coral) !important;
}

/* Top App Bar Header */
.top-nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 10px 18px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-subtle);
  margin-bottom: 24px;
}

.top-brand-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.top-brand-title {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 6px;
}

.top-brand-subtitle {
  font-size: 12px;
  color: var(--muted);
  font-family: var(--font-sans);
  border-left: 1px solid var(--border);
  padding-left: 10px;
}

.top-scope-tag {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  background: var(--surface-card);
  border: 1px solid var(--border);
  padding: 3px 9px;
  border-radius: var(--radius-full);
}

.top-status-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.top-status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--body);
  background: var(--surface-card);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-family: var(--font-sans);
}

.status-dot-green {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  display: inline-block;
}

.status-dot-warning {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--warning);
  display: inline-block;
}

/* Document Item Card */
.doc-card {
  background: var(--bg-canvas);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  margin-bottom: 6px;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.doc-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-subtle);
}

.doc-card.active-doc {
  border-color: var(--primary-coral-border);
  background: var(--primary-coral-soft);
}

.doc-card-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 5px;
}

.doc-card-meta {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.doc-type-pill {
  font-size: 9px;
  font-weight: 600;
  color: var(--muted);
  background: var(--surface-card);
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid var(--border);
}

/* Empty Hero State */
.empty-hero-wrap {
  text-align: center;
  padding: 40px 16px 24px 16px;
  max-width: 640px;
  margin: 0 auto;
}

.hero-sparkle {
  font-size: 32px;
  color: var(--primary-coral);
  margin-bottom: 10px;
  display: inline-block;
  line-height: 1;
}

.hero-heading {
  font-family: var(--font-serif);
  font-size: 36px;
  font-weight: 400;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.25;
  margin-bottom: 10px;
}

.hero-subheading {
  font-size: 14.5px;
  color: var(--muted);
  line-height: 1.6;
  margin-bottom: 28px;
}

.hero-prompts-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--muted-soft);
  text-transform: uppercase;
  margin-bottom: 12px;
}

/* Chat Messages */
div[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  padding: 12px 0 !important;
  gap: 12px !important;
}

/* User Message */
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) div[data-testid="stChatMessageContent"] {
  background: var(--surface-card) !important;
  color: var(--ink) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px 14px 4px 14px !important;
  padding: 12px 18px !important;
  font-size: 15px !important;
  line-height: 1.65 !important;
  box-shadow: var(--shadow-subtle) !important;
}

/* Assistant Message */
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) div[data-testid="stChatMessageContent"] {
  background: transparent !important;
  color: var(--body) !important;
  border: none !important;
  padding: 6px 0px !important;
  font-size: 15.5px !important;
  line-height: 1.7 !important;
}

div[data-testid="chatAvatarIcon-user"] {
  background: var(--surface-card) !important;
  color: var(--muted) !important;
  border: 1px solid var(--border) !important;
}

div[data-testid="chatAvatarIcon-assistant"] {
  background: var(--primary-coral-soft) !important;
  color: var(--primary-coral) !important;
  border: 1px solid var(--primary-coral-border) !important;
}

/* Markdown styling inside assistant response */
div[data-testid="stChatMessageContent"] h1,
div[data-testid="stChatMessageContent"] h2,
div[data-testid="stChatMessageContent"] h3,
div[data-testid="stChatMessageContent"] h4 {
  font-family: var(--font-serif) !important;
  font-weight: 400 !important;
  color: var(--ink) !important;
  margin-top: 16px !important;
  margin-bottom: 8px !important;
  line-height: 1.3 !important;
}

div[data-testid="stChatMessageContent"] h1 { font-size: 24px !important; }
div[data-testid="stChatMessageContent"] h2 { font-size: 21px !important; }
div[data-testid="stChatMessageContent"] h3 { font-size: 18px !important; }

div[data-testid="stChatMessageContent"] p {
  margin-bottom: 12px !important;
}
div[data-testid="stChatMessageContent"] p:last-child {
  margin-bottom: 0 !important;
}

div[data-testid="stChatMessageContent"] code {
  font-family: var(--font-mono) !important;
  background: var(--surface-soft) !important;
  color: var(--ink) !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  font-size: 13px !important;
  border: 1px solid var(--border) !important;
}

div[data-testid="stChatMessageContent"] pre {
  background: var(--dark) !important;
  color: var(--bg-canvas) !important;
  border-radius: var(--radius-md) !important;
  padding: 12px 16px !important;
  border: 1px solid var(--dark-elevated) !important;
}

div[data-testid="stChatMessageContent"] pre code {
  background: transparent !important;
  color: #f3efe6 !important;
  border: none !important;
}

/* Evidence / Sources Section */
.sources-card-wrapper {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.sources-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--muted-soft);
  text-transform: uppercase;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.citations-flex-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.citation-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  color: var(--body);
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.citation-pill:hover {
  background: var(--surface-card);
  border-color: var(--border-strong);
  color: var(--ink);
}

.citation-page-badge {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--muted);
}

/* Evidence Inspector Card */
.evidence-inspector-card {
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 10px;
}

.evidence-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.evidence-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
}

.evidence-relevance {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--primary-coral);
  background: var(--primary-coral-soft);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--primary-coral-border);
}

.evidence-snippet {
  font-size: 13px;
  color: var(--body);
  line-height: 1.55;
  background: var(--bg-canvas);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  white-space: pre-wrap;
}

/* Bottom Chat Input */
[data-testid="stBottom"] {
  background: transparent !important;
}

[data-testid="stBottom"] > div {
  max-width: 880px !important;
  margin: 0 auto !important;
  padding-left: 20px !important;
  padding-right: 20px !important;
  padding-bottom: 16px !important;
  background: transparent !important;
}

[data-testid="stChatInput"] {
  border: 1px solid var(--border-strong) !important;
  border-radius: var(--radius-lg) !important;
  box-shadow: var(--shadow-pop) !important;
  background: var(--bg-canvas) !important;
  padding: 4px 6px !important;
  transition: all 0.15s ease !important;
}

[data-testid="stChatInput"]:focus-within {
  border-color: var(--primary-coral) !important;
  box-shadow: 0 0 0 3px rgba(204, 120, 92, 0.12), var(--shadow-pop) !important;
}

[data-testid="stChatInput"] textarea {
  color: var(--ink) !important;
  font-size: 14.5px !important;
  line-height: 1.5 !important;
  font-family: var(--font-sans) !important;
}

[data-testid="stChatInput"] textarea::placeholder {
  color: var(--muted-soft) !important;
}

[data-testid="stChatInput"] button {
  color: var(--primary-coral) !important;
  background: transparent !important;
  border-radius: var(--radius-md) !important;
  transition: all 0.15s ease !important;
}

[data-testid="stChatInput"] button:hover {
  background: var(--primary-coral-soft) !important;
  color: var(--primary-active) !important;
}

/* General Button Overrides */
.stButton > button,
[data-testid="stBaseButton-secondary"] {
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-canvas) !important;
  color: var(--ink) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 6px 12px !important;
  box-shadow: var(--shadow-subtle) !important;
  transition: all 0.15s ease !important;
}

.stButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover {
  border-color: var(--border-strong) !important;
  background: var(--surface-card) !important;
}

.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
  background: var(--primary-coral) !important;
  border: 1px solid var(--primary-coral) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
}

.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
  background: var(--primary-active) !important;
  border-color: var(--primary-active) !important;
}

/* Sidebar Action Buttons */
.sidebar-cta-btn button {
  width: 100% !important;
  background: var(--bg-canvas) !important;
  border: 1px solid var(--border) !important;
  color: var(--ink) !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md) !important;
  padding: 8px 14px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px !important;
}

.sidebar-cta-btn button:hover {
  border-color: var(--primary-coral) !important;
  color: var(--primary-coral) !important;
  background: var(--primary-coral-soft) !important;
}

/* Expanders */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  background: var(--bg-canvas) !important;
  box-shadow: none !important;
  margin-top: 6px !important;
}

[data-testid="stExpander"] summary {
  font-size: 12.5px !important;
  color: var(--muted) !important;
  font-weight: 500 !important;
}

/* Status Widget */
[data-testid="stStatusWidget"] {
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-canvas) !important;
  box-shadow: var(--shadow-subtle) !important;
}
"""

st.markdown(f"<style>{STYLES}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Backend Helper Functions
# ---------------------------------------------------------------------------


def _file_hash(content):
    return hashlib.sha256(content).hexdigest()


def friendly_error(exc):
    message = str(exc) or exc.__class__.__name__
    low = message.lower()

    if any(key in low for key in ("password", "encrypt", "protection")):
        return "The document is password-protected or could not be opened."
    if any(key in low for key in (
        "mupdf", "cannot open", "failed to open", "not a pdf",
        "corrupt", "damage", "invalid", "unsupported",
    )):
        return "The document could not be read. It may be corrupted or unsupported."
    if any(key in low for key in ("empty", "no usable", "no readable")):
        return "The document appears to be empty or contains no extractable text."
    if any(key in low for key in ("file type", "extension")):
        return "Unsupported file type. Please upload a PDF, DOCX, TXT, MD, CSV, XLSX, or PPTX file."

    return "The document could not be indexed. Please check the file and try again."


def process_upload(uploaded_file):
    name = uploaded_file.name
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    content = uploaded_file.getvalue()
    doc_id = _file_hash(content)

    if ext not in ALLOWED_EXTENSIONS:
        return {
            "status": "error",
            "message": f"Unsupported file type: .{ext}. Supported: PDF, DOCX, TXT, MD, CSV, XLSX, PPTX.",
        }

    if document_exists(doc_id):
        return {"status": "duplicate", "message": f"{name} already indexed."}

    try:
        with st.status(f"Indexing {name}…", expanded=False) as status:
            st.write("Reading document…")
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f".{ext}"
            ) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            try:
                st.write("Extracting text and structure…")
                pages = load_document(temp_path)
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

            if not pages:
                status.update(label=f"⚠ Could not read text from {name}", state="error")
                return {
                    "status": "error",
                    "message": f"Could not read text from {name}. The file may be empty or corrupted.",
                }

            st.write("Creating structure-aware chunks…")
            chunks = create_chunks(
                pages,
                name,
                document_id=doc_id,
                chunk_size=CHUNK_SIZE,
                overlap=CHUNK_OVERLAP,
            )

            if not chunks:
                status.update(label=f"⚠ No text chunks found in {name}", state="error")
                return {
                    "status": "error",
                    "message": f"No readable text chunks were created from {name}.",
                }

            st.write("Generating embeddings…")
            add_chunks(chunks)

            st.write("Indexing document…")
            register_document(
                doc_id=doc_id,
                source=name,
                file_type=FILE_TYPE_LABELS.get(ext, ext.upper()),
                page_count=len(pages),
                chunk_count=len(chunks),
            )

            status.update(
                label=f"✓ {name} indexed ({len(chunks)} chunks)",
                state="complete",
            )

        return {"status": "ok", "message": f"{name} ready"}

    except Exception as exc:
        print(f"[DocuMind] Failed to index {name}: {exc}")
        return {
            "status": "error",
            "message": f"Could not index {name}. {friendly_error(exc)}",
        }


def generate_suggested_questions(docs):
    """Generate dynamic suggested prompts based on actual uploaded documents."""
    if not docs:
        return []

    # Check if resume/cv/profile is among documents
    has_resume = any(
        any(k in d["source"].lower() for k in ("resume", "cv", "profile", "prajwal", "experience", "bio"))
        for d in docs
    )

    if has_resume:
        prompts = [
            "What is Prajwal's education & qualifications?",
            "What are Prajwal's technical skills?",
            "What projects has Prajwal worked on?",
            "Summarize the candidate's work experience.",
        ]
    else:
        prompts = [
            "Summarize the key points in this document",
            "What are the main requirements and policies?",
            "What dates, deadlines, or timelines are mentioned?",
            "Extract all important names, IDs, and figures",
        ]

    if len(docs) > 1:
        d1, d2 = docs[0]["source"], docs[1]["source"]
        prompts[0] = f"Compare key details between {d1} and {d2}"
        prompts[3] = "What key topics are mentioned across all documents?"

    return prompts


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "processed" not in st.session_state:
    st.session_state.processed = set()

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "scope" not in st.session_state:
    st.session_state.scope = None

if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = (
        os.getenv("RAG_DEBUG", os.getenv("DEBUG_MODE", "false")).lower() in ("1", "true", "yes", "on")
    )

if "preview_doc_id" not in st.session_state:
    st.session_state.preview_doc_id = None


# ---------------------------------------------------------------------------
# UI Renderers
# ---------------------------------------------------------------------------


def render_top_bar(doc_count, llm_status, active_scope_name):
    is_ready = llm_status.get("ready", False)
    if is_ready:
        status_text = "Gemini · Ready"
        dot_class = "status-dot-green"
    else:
        status_text = "Gemini · Key Missing"
        dot_class = "status-dot-warning"

    doc_label = f"{doc_count} Doc{'s' if doc_count != 1 else ''}"

    st.markdown(
        f"""
        <div class="top-nav-bar">
          <div class="top-brand-group">
            <span class="top-brand-title"><span class="brand-mark">✦</span> DocuMind</span>
            <span class="top-brand-subtitle">Document Intelligence</span>
            <span class="top-scope-tag">Scope: {esc(active_scope_name)}</span>
          </div>
          <div class="top-status-group">
            <div class="top-status-chip">
              <span class="{dot_class}"></span>
              <span>{esc(status_text)} · {doc_label}</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_evidence_panel(sources):
    """
    Renders compact, deduplicated citations and expandable evidence inspector.
    """
    if not sources:
        return

    # Deduplicate sources by (source, page)
    seen = set()
    deduped = []
    for s in sources:
        key = (s.get("source", "Unknown"), s.get("page"))
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    chips_html = '<div class="citations-flex-row">'
    for idx, s in enumerate(deduped):
        name = esc(s.get("source", "Unknown"))
        page = s.get("page")
        page_str = f'<span class="citation-page-badge">· Page {page}</span>' if page else ""
        chips_html += f'<span class="citation-pill">📄 <strong>[{idx+1}]</strong> {name} {page_str}</span>'
    chips_html += '</div>'

    st.markdown(
        f"""
        <div class="sources-card-wrapper">
          <div class="sources-label">Sources & Retrieved Evidence ({len(deduped)})</div>
          {chips_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"View Supporting Evidence Passages ({len(deduped)})"):
        for idx, s in enumerate(deduped):
            name = s.get("source", "Unknown")
            page = s.get("page")
            page_text = f" · Page {page}" if page else ""
            dist = s.get("distance")

            relevance_str = ""
            if dist is not None:
                sim = max(0.0, min(1.0, 1.0 - (float(dist) / 2.0)))
                relevance_str = f"{int(sim * 100)}% Match"

            text = (s.get("text") or "").strip()

            st.markdown(
                f"""
                <div class="evidence-inspector-card">
                  <div class="evidence-header">
                    <span class="evidence-title">SOURCE [{idx+1}] — {esc(name)}{esc(page_text)}</span>
                    {f'<span class="evidence-relevance">{relevance_str}</span>' if relevance_str else ''}
                  </div>
                  <div class="evidence-snippet">{esc(text)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_debug_details(debug):
    if not debug:
        return

    with st.expander("🔍 Retrieval & Intent Debug", expanded=False):
        st.caption(f"**Question Type:** `{debug.get('question_type')}`")

        if debug.get("resolved_question") != debug.get("question"):
            st.caption(f"**Resolved Search Query:** {debug['resolved_question']}")

        if debug.get("keywords"):
            st.caption(f"**Keywords:** {', '.join(debug['keywords'])}")

        if debug.get("entities"):
            st.caption(f"**Entities:** {', '.join(f'{t}={v}' for t, v in debug['entities'])}")

        if debug.get("expansions"):
            st.caption(f"**Expansions:** {', '.join(debug['expansions'])}")

        sufficiency = debug.get("sufficiency")
        if sufficiency:
            status = "✅ Sufficient" if sufficiency.get("ok") else "❌ Insufficient"
            st.caption(f"**Evidence Sufficiency Gate:** {status} — {sufficiency.get('reason')}")

        candidates = debug.get("candidates") or []
        if candidates:
            st.caption(f"**Candidates Retrieved ({len(candidates)}):**")
            for cand in candidates:
                flag = "✓" if cand.get("relevant") else "✗"
                d = cand.get("distance")
                d_str = f"d={d:.3f}" if d is not None else "d=Lexical"
                score_str = f"score={cand.get('_score', 0):.2f}"
                st.code(
                    f"{flag} {d_str} {score_str} {cand.get('source')} p={cand.get('page')} :: "
                    f"{cand.get('text', '')[:120]}",
                    language="text",
                )


def render_empty_state(docs):
    prompts = generate_suggested_questions(docs)

    if docs:
        st.markdown(
            f"""
            <div class="empty-hero-wrap">
              <div class="hero-sparkle">✦</div>
              <div class="hero-heading">What would you like to know<br/>about your documents?</div>
              <div class="hero-subheading">
                Ask questions across all indexed files. Evidence is retrieved with exact document citations.
              </div>
              <div class="hero-prompts-label">Suggested Questions</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns(2)
        for idx, prompt in enumerate(prompts):
            with cols[idx % 2]:
                if st.button(
                    prompt,
                    key=f"suggest_prompt_{idx}",
                    use_container_width=True,
                ):
                    st.session_state.pending_question = prompt
                    st.rerun()
    else:
        st.markdown(
            """
            <div class="empty-hero-wrap">
              <div class="hero-sparkle">✦</div>
              <div class="hero-heading">Upload your first document</div>
              <div class="hero-subheading">
                Add PDFs, DOCX files, text files, spreadsheets, or presentations in the sidebar to start asking questions.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_messages():
    for idx, message in enumerate(st.session_state.messages):
        role = message["role"]

        if role == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"])

                if message.get("sources"):
                    render_evidence_panel(message["sources"])

                # Action Bar below assistant message
                action_cols = st.columns([0.15, 0.18, 0.67])
                with action_cols[0]:
                    if st.button("📋 Copy", key=f"copy_btn_{idx}", help="Copy response text"):
                        st.toast("Response copied to view")
                with action_cols[1]:
                    if st.button("🔄 Retry", key=f"retry_btn_{idx}", help="Regenerate this response"):
                        if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user":
                            st.session_state.pending_question = st.session_state.messages[idx - 1]["content"]
                            st.session_state.messages = st.session_state.messages[:idx - 1]
                            st.rerun()

                if st.session_state.get("debug_mode") and message.get("debug"):
                    render_debug_details(message["debug"])


def handle_user_question(question_text):
    st.session_state.messages.append({
        "role": "user",
        "content": question_text,
    })

    scope_id = st.session_state.get("scope")
    history = list(st.session_state.messages)[:-1]
    debug = st.session_state.get("debug_mode", False)

    with st.chat_message("user"):
        st.markdown(question_text)

    with st.chat_message("assistant"):
        with st.status("Searching your documents…", expanded=False) as status:
            try:
                result = answer_question(
                    question_text,
                    stream=True,
                    document_id=scope_id,
                    chat_history=history,
                    debug=debug,
                )
                status.update(label="Generating grounded answer…", state="complete")
            except Exception as exc:
                print(f"[DocuMind] answer_question error: {exc}")
                result = {
                    "answer": "Something went wrong while searching your documents. Please try again.",
                    "sources": [],
                    "no_context": True,
                }
                status.update(label="⚠ Search completed with error", state="error")

        if result.get("no_context"):
            answer_text = result["answer"]
            st.markdown(answer_text)
        elif result.get("answer_stream"):
            answer_text = st.write_stream(result["answer_stream"])
            if not (answer_text or "").strip():
                answer_text = "No answer was generated. Please try again."
        else:
            answer_text = result["answer"]
            st.markdown(answer_text)

        if result.get("sources"):
            render_evidence_panel(result["sources"])

        if debug and result.get("debug"):
            render_debug_details(result["debug"])

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer_text,
        "sources": result.get("sources", []),
        "debug": result.get("debug"),
    })


# ---------------------------------------------------------------------------
# Sidebar: Documents & Navigation
# ---------------------------------------------------------------------------

documents = list_documents()
llm_status = get_llm_status()

# Resolve active scope display name
scope_id_to_name = {doc["id"]: doc["source"] for doc in documents}
active_scope_id = st.session_state.get("scope")
if active_scope_id and active_scope_id in scope_id_to_name:
    active_scope_name = scope_id_to_name[active_scope_id]
else:
    active_scope_name = "All Documents"
    st.session_state.scope = None

with st.sidebar:
    # Editorial Brand Header
    st.markdown(
        """
        <div class="sidebar-header-row">
          <span class="brand-mark">✦</span>
          <span class="brand-name">DocuMind</span>
          <span class="brand-badge">Assistant</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # + New Chat CTA Button
    st.markdown('<div class="sidebar-cta-btn">', unsafe_allow_html=True)
    if st.button("＋  New Chat", key="sidebar_new_chat_btn", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_question = None
        st.session_state.preview_doc_id = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # SECTION 1: DOCUMENTS / UPLOAD DOCUMENTS (Prominent & Always Visible)
    # -----------------------------------------------------------------------
    st.markdown('<div class="sidebar-section-title">Documents</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="upload-card-wrapper">
          <div class="upload-icon-mark">↑</div>
          <div class="upload-card-title">Upload documents</div>
          <div class="upload-card-subtitle">Drag and drop files here, or browse</div>
          <div class="upload-card-formats">PDF · DOCX · TXT · MD · CSV · XLSX · PPTX</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploader = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt", "md", "csv", "xlsx", "pptx"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="main_doc_uploader",
        help="Upload multiple PDF, DOCX, TXT, MD, CSV, XLSX, or PPTX documents.",
    )

    if uploader:
        new_files = []
        for uploaded_file in uploader:
            file_key = getattr(uploaded_file, "file_id", None) or f"{uploaded_file.name}_{uploaded_file.size}"
            if file_key not in st.session_state.processed:
                new_files.append((file_key, uploaded_file))

        if new_files:
            indexed_count = 0
            for file_key, uploaded_file in new_files:
                st.session_state.processed.add(file_key)
                content = uploaded_file.getvalue()
                doc_id = _file_hash(content)

                if document_exists(doc_id):
                    st.toast(f"ℹ {uploaded_file.name} is already indexed.")
                    continue

                result = process_upload(uploaded_file)
                if result["status"] == "ok":
                    indexed_count += 1
                elif result["status"] == "duplicate":
                    st.toast(f"ℹ {result['message']}")
                else:
                    st.error(result["message"])

            if indexed_count > 0:
                doc_word = "document" if indexed_count == 1 else "documents"
                st.toast(f"✓ {indexed_count} {doc_word} indexed successfully")
                st.rerun()

    # -----------------------------------------------------------------------
    # SECTION 2: INDEXED DOCUMENTS
    # -----------------------------------------------------------------------
    st.markdown(
        f'<div class="sidebar-section-title">Indexed Documents ({len(documents)})</div>',
        unsafe_allow_html=True,
    )

    if documents:
        for doc in documents:
            is_active = (st.session_state.scope == doc["id"])
            card_class = "doc-card active-doc" if is_active else "doc-card"

            doc_type = (doc.get("type") or "DOC").upper()
            pages = doc.get("page_count")
            chunks_cnt = doc.get("chunk_count", 0)
            page_text = f"{pages} pgs" if pages else f"{chunks_cnt} chunks"

            with st.container():
                col_info, col_del = st.columns([0.84, 0.16])
                with col_info:
                    st.markdown(
                        f"""
                        <div class="{card_class}">
                          <div class="doc-card-title">📄 {esc(doc['source'])}</div>
                          <div class="doc-card-meta">
                            <span class="doc-type-pill">{doc_type}</span>
                            <span>{page_text}</span>
                            <span style="color: var(--success);">✓ Indexed</span>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_del:
                    if st.button("✕", key=f"del_doc_{doc['id']}", help=f"Remove {doc['source']}"):
                        remove_document(doc["id"])
                        st.session_state.processed = set()
                        if st.session_state.scope == doc["id"]:
                            st.session_state.scope = None
                        if st.session_state.preview_doc_id == doc["id"]:
                            st.session_state.preview_doc_id = None
                        st.rerun()
    else:
        st.caption("No documents indexed yet. Upload files above to get started.")

    # -----------------------------------------------------------------------
    # SECTION 3: RETRIEVAL SCOPE
    # -----------------------------------------------------------------------
    st.markdown('<div class="sidebar-section-title">Retrieval Scope</div>', unsafe_allow_html=True)
    scope_options = {"All Documents": None}
    for doc in documents:
        scope_options[doc["source"]] = doc["id"]

    scope_keys = list(scope_options.keys())
    current_index = 0
    if active_scope_name in scope_keys:
        current_index = scope_keys.index(active_scope_name)

    selected_scope_key = st.selectbox(
        "Retrieval Scope",
        options=scope_keys,
        index=current_index,
        label_visibility="collapsed",
        key="retrieval_scope_select",
    )
    st.session_state.scope = scope_options[selected_scope_key]

    # Document Excerpt Preview Expander
    if documents:
        with st.expander("📄 Document Excerpt Preview"):
            preview_doc_names = {d["source"]: d["id"] for d in documents}
            selected_preview_name = st.selectbox(
                "Select document to preview",
                options=list(preview_doc_names.keys()),
                label_visibility="collapsed",
                key="doc_preview_select",
            )
            selected_preview_id = preview_doc_names[selected_preview_name]
            chunks = get_document_chunks(selected_preview_id)
            if chunks:
                st.caption(f"Showing first 3 chunks of **{selected_preview_name}** ({len(chunks)} total):")
                for c in chunks[:3]:
                    p = (c.get("metadata") or {}).get("page")
                    p_str = f"Page {p}" if p else "Section"
                    st.text(f"[{p_str}]\n" + c.get("text", "")[:220])
            else:
                st.caption("No chunks found.")

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # SECTION 4: MODEL & SETTINGS
    # -----------------------------------------------------------------------
    st.markdown('<div class="sidebar-section-title">Model & Settings</div>', unsafe_allow_html=True)

    with st.popover("⚙ Settings & AI Engine", use_container_width=True):
        st.markdown("**Google Gemini AI Engine**")
        st.caption(f"Model: **{llm_status.get('display_name')}** (`{llm_status.get('model')}`)")

        if llm_status.get("ready"):
            st.success("✓ Gemini API Ready")
        else:
            st.warning("⚠ Gemini API key not set in `.env`")

        st.session_state.debug_mode = st.toggle(
            "Developer retrieval diagnostics",
            value=st.session_state.get("debug_mode", False),
            help="Show retrieved chunk distances, keywords, and sufficiency decisions.",
        )

        st.divider()

        st.markdown("**Conversation**")
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_question = None
            st.rerun()

        st.divider()

        st.markdown("**Knowledge Base**")
        st.caption(f"Delete all {len(documents)} indexed document(s).")
        if st.button("Delete All Indexed Documents", type="primary", use_container_width=True):
            clear_all_documents()
            st.session_state.messages = []
            st.session_state.processed = set()
            st.session_state.scope = None
            st.session_state.preview_doc_id = None
            st.rerun()


# ---------------------------------------------------------------------------
# Main Stage: Conversation & Top Bar
# ---------------------------------------------------------------------------

render_top_bar(len(documents), llm_status, active_scope_name)

pending_question = st.session_state.pop("pending_question", None)

render_chat_messages()

if not st.session_state.messages and pending_question is None:
    render_empty_state(documents)

user_input = st.chat_input("Ask anything about your documents…")

active_query = user_input or pending_question

if active_query:
    handle_user_question(active_query)
