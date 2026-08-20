# Legacy Streamlit Prototype & ChromaDB RAG Module

This directory contains the legacy standalone Streamlit user interface (`app_streamlit_legacy.py`) and the retired ChromaDB-based RAG engine (`rag/`) used during the initial prototype phase of DocuMind.

## Migration to Production Architecture
The platform has been migrated to a production decoupled architecture:
- **Backend**: FastAPI REST & SSE Streaming API located in `backend/main.py` (served on port 8000).
- **Frontend**: React 18 + Vite SPA located in `frontend/` (served on port 5173).
- **RAG Engine**: Core extraction, hybrid retrieval, and re-ranking now live in `backend/src/` backed by Supabase PostgreSQL + pgvector.
- **Storage**: Local SQLite and ChromaDB replaced by Supabase PostgreSQL + pgvector (HNSW halfvec indexing). Migrate legacy data via `scripts/migrate_to_supabase.py`.

## Running the Legacy Streamlit App (Optional / Reference Only)
If you wish to run the legacy Streamlit prototype for historical reference, execute:
```bash
streamlit run legacy/app_streamlit_legacy.py
```
*(Note: Active development and production features are in `backend/` and `frontend/`.)*
