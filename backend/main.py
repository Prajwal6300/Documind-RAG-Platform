"""DocuMind Backend Entrypoint (FastAPI)

Production RAG document intelligence platform integrating:
- Google Gemini Generation & Embeddings
- Supabase PostgreSQL with pgvector & HNSW Cosine Indexing
- Multi-format extraction (PDF, DOCX, XLSX, PPTX, CSV, TXT)
- Supabase PostgreSQL persistence for documents, chat history, and archive
- Server-Sent Events (SSE) Streaming & Observability Logs
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

# Ensure repository root is on sys.path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from backend.src.utils.config import CORS_ORIGINS
from backend.src.utils.errors import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

from backend.src.api.routes import router as api_router

app = FastAPI(
    title="DocuMind RAG API",
    version="3.0.0",
    description="Enterprise RAG Document Intelligence Platform powered by Google Gemini and Supabase pgvector",
)

# ---------------------------------------------------------------------------
# CORS: restrict to explicitly configured frontend origins.
# Never use "*" with credentials; a wildcard is only allowed without cookies.
# ---------------------------------------------------------------------------
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # No explicit origins configured -> do not allow cross-origin browser calls.
    # Same-origin requests (e.g. via the Vite proxy) are unaffected.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Global exception handling: never return a raw crash / stack trace to clients.
# ---------------------------------------------------------------------------
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Mount modular API routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)