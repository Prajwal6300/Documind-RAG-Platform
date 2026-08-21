"""Multi-stage hybrid retrieval engine for the DocuMind RAG pipeline.

Architecture:
  1. Multi-Document Search: Searches across ALL indexed documents (or scoped document).
  2. Two-Stage Candidate Retrieval:
     - Stage 1: Retrieve RETRIEVAL_CANDIDATES (e.g. 14-16) via Semantic (Supabase pgvector) + Lexical (BM25 & exact matcher).
     - Stage 2: Merge, deduplicate, score with combined hybrid formula, filter by relevance threshold.
  3. Exact Match Boosting: Prioritizes chunks containing exact names, IDs (EMP-1042), dates, amounts, codes.
  4. Document Diversity Selection: Ensures multi-document queries retrieve evidence from all relevant files.
  5. Context Expansion: Expands parent / adjacent chunks for top relevant sections.
  6. Final Selection: Selects strongest FINAL_CONTEXT_CHUNKS (e.g. 3-5) for Gemini generation.
"""

from backend.src.utils.config import (
    RETRIEVAL_CANDIDATES,
    FINAL_CONTEXT_CHUNKS,
    RELEVANCE_THRESHOLD,
    STRONG_RELEVANCE_THRESHOLD,
    KEYWORD_RESOLVE_DISTANCE,
    KEYWORD_MATCH_REQUIRED,
    SEMANTIC_WEIGHT,
    LEXICAL_WEIGHT,
    EXACT_BOOST_WEIGHT,
    SOURCE_WEIGHT,
    MAX_SUMMARY_CHUNKS,
    ENABLE_CONTEXT_EXPANSION,
    MAX_EXPANSION_CHUNKS,
    RAG_DEBUG,
)
from backend.src.vectordb.vector_store import (
    get_collection,
    get_document_chunks,
    get_all_chunks,
    get_adjacent_chunks,
    list_documents,
    query_vector_store,
)
from backend.src.vectordb.database import list_all_documents, get_document_by_id
from backend.src.embeddings.embedder import embed_query
from backend.src.utils.logger import logger
from backend.src.retrieval.lexical_search import (
    BM25Index,
    tokenize_meaningful,
    calculate_exact_match_boost,
    calculate_keyword_overlap,
)
from backend.src.retrieval.query_analyzer import (
    expand_query,
    extract_keywords,
    extract_entities,
    detect_query_intents,
)


def _semantic_score(distance: float | None) -> float:
    """Convert pgvector squared L2 distance on normalized embeddings to similarity [0..1].

    For normalized vectors u, v:
      ||u - v||^2 = 2 - 2 * cos_sim
      cos_sim = 1 - distance / 2
    """
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (float(distance) / 2.0)))


def _source_match(query_tokens: list[str], metadata: dict) -> float:
    """1.0 if any query token matches the document filename or stem."""
    if not query_tokens:
        return 0.0

    source = (metadata.get("source") or "").lower()
    if not source:
        return 0.0

    stem = source.rsplit(".", 1)[0]
    for token in query_tokens:
        tok = token.lower().strip()
        if tok and len(tok) > 2 and (tok in source or tok in stem):
            return 1.0

    return 0.0


def _flatten_analysis_terms(doc: dict) -> str:
    parts = [
        doc.get("name") or "",
        doc.get("title") or "",
        doc.get("doc_summary") or "",
        doc.get("doc_category") or "",
    ]
    for entity in doc.get("entities") or []:
        if isinstance(entity, dict):
            parts.append(str(entity.get("value") or ""))
            parts.append(str(entity.get("type") or ""))
        else:
            parts.append(str(entity))
    for section in doc.get("structure") or []:
        if isinstance(section, dict):
            parts.append(str(section.get("heading") or ""))
            parts.append(str(section.get("description") or ""))
        else:
            parts.append(str(section))
    return " ".join(parts).lower()


