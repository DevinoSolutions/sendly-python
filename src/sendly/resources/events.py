"""Events resource (legacy ``/api/track`` + the ``/api/v1/events`` surface)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        EventList,
        EventNameList,
        EventRecord,
        EventStats,
        JSONDict,
        Query,
        TrackEventData,
    )


class EventsResource:
    """Record custom events for contacts, and query the ones already recorded.

    Two write methods, one per API surface. :meth:`track` is the original
    ``POST /api/track`` call and is unchanged; :meth:`record` is its ``/api/v1``
    counterpart. They do the same thing — the difference is the dialect: v1
    returns the event body directly and reports failures as RFC 9457 problem
    documents. New code should prefer :meth:`record`, alongside the v1 read
    methods below.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def track(self, body: Body) -> TrackEventData:
        """Record a custom event for a contact (legacy ``/api/track``).

        Both full (``sk_*``) and sending-only (``pk_*``) keys are accepted.
        Reserved system event names (e.g. ``email.sent``) are rejected by the API.
        """
        envelope = self._client.request(method="POST", path="/api/track", body=body)
        data: TrackEventData = self._client.unwrap(envelope)
        return data

    def record(self, body: Body) -> EventRecord:
        """Record a custom event for a contact (``/api/v1``).

        Requires ``name``; optionally takes ``contact_id`` and a ``data`` object.
        The v1 counterpart of :meth:`track`, returning the created event body
        rather than a ``{success, data}`` envelope.

        Takes no ``Idempotency-Key``: events are the highest-volume write on the
        surface and append-only by nature, so the API deliberately does not
        ledger them. If a duplicate would matter to you, dedupe on your side.
        """
        response: EventRecord = self._client.request(
            method="POST", path="/api/v1/events", body=body
        )
        return response

    def list(self, query: Query | None = None) -> EventList:
        """List recorded events, newest first.

        Accepts ``limit`` (1-100, default 20), ``after`` (opaque cursor), and
        ``event_name`` to filter to one event. Answers
        ``{data, has_more, next_cursor}`` — no total, deliberately. Keep the
        filters identical across one walk: changing them invalidates the cursor
        and the API answers 422 ``validation_error`` telling you to restart from
        the first page.
        """
        response: EventList = self._client.request(method="GET", path="/api/v1/events", query=query)
        return response

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every matching event across pages, following the cursor for you."""
        return iterate_cursor(self.list, query)

    def list_names(self) -> EventNameList:
        """The distinct event names recorded on the project.

        Takes no arguments — the endpoint declares no parameters, and the answer
        is the project's whole name set. Useful for building a workflow trigger:
        a workflow's ``event_name`` has to match a name events are actually
        recorded under.
        """
        response: EventNameList = self._client.request(method="GET", path="/api/v1/events/names")
        return response

    def stats(self, query: Query | None = None) -> EventStats:
        """Per-event counts over an optional ``from`` / ``to`` window."""
        response: EventStats = self._client.request(
            method="GET", path="/api/v1/events/stats", query=query
        )
        return response
