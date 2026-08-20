"""DocuMind LLM generation layer powered exclusively by Google Gemini API.

Provides grounded question answering using official Google GenAI Python SDK with
strict anti-hallucination prompting and streaming support.
"""

import os
from typing import Generator
from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.src.utils.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
    GEMINI_TIMEOUT,
    MAX_CONTEXT_TOKENS,
)
from backend.src.utils.logger import logger
from backend.src.prompts.prompt_templates import (
    SYSTEM_PROMPT,
    GEMINI_AUTH_ERROR,
    GEMINI_RATE_LIMIT_ERROR,
    GEMINI_TIMEOUT_ERROR,
    GEMINI_CONNECTION_ERROR,
    GEMINI_NOT_FOUND_ERROR,
    GEMINI_MISSING_KEY_ERROR,
    GENERIC_ERROR_MESSAGE,
    build_rag_prompt,
)

load_dotenv()

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
        "your_actual_gemini_api_key",
    ):
        return None

    if _gemini_client is None or _cached_api_key != api_key:
        try:
            _gemini_client = genai.Client(api_key=api_key)
            _cached_api_key = api_key
        except Exception as exc:
            logger.error("Failed to initialize Gemini client: %s", exc)
            return None

    return _gemini_client


def get_llm_status() -> dict:
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
            "your_actual_gemini_api_key",
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


def _trim_context(context: str, max_tokens: int | None = None) -> str:
    """
    Trim context to fit within the configured token budget (~4 chars per token)
    while preserving document boundaries and metadata where possible.
    """
    if max_tokens is None:
        max_tokens = MAX_CONTEXT_TOKENS

    max_chars = max_tokens * 4

    if not context or len(context) <= max_chars:
        return context

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


def _format_and_log_error(exc: Exception, context_msg: str = "generation") -> str:
    """
    Log technical error details safely to terminal (never printing API key)
    and return clean, user-friendly error messages.
    """
    raw_msg = str(exc).strip()
    status_code = getattr(exc, "code", getattr(exc, "status_code", None))
    err_str = raw_msg.lower()

    logger.warning("Gemini API %s error (status=%s): %s", context_msg, status_code, raw_msg)

    if (
        status_code in (400, 401, 403)
        and ("api_key_invalid" in err_str or "api key not valid" in err_str or "unauthenticated" in err_str)
    ) or "api key not valid" in err_str or "unauthenticated" in err_str:
        return GEMINI_AUTH_ERROR

    if status_code == 429 or "resource_exhausted" in err_str or "quota" in err_str or "rate limit" in err_str:
        return GEMINI_RATE_LIMIT_ERROR

    if status_code == 404 or "not_found" in err_str or "model" in err_str and "not found" in err_str:
        return GEMINI_NOT_FOUND_ERROR

    if "timeout" in err_str or "timed out" in err_str:
        return GEMINI_TIMEOUT_ERROR

    if "connect" in err_str or "network" in err_str or "dns" in err_str or "connection" in err_str:
        return GEMINI_CONNECTION_ERROR

    return GENERIC_ERROR_MESSAGE


def generate_answer(question: str, context: str, conversation: str | None = None) -> str:
    """
    Generate a grounded answer using Google Gemini.
    Returns a string on every path; never raises unhandled exceptions.
    """
    client = get_gemini_client()
    if not client:
        return GEMINI_MISSING_KEY_ERROR

    primary_model = os.getenv("GEMINI_MODEL", GEMINI_MODEL).strip() or "gemini-3.6-flash"
    fallback_models = [
        primary_model,
        "gemini-3.6-flash",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.7-flash",
    ]
    # Deduplicate while preserving order
    candidate_models = list(dict.fromkeys(fallback_models))

    max_tokens = GEMINI_MAX_TOKENS
    temperature = GEMINI_TEMPERATURE
    timeout = float(GEMINI_TIMEOUT)

    context = _trim_context(context)
    prompt = build_rag_prompt(question, context, conversation)

    last_exc = None
    for model in candidate_models:
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
            last_exc = exc
            err_str = str(exc).lower()
            if (
                "503" in err_str
                or "unavailable" in err_str
                or "404" in err_str
                or "not_found" in err_str
                or "429" in err_str
                or "resource_exhausted" in err_str
                or "quota" in err_str
            ):
                continue
            return _format_and_log_error(exc, context_msg="generate_answer")

    return _format_and_log_error(last_exc, context_msg="generate_answer") if last_exc else GENERIC_ERROR_MESSAGE


def generate_answer_stream(question: str, context: str, conversation: str | None = None) -> Generator[str, None, None]:
    """
    Generator yielding response tokens from Google Gemini.
    Yields friendly error messages on failure paths instead of crashing.
    """
    client = get_gemini_client()
    if not client:
        yield GEMINI_MISSING_KEY_ERROR
        return

    primary_model = os.getenv("GEMINI_MODEL", GEMINI_MODEL).strip() or "gemini-3.6-flash"
    candidate_models = list(dict.fromkeys([
        primary_model,
        "gemini-3.6-flash",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash-lite",
        "gemini-3.7-flash",
    ]))

    max_tokens = GEMINI_MAX_TOKENS
    temperature = GEMINI_TEMPERATURE
    timeout = float(GEMINI_TIMEOUT)

    context = _trim_context(context)
    prompt = build_rag_prompt(question, context, conversation)

    last_exc = None
    for model in candidate_models:
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
            return

        except Exception as exc:
            last_exc = exc
            err_str = str(exc).lower()
            if (
                "503" in err_str
                or "unavailable" in err_str
                or "404" in err_str
                or "not_found" in err_str
                or "429" in err_str
                or "resource_exhausted" in err_str
                or "quota" in err_str
            ):
                continue
            yield _format_and_log_error(exc, context_msg="generate_answer_stream")
            return

    if last_exc:
        yield _format_and_log_error(last_exc, context_msg="generate_answer_stream")