def _document_analysis_scores(query: str, query_tokens: list[str], entities: list[tuple[str, str]]) -> dict[str, float]:
    """Score query/document metadata affinity to reduce wrong-document retrieval."""
    try:
        docs = list_all_documents(include_archived=False)
    except Exception:
        return {}

    entity_values = [v.lower() for _t, v in (entities or []) if v]
    scores = {}
    for doc in docs:
        if doc.get("status") != "indexed":
            continue
        haystack = _flatten_analysis_terms(doc)
        if not haystack:
            continue
        token_hits = sum(1 for token in query_tokens if len(token) > 2 and token.lower() in haystack)
        token_score = min(0.60, token_hits / max(4, len(query_tokens)))
        entity_hits = sum(1 for value in entity_values if value and value in haystack)
        entity_score = min(0.80, entity_hits * 0.35)
        category_score = 0.0
        category = (doc.get("doc_category") or "").replace("_", " ")
        if category and category in query.lower():
            category_score = 0.25
        score = max(token_score, entity_score, category_score)
        if score > 0:
            scores[doc["id"]] = score
    return scores


def _hybrid_score(distance: float | None, lexical_score: float, exact_boost: float, source_match_ratio: float) -> float:
    """Compute combined hybrid relevance score in [0..1]."""
    sem = _semantic_score(distance) if distance is not None else 0.0
    return (
        SEMANTIC_WEIGHT * sem
        + LEXICAL_WEIGHT * lexical_score
        + EXACT_BOOST_WEIGHT * exact_boost
        + SOURCE_WEIGHT * source_match_ratio
    )


def _query_pgvector(query: str, top_k: int, document_id: str | None = None) -> list[dict]:
    """Run semantic search on Supabase pgvector and return candidate chunk dicts."""
    query_embedding = embed_query(query)
    if not query_embedding:
        return []
    return query_vector_store(query_embedding, top_k=top_k, document_id=document_id)



def _lexical_candidates(
    query: str,
    query_tokens: list[str],
    entities: list[tuple[str, str]],
    document_id: str | None = None,
    top_k: int = 10,
) -> list[dict]:
    """Run in-memory BM25 and exact matching across chunks."""
    if document_id:
        chunks = get_document_chunks(document_id)
    else:
        chunks = get_all_chunks()

    if not chunks:
        return []

    index = BM25Index()
    index.index_chunks(chunks)

    scored_bm25 = index.score_query(query_tokens)
    max_bm25 = max([s for _c, s in scored_bm25], default=1.0) or 1.0

    candidates = []
    for chunk, bm25_score in scored_bm25:
        norm_bm25 = min(1.0, bm25_score / max_bm25) if max_bm25 > 0 else 0.0
        exact_boost = calculate_exact_match_boost(query, entities, chunk.get("text", ""))
        kw_ratio = calculate_keyword_overlap(query_tokens, chunk.get("text", ""))

        if exact_boost >= 0.50 or (norm_bm25 >= 0.35 and kw_ratio >= 0.40):
            c = dict(chunk)
            c["distance"] = None
            c["lexical_score"] = max(norm_bm25, kw_ratio)
            c["exact_boost"] = exact_boost
            c["keyword_ratio"] = kw_ratio
            candidates.append(c)

    candidates.sort(key=lambda x: (x["exact_boost"], x["lexical_score"]), reverse=True)
    return candidates[:top_k]


import hashlib
import re


