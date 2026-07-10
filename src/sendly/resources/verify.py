"""Verify resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import Body, VerifyEmailData


class VerifyResource:
    """Validate email addresses (syntax, MX, disposable, plus-addressing)."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def email(self, body: Body) -> VerifyEmailData:
        """Validate a single email address.

        The endpoint is open (no auth required server-side); the SDK still sends
        its usual ``Authorization`` header, which the API harmlessly ignores.
        """
        envelope = self._client.request(method="POST", path="/api/verify", body=body)
        data: VerifyEmailData = self._client.unwrap(envelope)
        return data
