"""Multi-stage hybrid retrieval engine for the DocuMind RAG pipeline.

Architecture:
  1. Multi-Document Search: Searches across ALL indexed documents (or scoped document).
  2. Two-Stage Candidate Retrieval:
     - Stage 1: Retrieve RETRIEVAL_CANDIDATES (e.g. 14-16) via Semantic (ChromaDB) + Lexical (BM25 & exact matcher).
     - Stage 2: Merge, deduplicate, score with combined hybrid formula, filter by relevance threshold.
  3. Exact Match Boosting: Prioritizes chunks containing exact names, IDs (EMP-1042), dates, amounts, codes.
  4. Document Diversity Selection: Ensures multi-document queries retrieve evidence from all relevant files.
  5. Context Expansion: Expands parent / adjacent chunks for top relevant sections.
  6. Final Selection: Selects strongest FINAL_CONTEXT_CHUNKS (e.g. 3-5) for Gemini generation.
"""

import os
import sys

from rag.config import (
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
from rag.vector_store import (
    get_collection,
    get_document_chunks,
    get_all_chunks,
    get_adjacent_chunks,
    list_documents,
)
from rag.embeddings import embed_query
from rag.lexical_search import (
    BM25Index,
    tokenize_meaningful,
    calculate_exact_match_boost,
    calculate_keyword_overlap,
)
from rag.question_analyzer import (
    expand_query,
    extract_keywords,
    extract_entities,
    detect_query_intents,
)


def _semantic_score(distance):
    """Convert ChromaDB squared L2 distance on normalized embeddings to similarity [0..1].

    For normalized vectors u, v:
      ||u - v||^2 = 2 - 2 * cos_sim
      cos_sim = 1 - distance / 2
    """
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (float(distance) / 2.0)))


def _source_match(query_tokens, metadata):
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


def _hybrid_score(distance, lexical_score, exact_boost, source_match_ratio):
    """Compute combined hybrid relevance score in [0..1]."""
    sem = _semantic_score(distance) if distance is not None else 0.0
    return (
        SEMANTIC_WEIGHT * sem
        + LEXICAL_WEIGHT * lexical_score
        + EXACT_BOOST_WEIGHT * exact_boost
        + SOURCE_WEIGHT * source_match_ratio
    )


