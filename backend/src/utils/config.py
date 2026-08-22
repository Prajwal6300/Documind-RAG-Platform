"""Centralized configuration loader for DocuMind backend and RAG pipeline.

Loads configuration defaults from `backend/config.yaml` and allows environment
variables (`.env`) to dynamically override runtime settings.
"""

import os
from pathlib import Path
import logging
import yaml
from dotenv import load_dotenv

load_dotenv()

_log = logging.getLogger("documind.config")

# Determine project directories
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BACKEND_DIR.parent if BACKEND_DIR.name == "backend" else BACKEND_DIR
CONFIG_YAML_PATH = BACKEND_DIR / "config.yaml"


def _load_yaml_config():
    """Load config.yaml if present, otherwise return empty dict."""
    if CONFIG_YAML_PATH.exists():
        try:
            with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            _log.warning("Could not parse %s: %s", CONFIG_YAML_PATH, e)
    return {}


_YAML_CONFIG = _load_yaml_config()


def _get_val(section: str, key: str, env_var: str, default):
    """Retrieve config value with environment variable override precedence."""
    env_val = os.getenv(env_var)
    if env_val is not None:
        if isinstance(default, bool):
            return env_val.strip().lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            try:
                return int(env_val)
            except ValueError:
                return default
        if isinstance(default, float):
            try:
                return float(env_val)
            except ValueError:
                return default
        return env_val.strip()

    sec_dict = _YAML_CONFIG.get(section, {})
    return sec_dict.get(key, default)


# --- LLM Provider Settings ---
LLM_PROVIDER = _get_val("llm", "provider", "LLM_PROVIDER", "gemini")

# --- Google Gemini Settings ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = _get_val("llm", "model", "GEMINI_MODEL", "gemini-flash-latest")
GEMINI_EMBEDDING_MODEL = _get_val("llm", "embedding_model", "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_MAX_TOKENS = _get_val("llm", "max_tokens", "GEMINI_MAX_TOKENS", 4096)
GEMINI_TEMPERATURE = _get_val("llm", "temperature", "GEMINI_TEMPERATURE", 0.1)
GEMINI_TIMEOUT = _get_val("llm", "timeout", "GEMINI_TIMEOUT", 120)

# --- Storage & Database Settings ---
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
UPLOAD_DIR = Path(_get_val("storage", "upload_dir", "UPLOAD_DIR", "data/uploads"))
LOG_PATH = Path(_get_val("storage", "log_path", "LOG_PATH", "data/logs/documind.log"))

MAX_FILE_SIZE_MB = _get_val("storage", "max_file_size_mb", "MAX_FILE_SIZE_MB", 25)
ALLOWED_EXTENSIONS = set(_YAML_CONFIG.get("storage", {}).get("allowed_extensions", [
    "pdf", "docx", "txt", "csv", "xlsx", "xls", "pptx", "ppt", "md", "markdown"
]))

# --- Database Connectivity (timeouts to prevent hangs) ---
DB_CONNECT_TIMEOUT = _get_val("storage", "connect_timeout", "DB_CONNECT_TIMEOUT", 15)
DB_STATEMENT_TIMEOUT_MS = _get_val("storage", "statement_timeout_ms", "DB_STATEMENT_TIMEOUT_MS", 30000)

# --- CORS & Rate Limiting ---
_cors_default = _YAML_CONFIG.get("security", {}).get("cors_origins", [])
if isinstance(_cors_default, str):
    _cors_default = [o.strip() for o in _cors_default.split(",") if o.strip()]
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", ",".join(_cors_default)).split(",")
    if o.strip()
]

RATE_LIMIT_CHAT_LIMIT = _get_val("security", "chat_rate_limit", "RATE_LIMIT_CHAT_LIMIT", 30)
RATE_LIMIT_CHAT_WINDOW = _get_val("security", "chat_rate_window", "RATE_LIMIT_CHAT_WINDOW", 60)
RATE_LIMIT_UPLOAD_LIMIT = _get_val("security", "upload_rate_limit", "RATE_LIMIT_UPLOAD_LIMIT", 20)
RATE_LIMIT_UPLOAD_WINDOW = _get_val("security", "upload_rate_window", "RATE_LIMIT_UPLOAD_WINDOW", 3600)

# --- Input Validation Limits ---
MAX_QUERY_LENGTH = _get_val("security", "max_query_length", "MAX_QUERY_LENGTH", 4000)
MAX_FILENAME_LENGTH = _get_val("security", "max_filename_length", "MAX_FILENAME_LENGTH", 200)

# --- Chunking Settings ---
CHUNK_SIZE = _get_val("chunking", "chunk_size", "CHUNK_SIZE", 650)
CHUNK_OVERLAP = _get_val("chunking", "chunk_overlap", "CHUNK_OVERLAP", 100)

# --- Retrieval Tuning (Two-Stage Strategy) ---
TOP_K = _get_val("retrieval", "top_k", "TOP_K", 5)
MAX_CONTEXT_TOKENS = _get_val("retrieval", "max_context_tokens", "MAX_CONTEXT_TOKENS", 4000)

