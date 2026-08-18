"""Shared test helpers: hermetic httpx MockTransport wiring (zero network)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from sendly import Sendly


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> Sendly:
    """Build a Sendly client backed by an httpx ``MockTransport`` (no network)."""
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return Sendly(
        api_key="sk_test_key",
        base_url="http://localhost",
        client=http_client,
        timeout=0,
    )


def json_response(status: int, body: object) -> httpx.Response:
    """Build a JSON response, or a raw-text response when ``body`` is a ``str``."""
    if isinstance(body, str):
        return httpx.Response(status, text=body, headers={"content-type": "application/json"})
    return httpx.Response(status, json=body)


def empty_response(status: int = 204) -> httpx.Response:
    """Build an empty-body response (e.g. 204 No Content)."""
    return httpx.Response(status)


def problem_response(status: int, problem: dict[str, object]) -> httpx.Response:
    """Build an RFC 9457 ``application/problem+json`` error response."""
    return httpx.Response(
        status, json=problem, headers={"content-type": "application/problem+json"}
    )


class Recorder:
    """Request handler that records requests and replies with a fixed response."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._response

    @property
    def request(self) -> httpx.Request:
        """The first (usually only) recorded request."""
        return self.requests[0]


class SequenceRecorder:
    """Request handler that replies with a queued response per call, in order.

    Used to walk a paginated endpoint. Running past the last queued response
    fails the test rather than repeating one, so an auto-paginator that ignores
    its stop condition surfaces as an error instead of an infinite loop.
    """

    def __init__(self, *responses: httpx.Response) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        index = len(self.requests) - 1
        assert index < len(self._responses), (
            f"unexpected request #{index + 1} to {request.url}: only "
            f"{len(self._responses)} responses were queued"
        )
        return self._responses[index]

    @property
    def urls(self) -> list[str]:
        """Every requested URL, in call order."""
        return [str(request.url) for request in self.requests]


def cursor_page(items: list[object], *, next_cursor: str | None = None) -> dict[str, object]:
    """Build an ``/api/v1`` cursor-list envelope: ``{data, has_more, next_cursor}``."""
    return {"data": items, "has_more": next_cursor is not None, "next_cursor": next_cursor}
