"""Templates resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        Body,
        Query,
        TemplateListResponse,
        TemplateRecord,
    )


class TemplatesResource:
    """Create and manage reusable email templates."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def create(self, body: Body) -> TemplateRecord:
        """Create a reusable email template."""
        envelope = self._client.request(method="POST", path="/api/templates", body=body)
        record: TemplateRecord = self._client.unwrap(envelope)
        return record

    def list(self, query: Query | None = None) -> TemplateListResponse:
        """List templates with cursor pagination (``limit``/``cursor``) + optional
        type filter."""
        response: TemplateListResponse = self._client.request(
            method="GET", path="/api/templates", query=query
        )
        return response

    def get(self, id: str) -> TemplateRecord:
        """Fetch a single template by id."""
        envelope = self._client.request(
            method="GET", path=f"/api/templates/{encode_path_segment(id)}"
        )
        record: TemplateRecord = self._client.unwrap(envelope)
        return record

    def update(self, id: str, body: Body) -> TemplateRecord:
        """Patch an existing template."""
        envelope = self._client.request(
            method="PATCH", path=f"/api/templates/{encode_path_segment(id)}", body=body
        )
        record: TemplateRecord = self._client.unwrap(envelope)
        return record

    def delete(self, id: str) -> None:
        """Delete a template. Returns ``None`` (the API responds 200 with the
        deleted template's id); raises :class:`SendlyConflictError` if the
        template is still referenced."""
        self._client.request(
            method="DELETE", path=f"/api/templates/{encode_path_segment(id)}", no_content=True
        )
