"""Audit log resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._pagination import iterate_legacy_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import AuditLogPage, JSONDict, Query


class AuditLogResource:
    """Who changed what in the project, newest first.

    The legacy ``{success, data}`` dialect, unwrapped by the SDK, with the legacy
    cursor: ``cursor`` in, ``{data, total, cursor, hasMore}`` out.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self, query: Query | None = None) -> AuditLogPage:
        """One page of audit entries.

        ``query`` takes ``limit`` (default 50, at most 100 -- more is refused with
        422), ``cursor`` and ``action`` (a prefix filter such as ``contact.`` or
        ``campaign.``). ``total`` is counted on the first page only; later pages
        report ``0``.
        """
        envelope = self._client.request(method="GET", path="/api/audit-log", query=query)
        page: AuditLogPage = self._client.unwrap(envelope)
        return page

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every audit entry across pages, following the cursor for you."""
        return iterate_legacy_cursor(self.list, query)
