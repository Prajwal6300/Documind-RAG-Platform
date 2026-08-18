"""Central configuration for the DocuMind RAG pipeline (Google Gemini only).

All tunable values are read from the environment (`.env`) with sane defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# --- LLM Provider Settings --------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip()

# --- Google Gemini Settings -------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_MAX_TOKENS = _int("GEMINI_MAX_TOKENS", 4096)
GEMINI_TEMPERATURE = _float("GEMINI_TEMPERATURE", 0.1)
GEMINI_TIMEOUT = _int("GEMINI_TIMEOUT", 120)

# --- Context Budget & RAG Settings ------------------------------------------
TOP_K = _int("TOP_K", 5)
MAX_CONTEXT_TOKENS = _int("MAX_CONTEXT_TOKENS", 4000)

# --- Retrieval Tuning (Two-Stage Strategy) -----------------------------------
# Stage 1: Candidate retrieval count before ranking & filtering
RETRIEVAL_CANDIDATES = _int("RETRIEVAL_CANDIDATES", _int("INITIAL_RETRIEVAL_K", 14))
INITIAL_RETRIEVAL_K = RETRIEVAL_CANDIDATES

# Stage 2: Final strongest context chunks passed to Gemini
FINAL_CONTEXT_CHUNKS = _int("FINAL_CONTEXT_CHUNKS", _int("FINAL_CONTEXT_K", 5))
FINAL_CONTEXT_K = FINAL_CONTEXT_CHUNKS

# ChromaDB distance threshold. With default (l2) metric on normalized
# embeddings: cos_sim = 1 - distance/2. Distance <= 1.48 means cos_sim >= 0.26.
RELEVANCE_THRESHOLD = _float("RELEVANCE_THRESHOLD", 1.48)

# Distance below which a chunk is considered clearly relevant.
STRONG_RELEVANCE_THRESHOLD = _float("STRONG_RELEVANCE_THRESHOLD", 1.20)

# Keyword match score required for a chunk to be admitted when its distance
# sits between RELEVANCE_THRESHOLD and the keyword rescue limit.
KEYWORD_RESOLVE_DISTANCE = _float("KEYWORD_RESOLVE_DISTANCE", 1.62)
KEYWORD_MATCH_REQUIRED = _float("KEYWORD_MATCH_REQUIRED", 0.30)

# Weights for hybrid ranking: semantic similarity + lexical BM25/keyword +
# exact match boost + source-filename match.
SEMANTIC_WEIGHT = _float("SEMANTIC_WEIGHT", 0.50)
LEXICAL_WEIGHT = _float("LEXICAL_WEIGHT", 0.30)
EXACT_BOOST_WEIGHT = _float("EXACT_BOOST_WEIGHT", 0.20)
KEYWORD_WEIGHT = LEXICAL_WEIGHT  # Backward compatibility alias
SOURCE_WEIGHT = _float("SOURCE_WEIGHT", 0.10)

# --- Context Expansion (Parent / Neighbor Chunks) ---------------------------
ENABLE_CONTEXT_EXPANSION = _bool("ENABLE_CONTEXT_EXPANSION", True)
MAX_EXPANSION_CHUNKS = _int("MAX_EXPANSION_CHUNKS", 2)

# --- Chunking Settings ------------------------------------------------------
CHUNK_SIZE = _int("CHUNK_SIZE", 650)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 100)

# --- Broad / Summary Questions ----------------------------------------------
MAX_SUMMARY_CHUNKS = _int("MAX_SUMMARY_CHUNKS", 10)

# --- Debug & Logging --------------------------------------------------------
RAG_DEBUG = _bool("RAG_DEBUG", _bool("DEBUG_MODE", False))
DEBUG_MODE = RAG_DEBUG
