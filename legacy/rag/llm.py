"""DocuMind LLM generation layer powered exclusively by Google Gemini API.

Provides grounded question answering using official Google GenAI Python SDK with
strict anti-hallucination prompting and streaming support.
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from rag.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT,
    MAX_CONTEXT_TOKENS,
)

load_dotenv()

# Strict Document-Grounded System Instruction
SYSTEM_PROMPT = (
    "You are DocuMind, an enterprise document question-answering assistant.\n\n"
    "Your answers MUST be based ONLY on the supplied document evidence.\n\n"
    "Rules:\n\n"
    "1. Never use outside knowledge to answer document questions.\n"
    "2. Never invent facts.\n"
    "3. Never guess missing information.\n"
    '4. If the answer cannot be supported by the supplied evidence, say exactly:\n'
    '   "I couldn\'t find that information in the uploaded documents."\n'
    "5. Read and compare ALL relevant supplied evidence before answering.\n"
    "6. Do not answer from only the first retrieved chunk.\n"
    "7. Combine information from multiple documents when necessary.\n"
    '8. Resolve references such as "he", "she", "they", "this person", "that project", etc. using the uploaded document evidence.\n'
    "9. Preserve exact values for:\n"
    "   - names\n"
    "   - employee IDs\n"
    "   - dates\n"
    "   - phone numbers\n"
    "   - email addresses\n"
    "   - amounts\n"
    "   - percentages\n"
    "   - addresses\n"
    "   - qualifications\n"
    "   - job titles\n"
    "   - company names\n"
    "   - project names\n"
    "   - technical specifications\n"
    "10. Never modify or normalize exact document values unless explicitly requested.\n"
    "11. If two documents contain conflicting information, clearly state the conflict and identify which document contains each value.\n"
    "12. If the user asks about a specific person, search all supplied evidence relevant to that person before answering.\n"
    "13. If multiple uploaded files are relevant, synthesize them into one accurate answer.\n"
    "14. Do not mention information that is not supported by the evidence.\n"
    "15. Give the direct answer first.\n"
    "16. Use concise formatting unless the user requests details.\n"
    "17. For lists, use bullet points.\n"
    "18. For comparisons, use tables when useful.\n"
    "19. If evidence is insufficient, say so instead of guessing."
)

GEMINI_AUTH_ERROR = "Gemini authentication failed. Please check your Gemini API key."
GEMINI_RATE_LIMIT_ERROR = "Gemini API quota or rate limit was reached. Please check your Gemini API usage and billing/quota settings."
GEMINI_TIMEOUT_ERROR = "Gemini request timed out. Please try again."
GEMINI_CONNECTION_ERROR = "Unable to connect to Gemini. Please check your internet connection."
GEMINI_NOT_FOUND_ERROR = "The configured Gemini model is unavailable. Please check GEMINI_MODEL."
GEMINI_MISSING_KEY_ERROR = "Gemini API key is not configured. Please set GEMINI_API_KEY in your .env file."
GENERIC_ERROR_MESSAGE = "Something went wrong while generating the answer. Please try again."

# Singleton Gemini client instance
_gemini_client = None
_cached_api_key = None


def get_gemini_client():
    """Retrieve or initialize the singleton Google Gemini client."""
    global _gemini_client, _cached_api_key
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()

    if not api_key or api_key in (
        "your_actual_api_key",
        "YOUR_GEMINI_API_KEY_HERE",
        "YOUR_API_KEY_HERE",
    ):
        return None

    if _gemini_client is None or _cached_api_key != api_key:
        try:
            _gemini_client = genai.Client(api_key=api_key)
            _cached_api_key = api_key
        except Exception as exc:
            print(f"[DocuMind] Failed to initialize Gemini client: {exc}")
            return None

    return _gemini_client


def get_llm_status():
    """
    Return clean metadata about the Gemini LLM status and readiness
    without exposing credentials.
    """
    api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    has_valid_key = bool(
        api_key
        and api_key not in (
            "your_actual_api_key",
            "YOUR_GEMINI_API_KEY_HERE",
            "YOUR_API_KEY_HERE",
        )
    )
    model = os.getenv("GEMINI_MODEL", GEMINI_MODEL).strip() or "gemini-2.5-flash"

    if "2.5-flash" in model or "2.5" in model:
        display = "Gemini 2.5 Flash"
    elif "flash" in model.lower():
        display = "Gemini Flash"
    elif "pro" in model.lower():
        display = "Gemini Pro"
    else:
        display = "Gemini"

    status_text = "Gemini · Ready" if has_valid_key else "Gemini · Key Missing"

    return {
        "provider": "gemini",
        "model": model,
        "display_name": display,
        "ready": has_valid_key,
        "status_text": status_text,
        "details": f"Model: {model}",
    }


def _trim_context(context, max_tokens=None):
    """
    Trim context to fit within the configured token budget (~4 chars per token)
    while preserving document boundaries and metadata where possible.
    """
    if max_tokens is None:
        try:
            max_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", str(MAX_CONTEXT_TOKENS)))
        except (ValueError, TypeError):
            max_tokens = 4000

    max_chars = max_tokens * 4

    if not context or len(context) <= max_chars:
        return context

    # If context exceeds max_chars, preserve whole chunks separated by '---'
    sections = context.split("\n\n---\n\n")
    kept = []
    current_len = 0

    for section in sections:
        sec_len = len(section) + 7  # separator length
        if current_len + sec_len <= max_chars or not kept:
            kept.append(section)
            current_len += sec_len
        else:
            break

    trimmed = "\n\n---\n\n".join(kept)
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars] + " ... [context truncated]"
    return trimmed


def _build_gemini_prompt(question, context, conversation=None):
    """Format structured context, history, and user question for Gemini."""
    context = _trim_context(context)
    parts = [f"DOCUMENT EVIDENCE:\n{context}"]

    if conversation:
        parts.append(f"CONVERSATION HISTORY:\n{conversation}")

    parts.append(f"USER QUESTION:\n{question}")
    return "\n\n".join(parts)


def _format_and_log_error(exc, context_msg="generation"):
    """
    Log technical error details safely to terminal (never printing API key)
    and return clean, user-friendly error messages.
    """
    raw_msg = str(exc).strip()
    status_code = getattr(exc, "code", getattr(exc, "status_code", None))
    err_str = raw_msg.lower()

    # Log sanitized technical detail to server console
    print(f"[DocuMind] Gemini API {context_msg} error ({status_code}): {raw_msg}")

    # Check for authentication / API key issues
    if (
        status_code in (400, 401, 403)
        and ("api_key_invalid" in err_str or "api key not valid" in err_str or "unauthenticated" in err_str)
    ) or "api key not valid" in err_str or "unauthenticated" in err_str:
        return GEMINI_AUTH_ERROR

    # Check for quota / rate limit issues
    if status_code == 429 or "resource_exhausted" in err_str or "quota" in err_str or "rate limit" in err_str:
        return GEMINI_RATE_LIMIT_ERROR

    # Check for model not found
    if status_code == 404 or "not_found" in err_str or "model" in err_str and "not found" in err_str:
        return GEMINI_NOT_FOUND_ERROR

    # Check for timeout
    if "timeout" in err_str or "timed out" in err_str:
        return GEMINI_TIMEOUT_ERROR

    # Check for connection / network errors
    if "connect" in err_str or "network" in err_str or "dns" in err_str or "connection" in err_str:
        return GEMINI_CONNECTION_ERROR

    return GENERIC_ERROR_MESSAGE


def generate_answer(question, context, conversation=None):
    """
    Generate a grounded answer using Google Gemini.
    Returns a string on every path; never raises unhandled exceptions.
    """
    client = get_gemini_client()
    if not client:
        return GEMINI_MISSING_KEY_ERROR

    model = os.getenv("GEMINI_MODEL", GEMINI_MODEL).strip() or "gemini-2.5-flash"
    try:
        max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", str(GEMINI_MAX_TOKENS)))
    except (ValueError, TypeError):
        max_tokens = 4096

    try:
        temperature = float(os.getenv("GEMINI_TEMPERATURE", str(GEMINI_TEMPERATURE)))
    except (ValueError, TypeError):
        temperature = 0.1

    try:
        timeout = float(os.getenv("GEMINI_TIMEOUT", str(GEMINI_TIMEOUT)))
    except (ValueError, TypeError):
        timeout = 120.0

    prompt = _build_gemini_prompt(question, context, conversation)

    try:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=temperature,
            max_output_tokens=max_tokens,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        if response and response.text:
            text = response.text.strip()
            if text:
                return text

        return "I could not generate an answer. Gemini returned an empty response."

    except Exception as exc:
        return _format_and_log_error(exc, context_msg="generate_answer")


def generate_answer_stream(question, context, conversation=None):
    """
    Generator yielding response tokens from Google Gemini.
    Yields friendly error messages on failure paths instead of crashing.
    """
    client = get_gemini_client()
    if not client:
        yield GEMINI_MISSING_KEY_ERROR
        return

    model = os.getenv("GEMINI_MODEL", GEMINI_MODEL).strip() or "gemini-2.5-flash"
    try:
        max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", str(GEMINI_MAX_TOKENS)))
    except (ValueError, TypeError):
        max_tokens = 4096

    try:
        temperature = float(os.getenv("GEMINI_TEMPERATURE", str(GEMINI_TEMPERATURE)))
    except (ValueError, TypeError):
        temperature = 0.1

    try:
        timeout = float(os.getenv("GEMINI_TIMEOUT", str(GEMINI_TIMEOUT)))
    except (ValueError, TypeError):
        timeout = 120.0

    prompt = _build_gemini_prompt(question, context, conversation)

    try:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=temperature,
            max_output_tokens=max_tokens,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        response_stream = client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=config,
        )

        has_output = False
        for chunk in response_stream:
            if chunk and chunk.text:
                has_output = True
                yield chunk.text

        if not has_output:
            yield "I could not generate an answer. Gemini returned an empty response."

    except Exception as exc:
        yield _format_and_log_error(exc, context_msg="generate_answer_stream")
