"""Helpers for safe text search in SQL LIKE patterns."""
from __future__ import annotations

LIKE_ESCAPE = "\\"


def like_contains(text: str) -> str:
    """'%' and '_' typed by a user are matched literally, not as wildcards."""
    cleaned = text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2).replace("%", LIKE_ESCAPE + "%").replace("_", LIKE_ESCAPE + "_")
    return f"%{cleaned}%"
