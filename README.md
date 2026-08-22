# DocuMind — Enterprise Grounded RAG Document Intelligence Platform

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB?logo=react&logoColor=black)](https://reactjs.org)
[![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Supabase](https://img.shields.io/badge/Database-Supabase%20(Postgres%20%2B%20pgvector)-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![Cross-Encoder](https://img.shields.io/badge/Re--Ranker-ms--marco--MiniLM--L6--v2-FFA116)](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2)
[![Vercel](https://img.shields.io/badge/Frontend%20Deployment-Vercel-black?logo=vercel&logoColor=white)](https://documind-rag-platform.vercel.app)
[![Render](https://img.shields.io/badge/Backend%20Deployment-Render-46E3B7?logo=render&logoColor=white)](https://documind-rag-platform.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**DocuMind** is a production-ready, strictly grounded Retrieval-Augmented Generation (RAG) platform that enables enterprise teams to index multi-format documents (PDF, DOCX, XLSX, TXT, PPTX) and query them through a natural-language conversational workspace. DocuMind pairs dense Gemini semantic embeddings stored in **Supabase PostgreSQL with pgvector**, sparse BM25 lexical search, a local neural Cross-Encoder re-ranker (`ms-marco-MiniLM-L-6-v2`), an anti-hallucination sufficiency gate, and an automated citation mapper that links every factual claim to verbatim chunk evidence.

---

## 🌐 Live Production Deployments

* **Live Frontend (Vercel)**: [https://documind-rag-platform.vercel.app](https://documind-rag-platform.vercel.app)
* **Live Backend API (Render)**: [https://documind-rag-platform.onrender.com](https://documind-rag-platform.onrender.com)
* **Backend Health Check**: [https://documind-rag-platform.onrender.com/api/health](https://documind-rag-platform.onrender.com/api/health)
* **Interactive OpenAPI Swagger Docs**: [https://documind-rag-platform.onrender.com/docs](https://documind-rag-platform.onrender.com/docs)

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Ingestion ["1. Document Ingestion Pipeline"]
        A["User Document (PDF / DOCX / TXT / XLSX / PPTX)"] --> B["Format Extractor (PyMuPDF / python-docx / openpyxl)"]
        B --> C["Heading-Aware Structure Chunking (~650 tokens, overlap 120)"]
        C --> D["Gemini Embeddings (gemini-embedding-001, 3072-dim)"]
        D --> E[("Supabase PostgreSQL + pgvector (document_chunks with HNSW)")]
        C --> F[("Supabase PostgreSQL Relational Schema (documents, chat_sessions)")]
    end

    subgraph Retrieval ["2. Multi-Stage Hybrid Retrieval & Re-Ranking"]
        Q["User Query (Typos / Slang / Vague Scope)"] --> QN["Fast Query Normalizer (< 0.2ms) & Vague Scope Resolver"]
        QN --> H1["Semantic Vector Search (pgvector cosine <=> HNSW)"]
        QN --> H2["Lexical BM25 Search + Exact Match Boosting"]
        H1 & H2 --> M["Merged & Deduplicated Top-14 Candidates (Parallel ThreadPool)"]
        M --> RR["Neural Cross-Encoder Re-Ranker (ms-marco-MiniLM-L-6-v2)"]
        RR --> SG{"Anti-Hallucination Sufficiency Gate"}      
    end

    subgraph Generation ["3. Grounded Synthesis & Observability"]
        SG -- "Insufficient / Irrelevant" --> REF["Explicit Refusal: 'Not found in uploaded documents'"]
        SG -- "Sufficient Evidence" --> LLM["Google Gemini Generation (Strict Document-Bound Prompt)"]
        LLM --> CIT["Structured Section Parsing & Citation Linking"]
        CIT --> UI["Live React Chat UI with Evidence Cards & Telemetry Drawer"]
        CIT --> LOGS[("Structured Observability Logs")]
    end
```

---

## 📊 Safety Guardrails & Deterministic Verification

DocuMind includes deterministic safety guardrails executed in `tests/test_grounding_guardrails.py` to prevent hallucination, citation fabrication, and out-of-domain answering:

| Guardrail Test Case | Focus | Result | Status |
|---|---|---|---|
| **Single-Source Real Citation** | Ensures answer matches ground truth chunk | Groundedness ≥ 0.55 | 🟢 PASS |
| **Strict Low-Groundedness Refusal** | Blocks unsupported answers even if text looks plausible | Refusal output emitted | 🟢 PASS |
| **Stream Non-Leakage** | Ensures SSE never emits tokens before validation | Zero unvalidated tokens | 🟢 PASS |
| **Scoped Query Isolation** | Restricts vector & lexical search to chosen document ID | Document boundary isolated | 🟢 PASS |
| **Fabricated Term Rejection** | Discards LLM summary terms not present in document text | Hallucination discarded | 🟢 PASS |
| **Typo & Slang Tolerance** | Normalizes casual queries (`wat is the sick leave policy`) | Clean grounded answer | 🟢 PASS |
| **Vague Scoped Resolution** | Resolves `what is it?` against scoped document name | Scope-targeted summary | 🟢 PASS |

---

## ✨ Core Features & Technical Highlights

### 1. Structure-Aware Document Processing
- **PyMuPDF (`pymupdf`) Layout Extraction**: Extracts page text blocks, tables, and multi-page structural headers.
- **`python-docx` & `openpyxl` Ingestion**: Extracts headings, bold keys, and tabular data from Word documents and Excel sheets.
- **Section-Preserving Chunking**: Splits text along headings and sentence boundaries without slicing mid-number, code, or entity.

### 2. High-Speed Hybrid Search & Neural Re-Ranking
- **Supabase pgvector + Okapi BM25**: Combines cosine semantic vector distance with term-frequency lexical ranking in parallel (`ThreadPoolExecutor`).
- **Typo-Tolerant Query Normalization**: Fast `< 0.2ms` dictionary and regex normalizer cleans typos, casual contractions, and slang without adding LLM round-trips.
- **Vague Scoped Query Resolution**: Resolves questions like `"what is it?"` or `"tell me about this"` against active document metadata before retrieval.
- **Local Cross-Encoder**: Scores `(query, passage)` pairs via `cross-encoder/ms-marco-MiniLM-L-6-v2` loaded once on startup.

### 3. Strict Anti-Hallucination Sufficiency Gate
- Evaluates candidate relevance before calling Gemini. If relevance or keyword density is below threshold, immediately returns a clean refusal without fabricating answers or citations.
- Groundedness threshold (`0.55`) ensures low-groundedness outputs are converted to clear refusals.

### 4. Interactive UX & Telemetry Inspector
- **Evidence Cards**: Collapsible cards rendering the exact chunk quote, page number, and source file with scroll-to-highlight animations.
- **Telemetry Drawer**: Live inspect drawer showing resolved query, candidate count, Cross-Encoder scores, and groundedness percentages.
- **Live Status Polling & Highlight**: Active background polling for indexing files with animated sidebar highlighting and counter updates.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- **Python 3.10+** (tested on Python 3.11 & 3.13)
- **Node.js 18+** and npm
- **Google Gemini API Key** (Free tier available at [Google AI Studio](https://aistudio.google.com/))
- **Supabase Account** with PostgreSQL 17 + `pgvector` extension

### 2. Installation

#### Clone Repository & Configure Environment
```bash
git clone https://github.com/Prajwal6300/Documind-RAG-Platform.git
cd Documind-RAG-Platform

# Copy environment template
cp .env.example .env
```

Edit `.env` and configure required variables:
```env
# Google Gemini
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Supabase PostgreSQL + pgvector
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# HuggingFace (Optional - for faster Cross-Encoder downloads)
HF_TOKEN=your_optional_hf_token

# CORS
CORS_ORIGINS=http://localhost:5173,https://documind-rag-platform.vercel.app

# Reranker & Guardrails
ENABLE_RERANKER=true
GROUNDEDNESS_THRESHOLD=0.55
```

#### Install Backend Dependencies
```bash
# Activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

#### Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

---

## 💻 Running the Application

> [!IMPORTANT]
> **Single Correct Run Path**: DocuMind uses a decoupled architecture with a **FastAPI backend** on port `8000` and a **React + Vite frontend** on port `5173`. Run the backend with `uvicorn backend.main:app` and the frontend with `npm run dev --prefix frontend`.

### Option A: One-Command Startup (Recommended)                      
**Windows PowerShell:**
```powershell
.\scripts\start.ps1
```
**Linux / macOS:**
```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

### Option B: Manual Startup (Two Terminals)

**Step 1: Start Backend (Terminal 1)**
```bash
# Windows (PowerShell/CMD):
.\venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Linux / macOS:
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
* Backend API: `http://127.0.0.1:8000`
* Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
* Health Check: `http://127.0.0.1:8000/api/health`

**Step 2: Start Frontend (Terminal 2)**
```bash
cd frontend
npm run dev
```
* Web Application: `http://localhost:5173`
* Vite automatically proxies `/api/*` requests to `http://127.0.0.1:8000`.

---

## 🧪 Running Automated Tests

```bash
# Run 7 Grounding Guardrail Safety Tests
python -m pytest tests/test_grounding_guardrails.py
```

---

## 🌐 Production Deployment Guide

DocuMind uses a split production topology:

```
┌────────────────────────────────────────┐
│   Vercel (Frontend Client SPA)         │
│   https://documind-rag-platform.vercel.app│
└───────────────────┬────────────────────┘
                    │ HTTPS / REST / SSE Stream
┌───────────────────▼────────────────────┐
│   Render (FastAPI Python Web Service)   │
│   https://documind-rag-platform.onrender.com│
└─────────┬──────────────────────┬───────┘
          │                      │
┌─────────▼────────┐   ┌─────────▼────────┐
│  Google Gemini   │   │  Supabase        │
│  (GenAI SDK v2)  │   │  PostgreSQL 17   │
│  Embed + Chat    │   │  + pgvector HNSW │
└──────────────────┘   └──────────────────┘
```

### Why Split Deployment?
- **Vercel**: Optimized for static React asset delivery, instant global edge caching, and zero frontend maintenance.
- **Render**: Required for running the persistent FastAPI Python runtime, holding the `sentence-transformers` Cross-Encoder in memory, supporting long-lived SSE streaming responses, and managing background document vectorization.
- **Supabase**: Managed PostgreSQL 17 database with native `pgvector` HNSW indexing, eliminating local stateful disks.

### Deploying Frontend to Vercel
1. Connect GitHub repository to Vercel.
2. Root Directory: `frontend`
3. Build Command: `npm run build`
4. Output Directory: `dist`
5. Environment Variable:
   - `VITE_API_BASE_URL` = `https://documind-rag-platform.onrender.com` (no trailing slash)

### Deploying Backend to Render
1. Create a new Web Service using the repository Dockerfile.
2. Environment Variables:
   - `DATABASE_URL` = `postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`
   - `GEMINI_API_KEY` = `your_gemini_api_key`
   - `GEMINI_MODEL` = `gemini-2.5-flash`
   - `GEMINI_EMBEDDING_MODEL` = `gemini-embedding-001`
   - `CORS_ORIGINS` = `https://documind-rag-platform.vercel.app,http://localhost:5173`
   - `ENABLE_RERANKER` = `true`
   - `PORT` = `8000`

---

## 📁 Repository Directory Structure

```
Documind-RAG-Platform/
├── backend/
│   ├── main.py                  # FastAPI server & REST/SSE routes
│   ├── config.yaml              # Global configuration & database settings
│   ├── Dockerfile               # Backend container definition
│   └── src/
│       ├── api/routes.py        # API route handlers (/api/chat, /api/documents)
│       ├── chunking/            # Structure-aware heading chunker
│       ├── embeddings/          # Google Gemini normalized embeddings
│       ├── ingestion/           # Multi-format document parser (PDF/DOCX/XLSX/PPTX/TXT)
│       ├── llm/                 # Google GenAI generation & streaming client
│       ├── pipeline/            # End-to-end RAG pipeline orchestrator
│       ├── prompts/             # System prompts & anti-hallucination templates
│       ├── retrieval/           # Hybrid pgvector + BM25 + Cross-Encoder retriever
│       ├── utils/               # Config loaders & structured logging
│       └── vectordb/            # Supabase Postgres database & pgvector store
├── frontend/
│   ├── src/
│   │   ├── api/client.js        # Backend API integration layer
│   │   ├── context/             # AppContext live state management
│   │   ├── pages/               # InitialWorkspace, Chat, Library, Archive
│   │   ├── components/          # EvidenceCard, CitationBadge, DebugPanel
│   ├── package.json
│   ├── vite.config.js           # Vite build & proxy configuration
│   └── vercel.json              # Vercel SPA routing
├── migrations/
│   └── 001_initial_supabase_schema.sql  # Supabase PostgreSQL + pgvector schema
├── scripts/
│   ├── eval.py                  # 35-query benchmark evaluation harness
│   ├── eval_dataset.json        # Benchmark dataset
│   ├── run_migrations.py        # Automated SQL migration runner
│   ├── migrate_to_supabase.py   # SQLite + ChromaDB -> Supabase data migrator
│   ├── start.ps1                # PowerShell launcher
│   └── start.sh                 # Unix launcher
├── tests/
│   ├── test_grounding_guardrails.py # Deterministic safety & anti-hallucination guardrail tests (7/7 pass)
│   ├── test_e2e_verification.py     # Automated FastAPI integration verification
│   └── ...                          # Benchmark & pipeline validation suites
├── pytest.ini                   # Standardized pytest test discovery configuration
├── SUPABASE_SETUP.md            # Supabase setup & verification guide
├── requirements.txt             # Production Python dependencies (psycopg, pgvector)
├── docker-compose.yml           # Production Docker Compose orchestration
├── Dockerfile                   # Root container Dockerfile
├── CHANGELOG.md                 # Chronological version history
└── README.md                    # Project documentation
```

---

## 🛡️ License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
