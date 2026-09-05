"""Webhooks resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        JSONDict,
        Query,
        WebhookCallsListResponse,
        WebhookCreatedV1,
        WebhookCreateResponse,
        WebhookDeletedV1,
        WebhookGetResponse,
        WebhookListResponse,
        WebhookListV1,
        WebhookRecord,
        WebhookRotateSecretResponse,
        WebhookSecretRotatedV1,
        WebhookV1,
    )


class WebhooksResource:
    """Manage outbound webhook subscriptions and inspect deliveries.

    The unsuffixed methods speak the legacy ``/api/*`` dialect -- camelCase
    bodies inside a ``{success, data}`` envelope the SDK unwraps. The
    ``_v1``-suffixed methods speak ``/api/v1``: bare snake_case bodies, cursor
    pagination, and RFC 9457 problem documents on error. Both answer the same
    questions, so the suffix is there to keep a call site from confusing one for
    the other.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def create(self, body: Body) -> WebhookCreateResponse:
        """Create a new outbound webhook subscription.

        The response includes the signing secret — store it now, it is only
        returned in full at creation and rotation time.
        """
        response: WebhookCreateResponse = self._client.request(
            method="POST", path="/api/webhooks", body=body
        )
        return response

    def list(self) -> WebhookListResponse:
        """List all webhooks for the project."""
        response: WebhookListResponse = self._client.request(method="GET", path="/api/webhooks")
        return response

    def get(self, id: str) -> WebhookGetResponse:
        """Fetch a single webhook (without its signing secret)."""
        response: WebhookGetResponse = self._client.request(
            method="GET", path=f"/api/webhooks/{encode_path_segment(id)}"
        )
        return response

    def update(self, id: str, body: Body) -> WebhookRecord:
        """Patch a webhook (URL, event types, active flag)."""
        envelope = self._client.request(
            method="PATCH", path=f"/api/webhooks/{encode_path_segment(id)}", body=body
        )
        record: WebhookRecord = self._client.unwrap(envelope)
        return record

    def delete(self, id: str) -> None:
        """Delete a webhook."""
        self._client.request(method="DELETE", path=f"/api/webhooks/{encode_path_segment(id)}")

    def rotate_secret(self, id: str) -> WebhookRotateSecretResponse:
        """Rotate the webhook signing secret. The response contains the new secret."""
        response: WebhookRotateSecretResponse = self._client.request(
            method="POST", path=f"/api/webhooks/{encode_path_segment(id)}/rotate-secret"
        )
        return response

    def list_calls(self, id: str, query: Query | None = None) -> WebhookCallsListResponse:
        """List recent delivery attempts for a webhook."""
        response: WebhookCallsListResponse = self._client.request(
            method="GET", path=f"/api/webhooks/{encode_path_segment(id)}/calls", query=query
        )
        return response

    def list_v1(self, query: Query | None = None) -> WebhookListV1:
        """List webhook endpoints, newest first.

        Accepts ``limit`` (1-100, default 20) and ``after`` (opaque cursor), and
        answers ``{data, has_more, next_cursor}``. :meth:`iter_list_v1` drives
        that walk for you. Signing secrets are not on this response -- see
        :meth:`rotate_secret_v1` if you have lost one.
        """
        response: WebhookListV1 = self._client.request(
            method="GET", path="/api/v1/webhooks", query=query
        )
        return response

    def iter_list_v1(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every webhook endpoint across pages, following the cursor for you."""
        return iterate_cursor(self.list_v1, query)

    def create_v1(self, body: Body) -> WebhookCreatedV1:
        """Register an endpoint to receive HMAC-signed deliveries.

        Requires ``url`` and a non-empty ``event_types``. Returns
        ``{webhook, secret}``, and this is one of only two calls that ever carry
        the signing secret -- :meth:`rotate_secret_v1` is the other. It is shown
        exactly once: no read endpoint returns it, so store it now, because a
        secret you lose is replaced by rotating rather than recovered. Feed it
        to :func:`sendly.verify_signature` to authenticate the deliveries that
        arrive at your endpoint.
        """
        response: WebhookCreatedV1 = self._client.request(
            method="POST", path="/api/v1/webhooks", body=body
        )
        return response

    def get_v1(self, id: str) -> WebhookV1:
        """Fetch one webhook endpoint. The signing secret is not on this response."""
        response: WebhookV1 = self._client.request(
            method="GET", path=f"/api/v1/webhooks/{encode_path_segment(id)}"
        )
        return response

    def update_v1(self, id: str, body: Body) -> WebhookV1:
        """Patch a webhook endpoint. Omitted fields are left alone.

        ``event_types`` REPLACES the stored subscription list rather than
        merging into it, so an event you omit is unsubscribed. Setting
        ``status`` back to ``ACTIVE`` from ``DISABLED`` also clears the
        consecutive-failure counter, so an auto-disabled endpoint gets a clean
        slate. The signing secret is untouched by an update, and is not on this
        response.
        """
        response: WebhookV1 = self._client.request(
            method="PATCH", path=f"/api/v1/webhooks/{encode_path_segment(id)}", body=body
        )
        return response

    def delete_v1(self, id: str) -> WebhookDeletedV1:
        """Delete a webhook endpoint, and its delivery history with it.

        A delivery attempt is a fact about this endpoint and means nothing once
        the endpoint is gone. Returns the ``{id, deleted}`` confirmation body.
        Deliveries already in flight are not recalled, so the endpoint may still
        receive an event shortly after this returns.
        """
        response: WebhookDeletedV1 = self._client.request(
            method="DELETE", path=f"/api/v1/webhooks/{encode_path_segment(id)}"
        )
        return response

    def rotate_secret_v1(self, id: str) -> WebhookSecretRotatedV1:
        """Mint a fresh signing secret for an endpoint.

        The new plaintext is returned exactly once, here -- this and
        :meth:`create_v1` are the only two responses that ever carry the secret,
        and no read endpoint hands it back, so store it now and give it to
        :func:`sendly.verify_signature`. A secret you lose is replaced by
        rotating again rather than recovered.

        The outgoing secret is not cut off at once: it keeps verifying until
        ``previous_secret_expires_at``, and every delivery inside that window
        carries BOTH signatures, so a verifier can be redeployed without
        dropping an event. Past that moment the old secret starts being rejected
        -- as does the older of two secrets if you rotate twice inside the
        window, because only one previous secret is ever live. ``url``,
        ``event_types`` and ``status`` are unchanged.
        """
        response: WebhookSecretRotatedV1 = self._client.request(
            method="POST", path=f"/api/v1/webhooks/{encode_path_segment(id)}/rotate-secret"
        )
        return response
