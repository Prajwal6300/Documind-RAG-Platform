"""Lightweight in-memory rate limiting for DocuMind API.

Implements a sliding-window counter keyed by client IP with no external
dependencies (Redis is not used yet). Suitable for single-process
deployments behind a single Uvicorn worker. If the app is later deployed
with multiple workers, swap this for a Redis-backed limiter.

Protects the expensive endpoints: chat generation and document upload.
"""

import threading
import time
from collections import defaultdict, deque

from backend.src.utils.logger import logger

_lock = threading.Lock()
# key -> deque of request timestamps (kept sorted, oldest first)
_hits: dict[str, deque] = defaultdict(deque)


def _is_allowed(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    with _lock:
        bucket = _hits[key]
        cutoff = now - window_seconds
        # Drop timestamps outside the window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        # Bound memory: drop the bucket entirely once idle past the window
        if len(bucket) == 1 and now - bucket[0] > window_seconds * 2:
            _hits.pop(key, None)
        return True


def check_rate_limit(
    request,
    limit: int,
    window_seconds: int,
    scope: str,
) -> None:
    """Raise an HTTP 429 if the caller has exceeded `limit` requests in the window."""
    from backend.src.utils.errors import too_many_requests

    client_host = getattr(request.client, "host", None) or "unknown"
    # Fall back to X-Forwarded-For when behind a reverse proxy (first hop only)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client_host = xff.split(",")[0].strip() or client_host

    key = f"{scope}:{client_host}"

    if not _is_allowed(key, int(limit), int(window_seconds)):
        logger.warning("Rate limit exceeded for %s (key=%s)", scope, key)
        raise too_many_requests(
            f"You are sending too many requests. Please wait a moment and try again.",
            code=f"{scope}_rate_limited",
        )