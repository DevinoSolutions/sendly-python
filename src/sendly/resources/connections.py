"""Connections resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import Body, ConnectionsStatus, ConnectLinks


class ConnectionsResource:
    """The services connected to a project, and the links that connect more."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self) -> ConnectionsStatus:
        """The project's Slack connection and the domains whose DNS DoDomain manages.

        Needs ``connections:read``. For a person it also lists their connected AI
        apps; for an API key ``connectedApps`` is ``None``.
        """
        response: ConnectionsStatus = self._client.request(method="GET", path="/api/v1/connections")
        return response

    def create_links(self, body: Body) -> ConnectLinks:
        """Mint one-time links a person opens to connect a service. Needs ``connections:write``.

        ``body["provider"]`` is ``slack`` (the default; opening it needs a project
        admin) or ``dodomain``, which also needs ``domainId`` and starts a metered
        guided-DNS session -- a second call for the same domain within 60 seconds
        answers 429 ``DODOMAIN_SESSION_COOLDOWN``. Each link works once, for 15
        minutes, for the account it was made for; the SDK only mints it, the person
        opens it.
        """
        response: ConnectLinks = self._client.request(
            method="POST", path="/api/v1/connections/links", body=body
        )
        return response
