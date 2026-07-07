"""Suppression resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        Body,
        Query,
        SuppressionCheckResponse,
        SuppressionListResponse,
        SuppressionRecord,
    )


class SuppressionResource:
    """Manage the project suppression list."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def add(self, body: Body) -> SuppressionRecord:
        """Add an email to the project suppression list."""
        envelope = self._client.request(method="POST", path="/api/suppression", body=body)
        record: SuppressionRecord = self._client.unwrap(envelope)
        return record

    def list(self, query: Query | None = None) -> SuppressionListResponse:
        """List suppressions with optional reason filter + cursor pagination."""
        response: SuppressionListResponse = self._client.request(
            method="GET", path="/api/suppression", query=query
        )
        return response

    def get(self, email: str) -> SuppressionCheckResponse:
        """Check whether a given email is suppressed."""
        response: SuppressionCheckResponse = self._client.request(
            method="GET", path=f"/api/suppression/{encode_path_segment(email)}"
        )
        return response

    def remove(self, email: str) -> None:
        """Remove an email from the suppression list. Returns 204."""
        self._client.request(
            method="DELETE",
            path=f"/api/suppression/{encode_path_segment(email)}",
            no_content=True,
        )
