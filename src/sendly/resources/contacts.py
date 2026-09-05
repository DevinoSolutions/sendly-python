"""Contacts resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment, idempotency_headers
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        ContactDeletedV1,
        ContactListResponse,
        ContactListV1,
        ContactRecord,
        ContactTopicPreferencesV1,
        ContactV1,
        JSONDict,
        Query,
    )


class ContactsResource:
    """Create, query, and manage contacts, on both surfaces.

    The unsuffixed methods speak the legacy ``/api/*`` dialect — camelCase
    bodies inside a ``{success, data}`` envelope the SDK unwraps. The
    ``_v1``-suffixed methods speak ``/api/v1``: bare snake_case bodies, cursor
    pagination, and RFC 9457 problem documents on error. Both answer the same
    questions, so the suffix is there to keep a call site from confusing one for
    the other.
    """

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

    def list_v1(self, query: Query | None = None) -> ContactListV1:
        """List contacts on the ``/api/v1`` surface.

        Accepts ``limit`` (1-100, default 20), ``after`` (opaque cursor),
        ``search`` (case-insensitive substring on the address) and
        ``subscribed`` (the string ``"true"`` or ``"false"``), and answers
        ``{data, has_more, next_cursor}``. Hold the filters steady across one
        walk — the cursor encodes them, and changing one mid-pagination is
        answered with 422 ``validation_error`` telling you to restart from the
        first page.
        """
        response: ContactListV1 = self._client.request(
            method="GET", path="/api/v1/contacts", query=query
        )
        return response

    def iter_list_v1(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every v1 contact across pages, following the cursor for you."""
        return iterate_cursor(self.list_v1, query)

    def create_v1(self, body: Body) -> ContactV1:
        """Create a contact. Requires ``email``.

        ``subscribed`` defaults to true server-side, and ``custom_fields`` is
        arbitrary JSON that templates read back as ``{{ variables }}``.
        """
        response: ContactV1 = self._client.request(
            method="POST", path="/api/v1/contacts", body=body
        )
        return response

    def get_v1(self, id: str) -> ContactV1:
        """Fetch a single contact by id.

        v1 has no lookup-by-address route — reach a contact you only know the
        email of through :meth:`list_v1`'s ``search`` filter.
        """
        response: ContactV1 = self._client.request(
            method="GET", path=f"/api/v1/contacts/{encode_path_segment(id)}"
        )
        return response

    def update_v1(self, id: str, body: Body) -> ContactV1:
        """Patch a contact's ``subscribed`` flag or ``custom_fields``.

        ``email`` is deliberately not patchable: an address is the contact's
        identity on this surface, and rewriting it in place would change who
        every earlier send was addressed to. Create the new address instead.

        ``custom_fields`` is **replaced, not merged** — the object you send
        becomes the whole of it, so read the contact and send back every key you
        mean to keep. A partial object silently drops the rest.
        """
        response: ContactV1 = self._client.request(
            method="PATCH", path=f"/api/v1/contacts/{encode_path_segment(id)}", body=body
        )
        return response

    def delete_v1(self, id: str) -> ContactDeletedV1:
        """Delete a contact, returning the ``{id, deleted}`` confirmation body.

        Unlike the legacy :meth:`delete`, the acknowledgement is handed back
        rather than discarded.
        """
        response: ContactDeletedV1 = self._client.request(
            method="DELETE", path=f"/api/v1/contacts/{encode_path_segment(id)}"
        )
        return response

    def topic_preferences(self, id: str) -> ContactTopicPreferencesV1:
        """Read everything this contact has said about what they want.

        The top-level ``subscribed`` is the global marketing opt-out and
        outranks every topic: false means no marketing reaches them whatever the
        topic rows say. Each topic's own ``subscribed`` is the effective answer
        the send path reaches today, with the topic's ``default_opt_in`` already
        folded in, so a contact who has never answered still reads correctly.
        """
        response: ContactTopicPreferencesV1 = self._client.request(
            method="GET", path=f"/api/v1/contacts/{encode_path_segment(id)}/topics"
        )
        return response
