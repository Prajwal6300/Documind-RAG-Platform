"""End-to-end orchestration for the DocuMind high-accuracy RAG pipeline (Google Gemini).

Flow:
    User Question
        ↓
    Query Rewriting & Context Resolution (Resolves follow-ups into standalone queries)
        ↓
    Multi-Document Hybrid Candidate Retrieval (pgvector Vector + BM25 Lexical + Exact Boost)
        ↓
    Cross-Encoder Re-Ranking (sentence-transformers / hybrid scoring)
        ↓
    Anti-Hallucination Sufficiency Gate (Refuse weak/irrelevant evidence early)
        ↓
    Google Gemini Grounded Generation (Strict document-grounded system instruction)
        ↓
    Structured Citations, Evidences, Groundedness Score & Observability Tracing
"""

import os
import re
import time
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv

from backend.src.utils.config import (
    RETRIEVAL_CANDIDATES,
    FINAL_CONTEXT_CHUNKS,
    RELEVANCE_THRESHOLD,
    STRONG_RELEVANCE_THRESHOLD,
    RAG_DEBUG,
    GROUNDEDNESS_THRESHOLD,
)
from backend.src.prompts.prompt_templates import (
    NO_CONTEXT_MESSAGE,
    build_conversation_snippet,
    build_citation_context,
)
from backend.src.retrieval import (
    retrieve,
    retrieve_for_summary,
    rerank_chunks,
    calculate_groundedness_score,
    classify_question,
    extract_keywords,
    extract_entities,
    expand_query,
    is_broad_question,
    resolve_follow_up,
)
from backend.src.llm import generate_answer
from backend.src.utils.logger import log_pipeline_event

load_dotenv()

DEBUG_MODE = RAG_DEBUG


def _check_evidence_sufficiency(
    results: list[dict],
    question_type: str,
    entities: list[tuple[str, str]],
    keywords: list[str],
    broad: bool = False,
) -> tuple[bool, str]:
    """Anti-hallucination gate: verify evidence strength before invoking Gemini."""
    if not results:
        return False, "no results"

    valid = [r for r in results if "_no_relevant" not in str(r)]
    if not valid:
        return False, "nothing passed the relevance filter"

    if broad or question_type == "SUMMARY":
        return True, "sufficient (broad question)"

    # At least one candidate chunk must show strong relevance, rerank score, or good keyword match
    strong = any(
        r.get("distance") is None
        or r.get("distance", float("inf")) <= STRONG_RELEVANCE_THRESHOLD
        or r.get("rerank_score", 0.0) >= 0.40
        or (
            r.get("distance", float("inf")) <= 1.35
            and r.get("keyword_ratio", 0.0) >= 0.25
        )
        or r.get("lexical_score", 0.0) >= 0.35
        or r.get("exact_boost", 0.0) >= 0.40
        or (
            r.get("source_match", 0.0) >= 1.0
            and r.get("distance", float("inf")) <= 1.55
        )
        for r in valid
    )

    if not strong:
        return False, "no chunk was strongly relevant"

    if entities and question_type == "FACT":
        joined_evidence = " ".join(r.get("text", "") for r in valid).lower()
        for _entity_type, value in entities:
            clean_val = value.lower().replace("-", "").replace(" ", "")
            clean_ev = joined_evidence.replace("-", "").replace(" ", "")
            if value.lower() not in joined_evidence and (len(clean_val) < 3 or clean_val not in clean_ev):
                return False, f"entity '{value}' not present in evidence"

    return True, "sufficient"


