# DocuMind System Architecture

## Overview

DocuMind is an enterprise-grade Retrieval-Augmented Generation (RAG) platform. It provides document ingestion, high-precision hybrid retrieval, Cross-Encoder re-ranking, and grounded generation backed by Google Gemini and Supabase PostgreSQL + pgvector.

---

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    subgraph Client ["Frontend Client (React 18 + Vite)"]
        UI["Workspace Chat UI"]
        EV["Evidence & Citation Cards"]
        TL["Observability Telemetry Drawer"]
    end

    subgraph API ["Backend API Layer (FastAPI)"]
        RT["REST & SSE Endpoints (/api/chat, /api/documents)"]
        Auth["Security & Request Validation"]
    end

    subgraph Ingestion ["Document Ingestion & Indexing"]
        Parser["Multi-Format Parser (PyMuPDF, docx, openpyxl)"]
        Chunker["Structure-Aware Recursive Chunker (~650 tokens, overlap 120)"]
        Embedder["Dense Embedder (Gemini gemini-embedding-001, 3072-dim)"]
    end

    subgraph Storage ["Supabase PostgreSQL 17.6 + pgvector"]
        PGDocs[("documents Table")]
        PGChunks[("document_chunks Table with HNSW Index")]
        PGSessions[("chat_sessions Table")]
        PGMessages[("chat_messages Table")]
    end

    subgraph Retrieval ["Hybrid Retrieval & Evaluation"]
        QueryProc["Zero-LLM Query Analyzer & Entity Extractor"]
        VecSearch["pgvector Cosine Distance Search (<=>)"]
        LexSearch["In-Memory BM25 Lexical Indexer"]
        Rerank["Neural Cross-Encoder (ms-marco-MiniLM-L-6-v2)"]
        SuffCheck{"Anti-Hallucination Sufficiency Gate"}
    end

    subgraph LLM ["Generation & Groundedness"]
        Gemini["Google Gemini LLM (Strict Document-Bound Prompt)"]
        Groundedness["Multi-Factor Groundedness Evaluator"]
    end

    UI --> RT
    RT --> Parser
    Parser --> Chunker
    Chunker --> Embedder
    Embedder --> PGChunks
    Parser --> PGDocs

    RT --> QueryProc
    QueryProc --> VecSearch & LexSearch
    VecSearch --> PGChunks
    VecSearch & LexSearch --> Rerank
    Rerank --> SuffCheck
    SuffCheck -- "Sufficient" --> Gemini
    SuffCheck -- "Insufficient" --> RT
    Gemini --> Groundedness
    Groundedness --> RT
    RT --> PGSessions & PGMessages
    RT --> EV & TL & UI
```

---

## 2. Storage Layer: Supabase PostgreSQL + pgvector

### Schema Overview

1. **`documents`**:
   - `id VARCHAR(64) PRIMARY KEY`
   - `name TEXT NOT NULL`
   - `title TEXT NOT NULL`
   - `type VARCHAR(16) NOT NULL`
   - `size VARCHAR(32) NOT NULL`
   - `size_bytes BIGINT NOT NULL`
   - `pages INTEGER NOT NULL DEFAULT 0`
   - `chunks INTEGER NOT NULL DEFAULT 0`
   - `file_path TEXT NOT NULL`
   - `status VARCHAR(32) NOT NULL DEFAULT 'processing'`
   - `error_message TEXT`
   - `is_archived BOOLEAN NOT NULL DEFAULT FALSE`
   - `archived_at TIMESTAMPTZ`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

2. **`document_chunks`**:
   - `id TEXT PRIMARY KEY`
   - `document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE`
   - `source TEXT NOT NULL`
   - `chunk_index INTEGER NOT NULL`
   - `page INTEGER DEFAULT 1`
   - `section TEXT DEFAULT ''`
   - `text TEXT NOT NULL`
   - `metadata JSONB DEFAULT '{}'::jsonb`
   - `embedding vector NOT NULL`

3. **`chat_sessions`**:
   - `id TEXT PRIMARY KEY`
   - `title TEXT NOT NULL`
   - `document_count INTEGER DEFAULT 0`
   - `is_archived BOOLEAN NOT NULL DEFAULT FALSE`
   - `archived_at TIMESTAMPTZ`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

4. **`chat_messages`**:
   - `id TEXT PRIMARY KEY`
   - `session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE`
   - `sender VARCHAR(16) NOT NULL`
   - `content TEXT NOT NULL`
   - `sources_json JSONB DEFAULT '[]'::jsonb`
   - `sections_json JSONB DEFAULT '[]'::jsonb`
   - `evidences_json JSONB DEFAULT '[]'::jsonb`
   - `no_context BOOLEAN NOT NULL DEFAULT FALSE`
   - `timestamp TEXT NOT NULL`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### Vector Indexing & Distance Metric

- **HNSW Index on 3072-Dimensional Embeddings**:
  Postgres `pgvector` limits standard 32-bit float indexing to $\le 2000$ dimensions. Using pgvector 0.8.2+, 3072-dimensional Gemini embeddings are indexed using `halfvec` (16-bit float) indexing:
  ```sql
  CREATE INDEX idx_chunks_embedding_hnsw 
  ON document_chunks USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);
  ```

- **Distance Metric Parity**:
  pgvector's `<=>` operator computes cosine distance $d_{\text{cos}} = 1 - \cos(u, v)$.
  Normalized Euclidean distance squared equals $2 - 2\cos(u, v) = 2 \cdot d_{\text{cos}}$.
  The vector store scales distance as `calibrated_distance = 2.0 * cos_dist`, achieving 1:1 numerical parity with all existing thresholds (`RELEVANCE_THRESHOLD = 1.48`, `STRONG_RELEVANCE_THRESHOLD = 1.20`).

---

## 3. Transaction Pooler Compatibility

DocuMind uses `psycopg` with `prepare_threshold=None` to ensure complete compatibility with Supavisor transaction-mode poolers (port `6543`), preventing duplicate prepared statement errors across connection reuse.
