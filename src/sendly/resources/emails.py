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

    def send(self, body: Body, *, idempotency_key: str | None = None) -> EmailV1:
        """Send one transactional email.

        Posts to the versioned ``POST /api/v1/emails`` and returns the bare
        receipt it answers 202 with: ``{id, status, to, from}``. ``status`` is a
        real delivery state -- poll ``emails.get(id)`` for the events behind
        it. Takes a single recipient; use ``cc``/``bcc`` to copy others.

        Pass ``idempotency_key`` (1-255 chars) to dedupe replays for 24h.

        Before 1.0 this posted to the legacy ``POST /api/emails``, which
        answered with row ids and no delivery status and fanned an array
        ``to`` out to several recipients. That behaviour is
        :meth:`send_legacy`, unchanged.
        """
        response: EmailV1 = self._client.request(
            method="POST",
            path="/api/v1/emails",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        return response

    def send_legacy(
        self, body: Body, *, idempotency_key: str | None = None
    ) -> SendEmailData | list[SendEmailData]:
        """The pre-1.0 :meth:`send`: the legacy ``POST /api/emails``.

        Returns the envelope's ``data``, ``{emails, timestamp}``, where
        ``emails`` has one entry per recipient (an array ``to`` fans out to
        several). Each entry is ``{contact: {id, email}, email}`` -- ``email``
        being the id of the queued email record for that recipient. Reports no
        delivery status of its own.

        Kept as the escape hatch for a caller that depends on the fan-out or on
        the envelope shape. New code should use :meth:`send`.
        """
        envelope = self._client.request(
            method="POST",
            path="/api/emails",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        data: SendEmailData | list[SendEmailData] = self._client.unwrap(envelope)
        return data

    def send_test(self, body: Body) -> EmailTestV1:
        """Send a test email from the project's sandbox address.

        Goes nowhere real: the sandbox address is the SENDER, resolved
        server-side (naming a ``from`` is refused), and the mail lands in the
        project owner's own verified inbox. This exercises rendering and the
        send path without touching a live recipient or a sending reputation.
        Read ``projects.get()["sandbox_address"]`` to know what it sends from
        -- the response's ``sandbox: true`` says only that it was one.
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
