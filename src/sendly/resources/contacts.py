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
        ContactFieldList,
        ContactFieldUsage,
        ContactFieldValues,
        ContactImportAccepted,
        ContactListResponse,
        ContactListV1,
        ContactLookupResult,
        ContactRecord,
        ContactTopicPreferencesV1,
        ContactV1,
        DownloadLink,
        JSONDict,
        Query,
        QueuedResult,
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

    # The methods below are the legacy ``/api/contacts`` operations beyond CRUD:
    # bulk actions that run as background jobs, custom-field management, CSV
    # import and export, lookup and GDPR erasure. They speak the ``{success, data}``
    # dialect, which the SDK unwraps.

    def queue_bulk_delete(self, body: Body) -> QueuedResult:
        """Queue the deletion of up to 1000 contacts. Needs ``contacts:write``.

        ``body`` is ``{"contactIds": [...]}`` and the delete runs in the
        background (the API answers 202 with a confirmation, not a count). This is
        the queued sibling of :meth:`bulk_delete`, which deletes synchronously.
        """
        envelope = self._client.request(method="POST", path="/api/contacts/bulk-delete", body=body)
        queued: QueuedResult = self._client.unwrap(envelope)
        return queued

    def queue_bulk_purge(self, body: Body) -> QueuedResult:
        """Queue the GDPR erasure of up to 1000 contacts. Needs ``contacts:write``.

        ``body`` is ``{"contactIds": [...]}``. Each contact, its events and its
        history are erased and its address is globally suppressed so no project
        can mail it again. Runs in the background and CANNOT be undone.
        """
        envelope = self._client.request(method="POST", path="/api/contacts/bulk-purge", body=body)
        queued: QueuedResult = self._client.unwrap(envelope)
        return queued

    def queue_bulk_subscribe(self, body: Body) -> QueuedResult:
        """Queue resubscribing up to 1000 contacts (``{"contactIds": [...]}``).

        Needs ``contacts:write``. Runs in the background.
        """
        envelope = self._client.request(
            method="POST", path="/api/contacts/bulk-subscribe", body=body
        )
        queued: QueuedResult = self._client.unwrap(envelope)
        return queued

    def queue_bulk_unsubscribe(self, body: Body) -> QueuedResult:
        """Queue unsubscribing up to 1000 contacts (``{"contactIds": [...]}``).

        Needs ``contacts:write``. Runs in the background.
        """
        envelope = self._client.request(
            method="POST", path="/api/contacts/bulk-unsubscribe", body=body
        )
        queued: QueuedResult = self._client.unwrap(envelope)
        return queued

    def export_link(self, query: Query | None = None) -> DownloadLink:
        """A one-time link a person opens to download the project's contacts as CSV.

        Needs ``contacts:read``. ``query`` takes ``search`` (part of an email
        address) and ``subscribed`` (``true`` or ``false``). The link is
        single-use and lives 15 minutes; the SDK hands it back as
        ``{status, url, expires_in, what, instruction}`` and never downloads the
        file itself.
        """
        response: DownloadLink = self._client.request(
            method="GET", path="/api/contacts/export", query=query
        )
        return response

    def list_fields(self) -> ContactFieldList:
        """The custom contact fields the project uses: ``{fields, count}``."""
        envelope = self._client.request(method="GET", path="/api/contacts/fields")
        fields: ContactFieldList = self._client.unwrap(envelope)
        return fields

    def get_field_usage(self, field: str) -> ContactFieldUsage:
        """Which segments, templates and workflows use a custom field.

        Check this before :meth:`delete_field`.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/contacts/fields/{encode_path_segment(field)}/usage"
        )
        usage: ContactFieldUsage = self._client.unwrap(envelope)
        return usage

    def list_field_values(self, field: str, query: Query | None = None) -> ContactFieldValues:
        """The distinct values stored in a custom field: ``{field, values, count, limit}``.

        ``query`` takes ``limit`` (default 100, at most 200).
        """
        envelope = self._client.request(
            method="GET",
            path=f"/api/contacts/fields/{encode_path_segment(field)}/values",
            query=query,
        )
        values: ContactFieldValues = self._client.unwrap(envelope)
        return values

    def delete_field(self, field: str) -> QueuedResult:
        """Remove a custom field and its values from EVERY contact.

        Needs ``contacts:write``. The rewrite runs in the background, so the API
        answers 202 ``{status: "queued"}`` rather than a count. Use
        :meth:`get_field_usage` first.
        """
        envelope = self._client.request(
            method="DELETE", path=f"/api/contacts/fields/{encode_path_segment(field)}"
        )
        queued: QueuedResult = self._client.unwrap(envelope)
        return queued

    def import_csv(
        self, csv: bytes | str, *, filename: str = "contacts.csv"
    ) -> ContactImportAccepted:
        """Queue a CSV import (at most 5 MB). Needs ``contacts:write``.

        The first row is the header and must include an ``email`` column; other
        columns become custom fields. Sent as ``multipart/form-data`` under the
        field ``file``, and the part is sent as ``text/csv`` (the API accepts a ``.csv`` filename or that type). An unimportable file
        or one over the plan's row ceiling is refused up front with 400; a good
        one answers 202 and the contacts appear as the background job finishes.
        """
        data = csv.encode("utf-8") if isinstance(csv, str) else csv
        envelope = self._client.request(
            method="POST",
            path="/api/contacts/import",
            files={"file": (filename, data, "text/csv")},
        )
        accepted: ContactImportAccepted = self._client.unwrap(envelope)
        return accepted

    def lookup(self, body: Body) -> ContactLookupResult:
        """Which of up to 500 email addresses already exist: ``{found, notFound}``.

        ``body`` is ``{"emails": [...]}``. Needs ``contacts:read``.
        """
        envelope = self._client.request(method="POST", path="/api/contacts/lookup", body=body)
        result: ContactLookupResult = self._client.unwrap(envelope)
        return result

    def purge(self, id: str) -> JSONDict:
        """GDPR erasure of one contact: the contact, every event about them and
        their message history are deleted and the address is globally suppressed.

        Needs ``contacts:write``. Returns ``{id}``. CANNOT be undone -- use
        :meth:`delete` to remove a contact without blocking the address.
        """
        envelope = self._client.request(
            method="POST", path=f"/api/contacts/{encode_path_segment(id)}/purge"
        )
        purged: JSONDict = self._client.unwrap(envelope)
        return purged
