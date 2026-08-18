"""End-to-end orchestration for the DocuMind high-accuracy RAG pipeline (Google Gemini).

Flow:
    User Question
        ↓
    Question Normalization & Understanding (Local, no LLM)
        ↓
    Multi-Document Hybrid Retrieval (Semantic ChromaDB + Lexical BM25 & Exact Boost)
        ↓
    Relevance Scoring & Filtering (ChromaDB distance + BM25 + Exact Entity Match)
        ↓
    Anti-Hallucination Sufficiency Gate (Refuse weak/irrelevant evidence early)
        ↓
    Context Expansion & Strongest Evidence Selection
        ↓
    Google Gemini Grounded Generation
        ↓
    Grounded Answer + Deduplicated (Source, Page) Citations
"""

import os
from dotenv import load_dotenv

from rag.config import (
    RETRIEVAL_CANDIDATES,
    FINAL_CONTEXT_CHUNKS,
    RELEVANCE_THRESHOLD,
    STRONG_RELEVANCE_THRESHOLD,
    RAG_DEBUG,
)
from rag.retriever import retrieve, retrieve_for_summary
from rag.llm import generate_answer, generate_answer_stream
from rag.question_analyzer import (
    classify_question,
    extract_keywords,
    extract_entities,
    expand_query,
    is_broad_question,
    resolve_follow_up,
    normalize_query_text,
    strip_question_boilerplate,
)

load_dotenv()

DEBUG_MODE = RAG_DEBUG
NO_CONTEXT_MESSAGE = "I couldn't find that information in the uploaded documents."


def _build_conversation_snippet(chat_history, max_messages=4):
    """Format compact conversation context for follow-up questions."""
    if not chat_history:
        return None

    snippet = []
    for message in chat_history[-max_messages:]:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        snippet.append(f"{label}: {content}")

    if not snippet:
        return None

    return "\n".join(snippet)


def build_citation_context(results):
    """Build structured context blocks with clear document and page boundaries."""
    context_parts = []

    for result in results:
        if "_no_relevant" in str(result):
            continue

        metadata = result.get("metadata") or {}
        source = metadata.get("source", "Unknown")
        page = metadata.get("page")
        text = result.get("text", "").strip()

        if not text:
            continue

        if page is not None and str(page).strip() and str(page).lower() != "none":
            header = f"[Document: {source} | Page: {page}]"
        else:
            header = f"[Document: {source}]"

        context_parts.append(f"{header}\n\n{text}")

    if not context_parts:
        return None

    return "\n\n---\n\n".join(context_parts)


def dedupe_display_sources(results):
    """
    Deduplicate DISPLAY sources by (source, page) while keeping every
    useful chunk internally for answer generation.
    """
    seen = {}
    ordered = []

    for result in results:
        if "_no_relevant" in str(result):
            continue

        metadata = result.get("metadata") or {}
        source = metadata.get("source", "Unknown")
        page = metadata.get("page")
        key = (source, page)

        if key in seen:
            continue

        seen[key] = True
        ordered.append({
            "source": source,
            "page": page,
            "distance": result.get("distance"),
            "text": result.get("text", ""),
            "chunk_id": result.get("chunk_id"),
        })

    return ordered


def _check_evidence_sufficiency(
    results,
    question_type,
    entities,
    keywords,
    broad=False,
):
    """Anti-hallucination gate: verify evidence strength before invoking Gemini."""
    if not results:
        return False, "no results"

    results = [r for r in results if "_no_relevant" not in str(r)]
    if not results:
        return False, "nothing passed the relevance filter"

    # Broad / summary questions: representative chunks across docs are sufficient
    if broad or question_type == "SUMMARY":
        return True, "sufficient (broad question)"

    # Specific questions: at least one candidate chunk must show strong relevance
    strong = any(
        r.get("distance") is None
        or r.get("distance", float("inf")) <= STRONG_RELEVANCE_THRESHOLD
        or (
            r.get("distance", float("inf")) <= 1.35
            and r.get("keyword_ratio", 0.0) >= 0.30
        )
        or r.get("lexical_score", 0.0) >= 0.40
        or r.get("exact_boost", 0.0) >= 0.50
        or (
            r.get("source_match", 0.0) >= 1.0
            and r.get("distance", float("inf")) <= 1.55
        )
        for r in results
    )

    if not strong:
        return False, "no chunk was strongly relevant"

    # Exact-value questions: if specific entity queried, verify its topic/terms exist in evidence
    if entities and question_type == "FACT":
        joined_evidence = " ".join(
            r.get("text", "") for r in results
        ).lower()

        # Check entity presence
        for _entity_type, value in entities:
            clean_val = value.lower().replace("-", "").replace(" ", "")
            clean_ev = joined_evidence.replace("-", "").replace(" ", "")
            if value.lower() not in joined_evidence and (len(clean_val) < 3 or clean_val not in clean_ev):
                return False, f"entity '{value}' not present in evidence"

    return True, "sufficient"


