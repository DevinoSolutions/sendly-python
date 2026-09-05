"""Templates resource."""

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
        TemplateDeletedV1,
        TemplateListResponse,
        TemplateListV1,
        TemplateRecord,
        TemplateV1,
    )


class TemplatesResource:
    """Create and manage reusable email templates, in both dialects.

    The unsuffixed methods speak legacy ``/api/templates`` — ``{success, data}``
    envelopes and camelCase fields. The ``_v1`` methods speak
    ``/api/v1/templates`` — bare bodies, snake_case fields and RFC 9457 problem
    documents. Both answer the same question, so the suffix is what stops a call
    site from reaching for one and reading the other's shape.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def create(self, body: Body) -> TemplateRecord:
        """Create a reusable email template."""
        envelope = self._client.request(method="POST", path="/api/templates", body=body)
        record: TemplateRecord = self._client.unwrap(envelope)
        return record

    def list(self, query: Query | None = None) -> TemplateListResponse:
        """List templates with cursor pagination (``limit``/``cursor``) + optional
        ``emailCategory`` filter."""
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

    def list_v1(self, query: Query | None = None) -> TemplateListV1:
        """List templates, newest first.

        Accepts ``limit`` (1-100, default 20), ``after`` (opaque cursor),
        ``search`` and ``email_category``, and answers
        ``{data, has_more, next_cursor}``. ``search`` matches the NAME only —
        narrower than the dashboard's search, which also reads description and
        subject. Hold the filters steady across one walk: changing them
        mid-pagination invalidates the cursor and the API answers 422
        ``validation_error`` telling you to restart from the first page.
        """
        response: TemplateListV1 = self._client.request(
            method="GET", path="/api/v1/templates", query=query
        )
        return response

    def iter_list_v1(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every template across pages, following the cursor for you."""
        return iterate_cursor(self.list_v1, query)

    def create_v1(self, body: Body) -> TemplateV1:
        """Create a template. ``email_category`` defaults to ``MARKETING``.

        The ``from`` domain must already be a verified sending identity — an
        unverified sender is refused with 403 ``forbidden`` here rather than
        becoming a campaign that fails at send time.
        """
        response: TemplateV1 = self._client.request(
            method="POST", path="/api/v1/templates", body=body
        )
        return response

    def get_v1(self, id: str) -> TemplateV1:
        """Fetch a single template by id."""
        response: TemplateV1 = self._client.request(
            method="GET", path=f"/api/v1/templates/{encode_path_segment(id)}"
        )
        return response

    def update_v1(self, id: str, body: Body) -> TemplateV1:
        """Patch a template. Omitted fields are left alone.

        Touching ``subject``, ``body``, ``from``, ``from_name`` or ``reply_to``
        snapshots the previous content into version history and increments
        ``version``; touching only ``name``, ``description`` or
        ``email_category`` does not, because neither is content a send would
        have rendered.
        """
        response: TemplateV1 = self._client.request(
            method="PATCH", path=f"/api/v1/templates/{encode_path_segment(id)}", body=body
        )
        return response

    def delete_v1(self, id: str) -> TemplateDeletedV1:
        """Delete a template. Returns the ``{id, deleted}`` confirmation body —
        the legacy :meth:`delete` discards it, this one hands it back.

        A template a workflow step or an active campaign (DRAFT, SCHEDULED or
        SENDING) still points at is refused with 409 ``conflict``. Emails
        already sent from it are not erased.
        """
        response: TemplateDeletedV1 = self._client.request(
            method="DELETE", path=f"/api/v1/templates/{encode_path_segment(id)}"
        )
        return response
