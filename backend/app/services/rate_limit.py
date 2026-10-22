"""Small in-memory request limiter (no extra package needed).

Each limit is "at most N events per window seconds" for one key, for example one client
address or one phone number. It is per server process: with several workers each keeps its
own counts, which still blocks fast guessing. For a large deployment use a shared store
such as Redis instead.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .. import config

_lock = threading.Lock()
_events: dict[tuple[str, str], deque] = defaultdict(deque)


def client_key(request: Request) -> str:
    if config.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _prune(queue: deque, now: float, window: float) -> None:
    while queue and now - queue[0] > window:
        queue.popleft()


def retry_after(bucket: str, key: str, limit: int, window: float) -> int:
    """Seconds until one more event is allowed (0 = allowed now). Does not record anything."""
    if not config.RATE_LIMIT_ENABLED:
        return 0
    now = time.monotonic()
    with _lock:
        queue = _events[(bucket, key)]
        _prune(queue, now, window)
        if len(queue) < limit:
            return 0
        return max(1, int(window - (now - queue[0])) + 1)


def record(bucket: str, key: str) -> None:
    if not config.RATE_LIMIT_ENABLED:
        return
    with _lock:
        _events[(bucket, key)].append(time.monotonic())


def check(bucket: str, key: str, limit: int, window: float) -> None:
    """Raise 429 if the key already used its allowance; otherwise count this event."""
    wait = retry_after(bucket, key, limit, window)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait and try again later.",
            headers={"Retry-After": str(wait)},
        )
    record(bucket, key)


def limit_client(request: Request, bucket: str, limit: int, window: float) -> None:
    check(bucket, client_key(request), limit, window)


def reset() -> None:
    """Forget every count (used by the automatic tests)."""
    with _lock:
        _events.clear()