def answer_question(
    question,
    stream=False,
    document_id=None,
    chat_history=None,
    debug=None,
):
    """Answer a user question from the indexed document collection."""
    if debug is None:
        debug = RAG_DEBUG

    debug_info = {
        "question": question,
        "resolved_question": question,
        "question_type": None,
        "keywords": [],
        "entities": [],
        "expansions": [],
        "candidates": [],
        "final_chunks": [],
        "context": None,
        "sufficiency": None,
    }

    # 1. Preprocess & normalize question
    question = (question or "").strip()
    if not question:
        return {
            "answer": "Please ask a question.",
            "sources": [],
            "no_context": True,
        }

    resolved_question = resolve_follow_up(question, chat_history)

    question_type = classify_question(resolved_question)
    keywords = extract_keywords(resolved_question)
    entities = extract_entities(resolved_question)
    expansions = expand_query(
        resolved_question,
        keywords=keywords,
        entities=entities,
    )

    debug_info["resolved_question"] = resolved_question
    debug_info["question_type"] = question_type
    debug_info["keywords"] = keywords
    debug_info["entities"] = entities
    debug_info["expansions"] = expansions

    # 2. Retrieve candidates
    broad = is_broad_question(resolved_question) or question_type == "SUMMARY"

    if broad:
        results = retrieve_for_summary(
            document_id=document_id,
            summary_query=resolved_question,
        )
    else:
        results = retrieve(
            query=resolved_question,
            top_k=RETRIEVAL_CANDIDATES,
            relevance_threshold=RELEVANCE_THRESHOLD,
            document_id=document_id,
            expanded_queries=expansions,
            query_keywords=keywords,
            entities=entities,
            final_k=FINAL_CONTEXT_CHUNKS,
        )

    debug_info["candidates"] = [
        {
            "chunk_id": r.get("chunk_id"),
            "source": (r.get("metadata") or {}).get("source"),
            "page": (r.get("metadata") or {}).get("page"),
            "distance": r.get("distance"),
            "lexical_score": r.get("lexical_score"),
            "exact_boost": r.get("exact_boost"),
            "keyword_ratio": r.get("keyword_ratio"),
            "_score": r.get("_score"),
            "relevant": r.get("relevant"),
            "text": r.get("text", "")[:180],
        }
        for r in results
        if "_no_relevant" not in str(r)
    ]

    # 3. Evidence sufficiency gate
    sufficient, reason = _check_evidence_sufficiency(
        results,
        question_type,
        entities,
        keywords,
        broad=broad,
    )

    debug_info["sufficiency"] = {"ok": sufficient, "reason": reason}

    if not sufficient:
        if RAG_DEBUG:
            print(f"[RAG_DEBUG] Evidence insufficient for '{question}': {reason}")
        return {
            "answer": NO_CONTEXT_MESSAGE,
            "sources": [],
            "no_context": True,
            "debug": debug_info if debug else None,
        }

    # 4. Final context selection & context formatting
    final_results = [r for r in results if "_no_relevant" not in str(r)]

    if not broad and len(final_results) > FINAL_CONTEXT_CHUNKS:
        final_results = sorted(
            final_results,
            key=lambda r: r.get("_score", 0.0),
            reverse=True,
        )[:FINAL_CONTEXT_CHUNKS]

    context = build_citation_context(final_results)

    if context is None:
        return {
            "answer": NO_CONTEXT_MESSAGE,
            "sources": [],
            "no_context": True,
            "debug": debug_info if debug else None,
        }

    debug_info["final_chunks"] = [
        {
            "chunk_id": r.get("chunk_id"),
            "source": (r.get("metadata") or {}).get("source"),
            "page": (r.get("metadata") or {}).get("page"),
            "distance": r.get("distance"),
            "keyword_ratio": r.get("keyword_ratio"),
            "_score": r.get("_score"),
        }
        for r in final_results
    ]
    debug_info["context"] = context

    sources = dedupe_display_sources(final_results)
    conversation = _build_conversation_snippet(chat_history)

    # 5. Call Gemini for grounded generation
    llm_question = question

    if stream:
        return {
            "answer": "",
            "answer_stream": generate_answer_stream(
                llm_question,
                context,
                conversation=conversation,
            ),
            "sources": sources,
            "no_context": False,
            "debug": debug_info if debug else None,
        }

    answer = generate_answer(
        llm_question,
        context,
        conversation=conversation,
    )

    return {
        "answer": answer,
        "sources": sources,
        "no_context": False,
        "debug": debug_info if debug else None,
    }