"""Lists resource (subscribe / unsubscribe)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        EmailValidationRunV1,
        JSONDict,
        ListDeletedV1,
        ListListV1,
        ListSubscribeData,
        ListUnsubscribeData,
        ListV1,
        Query,
    )


class ListsResource:
    """Subscriber lists, on both surfaces.

    :meth:`subscribe` and :meth:`unsubscribe` manage one contact's membership
    over the legacy ``/api/*`` dialect (camelCase inside a ``{success, data}``
    envelope the SDK unwraps) and accept sending-only (``pk_*``) keys, so they
    can back a public subscribe or preference form directly. The
    ``_v1``-suffixed methods manage the lists themselves over ``/api/v1``: bare
    snake_case bodies and RFC 9457 problem documents. Both dialects describe the
    same lists, so the suffix is there to keep a call site from confusing one for
    the other.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def subscribe(self, id: str, body: Body) -> ListSubscribeData:
        """Subscribe an address to a list, creating the contact if needed.

        Requires ``email``. Two behaviours worth knowing before you wire this to
        a form:

        * When the list has double opt-in, the membership is created ``PENDING``
          and the response carries a ``confirmToken``. Sendly does **not** send
          the confirmation email — deliver
          ``/api/lists/confirm-subscription?token=<token>`` to the contact
          yourself.
        * Re-subscribing an address that previously opted out fails with
          ``409 RESUBSCRIBE_CONFIRMATION_REQUIRED`` unless the body sets
          ``allowResubscribe: true``. Read ``previousStatus`` rather than
          ``created`` to describe the transition back to the user.
        """
        envelope = self._client.request(
            method="POST",
            path=f"/api/lists/{encode_path_segment(id)}/subscribe",
            body=body,
        )
        data: ListSubscribeData = self._client.unwrap(envelope)
        return data

    def unsubscribe(self, id: str, body: Body) -> ListUnsubscribeData:
        """Mark an address's membership on this list ``UNSUBSCRIBED``.

        Requires ``email``. Idempotent — unsubscribing an address that is not a
        member succeeds.
        """
        envelope = self._client.request(
            method="POST",
            path=f"/api/lists/{encode_path_segment(id)}/unsubscribe",
            body=body,
        )
        data: ListUnsubscribeData = self._client.unwrap(envelope)
        return data

    def list_v1(self, query: Query | None = None) -> ListListV1:
        """List the project's subscriber lists on the ``/api/v1`` surface.

        Accepts ``limit`` (1-100, default 20) and ``after`` (opaque cursor), and
        answers ``{data, has_more, next_cursor}``. Hold the arguments steady
        across one walk — changing them mid-pagination invalidates the cursor
        and the API answers 422 ``validation_error`` telling you to restart from
        the first page.
        """
        response: ListListV1 = self._client.request(method="GET", path="/api/v1/lists", query=query)
        return response

    def iter_list_v1(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every list across pages, following the cursor for you."""
        return iterate_cursor(self.list_v1, query)

    def create_v1(self, body: Body) -> ListV1:
        """Create a list. Requires ``name``; ``double_opt_in`` defaults to false.

        Turning double opt-in on does not make Sendly send anything — it only
        changes :meth:`subscribe` to create the membership ``PENDING`` and hand
        back the ``confirmToken`` your application delivers.
        """
        response: ListV1 = self._client.request(method="POST", path="/api/v1/lists", body=body)
        return response

    def get_v1(self, id: str) -> ListV1:
        """Fetch a single list.

        ``member_count`` counts memberships in *any* status, ``PENDING`` and
        ``UNSUBSCRIBED`` included, so it is not the size of the audience a
        campaign would reach.
        """
        response: ListV1 = self._client.request(
            method="GET", path=f"/api/v1/lists/{encode_path_segment(id)}"
        )
        return response

    def update_v1(self, id: str, body: Body) -> ListV1:
        """Patch a list's name, description, opt-in mode, confirmation template,
        or redirect URL.

        Only the fields you send are changed; ``member_count`` is derived and
        never accepted here.
        """
        response: ListV1 = self._client.request(
            method="PATCH", path=f"/api/v1/lists/{encode_path_segment(id)}", body=body
        )
        return response

    def delete_v1(self, id: str) -> ListDeletedV1:
        """Delete a list, returning the ``{id, deleted}`` confirmation body.

        Removes the list, not the contacts on it.
        """
        response: ListDeletedV1 = self._client.request(
            method="DELETE", path=f"/api/v1/lists/{encode_path_segment(id)}"
        )
        return response

    def start_validation_run(self, id: str) -> EmailValidationRunV1:
        """Start a bulk address-validation run over the list's members.

        **Billed per address checked**, so starting a run over a large list
        costs real money every time — it is not a free refresh. Answers 202 with
        the run in ``pending``; read its progress and counts back with
        ``validation.get_run``.
        """
        response: EmailValidationRunV1 = self._client.request(
            method="POST", path=f"/api/v1/lists/{encode_path_segment(id)}/validation-runs"
        )
        return response
