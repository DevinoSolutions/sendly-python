"""Support resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import Body, SupportTicketCreated, SupportTicketList


class SupportResource:
    """Open and review support tickets."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list_tickets(self) -> SupportTicketList:
        """The project's own tickets, newest first, up to 50, as ``{items}``.

        Needs ``support:read``. Not paginated, so there is no iterator.
        """
        response: SupportTicketList = self._client.request(
            method="GET", path="/api/v1/support/tickets"
        )
        return response

    def create_ticket(self, body: Body) -> SupportTicketCreated:
        """Email the support inbox. Needs ``support:write``.

        ``body`` takes ``subject`` (1-200 characters) and ``body`` (1-4000), both
        required, plus ``type`` (``problem``, ``feature``, ``question`` or
        ``other``), ``attachments`` (up to 5 https links the support team opens;
        nothing fetches them) and ``wantsReply``. An API key has no account email
        to reply to, so it should send ``wantsReply: False``. Ten tickets per
        caller per hour. Returns ``{ticketId, status}``; ``logged`` means the email
        failed but support still sees the ticket.
        """
        response: SupportTicketCreated = self._client.request(
            method="POST", path="/api/v1/support/tickets", body=body
        )
        return response
