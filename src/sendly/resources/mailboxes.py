"""Mailboxes resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import AppPasswordList, MailboxDetail, MailboxList


class MailboxesResource:
    """Receiving mailboxes on the project's verified domains.

    Read only, and deliberately so. Creating or deleting a mailbox, and minting
    or revoking an app password, all resolve the acting project admin from the
    session user. An API-key context carries no user, so those routes answer
    401 to any key however broad its scopes -- the contract records this by
    publishing ``SessionAuth`` without ``ApiKeyAuth`` on them. This SDK
    authenticates only with API keys, so such methods could never succeed; they
    are listed in ``tests/test_contract.py``'s ``NOT_SDK_CALLABLE`` instead.

    The three reads below are the opposite case: their membership check is
    conditional, so a key really can call them.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self) -> MailboxList:
        """Every mailbox on the project's domains, newest first.

        Not paginated -- a project may hold at most 10 mailboxes. This lists the
        mailboxes themselves, never their contents: received messages are not
        part of the public API.
        """
        envelope = self._client.request(method="GET", path="/api/mailboxes")
        records: MailboxList = self._client.unwrap(envelope)
        return records

    def get(self, id: str) -> MailboxDetail:
        """One mailbox, with the IMAP/SMTP host, port and username to connect with.

        The password is not included and is never returned here -- mailbox
        credentials are app passwords, created from the dashboard and shown once.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/mailboxes/{encode_path_segment(id)}"
        )
        detail: MailboxDetail = self._client.unwrap(envelope)
        return detail

    def list_app_passwords(self, id: str) -> AppPasswordList:
        """The app passwords issued for a mailbox -- metadata only.

        ``lastFour`` is the only fragment of the secret that survives creation,
        so this identifies a credential without being able to reconstruct it.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/mailboxes/{encode_path_segment(id)}/app-passwords"
        )
        records: AppPasswordList = self._client.unwrap(envelope)
        return records
