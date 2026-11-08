"""Analytics resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        AnalyticsTimeseries,
        CampaignAnalytics,
        Query,
        TopCampaignList,
        TopEventList,
    )


class AnalyticsResource:
    """Aggregate sending and engagement metrics.

    Every method takes an optional ``from`` / ``to`` window (ISO 8601) and echoes
    the resolved window back as ``window``, so a caller can tell what the API
    actually measured when it defaulted the range. None of these are
    cursor-paginated — they answer a bounded aggregate, not a listing — so there
    are no iterators here.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def timeseries(self, query: Query | None = None) -> AnalyticsTimeseries:
        """Per-day sending and engagement counts over the window."""
        response: AnalyticsTimeseries = self._client.request(
            method="GET", path="/api/v1/analytics/timeseries", query=query
        )
        return response

    def campaigns(self, query: Query | None = None) -> CampaignAnalytics:
        """Campaign totals for the window: counts plus average open/click rates."""
        response: CampaignAnalytics = self._client.request(
            method="GET", path="/api/v1/analytics/campaigns", query=query
        )
        return response

    def top_campaigns(self, query: Query | None = None) -> TopCampaignList:
        """Best-performing campaigns in the window. Accepts ``limit``."""
        response: TopCampaignList = self._client.request(
            method="GET", path="/api/v1/analytics/top-campaigns", query=query
        )
        return response

    def top_events(self, query: Query | None = None) -> TopEventList:
        """The most frequent events in the period.

        ``query`` takes ``limit`` (default 5, at most 20), ``startDate`` and
        ``endDate``. Needs ``analytics:read``. Unlike the ``/api/v1`` methods above,
        this route speaks the legacy ``{success, data}`` dialect, which the SDK
        unwraps.
        """
        envelope = self._client.request(method="GET", path="/api/analytics/top-events", query=query)
        events: TopEventList = self._client.unwrap(envelope)
        return events