def _content_fingerprint(text: str) -> str:
    """Generate normalized fingerprint for text deduplication."""
    norm = re.sub(r"\s+", " ", (text or "")).strip().lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _retrieve_candidates(
    query: str,
    expanded_queries: list[str] | None = None,
    top_k: int | None = None,
    document_id: str | None = None,
    query_keywords: list[str] | None = None,
    entities: list[tuple[str, str]] | None = None,
) -> list[dict]:
    """Retrieve candidates across all documents using semantic and lexical search."""
    if top_k is None:
        top_k = RETRIEVAL_CANDIDATES

    candidates = {}
    fingerprint_to_key = {}

    def _merge(chunks):
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                continue

            fp = _content_fingerprint(chunk.get("text", ""))
            # Check if this exact text content is already represented under another chunk ID
            target_id = fingerprint_to_key.get(fp, chunk_id)

            if target_id not in candidates:
                candidates[target_id] = chunk
                fingerprint_to_key[fp] = target_id
            else:
                existing = candidates[target_id]
                # Keep the best (lowest) distance
                if (
                    chunk.get("distance") is not None
                    and (
                        existing.get("distance") is None
                        or chunk["distance"] < existing["distance"]
                    )
                ):
                    existing["distance"] = chunk["distance"]

                # Keep the best lexical / boost scores
                if chunk.get("lexical_score", 0) > existing.get("lexical_score", 0):
                    existing["lexical_score"] = chunk["lexical_score"]
                if chunk.get("exact_boost", 0) > existing.get("exact_boost", 0):
                    existing["exact_boost"] = chunk["exact_boost"]
                if chunk.get("keyword_ratio", 0) > existing.get("keyword_ratio", 0):
                    existing["keyword_ratio"] = chunk["keyword_ratio"]

    # Build search query list (limit to top 3 expansions)
    queries_to_search = [query]
    if expanded_queries:
        for v in expanded_queries:
            if v and v.lower() != query.lower() and v not in queries_to_search:
                queries_to_search.append(v)
    queries_to_search = queries_to_search[:3]

    # 1. Semantic search with Supabase pgvector
    for q_str in queries_to_search:
        q_emb = embed_query(q_str)
        if q_emb:
            _merge(query_vector_store(q_emb, top_k=top_k, document_id=document_id))

    # 2. Lexical BM25 & exact term search
    meaningful_tokens = tokenize_meaningful(query)
    if query_keywords:
        for kw in query_keywords:
            meaningful_tokens.extend(tokenize_meaningful(kw))
    meaningful_tokens = list(dict.fromkeys(meaningful_tokens))

    lex_candidates = _lexical_candidates(
        query=query,
        query_tokens=meaningful_tokens,
        entities=entities or [],
        document_id=document_id,
        top_k=top_k,
    )
    _merge(lex_candidates)

    return list(candidates.values())


def _select_final_with_diversity(results: list[dict], final_k: int) -> list[dict]:
    """Pick the strongest `final_k` chunks while ensuring multi-document diversity."""
    if len(results) <= final_k:
        return results

    sorted_results = sorted(
        results,
        key=lambda r: r.get("_score", 0.0),
        reverse=True,
    )

    selected = []
    seen_chunk_ids = set()
    seen_sources = set()
    seen_fingerprints = set()

    # Pass 1: Top chunk from each distinct document source
    for chunk in sorted_results:
        src = (chunk.get("metadata") or {}).get("source") or (chunk.get("metadata") or {}).get("document_id")
        fp = _content_fingerprint(chunk.get("text", ""))
        if src and src not in seen_sources and fp not in seen_fingerprints:
            selected.append(chunk)
            seen_chunk_ids.add(chunk["chunk_id"])
            seen_sources.add(src)
            seen_fingerprints.add(fp)
            if len(selected) >= final_k:
                break

    # Pass 2: Fill remaining budget with highest scoring chunks overall
    if len(selected) < final_k:
        for chunk in sorted_results:
            fp = _content_fingerprint(chunk.get("text", ""))
            if chunk["chunk_id"] not in seen_chunk_ids and fp not in seen_fingerprints:
                selected.append(chunk)
                seen_chunk_ids.add(chunk["chunk_id"])
                seen_fingerprints.add(fp)
                if len(selected) >= final_k:
                    break

    return selected


def _expand_context_for_top_chunks(top_chunks: list[dict], max_additions: int = 2) -> list[dict]:
    """Retrieve adjacent chunks for top-scoring candidates to preserve full context."""
    if not ENABLE_CONTEXT_EXPANSION or not top_chunks:
        return top_chunks

    existing_ids = {c["chunk_id"] for c in top_chunks}
    additions = []

    for chunk in top_chunks[:2]:
        meta = chunk.get("metadata") or {}
        doc_id = meta.get("document_id")
        idx = meta.get("chunk_index")

        if doc_id and idx is not None:
            adjacent = get_adjacent_chunks(doc_id, idx, window=1)
            for adj in adjacent:
                if adj["chunk_id"] not in existing_ids:
                    adj_copy = dict(adj)
                    adj_copy["distance"] = chunk.get("distance")
                    adj_copy["lexical_score"] = 0.0
                    adj_copy["exact_boost"] = 0.0
                    adj_copy["keyword_ratio"] = 0.0
                    adj_copy["source_match"] = chunk.get("source_match", 0.0)
                    adj_copy["_score"] = chunk.get("_score", 0.0) * 0.9
                    adj_copy["relevant"] = True
                    adj_copy["_is_expansion"] = True
                    additions.append(adj_copy)
                    existing_ids.add(adj["chunk_id"])
                    if len(additions) >= max_additions:
                        break
        if len(additions) >= max_additions:
            break

    return top_chunks + additions


