# Changelog

All notable changes to the **DocuMind Enterprise RAG Document Platform** are documented in this file in chronological order.

---

## [v2.0.0] - Production RAG Conversion & Architecture Overhaul

### 1. Backend & Persistence
- **FastAPI Core**: Built a complete REST API in `backend/main.py` with asynchronous document ingestion, background task processing, and Server-Sent Events (SSE) token streaming.
- **SQLite Database**: Implemented `backend/database.py` with SQLite WAL mode to persist documents, chat sessions, message histories, and archive records across server restarts.
- **Strict Anti-Hallucination Sufficiency Gate**: Configured a pre-generation gate that blocks queries lacking sufficient document evidence, enforcing unambiguous refusals (*"I couldn't find that information in the uploaded documents."*).

### 2. Document Processing & Ingestion Pipeline
- **Multi-Format Extraction**: Enhanced `rag/document_loader.py` with structure-preserving parsers:
  - PyMuPDF (`pymupdf`) for PDFs with page numbering and table block detection.
  - Python-docx (`docx`) for Word documents with section headings and tabular data.
  - Openpyxl for Excel spreadsheets (`.xlsx`).
  - Python-pptx for PowerPoint presentations (`.pptx`).
  - Text & CSV tabular parser for structured delimiter text.
- **Heading-Aware Chunking**: Upgraded `rag/chunker.py` to recursively split on headings and sentence boundaries with token overlap (~650 tokens, ~100 overlap), retaining page number, document ID, section title, and chunk index.
- **Gemini Embeddings**: Integrated Google Gemini `gemini-embedding-001` (3072-dimensional normalized vectors) with local `sentence-transformers/all-MiniLM-L6-v2` fallback.
- **Persistent ChromaDB**: Configured disk-persisted vector collection under `data/chroma/`.

### 3. Advanced Retrieval & Re-Ranking
- **Hybrid Retrieval**: Merged ChromaDB semantic vector search with in-memory BM25 lexical search and exact entity boosting (`rag/retriever.py`).
- **Cross-Encoder Re-Ranking**: Integrated `cross-encoder/ms-marco-MiniLM-L-6-v2` (`rag/reranker.py`) to re-score candidate chunks and surface high-signal context.
- **Query Resolution**: Added conversational history query rewriting to resolve pronouns and contextual follow-ups into standalone search queries.
- **Groundedness & Confidence Scoring**: Computed per-answer groundedness metrics based on retrieval strength and term coverage.

### 4. Frontend - Zero Mock Data Architecture
- **Mock Data Elimination**: Deleted all static mock arrays in `frontend/src/data/mockData.js`.
- **API Client Layer**: Built `frontend/src/api/client.js` connecting all views to real backend endpoints.
- **Context Overhaul**: Rewrote `frontend/src/context/AppContext.jsx` to maintain live backend state, real status polling for processing documents, and toast feedback.
- **Initial Workspace**: Added dynamic suggested questions generated from indexed files and an empty-state onboarding CTA.
- **Chat Workspace**: Wired citation badges to exact quotes in collapsible `EvidenceCard` components with scroll-to-highlight animations.
- **Observability Inspector**: Built `DebugPanel.jsx` and a live pipeline telemetry log viewer in the UI.
- **Library Page**: Enabled real document counts, file sizes, page counts, type filtering, sorting, and direct file downloads.
- **Recent Analysis & Archive**: Persisted chat threads and enabled full document restoration and permanent deletion.

### 5. Evaluation Harness & Benchmarking
- Created `scripts/eval_dataset.json` with 35 benchmark queries across factual QA, summaries, multi-document synthesis, and adversarial unanswerable questions.
- Built `scripts/eval.py` measuring Retrieval Precision@k, Refusal Accuracy, Answer Correctness, and Latency.

### 6. Deployment & Containerization
- **Vercel**: Added `frontend/vercel.json` SPA configuration.
- **Render**: Created `render.yaml` infrastructure blueprint.
- **Docker**: Added root and backend `Dockerfile` for containerized environments.
- **Environment Template**: Documented `.env.example` with zero hardcoded credentials.
