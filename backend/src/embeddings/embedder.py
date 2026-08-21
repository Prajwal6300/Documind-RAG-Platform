"""Embedding generation for DocuMind.

Supports:
- Google Gemini Embeddings (gemini-embedding-001, 3072 dim) via google-genai SDK
- Local SentenceTransformer fallback (all-MiniLM-L6-v2) for offline/backup operation
- L2 vector normalization for consistent cosine distance metrics
"""

import os
import math
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

# Multi-threading safeguards on Windows
for _threading_var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_threading_var, "1")
del _threading_var

from backend.src.utils.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_TIMEOUT,
    LLM_PROVIDER,
)
from backend.src.utils.logger import logger

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", LLM_PROVIDER).strip().lower()
LOCAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_gemini_client = None
_local_model = None


def _normalize_vector(vec: list[float]) -> list[float]:
    """Normalize vector to unit length."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-12:
        return vec
    return [x / norm for x in vec]


def _get_gemini_client():
    global _gemini_client
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not api_key or api_key in ("YOUR_GEMINI_API_KEY_HERE", "YOUR_API_KEY_HERE", "your_actual_gemini_api_key"):
        return None
    if _gemini_client is None:
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=api_key)
        except Exception as e:
            logger.error("Failed to init Gemini embeddings client: %s", e)
            return None
    return _gemini_client


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(LOCAL_MODEL_NAME)
    return _local_model


def embed_documents(documents: list[str]) -> list[list[float]]:
    """Generate normalized embeddings for a list of document chunks."""
    if not documents:
        return []

    client = _get_gemini_client() if EMBEDDING_PROVIDER == "gemini" else None

    if client is not None:
        try:
            embeddings = []
            # Batch in chunks of 50 to respect API payload limits
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]
                # Filter empty strings
                clean_batch = [t if t.strip() else " " for t in batch]
                response = client.models.embed_content(
                    model=GEMINI_EMBEDDING_MODEL,
                    contents=clean_batch,
                    config={"http_options": {"timeout": int(float(GEMINI_TIMEOUT) * 1000)}},
                )
                for emb in response.embeddings:
                    embeddings.append(_normalize_vector(emb.values))
            return embeddings
        except Exception as exc:
            logger.warning("Gemini embed failed (%s), falling back to local model.", exc)

    # Fallback to SentenceTransformer
    local = _get_local_model()
    raw = local.encode(documents, normalize_embeddings=True)
    return raw.tolist()


ZERO_EMBEDDING = tuple([0.0] * 3072)

@lru_cache(maxsize=512)
def _embed_query_cached(query: str) -> tuple[float, ...]:
    """Internal cached implementation of query embedding."""
    client = _get_gemini_client() if EMBEDDING_PROVIDER == "gemini" else None

    if client is not None:
        try:
            response = client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=query,
                config={"http_options": {"timeout": int(float(GEMINI_TIMEOUT) * 1000)}},
            )
            if response.embeddings:
                return tuple(_normalize_vector(response.embeddings[0].values))
        except Exception as exc:
            if EMBEDDING_PROVIDER == "gemini":
                logger.warning("Gemini query embed failed (%s), using zero embedding fallback.", exc)
                return ZERO_EMBEDDING
            logger.warning("Gemini query embed failed (%s), falling back to local.", exc)

    local = _get_local_model()
    raw = local.encode(query, normalize_embeddings=True)
    return tuple(raw.tolist())


def embed_query(query: str) -> list[float]:
    """Generate normalized embedding for a search query string."""
    if not query or not query.strip():
        return []
    return list(_embed_query_cached(query.strip()))

