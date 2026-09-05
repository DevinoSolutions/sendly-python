"""Email validation resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        EmailValidationBatchV1,
        EmailValidationResultListV1,
        EmailValidationRunV1,
        JSONDict,
        Query,
    )


class ValidationResource:
    """Check addresses before you mail them, and read back what a bulk run found.

    Responses are bare ``/api/v1`` bodies -- no ``{success, data}`` envelope --
    and errors are RFC 9457 problem documents.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def validate_emails(self, body: Body) -> EmailValidationBatchV1:
        """Check a batch of addresses. **This is billed per address checked.**

        Every entry in ``emails`` costs money, so looping this over a contact
        list is looping over your invoice. Validate a whole list with the
        background run (``client.lists.start_validation_run``) instead of paging
        it through here.

        At most 50 addresses per call. That ceiling is a latency bound, not a
        payload one: every distinct domain in the batch costs a DNS round trip.

        Branch on each result's ``verdict``, never on the flags -- ``is_personal``
        (Gmail, Outlook) and ``is_role_address`` (``support@``) describe ordinary,
        deliverable addresses that real customers use. A verdict of ``unknown``
        means DNS did not answer in time, so that address was NOT checked; it is
        a separate value from ``undeliverable`` on purpose, and deleting a contact
        on ``unknown`` deletes a live one over a network hiccup.
        """
        response: EmailValidationBatchV1 = self._client.request(
            method="POST", path="/api/v1/email-validations", body=body
        )
        return response

    def get_run(self, id: str) -> EmailValidationRunV1:
        """Fetch a bulk validation run: how far it has got, and what it found.

        The other way a run starts is ``client.lists.start_validation_run``,
        which validates every address on a list in the background and answers
        with the run this method polls. A run is finished when ``status`` is
        ``completed`` or ``failed`` -- never when a percentage reaches 100,
        because there is deliberately no total to divide by: a list changes size
        while a run walks it.
        """
        response: EmailValidationRunV1 = self._client.request(
            method="GET", path=f"/api/v1/validation-runs/{encode_path_segment(id)}"
        )
        return response

    def list_results(self, id: str, query: Query | None = None) -> EmailValidationResultListV1:
        """List one page of a run's verdicts.

        Filter with ``verdict`` -- ``undeliverable`` is the page to read before
        acting on a run, and ``unknown`` is the one never to act on, since those
        addresses were not actually checked.

        This list pages on ``cursor``, not the ``after`` every other v1
        collection takes, and its envelope carries the next page under
        ``cursor`` rather than ``next_cursor``. :meth:`iter_list_results` drives
        that loop for you.
        """
        response: EmailValidationResultListV1 = self._client.request(
            method="GET",
            path=f"/api/v1/validation-runs/{encode_path_segment(id)}/results",
            query=query,
        )
        return response

    def iter_list_results(self, id: str, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every result across pages, one address's verdict at a time.

        Hand-rolled rather than routed through
        :func:`~sendly.resources._pagination.iterate_cursor`: the shared helper
        sends ``after`` and reads ``next_cursor``, and this endpoint speaks
        ``cursor`` on both sides, so the helper would send an ignored parameter
        and re-fetch page one forever. Stops on ``has_more`` false, a null
        cursor, or a cursor the server repeats.
        """
        params: dict[str, Any] = dict(query or {})
        while True:
            page = self.list_results(id, params)
            if not isinstance(page, dict):
                return
            items = page.get("data")
            if not isinstance(items, list):
                return
            yield from items
            if not page.get("has_more"):
                return
            cursor = page.get("cursor")
            if not cursor or cursor == params.get("cursor"):
                return
            params = {**params, "cursor": cursor}