def _build_evidences_and_sources(final_results: list[dict]) -> tuple[list[dict], list[dict]]:
    """Create structured evidences list and deduplicated sources list."""
    evidences = []
    sources = []
    seen_sources = set()
    seen_evidence = set()

    for idx, r in enumerate(final_results):
        metadata = r.get("metadata") or {}
        source = metadata.get("source", "Unknown Document")
        page = metadata.get("page")
        if page is None or str(page).lower() == "none" or str(page).strip() == "":
            page = 1
        else:
            try:
                page = int(page)
            except Exception:
                page = str(page)

        ev_id = f"ev-{idx + 1}"
        text_quote = r.get("text", "").strip()
        evidence_key = (source, page, re.sub(r"\s+", " ", text_quote).lower())
        if evidence_key in seen_evidence:
            continue
        seen_evidence.add(evidence_key)
        if len(text_quote) > 350:
            text_quote = text_quote[:347] + "..."

        evidences.append({
            "id": ev_id,
            "docName": source,
            "page": page,
            "quote": text_quote,
        })

        src_key = (source, page)
        if src_key not in seen_sources:
            seen_sources.add(src_key)
            sources.append({
                "source": source,
                "name": source,
                "page": page,
                "evidenceId": ev_id,
            })

    return evidences, sources


def _refusal_result(groundedness: dict | None = None, debug_payload: dict | None = None) -> dict:
    """Return the single safe response shape used by every refusal path."""
    return {
        "answer": NO_CONTEXT_MESSAGE,
        "intro": NO_CONTEXT_MESSAGE,
        "sections": [],
        "sources": [],
        "evidences": [],
        "no_context": True,
        "groundedness": groundedness or {"score": 0.0, "confidence": "Low", "is_grounded": False},
        "debug": debug_payload,
    }


def _parse_answer_structure(raw_text: str, evidences: list[dict], sources: list[dict]) -> dict:
    """Parse raw markdown answer into intro, sections, and structured items with real citations."""
    if not raw_text or NO_CONTEXT_MESSAGE.lower() in raw_text.lower():
        return {
            "intro": NO_CONTEXT_MESSAGE,
            "sections": [],
            "sources": [],
            "evidences": [],
        }

    lines = raw_text.strip().split("\n")
    intro_lines = []
    sections = []
    current_section = None
    parsing_intro = True

    def match_evidence(doc_name, page_num):
        for ev in evidences:
            if doc_name and doc_name.lower() in ev["docName"].lower():
                if page_num is None or str(ev["page"]) == str(page_num):
                    return ev
        if evidences:
            return evidences[0]
        return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Check for section heading
        heading_match = re.match(r"^(?:#{1,4}\s+|\*\*)([^*#]+)(?:\*\*|:)?$", line)
        if heading_match and len(line) < 80:
            parsing_intro = False
            heading_title = heading_match.group(1).strip()
            current_section = {
                "heading": heading_title,
                "items": []
            }
            sections.append(current_section)
            continue

        # Check for bullet / list item
        item_match = re.match(r"^[-*•]\s+(?:\*\*(.*?)\*\*:?\s*|(.*?):\s+)?(.*)$", line)
        if item_match and (current_section is not None or not parsing_intro):
            title = (item_match.group(1) or item_match.group(2) or "").strip()
            desc = (item_match.group(3) or "").strip()

            if not title:
                parts = desc.split(".", 1)
                if len(parts) > 1 and len(parts[0]) < 50:
                    title = parts[0].strip()
                    desc = parts[1].strip()
                else:
                    title = "Key Point"

            citation_obj = None
            cite_match = re.search(r"\[(?:Document:\s*)?([^|\]]+)(?:\s*\|\s*Page:\s*(\d+))?\]", desc)
            if cite_match:
                doc_name = cite_match.group(1).strip()
                page_num = cite_match.group(2)
                ev = match_evidence(doc_name, page_num)
                if ev:
                    ext = Path(ev["docName"]).suffix.upper().replace(".", "") or "DOC"
                    citation_obj = {
                        "label": f"[ {ext} · Page {ev['page']} ]",
                        "docName": ev["docName"],
                        "page": ev["page"],
                        "evidenceId": ev["id"]
                    }
                desc = re.sub(r"\[(?:Document:\s*)?[^|\]]+(?:\s*\|\s*Page:\s*\d+)?\]", "", desc).strip()
            elif evidences:
                ev = evidences[min(len(current_section["items"] if current_section else 0), len(evidences) - 1)]
                ext = Path(ev["docName"]).suffix.upper().replace(".", "") or "DOC"
                citation_obj = {
                    "label": f"[ {ext} · Page {ev['page']} ]",
                    "docName": ev["docName"],
                    "page": ev["page"],
                    "evidenceId": ev["id"]
                }

            if current_section is None:
                current_section = {"heading": "Key Information", "items": []}
                sections.append(current_section)

            current_section["items"].append({
                "title": title,
                "description": desc,
                "citation": citation_obj
            })
            continue

        if parsing_intro:
            intro_lines.append(line)
        else:
            if current_section and current_section["items"]:
                current_section["items"][-1]["description"] += " " + line
            elif current_section:
                current_section["items"].append({
                    "title": "Detail",
                    "description": line,
                    "citation": None
                })

    intro_text = "\n\n".join(intro_lines).strip()
    if not intro_text and not sections:
        intro_text = raw_text.strip()

    return {
        "intro": intro_text,
        "sections": sections,
        "sources": sources,
        "evidences": evidences,
    }


