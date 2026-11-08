"""Cross-mailbox inbox resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._pagination import iterate_legacy_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import InboxConversationPage, JSONDict, Query


class InboxResource:
    """The "All inboxes" view across every mailbox in the project.

    Per-mailbox threads stay on :class:`~sendly.resources.mailboxes.MailboxesResource`.
    This is the same listing scoped to the whole project, each row carrying its
    owning ``mailbox`` (``id`` and ``address``) so a follow-up call can be routed
    to the right mailbox.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list_conversations(self, query: Query | None = None) -> InboxConversationPage:
        """One page of conversations across every mailbox, newest activity first.

        Needs the ``mailbox-conversations:read`` scope, which is opt-in only: a key
        holds it only if it was ticked by name when the key was created.

        ``query`` takes ``view`` (``inbox``, the default, or ``spam``), ``status``
        (``open``, ``snoozed``, ``closed`` or ``all``), ``q`` (a substring of the
        subject or the correspondent's address), ``cursor`` and ``limit``. Returns
        ``{items, nextCursor}``: pass ``nextCursor`` back as ``cursor`` until it
        is ``None``, or use :meth:`iter_list_conversations`.
        """
        envelope = self._client.request(method="GET", path="/api/inbox/conversations", query=query)
        page: InboxConversationPage = self._client.unwrap(envelope)
        return page

    def iter_list_conversations(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every conversation across pages, one at a time."""
        return iterate_legacy_cursor(
            self.list_conversations, query, items_key="items", next_key="nextCursor"
        )
