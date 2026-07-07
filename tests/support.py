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
