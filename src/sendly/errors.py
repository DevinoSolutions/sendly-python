"""Error hierarchy raised by the Sendly SDK.

Mirrors the TypeScript SDK's ``errors.ts``: a single :class:`SendlyError` base with
one subclass per meaningful HTTP status so callers can ``except`` a narrow type
without inspecting the response body.
"""

from __future__ import annotations

from typing import Any


class SendlyError(Exception):
    """Base error for any non-2xx HTTP response or transport failure.

    Attributes:
        status_code: HTTP status (``0`` for client-side/transport failures).
        error_code: Machine-readable code from the API error envelope, or a
            synthesized ``http_<status>`` / ``invalid_response`` / ``connection_error``.
        message: Human-readable message.
        body: The parsed (or raw) response body, when available.
    """

    def __init__(self, status_code: int, error_code: str, message: str, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.body = body


class SendlyValidationError(SendlyError):
    """400 — request body or query failed validation."""


class SendlyAuthenticationError(SendlyError):
    """401 — missing or invalid ``Authorization`` header."""


class SendlyPermissionError(SendlyError):
    """403 — authenticated but lacks permission for the operation."""


class SendlyNotFoundError(SendlyError):
    """404 — resource does not exist or is not visible to the caller."""


class SendlyConflictError(SendlyError):
    """409 — conflict (already exists, immutable, etc.)."""


class SendlyRateLimitError(SendlyError):
    """429 — rate limited. Honor ``Retry-After`` if present."""


class SendlyServerError(SendlyError):
    """5xx — server-side failure. Generally retryable with backoff."""


class SendlyConnectionError(SendlyError):
    """Transport-level failure (DNS, connect, timeout, parse)."""

    def __init__(self, message: str, body: Any = None) -> None:
        super().__init__(0, "connection_error", message, body)


def error_from_response(
    status_code: int, error_code: str, message: str, body: Any = None
) -> SendlyError:
    """Map an HTTP status + error envelope to the appropriate error subclass."""
    if status_code == 400:
        return SendlyValidationError(status_code, error_code, message, body)
    if status_code == 401:
        return SendlyAuthenticationError(status_code, error_code, message, body)
    if status_code == 403:
        return SendlyPermissionError(status_code, error_code, message, body)
    if status_code == 404:
        return SendlyNotFoundError(status_code, error_code, message, body)
    if status_code == 409:
        return SendlyConflictError(status_code, error_code, message, body)
    if status_code == 429:
        return SendlyRateLimitError(status_code, error_code, message, body)
    if status_code >= 500:
        return SendlyServerError(status_code, error_code, message, body)
    return SendlyError(status_code, error_code, message, body)
