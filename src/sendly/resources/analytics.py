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
