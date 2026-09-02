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
        EmailTestV1,
        EmailV1,
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

    def send_v1(self, body: Body, *, idempotency_key: str | None = None) -> EmailV1:
        """Send one email on the versioned ``/api/v1`` surface, reporting status.

        ADDITIVE -- :meth:`send` is untouched and still posts to the legacy
        ``/api/emails``. The two differ in what they can tell you: the legacy
        send answers with row ids and no status, so a caller cannot learn
        whether the message went anywhere; this one answers 202 with
        ``{id, status, to, from}`` where ``status`` is a real delivery state.
        It also takes a single recipient (use ``cc``/``bcc`` to copy others)
        rather than fanning an array out.

        Repointing :meth:`send` here would change what existing callers receive,
        so it is deliberately not done as part of adding this. Which one becomes
        the default is a breaking-change decision.
        """
        response: EmailV1 = self._client.request(
            method="POST",
            path="/api/v1/emails",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        return response

    def send_test_v1(self, body: Body) -> EmailTestV1:
        """Send a test email to the project's sandbox address.

        Goes nowhere real: delivery is to the sandbox, so this exercises
        rendering and the send path without touching a live recipient or a
        sending reputation. Read ``projects.get()["sandbox_address"]`` to know
        where it lands -- the response's ``sandbox: true`` says only that it was
        one.
        """
        response: EmailTestV1 = self._client.request(
            method="POST", path="/api/v1/emails/test", body=body
        )
        return response

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
