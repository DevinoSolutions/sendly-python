"""Campaigns resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment, idempotency_headers
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        CampaignDeleted,
        CampaignList,
        CampaignRecord,
        CampaignStats,
        JSONDict,
        Query,
    )


class CampaignsResource:
    """Create, schedule, and run bulk email campaigns.

    A campaign moves through ``DRAFT`` -> ``SENDING`` -> ``SENT``; :meth:`send`
    starts it (optionally at a future time), and :meth:`pause` / :meth:`resume` /
    :meth:`cancel` steer it while in flight. Responses are bare v1 resource
    bodies — there is no ``{success, data}`` envelope to unwrap.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self, query: Query | None = None) -> CampaignList:
        """List campaigns, newest first.

        Accepts ``limit`` (1-100, default 20) and ``after`` (opaque cursor), and
        answers ``{data, has_more, next_cursor}``. Keep the filters identical for
        every page of one walk — changing them invalidates the cursor and the API
        answers 422 ``validation_error`` telling you to restart from the first
        page. :meth:`iter_list` does that bookkeeping for you.
        """
        response: CampaignList = self._client.request(
            method="GET", path="/api/v1/campaigns", query=query
        )
        return response

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every campaign across pages, following the cursor for you."""
        return iterate_cursor(self.list, query)

    def create(self, body: Body, *, idempotency_key: str | None = None) -> CampaignRecord:
        """Create a campaign in ``DRAFT``.

        Requires ``name``, ``subject``, ``body``, ``from`` and ``audience_type``.
        Pass ``idempotency_key`` (1-255 chars) to make a replayed create return
        the original campaign instead of a second one.
        """
        response: CampaignRecord = self._client.request(
            method="POST",
            path="/api/v1/campaigns",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        return response

    def get(self, id: str) -> CampaignRecord:
        """Fetch a single campaign, including its delivery ``stats``."""
        response: CampaignRecord = self._client.request(
            method="GET", path=f"/api/v1/campaigns/{encode_path_segment(id)}"
        )
        return response

    def update(self, id: str, body: Body) -> CampaignRecord:
        """Patch a draft campaign's content or audience."""
        response: CampaignRecord = self._client.request(
            method="PATCH", path=f"/api/v1/campaigns/{encode_path_segment(id)}", body=body
        )
        return response

    def delete(self, id: str) -> CampaignDeleted:
        """Delete a campaign. Returns the ``{id, deleted}`` confirmation body."""
        response: CampaignDeleted = self._client.request(
            method="DELETE", path=f"/api/v1/campaigns/{encode_path_segment(id)}"
        )
        return response

    def send(
        self, id: str, body: Body | None = None, *, idempotency_key: str | None = None
    ) -> CampaignRecord:
        """Send a campaign now, or schedule it.

        Pass ``{"scheduled_for": "<ISO 8601>"}`` as ``body`` to queue it for a
        future time instead of sending immediately. ``idempotency_key`` is the
        guard that matters most on this call: a replayed send must not mail the
        audience twice.
        """
        response: CampaignRecord = self._client.request(
            method="POST",
            path=f"/api/v1/campaigns/{encode_path_segment(id)}/send",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        return response

    def cancel(self, id: str) -> CampaignRecord:
        """Cancel a scheduled or in-flight campaign. Already-sent mail stays sent."""
        response: CampaignRecord = self._client.request(
            method="POST", path=f"/api/v1/campaigns/{encode_path_segment(id)}/cancel"
        )
        return response

    def pause(self, id: str) -> CampaignRecord:
        """Pause an in-flight campaign, holding the remaining recipients."""
        response: CampaignRecord = self._client.request(
            method="POST", path=f"/api/v1/campaigns/{encode_path_segment(id)}/pause"
        )
        return response

    def resume(self, id: str) -> CampaignRecord:
        """Resume a paused campaign from where it stopped."""
        response: CampaignRecord = self._client.request(
            method="POST", path=f"/api/v1/campaigns/{encode_path_segment(id)}/resume"
        )
        return response

    def stats(self, id: str) -> CampaignStats:
        """Delivery and engagement counters plus derived rates for one campaign."""
        response: CampaignStats = self._client.request(
            method="GET", path=f"/api/v1/campaigns/{encode_path_segment(id)}/stats"
        )
        return response
