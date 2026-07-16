"""Contacts resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment, idempotency_headers

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        Body,
        ContactListResponse,
        ContactRecord,
        JSONDict,
        Query,
    )


class ContactsResource:
    """Create, query, and manage contacts."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def create(self, body: Body, *, idempotency_key: str | None = None) -> ContactRecord:
        """Create a new contact (fails on duplicate)."""
        envelope = self._client.request(
            method="POST",
            path="/api/contacts",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        record: ContactRecord = self._client.unwrap(envelope)
        return record

    def upsert(self, body: Body, *, idempotency_key: str | None = None) -> ContactRecord:
        """Insert or update a contact identified by email."""
        envelope = self._client.request(
            method="POST",
            path="/api/contacts/upsert",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        record: ContactRecord = self._client.unwrap(envelope)
        return record

    def bulk_create(self, body: Body, *, idempotency_key: str | None = None) -> JSONDict:
        """Bulk-create contacts (up to API limit). Returns per-row results."""
        response: JSONDict = self._client.request(
            method="POST",
            path="/api/contacts/bulk",
            body=body,
            headers=idempotency_headers(idempotency_key),
        )
        return response

    def bulk_delete(self, body: Body) -> JSONDict:
        """Bulk-delete contacts by id or email."""
        response: JSONDict = self._client.request(
            method="DELETE", path="/api/contacts/bulk", body=body
        )
        return response

    def list(self, query: Query | None = None) -> ContactListResponse:
        """List contacts with search + cursor pagination."""
        response: ContactListResponse = self._client.request(
            method="GET", path="/api/contacts", query=query
        )
        return response

    def get(self, id: str) -> ContactRecord:
        """Fetch a single contact by id."""
        envelope = self._client.request(
            method="GET", path=f"/api/contacts/{encode_path_segment(id)}"
        )
        record: ContactRecord = self._client.unwrap(envelope)
        return record

    def update(self, id: str, body: Body) -> ContactRecord:
        """Patch a contact (partial update of ``data``, ``subscribed``, etc.)."""
        envelope = self._client.request(
            method="PATCH", path=f"/api/contacts/{encode_path_segment(id)}", body=body
        )
        record: ContactRecord = self._client.unwrap(envelope)
        return record

    def delete(self, id: str) -> None:
        """Delete a contact. Returns ``None`` (the API responds 200 with the
        deleted contact's id)."""
        self._client.request(
            method="DELETE", path=f"/api/contacts/{encode_path_segment(id)}", no_content=True
        )
