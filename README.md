# DocuMind — Enterprise Grounded RAG Document Intelligence Platform

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite-61DAFB?logo=react&logoColor=black)](https://reactjs.org)
[![Google Gemini](https://img.shields.io/badge/LLM-Google%20Gemini%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
[![Supabase](https://img.shields.io/badge/Database-Supabase%20(Postgres%20%2B%20pgvector)-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![Cross-Encoder](https://img.shields.io/badge/Re--Ranker-ms--marco--MiniLM--L6--v2-FFA116)](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**DocuMind** is a production-ready, strictly grounded Retrieval-Augmented Generation (RAG) platform that enables enterprise teams to index multi-format documents (PDF, DOCX, XLSX, TXT, PPTX) and query them through a natural-language conversational workspace. Engineered with zero simulated data, DocuMind pairs dense Gemini semantic embeddings stored in **Supabase PostgreSQL with pgvector**, sparse BM25 lexical search, a local neural Cross-Encoder re-ranker (`ms-marco-MiniLM-L-6-v2`), an anti-hallucination sufficiency gate, and an automated citation mapper that links every factual claim to verbatim chunk evidence.

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
        Q["User Query"] --> QR["Conversational Query Rewriter"]
        QR --> H1["Semantic Vector Search (pgvector cosine <=> HNSW)"]
        QR --> H2["Lexical BM25 Search + Exact Match Boosting"]
        H1 & H2 --> M["Merged & Deduplicated Top-16 Candidates"]
        M --> RR["Neural Cross-Encoder Re-Ranker (ms-marco-MiniLM-L-6-v2)"]
        RR --> SG{"Anti-Hallucination Sufficiency Gate"}      
    end

    subgraph Generation ["3. Grounded Synthesis & Observability"]
        SG -- "Insufficient / Irrelevant" --> REF["Explicit Refusal: 'Not found in uploaded documents'"]
        SG -- "Sufficient Evidence" --> LLM["Google Gemini Generation (Strict Document-Bound Prompt)"]
        LLM --> CIT["Structured Section Parsing & Citation Linking"]
        CIT --> UI["Live React Chat UI with Evidence Cards & Telemetry Drawer"]
        CIT --> LOGS[("Structured Observability Logs (data/logs/documind.log)")]
    end
```

---

## 📊 Benchmark Evaluation Report

DocuMind includes an automated evaluation harness (`scripts/eval.py`) executed against a verified 35-query benchmark dataset (`scripts/eval_dataset.json`) containing factual QA, document summaries, multi-file synthesis, and out-of-domain unanswerable queries.

### Evaluation Results

| Metric | Target | Result | Status |
|---|---|---|---|
| **Overall Accuracy** | ≥ 90.0% | **97.1%** | 🟢 PASS |
| **Retrieval Precision@k** | ≥ 90.0% | **100.0%** | 🟢 PASS |
| **Refusal Accuracy (Zero Hallucination)** | 100.0% | **100.0%** | 🟢 PASS |
| **Answer Correctness (Entity & Keyword Match)** | ≥ 90.0% | **95.2%** | 🟢 PASS |
| **Average End-to-End Latency** | < 3000 ms | **1,840 ms** | 🟢 PASS |

> **Evaluation Methodology**: The benchmark tests answerable queries against exact keywords and source citations, while out-of-domain queries (e.g. quantum physics, dress codes not in documents, unmentioned figures) are evaluated for strict refusal (*"I couldn't find that information in the uploaded documents."*).

---

## ✨ Core Features & Technical Highlights

### 1. Structure-Aware Document Processing
- **PyMuPDF (`pymupdf`) Layout Extraction**: Extracts page text blocks, tables, and multi-page structural headers.
- **`python-docx` & `openpyxl` Ingestion**: Extracts headings, bold keys, and tabular data from Word documents and Excel sheets.
- **Section-Preserving Chunking**: Splits text along headings and sentence boundaries without slicing mid-number, code, or entity.

### 2. Hybrid Search & Neural Re-Ranking
- **Supabase pgvector + Okapi BM25**: Combines cosine semantic vector distance with term-frequency lexical ranking.
- **Exact Identifier Boosting**: High-priority score boost for part numbers, employee IDs (`EMP1024`), dates, and dollar amounts.
- **Local Cross-Encoder**: Scores `(query, passage)` pairs via `cross-encoder/ms-marco-MiniLM-L-6-v2` with zero external API cost.

### 3. Strict Anti-Hallucination Sufficiency Gate
- Evaluates candidate relevance before calling Gemini. If relevance or keyword density is below threshold, immediately returns a clean refusal without fabricating answers or citations.

### 4. Interactive UX & Telemetry Inspector
- **Evidence Cards**: Collapsible cards rendering the exact chunk quote, page number, and source file. Clicking a citation badge smoothly scrolls to and highlights the corresponding evidence card.
- **Telemetry Drawer**: Live inspect drawer showing resolved query, candidate count, Cross-Encoder scores, and groundedness percentages.
- **Recent Analysis & Library**: All documents and chat sessions persist in Supabase PostgreSQL and survive backend restarts.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- **Python 3.10+** (tested on Python 3.11 & 3.13)
- **Node.js 18+** and npm
- **Google Gemini API Key** (Free tier available at [Google AI Studio](https://aistudio.google.com/))

### 2. Installation

#### Clone Repository & Configure Environment
```bash
git clone https://github.com/Prajwal6300/Documind-RAG-Platform.git
cd Documind-RAG-Platform

# Copy environment template
cp .env.example .env
```
Edit `.env` and add your Gemini API key:
```env
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
MAX_FILE_SIZE_MB=25
ENABLE_RERANKER=true
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
* Vite automatically proxies all `/api/*`, `/documents/*`, and `/chat/*` requests to `http://127.0.0.1:8000`.

---

## 🧪 Running Automated Tests & Benchmark

### 1. Run End-to-End Functional Test
```bash
python test_e2e_verification.py
```

### 2. Run Full 35-Query Evaluation Harness
```bash
python scripts/eval.py
```

---

## 🌐 Production Deployment Guide

### Deployment Architecture
- **Frontend**: Deploy to **Vercel** (Static SPA with `frontend/vercel.json` rewrites).
- **Backend**: Deploy to **Render** or **Railway** as a containerized Python Web Service connected to **Supabase**.
- **Database & Vectors**: Managed **Supabase (PostgreSQL 17 + pgvector)**, eliminating the need for stateful local disks.

### Deploying Frontend to Vercel
1. Link your repository to Vercel.
2. Set **Root Directory** to `frontend`.
3. Set **Build Command** to `npm run build`.
4. Set **Output Directory** to `dist`.
5. Add Environment Variable:
   - `VITE_API_URL` = `https://your-backend-service.onrender.com`

### Deploying Backend to Render / Railway / Docker
1. Create a new **Web Service** on [Render](https://render.com) or [Railway](https://railway.app).
2. Select repository and use `Dockerfile`.
3. Add Environment Variables:
   - `DATABASE_URL` = `postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`
   - `GEMINI_API_KEY` = `your_gemini_api_key`
   - `GEMINI_MODEL` = `gemini-flash-latest`
   - `GEMINI_EMBEDDING_MODEL` = `gemini-embedding-001`
   - `MAX_FILE_SIZE_MB` = `25`
   - `ENABLE_RERANKER` = `true`
4. Deploy — database tables and pgvector indexes are automatically managed and persisted in Supabase.

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
│   ├── test_e2e_verification.py # Automated integration verification test
│   ├── test_accuracy.py         # 12-category accuracy test suite
│   ├── test_multi.py            # Multi-document scoped test suite
│   └── ...                      # Pipeline/retrieval/live-server test suites
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
