"""Shared helpers for resource classes."""

from __future__ import annotations

from urllib.parse import quote


def encode_path_segment(segment: str) -> str:
    """Percent-encode a single URL path segment (mirrors JS ``encodeURIComponent``)."""
    return quote(str(segment), safe="")


def idempotency_headers(idempotency_key: str | None) -> dict[str, str] | None:
    """Build the optional ``Idempotency-Key`` header dict, or ``None`` when unset."""
    if not idempotency_key:
        return None
    return {"Idempotency-Key": idempotency_key}
