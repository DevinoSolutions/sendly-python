"""Webhooks resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        Body,
        Query,
        WebhookCallsListResponse,
        WebhookCreateResponse,
        WebhookGetResponse,
        WebhookListResponse,
        WebhookRecord,
        WebhookRotateSecretResponse,
    )


class WebhooksResource:
    """Manage outbound webhook subscriptions and inspect deliveries."""

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