def _query_chroma(query, top_k, document_id=None):
    """Run semantic search on ChromaDB and return candidate chunk dicts."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_query(query)
    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
    }

    if document_id:
        query_params["where"] = {"document_id": document_id}

    results = collection.query(**query_params)

    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []
    ids = results.get("ids", [[]])[0] or []

    chunks = []
    for chunk_id, document, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        if not document:
            continue
        chunks.append({
            "chunk_id": chunk_id or (metadata or {}).get("chunk_id"),
            "text": document,
            "metadata": metadata or {},
            "distance": distance,
        })

    return chunks


def _lexical_candidates(query, query_tokens, entities, document_id=None, top_k=10):
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


def _retrieve_candidates(
    query,
    expanded_queries=None,
    top_k=None,
    document_id=None,
    query_keywords=None,
    entities=None,
):
    """Retrieve candidates across all documents using semantic and lexical search."""
    if top_k is None:
        top_k = RETRIEVAL_CANDIDATES

    candidates = {}

    def _merge(chunks):
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                continue

            if chunk_id not in candidates:
                candidates[chunk_id] = chunk
            else:
                existing = candidates[chunk_id]
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

    # Build search query list
    all_docs = list_documents()
    queries_to_search = [query]
    if expanded_queries:
        for v in expanded_queries:
            if v and v.lower() != query.lower() and v not in queries_to_search:
                queries_to_search.append(v)

    # 1. Multi-document semantic search
    if document_id:
        for q_str in queries_to_search:
            _merge(_query_chroma(q_str, top_k, document_id))
    else:
        if all_docs:
            per_doc = max(2, top_k // max(1, len(all_docs)))
            for doc in all_docs:
                doc_id = doc.get("id")
                if doc_id:
                    for q_str in queries_to_search:
                        _merge(_query_chroma(q_str, per_doc, doc_id))
        else:
            for q_str in queries_to_search:
                _merge(_query_chroma(q_str, top_k))

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


def _select_final_with_diversity(results, final_k):
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
    seen_doc_ids = set()

    # Pass 1: Top chunk from each distinct document
    for chunk in sorted_results:
        doc_id = (chunk.get("metadata") or {}).get("document_id") or (chunk.get("metadata") or {}).get("source")
        if doc_id and doc_id not in seen_doc_ids:
            selected.append(chunk)
            seen_chunk_ids.add(chunk["chunk_id"])
            seen_doc_ids.add(doc_id)
            if len(selected) >= final_k:
                break

    # Pass 2: Fill remaining budget with highest scoring chunks overall
    if len(selected) < final_k:
        for chunk in sorted_results:
            if chunk["chunk_id"] not in seen_chunk_ids:
                selected.append(chunk)
                seen_chunk_ids.add(chunk["chunk_id"])
                if len(selected) >= final_k:
                    break

    return selected


def _expand_context_for_top_chunks(top_chunks, max_additions=2):
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
    query,
    top_k=None,
    relevance_threshold=None,
    document_id=None,
    expanded_queries=None,
    query_keywords=None,
    entities=None,
    final_k=None,
):
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
            print(f"[RAG_DEBUG] Query: '{query}' -> 0 candidates retrieved.")
        return [{"_no_relevant": True}]

    query_tokens = tokenize_meaningful(query)
    if query_keywords:
        for kw in query_keywords:
            query_tokens.extend(tokenize_meaningful(kw))
    query_tokens = list(dict.fromkeys(query_tokens))

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

        chunk["keyword_ratio"] = kw_ratio
        chunk["exact_boost"] = exact_boost
        chunk["source_match"] = source_match
        chunk["lexical_score"] = lex_score
        chunk["_score"] = combined_score
        chunk["relevant"] = relevant
        scored.append(chunk)

    filtered = [c for c in scored if c["relevant"]]

    if RAG_DEBUG:
        print(f"[RAG_DEBUG] Query: '{query}' ({len(candidates)} candidates, {len(filtered)} passed relevance gate)")
        for c in sorted(scored, key=lambda x: x["_score"], reverse=True)[:8]:
            d_str = f"d={c['distance']:.3f}" if c.get("distance") is not None else "d=None"
            flag = "✓" if c.get("relevant") else "✗"
            print(f"  {flag} {d_str} score={c['_score']:.3f} exact={c.get('exact_boost', 0):.2f} kw={c.get('keyword_ratio', 0):.2f} "
                  f"{(c.get('metadata') or {}).get('source')} p={(c.get('metadata') or {}).get('page')} :: {c.get('text', '')[:70].replace(chr(10), ' ')}")

    if not filtered:
        return [{"_no_relevant": True}]

    # Diverse Multi-Document Top-K Selection
    selected = _select_final_with_diversity(filtered, final_k)

    # Parent context expansion
    if ENABLE_CONTEXT_EXPANSION:
        selected = _expand_context_for_top_chunks(selected, max_additions=MAX_EXPANSION_CHUNKS)

    return selected


def retrieve_for_summary(
    document_id=None,
    summary_query=None,
    max_chunks=None,
    document_list=None,
):
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
    results = []

    for doc in document_list:
        doc_id = doc.get("id")
        if not doc_id:
            continue
        chunks = get_document_chunks(doc_id)
        if not chunks:
            continue
        results.extend(_representative_chunks(chunks, summary_query, per_doc))

    results = sorted(results, key=lambda r: r.get("_score", 0.0), reverse=True)
    if len(results) > max_chunks:
        results = results[:max_chunks]

    return results


def _representative_chunks(chunks, summary_query, limit):
    """Pick semantically relevant + evenly distributed chunks across a document."""
    if len(chunks) <= limit:
        for chunk in chunks:
            chunk["keyword_ratio"] = 0.0
            chunk["exact_boost"] = 0.0
            chunk["source_match"] = 0.0
            chunk["_score"] = 0.5
            chunk["relevant"] = True
        return chunks

    query_embedding = embed_query(summary_query)
    model = None
    try:
        from rag.embeddings import get_model
        model = get_model()
    except Exception:
        model = None

    scored = []
    for chunk in chunks:
        text = chunk["text"]
        distance = None
        if model is not None:
            try:
                vec = model.encode([text], normalize_embeddings=True)[0]
                import numpy as np
                q = np.asarray(query_embedding)
                v = np.asarray(vec)
                cosine = float(np.dot(q, v))
                distance = 2.0 * (1.0 - cosine)
            except Exception:
                distance = None

        sem = _semantic_score(distance) if distance is not None else 0.5
        chunk["distance"] = distance
        chunk["keyword_ratio"] = 0.0
        chunk["exact_boost"] = 0.0
        chunk["source_match"] = 0.0
        chunk["_score"] = sem
        chunk["relevant"] = True
        scored.append(chunk)

    scored.sort(key=lambda r: r["_score"], reverse=True)
    top_n = max(1, int(limit * 0.6))

    if len(scored) <= top_n:
        return scored

    selected = scored[:top_n]
    selected_ids = {c["chunk_id"] for c in selected}
    remaining = limit - top_n

    if remaining > 0 and len(scored) > top_n:
        step = max(1, (len(scored) - top_n) // remaining)
        for idx in range(top_n, len(scored), step):
            if len(selected) >= limit:
                break
            if scored[idx]["chunk_id"] not in selected_ids:
                selected.append(scored[idx])
                selected_ids.add(scored[idx]["chunk_id"])

    return selected
