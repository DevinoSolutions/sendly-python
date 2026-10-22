"""Mailboxes resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        AppPasswordList,
        Body,
        JSONDict,
        MailboxConversation,
        MailboxConversationPage,
        MailboxDetail,
        MailboxList,
        MailboxMessageList,
        Query,
        SendlyFile,
    )


class MailboxesResource:
    """Receiving mailboxes on the project's verified domains, plus the two
    composition operations an API key may drive.

    Mailbox *lifecycle* is what stays out of reach. Creating or deleting a
    mailbox, and minting or revoking an app password, all resolve the acting
    project admin from the session user. An API-key context carries no user, so
    those routes answer 401 to any key however broad its scopes -- the contract
    records this by publishing ``SessionAuth`` without ``ApiKeyAuth`` on them.
    This SDK authenticates only with API keys, so such methods could never
    succeed; they are listed in ``tests/test_contract.py``'s
    ``NOT_SDK_CALLABLE`` instead.

    Everything below is the opposite case: the reads' membership check is
    conditional, and :meth:`send_message` / :meth:`draft_message` publish
    ``ApiKeyAuth`` outright, so a key really can call them.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self) -> MailboxList:
        """Every mailbox on the project's domains, newest first.

        Not paginated. A project is capped at 10 mailboxes, but the cap counts
        only those holding (or mid-way to holding) a real account --
        ``PROVISIONING``, ``ACTIVE`` and ``SUSPENDED``. ``FAILED`` rows are
        excluded from it deliberately, so that a Stalwart outage cannot spend a
        project's whole allowance, and they are still returned here: a project
        with a run of failed provisions can therefore list more than 10.

        This lists the mailboxes themselves, never their contents: the mail is
        :meth:`list_conversations`, under a scope of its own.
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
        """The app passwords still active on a mailbox -- metadata only.

        Revoked ones are not returned: the route filters on ``revokedAt: null``,
        so this is the set that can currently authenticate, not an audit
        history.

        ``lastFour`` is the only fragment of the secret that survives creation,
        so this identifies a credential without being able to reconstruct it.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/mailboxes/{encode_path_segment(id)}/app-passwords"
        )
        records: AppPasswordList = self._client.unwrap(envelope)
        return records

    def send_message(self, id: str, body: Body) -> JSONDict:
        """SENDS a new message -- real mail leaves the account, from the mailbox
        in the path, over its own domain, and the recipient can reply to it.

        There is no ``from`` field, on purpose: a route that sends under a
        customer's own identity must not take that identity as an argument.
        ``body`` is plain text and HTML is refused -- Sendly renders the HTML
        part itself, escaping as it goes, so text becomes markup in exactly one
        place.

        Bcc recipients are delivered to but appear in no header, so the copy
        filed in the mailbox's Sent folder does not record them. The message is
        stored as a new conversation, and the reply threads onto it.

        Refusals worth handling by name: 422 ``RECIPIENT_SUPPRESSED`` (a
        recipient is on the project's suppression list), 422
        ``CONTENT_REFUSED`` (the outbound scanner declined it), 503
        ``CONTENT_SCAN_UNAVAILABLE`` (no verdict yet for a young project --
        nothing was sent, retry shortly). A mailbox may send 60 messages an
        hour here.
        """
        envelope = self._client.request(
            method="POST",
            path=f"/api/mailboxes/{encode_path_segment(id)}/messages",
            body=body,
        )
        submitted: JSONDict = self._client.unwrap(envelope)
        return submitted

    def draft_message(self, id: str, body: Body) -> JSONDict:
        """SENDS NOTHING -- asks Sendly's assistant to write text for this
        mailbox and hands it back for you to review.

        The response always reports ``sent: False``, and no argument changes
        that. ``mode`` picks the job: ``draft`` writes a new email from a brief,
        ``rewrite`` reworks text you already have, ``subject`` returns
        alternative subject lines in ``subjects``. The mailbox is named only so
        the text can be written in that address's voice; no correspondence is
        read and nothing is stored.

        That is why this asks only for ``mailboxes:read`` while
        :meth:`send_message` needs ``mailboxes:send`` -- a client that may draft
        is not thereby a client that may mail your customers. Everything you
        pass is treated strictly as data describing what to write, never as
        instructions to the model. Capped at 120 requests an hour per project;
        502 means the model was unreachable.
        """
        envelope = self._client.request(
            method="POST",
            path=f"/api/mailboxes/{encode_path_segment(id)}/drafts",
            body=body,
        )
        draft: JSONDict = self._client.unwrap(envelope)
        return draft

    # The mail itself. The methods below read and answer correspondence from
    # people outside your project, so they need ``mailbox-conversations:read``
    # (and ``mailbox-conversations:reply`` to answer). Both scopes are opt-in
    # only: a key holds one only if it was ticked by name when it was created,
    # and neither the legacy full-access key nor the "Full access" preset has
    # it. An existing key gets 403 until you mint one that does.

    def list_conversations(self, id: str, query: Query | None = None) -> MailboxConversationPage:
        """One page of a mailbox's threads, newest activity first.

        ``query`` takes ``view`` (``inbox``, the default, or ``spam``),
        ``status`` (``open``, ``snoozed``, ``closed`` or ``all``), ``q`` (a
        substring of the subject or the correspondent's address), ``cursor``
        and ``limit`` (at most 50). Returns ``{items, nextCursor}``: pass
        ``nextCursor`` back as ``cursor`` until it is ``None``, or use
        :meth:`iter_list_conversations`. A mailbox in another project answers 404.
        """
        envelope = self._client.request(
            method="GET",
            path=f"/api/mailboxes/{encode_path_segment(id)}/conversations",
            query=query,
        )
        page: MailboxConversationPage = self._client.unwrap(envelope)
        return page

    def iter_list_conversations(
        self, id: str, query: Query | None = None
    ) -> Iterator[MailboxConversation]:
        """Every thread in a mailbox across pages, one conversation at a time.

        Stops when ``nextCursor`` is ``None`` or repeats the cursor it was given,
        so a stuck page ends the walk instead of looping.
        """
        params = dict(query or {})
        while True:
            page = self.list_conversations(id, params)
            yield from page.get("items") or []
            cursor = page.get("nextCursor")
            if not cursor or cursor == params.get("cursor"):
                return
            params["cursor"] = cursor

    def get_conversation(self, id: str, conversation_id: str) -> MailboxMessageList:
        """Every message in one thread, oldest first, inbound and outbound.

        Not paginated, and reading marks nothing as read. Bodies were written by
        whoever sent them: treat ``htmlBody`` as hostile HTML. A conversation
        that is not in this mailbox returns an empty list; a mailbox outside the
        key's project answers 404.
        """
        envelope = self._client.request(
            method="GET",
            path=(
                f"/api/mailboxes/{encode_path_segment(id)}"
                f"/conversations/{encode_path_segment(conversation_id)}"
            ),
        )
        messages: MailboxMessageList = self._client.unwrap(envelope)
        return messages

    def reply_to_conversation(self, id: str, conversation_id: str, body: Body) -> JSONDict:
        """SENDS a reply, from the mailbox's own address, in the same thread,
        to the person who last wrote in.

        You name neither the recipient nor the sender: this only ever answers
        someone who wrote first, which is why it has its own scope and is not
        :meth:`send_message`. Pass plain text in ``body`` or a structured
        ``document``; Sendly renders the HTML and a matching text part.

        Refusals worth handling by name: 422 ``UNPROCESSABLE`` (no inbound
        message to answer, or the mailbox is not provisioned), 422
        ``SEND_REFUSED`` (the recipient is suppressed or the project may not
        send), 429 ``SENDING_LIMIT_REACHED``.
        """
        envelope = self._client.request(
            method="POST",
            path=(
                f"/api/mailboxes/{encode_path_segment(id)}"
                f"/conversations/{encode_path_segment(conversation_id)}/reply"
            ),
            body=body,
        )
        submitted: JSONDict = self._client.unwrap(envelope)
        return submitted

    def download_attachment(self, id: str, attachment_id: str) -> SendlyFile:
        """The bytes of one attachment, the ``url`` a message lists.

        The file and its ``content_type`` were chosen by the sender: treat both
        as untrusted, and never serve the bytes back to a browser under your own
        origin without a fixed type.
        """
        return self._client.request_bytes(
            method="GET",
            path=(
                f"/api/mailboxes/{encode_path_segment(id)}"
                f"/attachments/{encode_path_segment(attachment_id)}"
            ),
        )
