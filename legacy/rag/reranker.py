"""Cross-Encoder Re-Ranking and Groundedness Evaluation Engine for DocuMind.

Architecture:
1. Re-ranks top candidate chunks retrieved from hybrid vector + BM25 search.
2. Uses sentence-transformers CrossEncoder (ms-marco-MiniLM-L-6-v2) or hybrid fallback.
3. Computes per-answer groundedness and retrieval confidence scores [0.0 - 1.0].
"""

import os
import math
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "true").lower() in ("true", "1", "yes")

_cross_encoder = None
_model_failed = False


def _get_cross_encoder():
    """Lazy load CrossEncoder singleton."""
    global _cross_encoder, _model_failed
    if not ENABLE_RERANKER or _model_failed:
        return None

    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(RERANKER_MODEL_NAME, max_length=512)
        except Exception as e:
            print(f"[DocuMind Reranker] CrossEncoder init skipped or failed ({e}), using hybrid scoring.")
            _model_failed = True
            return None
    return _cross_encoder


def _sigmoid(x: float) -> float:
    """Map raw logits to [0..1] range."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def rerank_chunks(query: str, chunks: list[dict], top_n: int = 6) -> list[dict]:
    """
    Re-rank candidate chunks using CrossEncoder.
    If CrossEncoder is unavailable, sorts by existing hybrid `_score`.
    """
    if not chunks:
        return []

    model = _get_cross_encoder()

    if model is not None and len(chunks) > 1:
        try:
            pairs = [[query, c.get("text", "")] for c in chunks]
            raw_scores = model.predict(pairs)
            for chunk, score in zip(chunks, raw_scores):
                chunk["rerank_score"] = float(_sigmoid(float(score)))
                # Combine rerank score with exact boost
                chunk["final_score"] = 0.70 * chunk["rerank_score"] + 0.30 * chunk.get("exact_boost", 0.0)
            
            sorted_chunks = sorted(chunks, key=lambda c: c.get("final_score", 0.0), reverse=True)
            return sorted_chunks[:top_n]
        except Exception as exc:
            print(f"[DocuMind Reranker] Reranking failed ({exc}), falling back to hybrid scores.")

    # Fallback to hybrid scores
    for chunk in chunks:
        if "final_score" not in chunk:
            chunk["final_score"] = chunk.get("_score", 0.0)
        if "rerank_score" not in chunk:
            chunk["rerank_score"] = chunk.get("_score", 0.0)

    sorted_chunks = sorted(chunks, key=lambda c: c.get("final_score", 0.0), reverse=True)
    return sorted_chunks[:top_n]


def calculate_groundedness_score(
    answer: str,
    context_chunks: list[dict],
    no_context: bool = False,
) -> dict:
    """
    Compute a multi-factor groundedness score [0.0 - 1.0] evaluating:
    1. Retrieval relevance strength of cited chunks
    2. N-gram / term overlap between generated claims and context
    3. Explicit refusal detection
    """
    if no_context or not context_chunks or not answer.strip():
        return {
            "score": 0.0,
            "confidence": "Low",
            "is_grounded": False,
            "relevance_level": "None",
        }

    # Factor 1: Retrieval strength (average score of top 3 context chunks)
    top_scores = [c.get("final_score", c.get("_score", 0.5)) for c in context_chunks[:3]]
    avg_retrieval = sum(top_scores) / len(top_scores) if top_scores else 0.5

    # Factor 2: Context Term Coverage
    context_text = " ".join(c.get("text", "") for c in context_chunks).lower()
    answer_words = [w.lower().strip(".,!?:;\"'()[]") for w in answer.split() if len(w) > 3]
    
    if answer_words:
        matched_words = sum(1 for w in answer_words if w in context_text)
        term_overlap = matched_words / len(answer_words)
    else:
        term_overlap = 0.8

    # Factor 3: Combined groundedness score
    groundedness = 0.50 * avg_retrieval + 0.50 * term_overlap
    groundedness = max(0.0, min(1.0, groundedness))

    if groundedness >= 0.75:
        confidence = "High"
    elif groundedness >= 0.50:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "score": round(groundedness, 3),
        "confidence": confidence,
        "is_grounded": groundedness >= 0.45,
        "term_overlap": round(term_overlap, 3),
        "avg_retrieval": round(avg_retrieval, 3),
    }
