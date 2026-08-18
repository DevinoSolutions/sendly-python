"""Lists resource (subscribe / unsubscribe)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import Body, ListSubscribeData, ListUnsubscribeData


class ListsResource:
    """Manage a contact's membership on a subscriber list.

    Both calls accept sending-only (``pk_*``) keys so they can back a public
    subscribe or preference form directly.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def subscribe(self, id: str, body: Body) -> ListSubscribeData:
        """Subscribe an address to a list, creating the contact if needed.

        Requires ``email``. Two behaviours worth knowing before you wire this to
        a form:

        * When the list has double opt-in, the membership is created ``PENDING``
          and the response carries a ``confirmToken``. Sendly does **not** send
          the confirmation email — deliver ``/api/lists/confirm?token=<token>``
          to the contact yourself.
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
