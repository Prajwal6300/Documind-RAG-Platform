"""Centralized error types and helpers for DocuMind API.

All API endpoints raise `HTTPException` (or subclass) which the global
exception handlers in `backend/main.py` convert into a consistent JSON shape:

    {"detail": "human readable message"}

Nothing sensitive (stack traces, connection strings, file paths) is ever
returned to the client. Full technical details are logged server-side only.
"""

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.src.utils.logger import logger

# ---------------------------------------------------------------------------
# Domain-specific HTTP exceptions with clear messages
# ---------------------------------------------------------------------------


class ApiError(HTTPException):
    """Base class for all DocuMind API errors with consistent status + message."""

    def __init__(self, status_code: int, detail: str, code: str = "api_error"):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def bad_request(detail: str, code: str = "bad_request") -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, detail, code)


def not_found(detail: str, code: str = "not_found") -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, detail, code)


def conflict(detail: str, code: str = "conflict") -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, detail, code)


def too_large(detail: str, code: str = "payload_too_large") -> ApiError:
    return ApiError(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail, code)


def unsupported_media(detail: str, code: str = "unsupported_media_type") -> ApiError:
    return ApiError(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail, code)


def unprocessable(detail: str, code: str = "unprocessable_entity") -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, code)


def too_many_requests(detail: str, code: str = "rate_limited") -> ApiError:
    return ApiError(status.HTTP_429_TOO_MANY_REQUESTS, detail, code)


def database_unavailable(detail: str = "Database is temporarily unavailable. Please try again in a moment.") -> ApiError:
    return ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, detail, "database_unavailable")


# ---------------------------------------------------------------------------
# Exception -> response helpers (used by global handlers in main.py)
# ---------------------------------------------------------------------------

def _sanitize_message(msg: str) -> str:
    """Never leak full connection strings, file paths, or stack traces."""
    msg = str(msg).strip()
    for token in ("postgresql://", "postgres://", "GEMINI_API_KEY=", "api_key=", "password=", "PASSWORD"):
        if token.lower() in msg.lower():
            return "An internal error occurred. Please try again."
    return msg


def is_database_error(exc: Exception) -> bool:
    """Best-effort detection of PostgreSQL connectivity failures."""
    exc_name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return (
        "operationalerror" in exc_name
        or "interfaceerror" in exc_name
        or "connection" in msg
        or "could not connect" in msg
        or "connection refused" in msg
        or "timeout" in msg
    )


async def global_exception_handler(request: Request, exc: Exception):
    """Safety net: never return a raw crash to the client."""
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Render every HTTPException with the consistent error JSON shape."""
    if exc.status_code >= 500:
        logger.error("HTTP %s on %s %s: %s", exc.status_code, request.method, request.url.path, exc.detail)
    else:
        logger.warning("HTTP %s on %s %s: %s", exc.status_code, request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": _sanitize_message(exc.detail)},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert FastAPI's default 422 body into a single readable message."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
    msg = first.get("msg", "Invalid request input.")
    detail = f"Invalid request input"
    if loc:
        detail = f"Invalid value for '{loc}': {msg}"
    else:
        detail = f"Invalid request input: {msg}"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )