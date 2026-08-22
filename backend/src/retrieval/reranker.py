import hashlib
import math
import re
import os
from backend.src.utils.config import ENABLE_RERANKER, RERANKER_MODEL, GROUNDEDNESS_THRESHOLD
from backend.src.utils.logger import logger

_cross_encoder = None
_model_failed = False


def _content_fingerprint(text: str) -> str:
    """Generate normalized fingerprint for text deduplication."""
    norm = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _load_cross_encoder():
    """Load CrossEncoder model at startup."""
    global _cross_encoder, _model_failed
    if not ENABLE_RERANKER or _model_failed:
        return None

    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(
            RERANKER_MODEL,
            max_length=512,
            token=os.getenv("HF_TOKEN", "").strip() or None,
        )
        logger.info("CrossEncoder model loaded at startup: %s", RERANKER_MODEL)
        return _cross_encoder
    except Exception as e:
        logger.warning("CrossEncoder init skipped or failed (%s), using hybrid scoring.", e)
        _model_failed = True
        return None


def _sigmoid(x: float) -> float:
    """Map raw logits to [0..1] range."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def rerank_chunks(query: str, chunks: list[dict], top_n: int = 6) -> list[dict]:
    """
    Re-rank candidate chunks using CrossEncoder.
    Deduplicates candidates by text content fingerprint to prevent duplicate citations.
    If CrossEncoder is unavailable, sorts by existing hybrid `_score`.
    """
    if not chunks:
        return []

    # Deduplicate candidates by text fingerprint preserving the highest existing score
    deduped_chunks = []
    seen_fingerprints = set()
    for chunk in chunks:
        fp = _content_fingerprint(chunk.get("text", ""))
        if fp not in seen_fingerprints:
            seen_fingerprints.add(fp)
            deduped_chunks.append(chunk)

    chunks = deduped_chunks
    model = _cross_encoder

    if model is not None and len(chunks) > 1:
        try:
            pairs = [[query, c.get("text", "")] for c in chunks]
            raw_scores = model.predict(pairs)
            for chunk, score in zip(chunks, raw_scores):
                chunk["rerank_score"] = float(_sigmoid(float(score)))
                # Combine rerank score with exact boost and hybrid retrieval score
                chunk["final_score"] = (
                    0.50 * chunk["rerank_score"]
                    + 0.25 * chunk.get("exact_boost", 0.0)
                    + 0.25 * chunk.get("_score", 0.0)
                )

            sorted_chunks = sorted(chunks, key=lambda c: c.get("final_score", 0.0), reverse=True)
            return sorted_chunks[:top_n]
        except Exception as exc:
            logger.warning("Reranking failed (%s), falling back to hybrid scores.", exc)

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
    if no_context or not context_chunks or not answer or not answer.strip():
        return {
            "score": 0.0,
            "confidence": "Low",
            "is_grounded": False,
            "relevance_level": "None",
            "term_overlap": 0.0,
            "avg_retrieval": 0.0,
        }

    # Explicit refusal detection
    clean_ans = answer.lower()
    refusal_patterns = [
        "couldn't find that information",
        "could not find that information",
        "not mentioned in the provided",
        "not mentioned in the uploaded",
        "not found in your uploaded",
        "not found in the provided",
        "no information provided in the uploaded",
        "does not contain information",
        "cannot answer based on the provided",
    ]
    if any(p in clean_ans for p in refusal_patterns):
        return {
            "score": 0.0,
            "confidence": "Low",
            "is_grounded": False,
            "relevance_level": "Refusal",
            "term_overlap": 0.0,
            "avg_retrieval": 0.0,
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
    if avg_retrieval < 0.25:
        groundedness = min(0.50 * avg_retrieval + 0.50 * term_overlap, avg_retrieval * 1.5)
    else:
        groundedness = 0.50 * avg_retrieval + 0.50 * term_overlap

    groundedness = max(0.0, min(1.0, groundedness))

    is_grounded = (groundedness >= 0.55) and (avg_retrieval >= 0.20)

    if groundedness >= 0.70:
        confidence = "High"
    elif groundedness >= 0.45:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "score": round(groundedness, 3),
        "confidence": confidence,
        "is_grounded": is_grounded,
        "term_overlap": round(term_overlap, 3),
        "avg_retrieval": round(avg_retrieval, 3),
    }