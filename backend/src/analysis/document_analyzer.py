"""Upload-time document understanding via Gemini, grounded in extracted text."""

import json
import re
from typing import Any

from google import genai

from backend.src.llm.llm_client import get_gemini_client
from backend.src.utils.config import GEMINI_MODEL, GEMINI_TIMEOUT
from backend.src.utils.logger import log_pipeline_event, logger

MIN_ANALYSIS_CHARS = 120
MAX_ANALYSIS_CHARS = 24000

INSUFFICIENT_ANALYSIS = {
    "summary": "",
    "document_type": "insufficient_content",
    "entities": [],
    "structure": [],
    "suggested_questions": [],
    "analysis_status": "insufficient_content",
    "analysis_warnings": ["Insufficient extractable text to analyze without fabricating metadata."],
    "summary_consistency": {"passed": False, "warnings": ["No summary generated because extracted text was insufficient."]},
}


def _source_text_from_pages(pages: list[dict]) -> str:
    parts = []
    for page in pages:
        text = (page.get("text") or "").strip()
        if text:
            page_num = page.get("page") or "unknown"
            parts.append(f"[Page {page_num}]\n{text}")
    return "\n\n".join(parts).strip()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.I).strip()
        raw = re.sub(r"```$", "", raw).strip()
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if match:
        raw = match.group(0)
    return json.loads(raw)


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _normalize_analysis(data: dict[str, Any], source_text: str) -> dict[str, Any]:
    summary = str(data.get("summary") or "").strip()
    doc_type = str(data.get("document_type") or data.get("type") or "unknown").strip().lower().replace(" ", "_")
    source_lower = source_text.lower()
    entities = []
    for entity in _as_list(data.get("entities")):
        value = entity.get("value") if isinstance(entity, dict) else str(entity)
        if value and str(value).strip().lower() in source_lower:
            entities.append(entity)

    structure = []
    for item in _as_list(data.get("structure")):
        heading = item.get("heading") if isinstance(item, dict) else str(item)
        if heading and str(heading).strip().lower() in source_lower:
            structure.append(item)
    suggested = _as_list(data.get("suggested_questions"))

    clean_suggested = []
    for q in suggested:
        if isinstance(q, dict):
            text = q.get("question") or q.get("prompt") or q.get("title") or ""
        else:
            text = str(q)
        text = str(text).strip()
        if text:
            clean_suggested.append(text)

    clean_warnings = []
    for warning in _as_list(data.get("warnings")):
        if isinstance(warning, dict):
            text = warning.get("warning") or warning.get("caveat") or warning.get("message") or json.dumps(warning)
        else:
            text = str(warning)
        text = str(text).strip()
        if text:
            clean_warnings.append(text)

    return {
        "summary": summary,
        "document_type": doc_type[:80] or "unknown",
        "entities": entities[:60],
        "structure": structure[:40],
        "suggested_questions": clean_suggested[:6],
        "analysis_status": "analyzed" if summary else "failed",
        "analysis_warnings": clean_warnings[:10],
    }


def _content_words(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.@/-]{2,}", text or "")
        if len(token) > 2
    }


def _summary_consistency(summary: str, source_text: str) -> dict:
    """Basic safeguard: flag notable summary tokens absent from source text."""
    source_words = _content_words(source_text)
    summary_words = _content_words(summary)
    notable = {
        w for w in summary_words
        if len(w) >= 5 and not w.isdigit() and w not in {
            "document", "contains", "includes", "summary", "describes", "outlines",
            "provides", "information", "section", "details", "appears",
        }
    }
    missing = sorted(w for w in notable if w not in source_words)
    warnings = []
    if missing:
        warnings.append(f"Summary contains terms not found verbatim in extracted text: {', '.join(missing[:12])}")
    return {"passed": not warnings, "warnings": warnings}


def analyze_document_text(pages: list[dict], filename: str, is_low_text: bool = False) -> dict:
    """Generate real document metadata from extracted text only.

    Returns an explicit insufficient/failed status instead of fabricating metadata when
    extraction or the LLM call cannot support analysis.
    """
    source_text = _source_text_from_pages(pages)
    char_count = len(source_text.strip())

    if is_low_text or char_count < MIN_ANALYSIS_CHARS:
        result = dict(INSUFFICIENT_ANALYSIS)
        result["analysis_warnings"] = [
            f"Only {char_count} extractable characters were available; analysis was not generated."
        ]
        return result

    client = get_gemini_client()
    if not client:
        return {
            **INSUFFICIENT_ANALYSIS,
            "analysis_status": "failed",
            "analysis_warnings": ["Gemini API key is not configured; document analysis was not generated."],
        }

    prompt = f"""
Analyze ONLY the extracted document text below. Do not use the filename for facts.
Return strict JSON with these keys:
- summary: 2-4 sentences describing what the document actually contains.
- document_type: one concise category such as resume, policy_document, certificate, contract, report, invoice, technical_spec, spreadsheet, presentation, or other.
- entities: array of objects with type and value for real people, organizations, dates, amounts, IDs, locations, emails, phones, products, or key terms present in the text.
- structure: array of objects with heading, page, and description for real sections/headings present in the text. Use [] if no real structure is visible.
- suggested_questions: array of 3-5 answerable questions based only on this document.
- warnings: array of caveats about extraction quality or ambiguity.

Extracted text from {filename}:
<<<
{source_text[:MAX_ANALYSIS_CHARS]}
>>>
""".strip()

    candidate_models = list(dict.fromkeys([
        GEMINI_MODEL or "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest",
    ]))
    last_exc = None
    for model in candidate_models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    http_options=genai.types.HttpOptions(timeout=int(float(GEMINI_TIMEOUT) * 1000)),
                    automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            data = _extract_json(response.text or "")
            analysis = _normalize_analysis(data, source_text)
            consistency = _summary_consistency(analysis["summary"], source_text)
            analysis["summary_consistency"] = consistency
            if not consistency["passed"]:
                log_pipeline_event("analysis_consistency_warning", {
                    "filename": filename,
                    "warnings": consistency["warnings"],
                })
                # Metadata influences retrieval and the UI. Do not retain an
                # LLM analysis when its factual terms cannot be traced to the
                # extracted text.
                return {
                    **INSUFFICIENT_ANALYSIS,
                    "analysis_status": "failed",
                    "analysis_warnings": consistency["warnings"],
                    "summary_consistency": consistency,
                }
            analysis["analysis_model"] = model
            return analysis
        except Exception as exc:
            last_exc = exc
            err = str(exc).lower()
            if "429" in err or "resource_exhausted" in err or "404" in err or "not_found" in err:
                continue
            break

    logger.warning("Document analysis failed for %s: %s", filename, last_exc)
    return {
        **INSUFFICIENT_ANALYSIS,
        "analysis_status": "failed",
        "analysis_warnings": [f"Document analysis failed: {str(last_exc)[:240]}"],
    }
