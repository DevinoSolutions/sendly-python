"""Activity feed resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._pagination import iterate_legacy_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        ActivityCount,
        ActivityPage,
        ActivityStats,
        JSONDict,
        Query,
        UpcomingActivity,
    )


class ActivityResource:
    """What happened in the project: sends, opens, bounces, workflow steps and more.

    Needs the ``analytics:read`` scope. These routes speak the legacy
    ``{success, data}`` dialect, which the SDK unwraps. The feed pages with the
    legacy cursor (``cursor`` in, ``{data, cursor, hasMore}`` out), not the
    ``after`` / ``next_cursor`` pair of ``/api/v1``.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self, query: Query | None = None) -> ActivityPage:
        """One page of the activity feed, newest first.

        ``query`` takes ``limit`` (1-100), ``cursor``, ``contactId``, ``types``
        (comma-separated, e.g. ``email.sent,email.bounced,workflow.started``),
        ``startDate`` and ``endDate``. Returns ``{data, cursor, hasMore}``: pass
        ``cursor`` back until ``hasMore`` is false, or use :meth:`iter_list`.
        """
        envelope = self._client.request(method="GET", path="/api/activity", query=query)
        page: ActivityPage = self._client.unwrap(envelope)
        return page

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every activity item across pages, following the cursor for you."""
        return iterate_legacy_cursor(self.list, query)

    def recent_count(self, query: Query | None = None) -> ActivityCount:
        """How much happened in the last few minutes: ``{count, minutes}``.

        ``query`` takes ``minutes`` (1-60, default 5).
        """
        envelope = self._client.request(
            method="GET", path="/api/activity/recent-count", query=query
        )
        count: ActivityCount = self._client.unwrap(envelope)
        return count

    def stats(self, query: Query | None = None) -> ActivityStats:
        """Activity summarised by type over a period (``startDate`` / ``endDate``)."""
        envelope = self._client.request(method="GET", path="/api/activity/stats", query=query)
        stats: ActivityStats = self._client.unwrap(envelope)
        return stats

    def upcoming(self, query: Query | None = None) -> UpcomingActivity:
        """Scheduled sends and workflow steps due soon: ``{activities}``.

        ``query`` takes ``limit`` (1-100) and ``daysAhead`` (1-90).
        """
        envelope = self._client.request(method="GET", path="/api/activity/upcoming", query=query)
        upcoming: UpcomingActivity = self._client.unwrap(envelope)
        return upcoming