def retrieve(
    query: str,
    top_k: int | None = None,
    relevance_threshold: float | None = None,
    document_id: str | None = None,
    expanded_queries: list[str] | None = None,
    query_keywords: list[str] | None = None,
    entities: list[tuple[str, str]] | None = None,
    final_k: int | None = None,
) -> list[dict]:
    """Retrieve, rank, score, and filter evidence chunks for a question.

    Returns a list of candidate chunk dicts or `[{"_no_relevant": True}]`.
    """
    if top_k is None:
        top_k = RETRIEVAL_CANDIDATES

    if final_k is None:
        final_k = FINAL_CONTEXT_CHUNKS

    if relevance_threshold is None:
        relevance_threshold = RELEVANCE_THRESHOLD

    if query_keywords is None:
        query_keywords = extract_keywords(query)

    if entities is None:
        entities = extract_entities(query)

    if expanded_queries is None:
        expanded_queries = expand_query(query, keywords=query_keywords, entities=entities)

    candidates = _retrieve_candidates(
        query=query,
        expanded_queries=expanded_queries,
        top_k=top_k,
        document_id=document_id,
        query_keywords=query_keywords,
        entities=entities,
    )

    if not candidates:
        if RAG_DEBUG:
            logger.debug("Query: '%s' -> 0 candidates retrieved.", query)
        return [{"_no_relevant": True}]

    query_tokens = tokenize_meaningful(query)
    if query_keywords:
        for kw in query_keywords:
            query_tokens.extend(tokenize_meaningful(kw))
    query_tokens = list(dict.fromkeys(query_tokens))
    doc_analysis_scores = {} if document_id else _document_analysis_scores(query, query_tokens, entities)

    scored = []
    for chunk in candidates:
        text = chunk.get("text", "")
        metadata = chunk.get("metadata") or {}

        kw_ratio = chunk.get("keyword_ratio")
        if kw_ratio is None:
            kw_ratio = calculate_keyword_overlap(query_tokens, text)

        exact_boost = chunk.get("exact_boost")
        if exact_boost is None:
            exact_boost = calculate_exact_match_boost(query, entities, text)

        source_match = _source_match(query_tokens, metadata)
        doc_analysis_boost = 0.0
        chunk_doc_id = metadata.get("document_id")
        if chunk_doc_id and chunk_doc_id in doc_analysis_scores:
            doc_analysis_boost = doc_analysis_scores[chunk_doc_id]
        distance = chunk.get("distance")

        lex_score = chunk.get("lexical_score")
        if lex_score is None:
            lex_score = kw_ratio if len(query_tokens) >= 2 else 0.0

        # Determine relevance gate
        if distance is None:
            # Lexical / exact match candidate
            relevant = (exact_boost >= 0.50 or (lex_score >= 0.35 and kw_ratio >= 0.40))
        else:
            # Semantic candidate
            relevant = (distance <= relevance_threshold)
            if not relevant and distance <= KEYWORD_RESOLVE_DISTANCE and (kw_ratio >= KEYWORD_MATCH_REQUIRED or exact_boost > 0.0):
                relevant = True
            if not relevant and source_match == 1.0 and distance <= KEYWORD_RESOLVE_DISTANCE:
                relevant = True

        combined_score = _hybrid_score(distance, lex_score, exact_boost, source_match)
        combined_score = min(1.0, combined_score + (0.18 * doc_analysis_boost))

        chunk["keyword_ratio"] = kw_ratio
        chunk["exact_boost"] = exact_boost
        chunk["source_match"] = source_match
        chunk["doc_analysis_boost"] = doc_analysis_boost
        chunk["lexical_score"] = lex_score
        chunk["_score"] = combined_score
        chunk["relevant"] = relevant
        scored.append(chunk)

    filtered = [c for c in scored if c["relevant"]]

    if RAG_DEBUG:
        logger.debug(
            "Query: '%s' (%d candidates, %d passed relevance gate)",
            query,
            len(candidates),
            len(filtered),
        )
        for c in sorted(scored, key=lambda x: x["_score"], reverse=True)[:8]:
            d_str = f"d={c['distance']:.3f}" if c.get("distance") is not None else "d=None"
            flag = "ok" if c.get("relevant") else "no"
            logger.debug(
                "  [%s] %s score=%.3f exact=%.2f kw=%.2f %s p=%s :: %s",
                flag,
                d_str,
                c.get("_score", 0.0),
                c.get("exact_boost", 0),
                c.get("keyword_ratio", 0),
                (c.get("metadata") or {}).get("source"),
                (c.get("metadata") or {}).get("page"),
                c.get("text", "")[:70].replace("\n", " "),
            )

    if not filtered:
        return [{"_no_relevant": True}]

    # Diverse Multi-Document Top-K Selection
    selected = _select_final_with_diversity(filtered, final_k)

    # Parent context expansion
    if ENABLE_CONTEXT_EXPANSION:
        selected = _expand_context_for_top_chunks(selected, max_additions=MAX_EXPANSION_CHUNKS)

    return selected


