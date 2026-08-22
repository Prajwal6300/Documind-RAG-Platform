"""FastAPI route handlers for DocuMind backend.

Defines REST and SSE endpoints for:
- Document management (Upload, List, Get, Delete, Archive, Restore, Download)
- Grounded chat & SSE token streaming (/api/chat, /api/chat/stream)
- Chat session management (/api/chat/sessions, /api/chat/{session_id})
- Archive overview (/api/archive)
- Suggested questions & observability telemetry (/api/suggested-questions, /api/logs)
- Health check & LLM readiness (/api/health, /api/status)

⚠️ NOTE: This is a router module, NOT a FastAPI entrypoint.
  Do NOT run via `uvicorn backend.src.api.routes:app` — that will fail
  with "Attribute app not found". The correct entrypoint is `backend.main:app`.
"""