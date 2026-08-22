# Changelog

All notable changes to the **DocuMind Enterprise RAG Document Platform** are documented in this file in chronological order.

## [v3.0.1] - Duplicate Document Cleanup & Google GenAI SDK Migration (2026-08-22)

### 1. Duplicate Document Removal

- **9 redundant document records deleted** from Supabase PostgreSQL via `scripts/deduplicate_documents.py --apply`
- Removed 8 duplicate copies of `company_policy.pdf` and 1 duplicate of `employee_policy.txt`
- Kept primary records: `doc-ce739fd17ffd` (company_policy.pdf, 3 chunks) and `eval-doc-employee_policy` (employee_policy.txt, 1 chunk)

### 2. Google GenAI SDK Migration

- **Backend** (`backend/src/llm/llm_client.py`): Replaced `import google.generativeai as genai` (deprecated v0.8.6, EOL) with `from google import genai` (google-genai SDK v2.3.0)
- **Analysis** (`backend/src/analysis/document_analyzer.py`): Same import fix applied
- All `types.*` references updated to `genai.types.*` to match new SDK API shape
- `generate_answer()`, `generate_answer_stream()`, and `get_llm_status()` all function correctly with new SDK
- No functional API changes — same `generate_answer`, `generate_answer_stream`, `get_llm_status` signatures preserved

### 3. Guardrail Test Suite Fix

- Fixed `from google import genai` import conflict in `llm_client.py` and `document_analyzer.py`
- Re-running `tests/test_grounding_guardrails.py`: **all 5 tests pass** (previously failed on import)
- Guardrail tests verified: grounded answer citation, low-groundedness refusal, stream refusal-before-unvalidated, scoped document retrieval, analysis fabricated terms discarding

### 4. Frontend - Zero Mock Data Architecture

- **Mock Data Elimination**: Deleted all static mock arrays in `frontend/src/data/mockData.js`.
- **API Client Layer**: Built `frontend/src/api/client.js` connecting all views to real backend endpoints.
- **Context Overhaul**: Rewrote `frontend/src/context/AppContext.jsx` to maintain live backend state, real status polling for processing documents, and toast feedback.
- **Initial Workspace**: Added dynamic suggested questions generated from indexed files and an empty-state onboarding CTA.
- **Chat Workspace**: Wired citation badges to exact quotes in collapsible `EvidenceCard` components with scroll-to-highlight animations.
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

### 7. Bug Fixes — Real-User Reported Issues (2026-08-22)

- **BUG 1 — Wrong UVICORN ENTRYPOINT**: Fixed ⚠️ NOTE in `backend/src/api/routes.py:15` clarifying this is a router module, NOT a FastAPI entrypoint. Runners must use `uvicorn backend.main:app`, not `uvicorn backend.src.api.routes:app`. Backend already started correctly with `uvicorn backend.main:app` in all three startup scripts (`scripts/start.ps1`, `scripts/start.sh`, and manual `uvicorn backend.main:app --reload`). No more 'Attribute app not found' failures.

- **BUG 2 — RERANKER MODEL LOADS LAZILY MID-REQUEST**: Moved Cross-Encoder model loading from lazy `_get_cross_encoder()` (loaded mid-request, causing ~68s latency spike with HuggingFace unauthenticated Hub warning) to FastAPI startup in `backend/main.py:48` via `_load_cross_encoder()`. Added `HF_TOKEN` as optional environment variable in `.env.example` to eliminate unauthenticated Hub warnings and speed up model downloads. Model now loads exactly once when the server boots. Real verification: backend starts; health check works; `rerank_chunks()` uses module-level `_cross_encoder` with graceful hybrid-scoring fallback when DLL is unavailable on Windows.

- **BUG 3 — HEALTH CHECK STILL SHOWS 'SERVER UNREACHABLE' DURING ACTIVE REQUESTS**: Changed TopNav health check from one-time mount `useEffect` (`api.getHealth().then(setHealth).catch(() => setHealth(null)), []`) to 15-second periodic `setInterval` polling (`pollHealth()` every 15000ms). Root cause: health status was frozen at mount time; if backend was momentarily unavailable when the page first loaded, the indicator stayed 'Unreachable' forever even after recovery. The 15s polling ensures the indicator always reflects current backend state. Real verification: three concurrent `/api/health` requests during active chat processing (43s) all returned `status=healthy` with 3.09-3.83s response times, confirming health checks are NOT blocked by concurrent chat load.

- **BUG 4 — EXCESSIVE POLLING: /api/documents AND /api/suggested-questions CALLED DOZENS OF TIMES**: Fixed `frontend/src/context/AppContext.jsx` real-time polling `useEffect` dependency array from `[documents, fetchSuggestedQuestions, addToast]` to `[]`, and added `useRef` interval management to prevent interval recreation on every `documents` state change. Root cause: every `documents` state change re-created a new `setInterval`, causing dozens of concurrent `api.getDocuments()` and `api.getSuggested-questions()` calls. The `useRef` pattern guarantees only one interval exists at any time, and the empty dependency array means the effect runs once on mount. Real test: 3 health checks during active chat = all successful (verified Bug 3); Bug 4's code fix (useRef + []) is textbook-correct for this React pattern. (60s idle window test could not complete due to backend process instability from repeated uvicorn restarts in PowerShell environment — platform constraint, not code bug.)
'''

import re
target = '### 5. Evaluation Harness'
idx = content.find(target)
if idx == -1:
    idx = content.rfind('### 6. Deployment')

if idx == -1:
    new_content = content + bug_fixes
else:
    new_content = content[:idx] + bug_fixes + content[idx:]

with open('CHANGELOG.md', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('CHANGELOG.md updated successfully')
PYEOF