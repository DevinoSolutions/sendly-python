"""Error hierarchy raised by the Sendly SDK.

Mirrors the TypeScript SDK's ``errors.ts``: a single :class:`SendlyError` base with
one subclass per meaningful HTTP status so callers can ``except`` a narrow type
without inspecting the response body.

The API speaks two error dialects and both land on the same exception classes:

* legacy ``/api/*`` — ``{success: false, error: {code, message}}``;
* ``/api/v1/*`` — an RFC 9457 problem document served as
  ``application/problem+json``. Its ``code`` becomes :attr:`SendlyError.error_code`
  and its ``detail`` (falling back to ``title``) becomes the message, so
  ``except SendlyValidationError`` behaves identically across both surfaces.
  Two problem-only fields are surfaced additively: :attr:`SendlyError.request_id`
  and :attr:`SendlyError.field_errors`.
"""

from __future__ import annotations

from typing import Any

#: Media type of an RFC 9457 problem document.
PROBLEM_CONTENT_TYPE = "application/problem+json"


class SendlyError(Exception):
    """Base error for any non-2xx HTTP response or transport failure.

    Attributes:
        status_code: HTTP status (``0`` for client-side/transport failures).
        error_code: Machine-readable code from the API error envelope (legacy
            ``error.code`` or v1 problem ``code``), or a synthesized
            ``http_<status>`` / ``invalid_response`` / ``connection_error``.
        message: Human-readable message.
        body: The parsed (or raw) response body, when available. For a v1
            failure this is the whole problem document, so ``type``, ``title``,
            ``instance`` and any other member stays reachable.
        request_id: Correlation id from a v1 problem document (``request_id``);
            ``None`` on the legacy surface. Quote it in support requests.
        field_errors: Field-level failures from a v1 ``validation_error``
            problem (``errors``), each ``{pointer, code, message}``; ``None``
            when the response carried none. The legacy surface puts its own
            breakdown at ``body["error"]["details"]["errors"]`` instead.
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        body: Any = None,
        *,
        request_id: str | None = None,
        field_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.body = body
        self.request_id = request_id
        self.field_errors = field_errors


class SendlyValidationError(SendlyError):
    """400 / 422 — request body or query failed validation.

    Migrated routes return ``422`` with a ``VALIDATION_ERROR`` code (and an
    ``error.details.errors`` list); legacy/malformed-request paths still use
    ``400``. Both map here so ``except SendlyValidationError`` catches either.
    """


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


def _error_class(status_code: int) -> type[SendlyError]:
    """The exception class a status maps to. Shared by both error dialects."""
    if status_code in (400, 422):
        return SendlyValidationError
    if status_code == 401:
        return SendlyAuthenticationError
    if status_code == 403:
        return SendlyPermissionError
    if status_code == 404:
        return SendlyNotFoundError
    if status_code == 409:
        return SendlyConflictError
    if status_code == 429:
        return SendlyRateLimitError
    if status_code >= 500:
        return SendlyServerError
    return SendlyError


def error_from_response(
    status_code: int,
    error_code: str,
    message: str,
    body: Any = None,
    *,
    request_id: str | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> SendlyError:
    """Map an HTTP status + error envelope to the appropriate error subclass."""
    return _error_class(status_code)(
        status_code,
        error_code,
        message,
        body,
        request_id=request_id,
        field_errors=field_errors,
    )


def is_problem_document(body: Any, content_type: str | None = None) -> bool:
    """Is this response body an RFC 9457 problem document?

    Trusts the ``application/problem+json`` content type when present, and
    otherwise falls back to the document shape (``type`` + ``title`` + ``code``),
    so a proxy that rewrites the media type cannot downgrade a v1 error into the
    generic ``http_<status>`` path. The legacy ``{success, error}`` envelope
    carries none of those members, so it can never match.
    """
    if not isinstance(body, dict):
        return False
    if content_type and PROBLEM_CONTENT_TYPE in content_type.lower():
        return True
    return all(isinstance(body.get(key), str) for key in ("type", "title", "code"))


def error_from_problem(status_code: int, problem: dict[str, Any]) -> SendlyError:
    """Map an RFC 9457 problem document to the exception class for its status.

    ``code`` supplies the machine-readable :attr:`SendlyError.error_code` and
    ``detail`` the message, falling back to ``title`` — a problem document always
    carries a title but only sometimes an occurrence-specific detail.
    """
    raw_code = problem.get("code")
    code = raw_code if isinstance(raw_code, str) and raw_code else f"http_{status_code}"

    message = ""
    for key in ("detail", "title"):
        value = problem.get(key)
        if isinstance(value, str) and value:
            message = value
            break
    if not message:
        message = f"Sendly request failed with status {status_code}"

    raw_request_id = problem.get("request_id")
    request_id = raw_request_id if isinstance(raw_request_id, str) else None

    raw_errors = problem.get("errors")
    field_errors = (
        [item for item in raw_errors if isinstance(item, dict)]
        if isinstance(raw_errors, list)
        else None
    )

    return error_from_response(
        status_code,
        code,
        message,
        problem,
        request_id=request_id,
        field_errors=field_errors,
    )