def answer_question(
    question: str,
    stream: bool = False,
    document_id: str | None = None,
    chat_history: list[dict] | None = None,
    debug: bool | None = None,
) -> dict:
    """Answer a user question from the indexed document collection with advanced re-ranking and telemetry."""
    start_time = time.time()
    if debug is None:
        debug = RAG_DEBUG

    question = (question or "").strip()
    if not question:
        return {
            "answer": "Please ask a question about your documents.",
            "intro": "Please ask a question about your documents.",
            "sections": [],
            "sources": [],
            "evidences": [],
            "no_context": True,
            "groundedness": {"score": 0.0, "confidence": "Low"},
        }

    # 1. Query Normalization & Context Resolution
    resolved_question = resolve_follow_up(question, chat_history)
    question_type = classify_question(resolved_question)
    keywords = extract_keywords(resolved_question)
    entities = extract_entities(resolved_question)
    expansions = expand_query(resolved_question, keywords=keywords, entities=entities)

    log_pipeline_event("query", {
        "original_query": question,
        "resolved_query": resolved_question,
        "question_type": question_type,
        "keywords": keywords,
        "entities": entities,
    })

    # 2. Candidate Retrieval
    broad = is_broad_question(resolved_question) or question_type == "SUMMARY"

    if broad:
        raw_candidates = retrieve_for_summary(
            document_id=document_id,
            summary_query=resolved_question,
        )
    else:
        raw_candidates = retrieve(
            query=resolved_question,
            top_k=RETRIEVAL_CANDIDATES,
            relevance_threshold=RELEVANCE_THRESHOLD,
            document_id=document_id,
            expanded_queries=expansions,
            query_keywords=keywords,
            entities=entities,
            final_k=RETRIEVAL_CANDIDATES,
        )

    log_pipeline_event("retrieve", {
        "candidate_count": len(raw_candidates),
        "broad": broad,
    })

    # 3. Cross-Encoder Re-Ranking
    valid_candidates = [r for r in raw_candidates if "_no_relevant" not in str(r)]
    reranked = rerank_chunks(resolved_question, valid_candidates, top_n=FINAL_CONTEXT_CHUNKS)

    log_pipeline_event("rerank", {
        "top_chunks": len(reranked),
        "scores": [round(c.get("final_score", 0.0), 3) for c in reranked[:3]],
    })

    # 4. Anti-Hallucination Sufficiency Gate
    sufficient, reason = _check_evidence_sufficiency(
        reranked,
        question_type,
        entities,
        keywords,
        broad=broad,
    )

    log_pipeline_event("sufficiency_check", {
        "sufficient": sufficient,
        "reason": reason,
    })

    if not sufficient:
        log_pipeline_event("refusal", {
            "query": question,
            "reason": reason,
        })
        return {
            "answer": NO_CONTEXT_MESSAGE,
            "intro": NO_CONTEXT_MESSAGE,
            "sections": [],
            "sources": [],
            "evidences": [],
            "no_context": True,
            "groundedness": {"score": 0.0, "confidence": "Low", "is_grounded": False},
            "debug": {
                "resolved_query": resolved_question,
                "candidate_count": len(valid_candidates),
                "sufficiency": False,
                "reason": reason,
                "latency_ms": round((time.time() - start_time) * 1000, 1),
            } if debug else None,
        }

    context = build_citation_context(reranked)

    if context is None:
        return {
            "answer": NO_CONTEXT_MESSAGE,
            "intro": NO_CONTEXT_MESSAGE,
            "sections": [],
            "sources": [],
            "evidences": [],
            "no_context": True,
            "groundedness": {"score": 0.0, "confidence": "Low", "is_grounded": False},
        }

    evidences, sources = _build_evidences_and_sources(reranked)
    conversation = build_conversation_snippet(chat_history)

    # 5. Gemini Generation
    raw_answer = generate_answer(
        question,
        context,
        conversation=conversation,
    )

    structured = _parse_answer_structure(raw_answer, evidences, sources)
    groundedness = calculate_groundedness_score(raw_answer, reranked, no_context=False)

    latency_ms = round((time.time() - start_time) * 1000, 1)

    log_pipeline_event("answer", {
        "query": question,
        "groundedness_score": groundedness["score"],
        "confidence": groundedness["confidence"],
        "sources_count": len(sources),
        "latency_ms": latency_ms,
    })

    debug_payload = {
        "resolved_query": resolved_question,
        "question_type": question_type,
        "retrieved_candidates": len(valid_candidates),
        "final_context_chunks": len(reranked),
        "chunks": [
            {
                "id": c.get("chunk_id"),
                "source": (c.get("metadata") or {}).get("source"),
                "page": (c.get("metadata") or {}).get("page"),
                "distance": c.get("distance"),
                "rerank_score": c.get("rerank_score"),
                "final_score": c.get("final_score"),
                "snippet": c.get("text", "")[:120] + "...",
            }
            for c in reranked
        ],
        "groundedness": groundedness,
        "latency_ms": latency_ms,
    }

    # This is deliberately independent of the earlier sufficiency check.  A
    # plausible-looking model answer must never escape if it is weakly grounded.
    if (
        groundedness["score"] < GROUNDEDNESS_THRESHOLD
        or not groundedness.get("is_grounded", False)
    ):
        log_pipeline_event("refusal", {
            "query": question,
            "reason": "groundedness_below_threshold",
            "groundedness_score": groundedness["score"],
            "groundedness_threshold": GROUNDEDNESS_THRESHOLD,
        })
        debug_payload["refusal_reason"] = "groundedness_below_threshold"
        return _refusal_result(
            groundedness={**groundedness, "confidence": "Low", "is_grounded": False},
            debug_payload=debug_payload,
        )

    return {
        "answer": raw_answer,
        "intro": structured["intro"],
        "sections": structured["sections"],
        "sources": structured["sources"],
        "evidences": structured["evidences"],
        "no_context": False,
        "groundedness": groundedness,
        "debug": debug_payload,
    }


