"""Segments resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        ContactList,
        JSONDict,
        Query,
        QueuedResult,
        SegmentDeleted,
        SegmentList,
        SegmentMembersResult,
        SegmentRecord,
    )


class SegmentsResource:
    """Group contacts into static lists or dynamic, condition-driven audiences.

    A ``DYNAMIC`` segment's ``condition`` is evaluated by the API — its
    ``member_count`` is computed at creation and kept current — so an invalid
    condition fails the create with a 422 rather than silently matching nothing.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self, query: Query | None = None) -> SegmentList:
        """List segments.

        Accepts ``limit`` (1-100, default 20) and ``after`` (opaque cursor), and
        answers ``{data, has_more, next_cursor}``. Hold the filters steady across
        one walk — changing them mid-pagination invalidates the cursor and the
        API answers 422 ``validation_error`` telling you to restart from the
        first page.
        """
        response: SegmentList = self._client.request(
            method="GET", path="/api/v1/segments", query=query
        )
        return response

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every segment across pages, following the cursor for you."""
        return iterate_cursor(self.list, query)

    def create(self, body: Body) -> SegmentRecord:
        """Create a segment. Requires ``name``.

        Takes no ``Idempotency-Key``: creating a segment neither sends anything
        nor consumes quota, so a duplicate costs one row that a
        :meth:`delete` undoes.
        """
        response: SegmentRecord = self._client.request(
            method="POST", path="/api/v1/segments", body=body
        )
        return response

    def get(self, id: str) -> SegmentRecord:
        """Fetch a single segment, including its current ``member_count``."""
        response: SegmentRecord = self._client.request(
            method="GET", path=f"/api/v1/segments/{encode_path_segment(id)}"
        )
        return response

    def update(self, id: str, body: Body) -> SegmentRecord:
        """Patch a segment's name, description, condition, or membership tracking."""
        response: SegmentRecord = self._client.request(
            method="PATCH", path=f"/api/v1/segments/{encode_path_segment(id)}", body=body
        )
        return response

    def delete(self, id: str) -> SegmentDeleted:
        """Delete a segment. Returns the ``{id, deleted}`` confirmation body.

        Removes the grouping, not the contacts in it.
        """
        response: SegmentDeleted = self._client.request(
            method="DELETE", path=f"/api/v1/segments/{encode_path_segment(id)}"
        )
        return response

    def list_contacts(self, id: str, query: Query | None = None) -> ContactList:
        """List the contacts currently in a segment.

        Cursor-paginated like :meth:`list` (``limit`` / ``after``). For a dynamic
        segment this is evaluated against the live condition, so membership can
        differ between two walks.
        """
        response: ContactList = self._client.request(
            method="GET",
            path=f"/api/v1/segments/{encode_path_segment(id)}/contacts",
            query=query,
        )
        return response

    def iter_list_contacts(self, id: str, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every contact in a segment across pages."""
        return iterate_cursor(lambda params: self.list_contacts(id, params), query)

    # Legacy ``/api/segments`` operations. They speak the ``{success, data}``
    # dialect, which the SDK unwraps. All need ``segments:write``.

    def compute(self, id: str) -> QueuedResult:
        """Queue a recalculation of which contacts match the segment's rules.

        Answers 202 ``{status: "queued"}``; the count updates when the job ends.
        """
        envelope = self._client.request(
            method="POST", path=f"/api/segments/{encode_path_segment(id)}/compute"
        )
        queued: QueuedResult = self._client.unwrap(envelope)
        return queued

    def refresh(self, id: str) -> JSONDict:
        """Recount the segment's members now and answer ``{memberCount}``."""
        envelope = self._client.request(
            method="POST", path=f"/api/segments/{encode_path_segment(id)}/refresh"
        )
        refreshed: JSONDict = self._client.unwrap(envelope)
        return refreshed

    def add_members(self, id: str, body: Body) -> SegmentMembersResult:
        """Add addresses to a STATIC segment.

        ``body`` is ``{"emails": [...]}`` (up to 100,000), plus ``createMissing``
        to create contacts that do not exist yet, with ``subscribed`` as their
        status. Past 1000 addresses the change runs as a background job.
        """
        envelope = self._client.request(
            method="POST", path=f"/api/segments/{encode_path_segment(id)}/members", body=body
        )
        result: SegmentMembersResult = self._client.unwrap(envelope)
        return result

    def remove_members(self, id: str, body: Body) -> SegmentMembersResult:
        """Remove addresses from a STATIC segment; the contacts stay in the project.

        ``body`` is ``{"emails": [...]}`` (up to 100,000). Sent as a ``DELETE`` that
        carries a JSON body.
        """
        envelope = self._client.request(
            method="DELETE", path=f"/api/segments/{encode_path_segment(id)}/members", body=body
        )
        result: SegmentMembersResult = self._client.unwrap(envelope)
        return result
