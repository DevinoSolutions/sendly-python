"""Sendly SDK client — request core and resource wiring.

Ported from the reference TypeScript SDK's ``client.ts``. Behavioural parity:

* ``Authorization: Bearer <key>``, ``Accept`` and ``User-Agent`` on every request.
* ``{success, data}`` envelope unwrap (see :meth:`Sendly.unwrap`).
* Error envelope ``{error: {code, message}}`` mapped to typed exceptions.
* Query params skip ``None``/empty-string; list values append repeated keys.
* 204 / No-Content -> ``None``; non-JSON success body -> raw text.

One client, two response dialects. The legacy ``/api/*`` resources wrap results
in ``{success, data}`` and report failures as ``{error: {code, message}}``. The
``/api/v1/*`` resources (``campaigns``, ``segments``, ``workflows``,
``analytics``, ``usage``, and the v1 methods on ``events``) return the resource
body directly — no envelope, so they never call :meth:`Sendly.unwrap` — and
report failures as RFC 9457 problem documents. Both dialects raise the same
:class:`~sendly.errors.SendlyError` subclasses.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, NoReturn
from urllib.parse import urlencode

import httpx

from sendly.errors import (
    SendlyConnectionError,
    SendlyError,
    error_from_problem,
    error_from_response,
    is_problem_document,
)
from sendly.resources.analytics import AnalyticsResource
from sendly.resources.campaigns import CampaignsResource
from sendly.resources.contacts import ContactsResource
from sendly.resources.domains import DomainsResource
from sendly.resources.emails import EmailsResource
from sendly.resources.events import EventsResource
from sendly.resources.lists import ListsResource
from sendly.resources.mailboxes import MailboxesResource
from sendly.resources.projects import ProjectsResource
from sendly.resources.segments import SegmentsResource
from sendly.resources.suppression import SuppressionResource
from sendly.resources.templates import TemplatesResource
from sendly.resources.usage import UsageResource
from sendly.resources.verify import VerifyResource
from sendly.resources.webhooks import WebhooksResource
from sendly.resources.workflows import WorkflowsResource

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import TracebackType

    from sendly.types import Body, Query

__all__ = ["DEFAULT_BASE_URL", "SDK_VERSION", "Sendly"]

#: Package version. Kept in sync with ``pyproject.toml``.
SDK_VERSION = "0.2.0"

#: Default production API base. Override via ``base_url`` for staging/self-hosted.
DEFAULT_BASE_URL = "https://api.sendly.now"

#: Sent as the ``User-Agent`` on every request.
USER_AGENT = f"sendly-python/{SDK_VERSION}"


def _stringify(value: Any) -> str:
    """Render a query value the way the TS SDK's ``String(value)`` does."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class Sendly:
    """Sendly SDK entry point.

    Construct once with an API key and reuse the resource accessors for all
    calls: ``emails``, ``contacts``, ``events``, ``domains``, ``templates``,
    ``verify``, ``webhooks``, ``suppression`` and ``lists`` on the legacy
    surface, plus ``campaigns``, ``segments``, ``workflows``, ``analytics`` and
    ``usage`` on ``/api/v1``.

    Args:
        api_key: Project API key (``sk_*`` for full access, ``pk_*`` for
            sending-only). If omitted, falls back to the ``SENDLY_API_KEY``
            environment variable; if neither is set, a :class:`SendlyError` is
            raised (fail-loud — there is no degraded mode).
        base_url: Override API base URL. Trailing slashes are stripped.
        timeout: Per-request timeout in seconds (default 30). ``0`` or ``None``
            disables the timeout. Applied per request, even for an injected client.
        client: Inject a custom :class:`httpx.Client` (for testing, custom
            transports, proxies, etc.). If omitted, one is created and owned by
            this instance.
        default_headers: Extra headers merged into every request.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | None = 30.0,
        client: httpx.Client | None = None,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.environ.get("SENDLY_API_KEY")
        if not resolved_key:
            raise SendlyError(
                0,
                "invalid_options",
                "Sendly: `api_key` is required. Pass it explicitly or set the "
                "SENDLY_API_KEY environment variable.",
            )

        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._timeout: float | None = timeout if timeout and timeout > 0 else None
        self._default_headers: dict[str, str] = dict(default_headers or {})

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client()
            self._owns_client = True

        self.emails = EmailsResource(self)
        self.contacts = ContactsResource(self)
        self.events = EventsResource(self)
        self.domains = DomainsResource(self)
        self.templates = TemplatesResource(self)
        self.verify = VerifyResource(self)
        self.webhooks = WebhooksResource(self)
        self.suppression = SuppressionResource(self)
        self.lists = ListsResource(self)
        # Reads only -- the mailbox writes need a user, which an API key is not.
        self.mailboxes = MailboxesResource(self)
        # /api/v1 surface. Same client, same auth; bare resource bodies instead
        # of the legacy {success, data} envelope, and RFC 9457 problem errors.
        self.campaigns = CampaignsResource(self)
        self.segments = SegmentsResource(self)
        self.workflows = WorkflowsResource(self)
        self.analytics = AnalyticsResource(self)
        self.usage = UsageResource(self)
        self.projects = ProjectsResource(self)

    def request(
        self,
        *,
        method: str,
        path: str,
        body: Body | None = None,
        query: Query | None = None,
        headers: Mapping[str, str] | None = None,
        no_content: bool = False,
    ) -> Any:
        """Low-level request helper.

        Resources call this; consumers can call it directly for endpoints not
        yet wrapped by a resource. Returns the parsed JSON body of a successful
        response (the ``{success, data}`` envelope), raw text for a non-JSON
        success body, or ``None`` for 204 / ``no_content``. Errors are raised as
        :class:`SendlyError` subclasses based on status.
        """
        url = self._build_url(path, query)
        request_headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **self._default_headers,
            **(dict(headers) if headers else {}),
        }

        content: str | None = None
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            content = json.dumps(body)

        try:
            response = self._client.request(
                method,
                url,
                content=content,
                headers=request_headers,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise SendlyConnectionError(f"Sendly request failed: {exc}", exc) from exc

        # 204 No Content or caller-forced no-content (DELETE endpoints, which
        # now respond 200 with an id body the SDK intentionally discards).
        if response.status_code == 204 or no_content:
            if not response.is_success:
                self._raise_for_error(response)
            return None

        parsed: Any = None
        text = response.text
        if len(text) > 0:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                if not response.is_success:
                    raise error_from_response(
                        response.status_code,
                        "invalid_response",
                        f"Sendly returned non-JSON {response.status_code}: {text[:200]}",
                        text,
                    ) from None
                # Non-JSON success response; caller expects the raw text.
                return text

        if not response.is_success:
            self._raise_from_body(
                response.status_code, parsed, response.headers.get("content-type")
            )

        return parsed

    def unwrap(self, envelope: Any) -> Any:
        """Return the ``data`` field of a ``{success, data}`` envelope, else the
        value unchanged. Centralizing this keeps resource code clean.
        """
        if isinstance(envelope, dict) and "data" in envelope:
            return envelope["data"]
        return envelope

    def close(self) -> None:
        """Close the underlying HTTP client, if this instance owns it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Sendly:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _build_url(self, path: str, query: Query | None = None) -> str:
        if not path.startswith("/"):
            raise SendlyError(
                0, "invalid_path", f'Sendly: path must start with "/" (got "{path}").'
            )
        url = f"{self._base_url}{path}"
        if query:
            params: list[tuple[str, str]] = []
            for key, value in query.items():
                if value is None or value == "":
                    continue
                if isinstance(value, list | tuple):
                    for item in value:
                        if item is None or item == "":
                            continue
                        params.append((key, _stringify(item)))
                else:
                    params.append((key, _stringify(value)))
            if params:
                url = f"{url}?{urlencode(params)}"
        return url

    def _raise_for_error(self, response: httpx.Response) -> NoReturn:
        body: Any = None
        text = response.text
        if text:
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = None
        self._raise_from_body(response.status_code, body, response.headers.get("content-type"))

    def _raise_from_body(
        self, status_code: int, body: Any, content_type: str | None = None
    ) -> NoReturn:
        # /api/v1 speaks RFC 9457; the legacy surface speaks {success, error}.
        # Both land on the same exception classes, keyed off the status.
        if is_problem_document(body, content_type):
            raise error_from_problem(status_code, body)

        error = body.get("error") if isinstance(body, dict) else None
        error = error if isinstance(error, dict) else {}
        raw_message = error.get("message")
        message = (
            str(raw_message) if raw_message else f"Sendly request failed with status {status_code}"
        )
        raw_code = error.get("code")
        code = str(raw_code) if raw_code else f"http_{status_code}"
        raise error_from_response(status_code, code, message, body)
