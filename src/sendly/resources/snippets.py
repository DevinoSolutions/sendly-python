"""Snippets resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        Body,
        Query,
        SnippetListResponse,
        SnippetRecord,
    )


class SnippetsResource:
    """Reusable body fragments a template pulls in with ``{{> name}}``.

    Legacy dialect: ``{success, data}`` envelopes and camelCase fields. Gated by
    the same ``templates:*`` scopes as the templates that include them, because
    a snippet is part of a template body rather than a resource with an audience
    of its own.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def create(self, body: Body) -> SnippetRecord:
        """Create a snippet. Requires ``name`` and ``body``.

        ``name`` is the literal identifier templates include with ``{{> name}}``
        and is unique within the project, so a clash raises
        :class:`SendlyConflictError`.
        """
        envelope = self._client.request(method="POST", path="/api/snippets", body=body)
        record: SnippetRecord = self._client.unwrap(envelope)
        return record

    def list(self, query: Query | None = None) -> SnippetListResponse:
        """List snippets with cursor pagination (``limit``/``cursor``) + optional
        ``search`` over name and description."""
        response: SnippetListResponse = self._client.request(
            method="GET", path="/api/snippets", query=query
        )
        return response

    def get(self, id: str) -> SnippetRecord:
        """Fetch a single snippet by id."""
        envelope = self._client.request(
            method="GET", path=f"/api/snippets/{encode_path_segment(id)}"
        )
        record: SnippetRecord = self._client.unwrap(envelope)
        return record

    def update(self, id: str, body: Body) -> SnippetRecord:
        """Patch an existing snippet."""
        envelope = self._client.request(
            method="PATCH", path=f"/api/snippets/{encode_path_segment(id)}", body=body
        )
        record: SnippetRecord = self._client.unwrap(envelope)
        return record

    def delete(self, id: str) -> None:
        """Delete a snippet. Returns ``None`` (the API responds 200 with the
        deleted snippet's id). Templates that still include it keep rendering --
        an absent snippet renders as an empty string, like an absent variable."""
        self._client.request(
            method="DELETE", path=f"/api/snippets/{encode_path_segment(id)}", no_content=True
        )
