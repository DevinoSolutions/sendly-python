"""Events resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import Body, TrackEventData


class EventsResource:
    """Record custom events for contacts."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def track(self, body: Body) -> TrackEventData:
        """Record a custom event for a contact.

        Both full (``sk_*``) and sending-only (``pk_*``) keys are accepted.
        Reserved system event names (e.g. ``email.sent``) are rejected by the API.
        """
        envelope = self._client.request(method="POST", path="/api/track", body=body)
        data: TrackEventData = self._client.unwrap(envelope)
        return data
