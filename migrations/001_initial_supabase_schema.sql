-- ==============================================================================
-- DocuMind RAG Platform: Supabase PostgreSQL + pgvector Migration
-- Migration: 001_initial_supabase_schema.sql
-- ==============================================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Documents Table (Stores document metadata, processing status, and archive state)
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    size TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    pages INTEGER DEFAULT 0,
    chunks INTEGER DEFAULT 0,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing',
    error_message TEXT DEFAULT '',
    warning_message TEXT DEFAULT '',
    is_low_text BOOLEAN DEFAULT FALSE,
    content_hash TEXT DEFAULT '',
    doc_summary TEXT DEFAULT '',
    doc_category TEXT DEFAULT '',
    entities_json JSONB DEFAULT '[]'::jsonb,
    structure_json JSONB DEFAULT '[]'::jsonb,
    suggested_questions_json JSONB DEFAULT '[]'::jsonb,
    analysis_status TEXT DEFAULT 'pending',
    analysis_warnings_json JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMPTZ DEFAULT NULL
);

-- 3. Chat Sessions Table (Tracks multi-turn analysis threads)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    snippet TEXT DEFAULT '',
    doc_scope TEXT DEFAULT 'All Documents',
    doc_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMPTZ DEFAULT NULL
);

-- 4. Chat Messages Table (Stores conversation turns with citations and evidences)
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    text TEXT DEFAULT '',
    intro TEXT DEFAULT '',
    sections_json JSONB DEFAULT '[]'::jsonb,
    sources_json JSONB DEFAULT '[]'::jsonb,
    evidences_json JSONB DEFAULT '[]'::jsonb,
    no_context BOOLEAN NOT NULL DEFAULT FALSE,
    timestamp TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Document Chunks Table (Replaces ChromaDB vector collections)
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page INTEGER DEFAULT 1,
    section TEXT DEFAULT '',
    text TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector NOT NULL
);

-- 6. Relational & Query Indexes
CREATE INDEX IF NOT EXISTS idx_docs_archived ON documents(is_archived, status);
-- Run the deduplication dry run before applying this migration to an existing
-- database.  Active uploads are protected by this partial unique constraint;
-- archived copies may be retained for audit/history.
CREATE UNIQUE INDEX IF NOT EXISTS uq_docs_active_content_hash
ON documents(content_hash)
WHERE content_hash <> '' AND is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_docs_category ON documents(doc_category);
CREATE INDEX IF NOT EXISTS idx_docs_created ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_archived ON chat_sessions(is_archived);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_index ON document_chunks(document_id, chunk_index);

-- 7. Vector Search HNSW Index
-- For high-dimensional embeddings (e.g. Gemini 3072 dims), halfvec HNSW index provides 
-- high-speed approximate search while staying within PostgreSQL indexing limits.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
ON document_chunks USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);