RETRIEVAL_CANDIDATES = _get_val("retrieval", "candidates_k", "RETRIEVAL_CANDIDATES", 14)
INITIAL_RETRIEVAL_K = RETRIEVAL_CANDIDATES

FINAL_CONTEXT_CHUNKS = _get_val("retrieval", "final_context_chunks", "FINAL_CONTEXT_CHUNKS", 6)
FINAL_CONTEXT_K = FINAL_CONTEXT_CHUNKS

RELEVANCE_THRESHOLD = _get_val("retrieval", "relevance_threshold", "RELEVANCE_THRESHOLD", 1.48)
STRONG_RELEVANCE_THRESHOLD = _get_val("retrieval", "strong_relevance_threshold", "STRONG_RELEVANCE_THRESHOLD", 1.20)

KEYWORD_RESOLVE_DISTANCE = _get_val("retrieval", "keyword_resolve_distance", "KEYWORD_RESOLVE_DISTANCE", 1.62)
KEYWORD_MATCH_REQUIRED = _get_val("retrieval", "keyword_match_required", "KEYWORD_MATCH_REQUIRED", 0.30)

MAX_SUMMARY_CHUNKS = _get_val("retrieval", "max_summary_chunks", "MAX_SUMMARY_CHUNKS", 10)
ENABLE_CONTEXT_EXPANSION = _get_val("retrieval", "enable_context_expansion", "ENABLE_CONTEXT_EXPANSION", True)
MAX_EXPANSION_CHUNKS = _get_val("retrieval", "max_expansion_chunks", "MAX_EXPANSION_CHUNKS", 2)

GROUNDEDNESS_THRESHOLD = _get_val("retrieval", "groundedness_threshold", "GROUNDEDNESS_THRESHOLD", 0.55)
MIN_RERANK_SCORE = _get_val("retrieval", "min_rerank_score", "MIN_RERANK_SCORE", 0.30)

# Hybrid ranking weights
_weights = _YAML_CONFIG.get("retrieval", {}).get("weights", {})
SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", str(_weights.get("semantic", 0.50))))
LEXICAL_WEIGHT = float(os.getenv("LEXICAL_WEIGHT", str(_weights.get("lexical", 0.30))))
EXACT_BOOST_WEIGHT = float(os.getenv("EXACT_BOOST_WEIGHT", str(_weights.get("exact_boost", 0.20))))
KEYWORD_WEIGHT = LEXICAL_WEIGHT
SOURCE_WEIGHT = float(os.getenv("SOURCE_WEIGHT", str(_weights.get("source", 0.10))))

# --- Re-Ranker Settings ---
ENABLE_RERANKER = _get_val("reranker", "enabled", "ENABLE_RERANKER", True)
RERANKER_MODEL = _get_val("reranker", "model_name", "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()


# --- Observability & Debugging ---
RAG_DEBUG = _get_val("observability", "debug_mode", "RAG_DEBUG", False)
DEBUG_MODE = RAG_DEBUG


def get_config():
    """Return runtime configuration dictionary."""
    return {
        "llm": {
            "provider": LLM_PROVIDER,
            "model": GEMINI_MODEL,
            "embedding_model": GEMINI_EMBEDDING_MODEL,
            "max_tokens": GEMINI_MAX_TOKENS,
            "temperature": GEMINI_TEMPERATURE,
            "timeout": GEMINI_TIMEOUT,
        },
        "storage": {
            "upload_dir": str(UPLOAD_DIR),
            "database_url": DATABASE_URL[:25] + "..." if DATABASE_URL else "",
            "log_path": str(LOG_PATH),
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "allowed_extensions": list(ALLOWED_EXTENSIONS),
        },
        "security": {
            "cors_origins": CORS_ORIGINS,
            "chat_rate_limit": RATE_LIMIT_CHAT_LIMIT,
            "chat_rate_window": RATE_LIMIT_CHAT_WINDOW,
            "upload_rate_limit": RATE_LIMIT_UPLOAD_LIMIT,
            "upload_rate_window": RATE_LIMIT_UPLOAD_WINDOW,
            "max_query_length": MAX_QUERY_LENGTH,
            "max_filename_length": MAX_FILENAME_LENGTH,
        },
        "chunking": {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
        },
        "retrieval": {
            "top_k": TOP_K,
            "candidates_k": RETRIEVAL_CANDIDATES,
            "final_context_chunks": FINAL_CONTEXT_CHUNKS,
            "max_context_tokens": MAX_CONTEXT_TOKENS,
            "relevance_threshold": RELEVANCE_THRESHOLD,
            "strong_relevance_threshold": STRONG_RELEVANCE_THRESHOLD,
            "groundedness_threshold": GROUNDEDNESS_THRESHOLD,
            "min_rerank_score": MIN_RERANK_SCORE,
            "weights": {
                "semantic": SEMANTIC_WEIGHT,
                "lexical": LEXICAL_WEIGHT,
                "exact_boost": EXACT_BOOST_WEIGHT,
                "source": SOURCE_WEIGHT,
            },
        },
        "reranker": {
            "enabled": ENABLE_RERANKER,
            "model_name": RERANKER_MODEL,
        },
        "observability": {
            "debug_mode": DEBUG_MODE,
        },
    }
