"""Prompts module for DocuMind RAG."""

from backend.src.prompts.prompt_templates import (
    SYSTEM_PROMPT,
    NO_CONTEXT_MESSAGE,
    GEMINI_AUTH_ERROR,
    GEMINI_RATE_LIMIT_ERROR,
    GEMINI_TIMEOUT_ERROR,
    GEMINI_CONNECTION_ERROR,
    GEMINI_NOT_FOUND_ERROR,
    GEMINI_MISSING_KEY_ERROR,
    GENERIC_ERROR_MESSAGE,
    build_conversation_snippet,
    build_citation_context,
    build_rag_prompt,
)

__all__ = [
    "SYSTEM_PROMPT",
    "NO_CONTEXT_MESSAGE",
    "GEMINI_AUTH_ERROR",
    "GEMINI_RATE_LIMIT_ERROR",
    "GEMINI_TIMEOUT_ERROR",
    "GEMINI_CONNECTION_ERROR",
    "GEMINI_NOT_FOUND_ERROR",
    "GEMINI_MISSING_KEY_ERROR",
    "GENERIC_ERROR_MESSAGE",
    "build_conversation_snippet",
    "build_citation_context",
    "build_rag_prompt",
]