def answer_question_stream(
    question: str,
    document_id: str | None = None,
    chat_history: list[dict] | None = None,
) -> Generator[dict, None, None]:
    """
    Generator yielding token chunks and final metadata via Server-Sent Events (SSE).

    A response is fully validated by the same hard groundedness gate as the
    JSON endpoint before any answer text is sent.  This avoids leaking an
    ungrounded partial answer that a later metadata event would try to retract.
    """
    result = answer_question(
        question=question,
        document_id=document_id,
        chat_history=chat_history,
    )

    answer = result.get("answer") or NO_CONTEXT_MESSAGE
    # Small transport chunks keep the SSE client responsive while ensuring that
    # every visible token belongs to a response that already passed validation.
    for token in re.findall(r"\S+\s*", answer):
        yield {"type": "token", "token": token}

    yield {
        "type": "metadata",
        "intro": result.get("intro") or answer,
        "sections": result.get("sections") or [],
        "sources": result.get("sources") or [],
        "evidences": result.get("evidences") or [],
        "no_context": bool(result.get("no_context", False)),
        "groundedness": result.get("groundedness") or {"score": 0.0, "confidence": "Low", "is_grounded": False},
    }
    yield {"type": "done", "no_context": bool(result.get("no_context", False))}
    return

    question = (question or "").strip()
    if not question:
        yield {"type": "token", "token": "Please ask a question."}
        yield {"type": "done", "no_context": True}
        return

    resolved_question = resolve_follow_up(question, chat_history)
    question_type = classify_question(resolved_question)
    keywords = extract_keywords(resolved_question)
    entities = extract_entities(resolved_question)
    expansions = expand_query(resolved_question, keywords=keywords, entities=entities)

    broad = is_broad_question(resolved_question) or question_type == "SUMMARY"
    if broad:
        raw_candidates = retrieve_for_summary(document_id=document_id, summary_query=resolved_question)
    else:
        raw_candidates = retrieve(
            query=resolved_question,
            top_k=RETRIEVAL_CANDIDATES,
            relevance_threshold=RELEVANCE_THRESHOLD,
            document_id=document_id,
            expanded_queries=expansions,
            query_keywords=keywords,
            entities=entities,
            final_k=RETRIEVAL_CANDIDATES,
        )

    valid_candidates = [r for r in raw_candidates if "_no_relevant" not in str(r)]
    reranked = rerank_chunks(resolved_question, valid_candidates, top_n=FINAL_CONTEXT_CHUNKS)

    sufficient, reason = _check_evidence_sufficiency(reranked, question_type, entities, keywords, broad=broad)

    if not sufficient:
        yield {"type": "token", "token": NO_CONTEXT_MESSAGE}
        yield {
            "type": "metadata",
            "intro": NO_CONTEXT_MESSAGE,
            "sections": [],
            "sources": [],
            "evidences": [],
            "no_context": True,
            "groundedness": {"score": 0.0, "confidence": "Low"},
        }
        yield {"type": "done"}
        return

    context = build_citation_context(reranked)
    if not context:
        yield {"type": "token", "token": NO_CONTEXT_MESSAGE}
        yield {"type": "done", "no_context": True}
        return

    evidences, sources = _build_evidences_and_sources(reranked)
    conversation = build_conversation_snippet(chat_history)

    # Stream tokens from Gemini
    token_stream = generate_answer_stream(question, context, conversation=conversation)
    full_text_acc = []

    for token in token_stream:
        full_text_acc.append(token)
        yield {"type": "token", "token": token}

    full_answer = "".join(full_text_acc)
    structured = _parse_answer_structure(full_answer, evidences, sources)
    groundedness = calculate_groundedness_score(full_answer, reranked, no_context=False)

    # HARD GROUNDEDNESS THRESHOLD — unconditional refusal for streaming too
    groundedness_below_threshold = groundedness["score"] < GROUNDEDNESS_THRESHOLD
    is_refusal_answer = any(
        p in full_answer.lower()
        for p in [
            NO_CONTEXT_MESSAGE.lower(),
            "couldn't find that information",
            "could not find that information",
            "not mentioned in the provided",
            "not mentioned in the uploaded",
            "not found in your uploaded",
            "not found in the provided",
            "no information provided in the uploaded",
        ]
    )

    if groundedness_below_threshold or not groundedness.get("is_grounded", False) or is_refusal_answer:
        refusal_message = LOW_CONTENT_NO_ANSWER_MESSAGE if target_doc and target_doc.get("is_low_text") else NO_CONTEXT_MESSAGE
        yield {
            "type": "metadata",
            "intro": refusal_message,
            "sections": [],
            "sources": [],
            "evidences": [],
            "no_context": True,
            "groundedness": {"score": groundedness["score"], "confidence": "Low", "is_grounded": False},
        }
        yield {"type": "done"}
        return

    structured = _parse_answer_structure(full_answer, evidences, sources)

    yield {
        "type": "metadata",
        "intro": structured["intro"],
        "sections": structured["sections"],
        "sources": structured["sources"],
        "evidences": structured["evidences"],
        "no_context": False,
        "groundedness": groundedness,
    }
    yield {"type": "done"}
