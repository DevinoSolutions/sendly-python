"""Suppression resource."""

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
        SuppressionCheckResponse,
        SuppressionDeletedV1,
        SuppressionListResponse,
        SuppressionListV1,
        SuppressionRecord,
        SuppressionV1,
    )


class SuppressionResource:
    """Manage the project suppression list — the addresses no send may reach.

    The unsuffixed methods speak legacy ``/api/suppression`` (singular path,
    ``{success, data}`` envelopes); the ``_v1`` methods speak
    ``/api/v1/suppressions`` (plural path, bare bodies, RFC 9457 problem
    documents). Both answer the same question, so the suffix is what stops a
    call site from reaching for one and reading the other's shape.
    """

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

    def list_v1(self, query: Query | None = None) -> SuppressionListV1:
        """List suppressed addresses, newest first.

        Accepts ``limit`` (1-100, default 20), ``after`` (opaque cursor) and
        ``reason``, and answers ``{data, has_more, next_cursor}``. Hold
        ``reason`` steady across one walk: changing it mid-pagination
        invalidates the cursor and the API answers 422 ``validation_error``
        telling you to restart from the first page.
        """
        response: SuppressionListV1 = self._client.request(
            method="GET", path="/api/v1/suppressions", query=query
        )
        return response

    def iter_list_v1(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every suppressed address across pages, following the cursor for you."""
        return iterate_cursor(self.list_v1, query)

    def create_v1(self, body: Body) -> SuppressionV1:
        """Suppress an address, so no further send reaches it.

        Idempotent: an already-suppressed address answers 201 with the existing
        record, and the first ``reason`` wins — a later manual entry must not
        overwrite what an SES bounce recorded. ``source`` is not accepted in the
        body; it is derived from the credential, so a record's provenance cannot
        be dressed up as a deliverability fact.
        """
        response: SuppressionV1 = self._client.request(
            method="POST", path="/api/v1/suppressions", body=body
        )
        return response

    def get_v1(self, email: str) -> SuppressionV1:
        """Fetch the suppression record for one address.

        The answer is definite either way: 200 means suppressed and says why,
        404 ``resource_not_found`` means the address is not on the list. A 200
        may also come from a platform-wide block recorded outside this project.
        """
        response: SuppressionV1 = self._client.request(
            method="GET", path=f"/api/v1/suppressions/{encode_path_segment(email)}"
        )
        return response

    def delete_v1(self, email: str) -> SuppressionDeletedV1:
        """Un-suppress an address: mail can flow to it again. Returns the
        ``{email, deleted}`` confirmation body.

        This is the one call on this surface that can put mail back into an
        inbox that asked you to stop. It does NOT clear AWS SES's own
        account-level suppression list, so an address SES suppressed after a
        hard bounce stays undeliverable through SES even once this record is
        gone. Idempotent: an address that was never suppressed answers 200 too.
        """
        response: SuppressionDeletedV1 = self._client.request(
            method="DELETE", path=f"/api/v1/suppressions/{encode_path_segment(email)}"
        )
        return response
