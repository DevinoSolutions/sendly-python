"""Emails resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment, idempotency_headers

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        BatchSendResponse,
        Body,
        EmailGetResponse,
        EmailListResponse,
        Query,
        SendEmailData,
        SuccessEmpty,
    )


class EmailsResource:
    """Send and manage transactional emails."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def send(
        self, body: Body, *, idempotency_key: str | None = None
    ) -> SendEmailData | list[SendEmailData]:
        """Send a single transactional email.

        Pass ``idempotency_key`` (1-255 chars) to dedupe replays for 24h.
        """
        envelope = self._client.request(
            method="POST",
            path="/api/emails",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        data: SendEmailData | list[SendEmailData] = self._client.unwrap(envelope)
        return data

    def batch(self, body: Body, *, idempotency_key: str | None = None) -> BatchSendResponse:
        """Send a batch (up to 100) of transactional emails in one call."""
        response: BatchSendResponse = self._client.request(
            method="POST",
            path="/api/emails/batch",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        return response

    def list(self, query: Query | None = None) -> EmailListResponse:
        """List emails with cursor-based pagination + filters."""
        response: EmailListResponse = self._client.request(
            method="GET", path="/api/emails", query=query
        )
        return response

    def get(self, id: str) -> EmailGetResponse:
        """Fetch a single email and its delivery events."""
        response: EmailGetResponse = self._client.request(
            method="GET", path=f"/api/emails/{encode_path_segment(id)}"
        )
        return response

    def cancel_schedule(self, id: str) -> SuccessEmpty:
        """Cancel a scheduled (PENDING) email before it fires."""
        response: SuccessEmpty = self._client.request(
            method="DELETE", path=f"/api/emails/{encode_path_segment(id)}/schedule"
        )
        return response
