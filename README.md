# DocuMind — AI Document Intelligence & RAG Assistant

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.42+-FF4B4B?logo=streamlit&logoColor=white)
![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini%202.5%20Flash-4285F4?logo=google&logoColor=white)
![ChromaDB](https://img.shields.io/badge/Vector%20Store-ChromaDB-4183C4)
![Sentence Transformers](https://img.shields.io/badge/Embeddings-all--MiniLM--L6--v2-FFA116)
![License](https://img.shields.io/badge/License-MIT-green.svg)

DocuMind is an enterprise-grade document question-answering application that allows users to upload multiple documents and ask natural-language questions across all indexed files. Built with a two-stage hybrid retrieval engine (dense semantic embeddings + sparse BM25 + exact entity matching) and powered by Google Gemini, DocuMind delivers accurate, evidence-grounded answers with document and page citations while actively preventing hallucinations through a pre-generation sufficiency gate.

---

## Table of Contents

- [Key Features](#key-features)
- [How It Works](#how-it-works)
  - [Document Ingestion Pipeline](#document-ingestion-pipeline)
  - [Query & RAG Generation Flow](#query--rag-generation-flow)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
  - [Running the Application](#running-the-application)
- [Configuration Reference](#configuration-reference)
- [Testing & Evaluation](#testing--evaluation)
- [Implemented vs. Future Roadmap](#implemented-vs-future-roadmap)
- [Author & License](#author--license)

---

## Key Features

DocuMind includes only verified, fully implemented capabilities:

- **Multi-Format Document Ingestion & Table Extraction**
  - **PDF Documents** (`.pdf`): Extracts textual content and tabular layouts using PyMuPDF (`find_tables`).
  - **Word Documents** (`.docx`): Extracts paragraph text and structured table data using `python-docx`.
  - **Spreadsheets** (`.xlsx`, `.xls`): Extracts sheets, rows, and structured cell blocks using `openpyxl`.
  - **Presentations** (`.pptx`, `.ppt`): Extracts slide content, shapes, text boxes, and slide tables using `python-pptx`.
  - **Plain Text & Markdown** (`.txt`, `.md`, `.markdown`): Preserves raw formatting and headers.
  - **Tabular CSV** (`.csv`): Converts rows into structured table text blocks.

- **Intelligent Chunking & Section Awareness**
  - Sentence-boundary splitting that preserves numeric figures, currencies, codes, and uppercase initials.
  - Automatic detection of section headings (e.g., `EDUCATION`, `POLICIES`, `WORKING HOURS`) attached to chunk metadata.
  - Deterministic SHA-256 chunk identifiers for robust deduplication and index tracking.

- **Two-Stage Hybrid RAG Retrieval**
  - **Stage 1 (Candidate Retrieval)**: Retrieves top candidates across documents combining dense semantic search (ChromaDB) and pure-Python Okapi BM25 lexical search.
  - **Stage 2 (Hybrid Scoring & Diversity Selection)**: Scores chunks using a balanced formula:
    $$\text{Score} = 0.50 \times \text{Semantic} + 0.30 \times \text{Lexical} + 0.20 \times \text{Exact Match} + 0.10 \times \text{Source Match}$$
  - **Exact Identifier Boosting**: High-priority boost for exact codes (`EMP-1042`, `PO-2026-0042`), dates, monetary amounts, and multi-word phrase matches.
  - **Document Diversity Balancing**: Ensures multi-document queries draw candidate evidence from across all indexed files.
  - **Parent Context Expansion**: Automatically pulls adjacent neighbor chunks for top-ranked matches to maintain full context.

- **Zero-LLM Question Analysis & Query Expansion**
  - Fast, rule-based classification into query types: `FACT`, `LIST`, `EXPLANATION`, `COMPARISON`, `SUMMARY`, and `MULTI_PART`.
  - Entity extraction for codes, IDs, dates, currency, percentages, emails, and phone numbers.
  - Local query expansion and synonym mapping without consuming LLM API tokens.
  - Follow-up question resolution incorporating recent chat history.

- **Anti-Hallucination Evidence Sufficiency Gate**
  - Rigorous distance and keyword threshold verification before invoking the LLM.
  - If retrieved evidence is weak or irrelevant, DocuMind returns `"I couldn't find that information in the uploaded documents."` immediately without calling Gemini or inventing answers.

- **Google Gemini Grounded Generation**
  - Built with the official `google-genai` Python SDK, configured by default with `gemini-2.5-flash`.
  - Strict 19-rule system prompt enforcing complete document grounding, exact value preservation, and factual conflict reporting.
  - Real-time token streaming (`generate_answer_stream`) for low-latency responses.

- **Warm Editorial Streamlit Interface**
  - Multi-file drag-and-drop upload with status toasts and duplicate detection.
  - Document management dashboard with page/chunk counts and single or bulk deletion.
  - **Retrieval Scope Selector**: Toggle between searching across **All Documents** or scoping queries to a single active document.
  - **Document Excerpt Previewer**: Inspect chunked text and page metadata directly from the sidebar.
  - Chat interface with suggested prompt pills, message copying, and retry regeneration.
  - Collapsible citation cards showing source document names, page numbers, and relevance metrics.
  - **Developer Retrieval Diagnostics**: Toggleable inspection panel displaying question intent, candidate chunks, BM25 scores, and sufficiency gate decisions.

---

## How It Works

### Document Ingestion Pipeline

```text
User Uploads Documents (PDF / DOCX / TXT / MD / CSV / XLSX / PPTX)
                     ↓
Format Extraction & Table Parsing (PyMuPDF, python-docx, openpyxl, python-pptx)
                     ↓
Text Cleaning & Sentence Boundary Splitting
                     ↓
Section Heading Tagging & Overlapping Chunking (CHUNK_SIZE=650, OVERLAP=100)
                     ↓
Dense Embeddings (sentence-transformers/all-MiniLM-L6-v2)
                     ↓
ChromaDB Persistent Vector Store & Metadata Registry (data/chroma)
```

### Query & RAG Generation Flow

```text
User Question
     ↓
Question Analyzer (Local: Type Classification, Entities, Keywords, Synonyms, Follow-ups)
     ↓
Multi-Document Hybrid Retriever
     ├── Dense Semantic Search (ChromaDB Vector Distance)
     ├── Sparse Lexical Search (Okapi BM25 Indexing)
     └── Exact Identifier / Phrase Match Booster
     ↓
Relevance Scoring & Multi-Document Diversity Selection
     ↓
Anti-Hallucination Evidence Sufficiency Gate
     ├── [Insufficient Evidence] ──→ Return "I couldn't find that information..."
     └── [Sufficient Evidence]   ──→ Context Expansion & Citation Context Builder
                                         ↓
                                 Google Gemini API (System Instruction + Streaming)
                                         ↓
                                 Grounded Streaming Answer + (Document, Page) Sources
```

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend / UI** | Streamlit | Responsive conversational UI, file uploaders, citation cards, scope controls |
| **Backend / Core** | Python (3.10+) | Application logic, orchestration, and text preprocessing |
| **LLM Provider** | Google Gemini (`google-genai` SDK) | Grounded natural language generation and token streaming |
| **Embeddings** | Sentence-Transformers (`all-MiniLM-L6-v2`) | Local 384-dimensional dense semantic vector embeddings |
| **Vector Store** | ChromaDB (`PersistentClient`) | Persistent local vector database and metadata indexing |
| **Lexical Engine** | Okapi BM25 & Exact Matcher (Pure Python) | In-memory keyword scoring, entity matching, and IDF calculation |
| **Document Processing** | PyMuPDF (`pymupdf`), `python-docx`, `openpyxl`, `python-pptx` | Text, slide, sheet, and structural table extraction |
| **Environment** | Python virtual environment (`venv`), `python-dotenv` | Isolated dependencies and environment configuration |

---

## Project Structure

```text
DocuMind/
├── app.py                     # Streamlit web application & UI components
├── requirements.txt           # Python package dependencies
├── .env.example               # Template environment configuration file
├── .env                       # Local environment variables (gitignored)
├── .gitignore                 # Git ignore rules
├── README.md                  # Project documentation
│
├── rag/                       # Core RAG pipeline modules
│   ├── __init__.py
│   ├── config.py              # Central configuration & tunable thresholds
│   ├── document_loader.py     # PDF, DOCX, TXT, CSV, XLSX, PPTX loaders with table extraction
│   ├── chunker.py             # Sentence-aware chunker with section header tagging
│   ├── embeddings.py          # Sentence-Transformers all-MiniLM-L6-v2 embedding model
│   ├── vector_store.py        # ChromaDB persistent collection & document registry
│   ├── lexical_search.py      # Okapi BM25 engine & exact entity/phrase matcher
│   ├── question_analyzer.py   # Zero-LLM question classifier, entity extractor & synonym expander
│   ├── retriever.py           # Two-stage hybrid retriever (semantic + BM25 + diversity)
│   ├── llm.py                 # Google Gemini API integration (generation & streaming)
│   └── rag_pipeline.py        # End-to-end RAG orchestrator & anti-hallucination gate
│
├── data/                      # Local data directory (auto-created, gitignored)
│   └── chroma/                # ChromaDB persistent storage files
│
├── utils/                     # Shared utilities
│   ├── __init__.py
│   └── helpers.py
│
├── test_accuracy.py           # Automated accuracy & retrieval evaluation suite
├── test_accuracy_comprehensive.py # Comprehensive multi-category test runner
├── test_pipeline_retrieval.py # Retrieval pipeline verification script
├── test_pipeline_full.py      # End-to-end pipeline test script
├── test_multi.py              # Multi-document synthesis test script
└── test_followup.py           # Follow-up query resolution test script
```

---

## Getting Started

### Prerequisites

- **Python**: Version 3.10 or higher
- **Gemini API Key**: Obtain a key from [Google AI Studio](https://aistudio.google.com/)

### Installation

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/Prajwal6300/Documind-RAG-Platform.git
   cd Documind-RAG-Platform
   ```

2. **Create and activate a virtual environment:**

   *On Windows (PowerShell):*
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   *On macOS / Linux (Bash):*
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

### Environment Configuration

Copy the example environment file and add your Gemini API key:

```powershell
cp .env.example .env
```

Edit `.env` and set your key:

```ini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_TOKENS=4096
GEMINI_TEMPERATURE=0.1
GEMINI_TIMEOUT=120
LLM_PROVIDER=gemini

TOP_K=5
MAX_CONTEXT_TOKENS=4000
```

> **Security Note:** Never commit your `.env` file or expose your actual API key. The `.env` file is excluded in `.gitignore`.

### Running the Application

Launch the Streamlit web interface:

```powershell
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`.

1. Upload one or more documents (PDF, DOCX, TXT, CSV, XLSX, PPTX) via the sidebar.
2. Select your retrieval scope (**All Documents** or a specific file).
3. Enter questions in the chat box to receive grounded answers with source citations.

---

## Configuration Reference

All RAG pipeline parameters are configurable via `.env` or `rag/config.py`:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(Required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model identifier for generation |
| `GEMINI_MAX_TOKENS` | `4096` | Maximum generation token budget |
| `GEMINI_TEMPERATURE` | `0.1` | Sampling temperature for strict factual consistency |
| `GEMINI_TIMEOUT` | `120` | Request timeout in seconds |
| `LLM_PROVIDER` | `gemini` | Configured LLM provider |
| `TOP_K` | `5` | Target number of chunks to consider |
| `MAX_CONTEXT_TOKENS` | `4000` | Token budget ceiling for LLM context injection |
| `RETRIEVAL_CANDIDATES` | `14` | Stage-1 candidate pool size before ranking |
| `FINAL_CONTEXT_CHUNKS` | `5` | Stage-2 final context chunks passed to Gemini |
| `RELEVANCE_THRESHOLD` | `1.48` | ChromaDB squared L2 distance ceiling (cosine similarity $\ge 0.26$) |
| `STRONG_RELEVANCE_THRESHOLD` | `1.20` | Distance below which evidence is considered strongly relevant |
| `KEYWORD_RESOLVE_DISTANCE` | `1.62` | Borderline distance band eligible for keyword match rescue |
| `KEYWORD_MATCH_REQUIRED` | `0.30` | Keyword match ratio required in the rescue band |
| `SEMANTIC_WEIGHT` | `0.50` | Weight assigned to dense vector similarity |
| `LEXICAL_WEIGHT` | `0.30` | Weight assigned to BM25 / keyword overlap score |
| `EXACT_BOOST_WEIGHT` | `0.20` | Weight assigned to exact entity and code matches |
| `SOURCE_WEIGHT` | `0.10` | Boost applied when query references the document filename |
| `CHUNK_SIZE` | `650` | Target character length per text chunk |
| `CHUNK_OVERLAP` | `100` | Overlap character count between consecutive chunks |
| `ENABLE_CONTEXT_EXPANSION` | `True` | Whether to pull adjacent chunks for top hits |
| `RAG_DEBUG` | `False` | Terminal debug logging for candidate rankings |

---

## Testing & Evaluation

The repository includes automated test suites to validate retrieval accuracy, entity extraction, multi-document synthesis, and anti-hallucination behavior:

```powershell
# Run the core accuracy test suite
python test_accuracy.py

# Run comprehensive test coverage across document types
python test_accuracy_comprehensive.py

# Test multi-document retrieval and synthesis
python test_multi.py

# Test follow-up question context resolution
python test_followup.py
```

The test framework evaluates:
1. **Single-Document Precision**: Accurate extraction of specific dates, employee IDs, and leave rules.
2. **Multi-Document Synthesis**: Cross-document comparisons and composite query answering.
3. **Out-of-Scope Detection**: Confirmation that queries without evidence trigger safe refusal without hallucination.
4. **Follow-Up Resolution**: Proper pronoun and reference expansion across conversation turns.

---

## Implemented vs. Future Roadmap

### Implemented Features (Current Release)
- [x] Multi-document ingestion across 7 file formats (PDF, DOCX, TXT, MD, CSV, XLSX, PPTX)
- [x] Structure-preserving table extraction for PDF, DOCX, CSV, Excel, and PowerPoint
- [x] Sentence-aware chunking with section header tagging and overlap
- [x] Sentence-Transformers dense embedding pipeline (`all-MiniLM-L6-v2`)
- [x] Persistent ChromaDB vector storage and document registry
- [x] Pure-Python Okapi BM25 lexical retrieval and exact entity matching
- [x] Two-stage hybrid scoring with multi-document diversity balancing
- [x] Anti-hallucination evidence sufficiency gate
- [x] Google Gemini API integration with real-time token streaming
- [x] Strict 19-rule document grounding system prompt
- [x] Deduplicated source and page citations in UI
- [x] Document scope selection (All Documents vs. Single Document)
- [x] In-sidebar document excerpt previewer
- [x] Developer diagnostics inspection panel
- [x] Automated test suites for accuracy and retrieval evaluation

### Planned Features (Future Roadmap)
- [ ] **FastAPI REST API Layer**: Programmatic HTTP endpoints (`/api/documents`, `/api/chat`, `/api/search`)
- [ ] **OCR Ingestion**: Tesseract / Vision-based extraction for scanned image PDFs
- [ ] **Cross-Encoder Reranking**: Optional deep learning reranker for re-scoring candidates
- [ ] **Docker Deployment**: Production-ready containerization with Docker Compose
- [ ] **Authentication & Multi-Tenancy**: User accounts, role-based access control (RBAC), and tenant isolation
- [ ] **Vector Database Scaling**: Managed pgvector (PostgreSQL) support for high-throughput enterprise deployments

---

## Author & License

**Author:** Prajwal Yadav  
**GitHub:** [https://github.com/Prajwal6300](https://github.com/Prajwal6300)

This project is licensed under the MIT License.