def retrieve_for_summary(
    document_id: str | None = None,
    summary_query: str | None = None,
    max_chunks: int | None = None,
    document_list: list[dict] | None = None,
) -> list[dict]:
    """Retrieve representative chunks across documents for broad / summary questions."""
    if max_chunks is None:
        max_chunks = MAX_SUMMARY_CHUNKS

    if summary_query is None:
        summary_query = "summarize the key points and important information"

    collection = get_collection()

    if document_id:
        chunks = get_document_chunks(document_id)
        if not chunks:
            return [{"_no_relevant": True}]
        return _representative_chunks(chunks, summary_query, max_chunks)

    if document_list is None:
        document_list = list_documents()

    if not document_list or collection.count() == 0:
        return []

    per_doc = max(1, max_chunks // max(1, len(document_list)))
    all_stored = get_all_chunks()
    doc_chunks_map = {}
    for c in all_stored:
        d_id = (c.get("metadata") or {}).get("document_id")
        if d_id:
            doc_chunks_map.setdefault(d_id, []).append(c)

    results = []
    for doc in document_list:
        doc_id = doc.get("id")
        chunks = doc_chunks_map.get(doc_id, [])
        if not chunks:
            continue
        results.extend(_representative_chunks(chunks, summary_query, per_doc))

    results = sorted(results, key=lambda r: r.get("_score", 0.0), reverse=True)
    if len(results) > max_chunks:
        results = results[:max_chunks]

    return results


def _representative_chunks(chunks: list[dict], summary_query: str, limit: int) -> list[dict]:
    """Pick semantically relevant + evenly distributed chunks across a document."""
    if len(chunks) <= limit:
        for chunk in chunks:
            chunk["keyword_ratio"] = 0.0
            chunk["exact_boost"] = 0.0
            chunk["source_match"] = 0.0
            chunk["_score"] = 0.5
            chunk["relevant"] = True
        return chunks

    for chunk in chunks:
        chunk["distance"] = None
        chunk["keyword_ratio"] = 0.0
        chunk["exact_boost"] = 0.0
        chunk["source_match"] = 0.0
        chunk["_score"] = 0.5
        chunk["relevant"] = True

    top_n = max(1, int(limit * 0.6))
    selected = chunks[:top_n]
    selected_ids = {c["chunk_id"] for c in selected}
    remaining = limit - top_n

    if remaining > 0 and len(chunks) > top_n:
        step = max(1, (len(chunks) - top_n) // remaining)
        for idx in range(top_n, len(chunks), step):
            if len(selected) >= limit:
                break
            if chunks[idx]["chunk_id"] not in selected_ids:
                selected.append(chunks[idx])
                selected_ids.add(chunks[idx]["chunk_id"])

    return selected
