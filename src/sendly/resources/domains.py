"""Domains resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        Body,
        DomainListResponse,
        DomainRecord,
        DomainSetupSession,
        DomainVerificationStatus,
    )


class DomainsResource:
    """Register and verify sending domains."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def create(self, body: Body) -> DomainRecord:
        """Register a new sending domain.

        Pass ``region`` to pin this domain to a specific AWS SES region. On the
        first domain for a project this also locks the project's region;
        subsequent calls must match. The response includes DNS records to set.
        """
        envelope = self._client.request(method="POST", path="/api/domains", body=body)
        record: DomainRecord = self._client.unwrap(envelope)
        return record

    def list(self) -> DomainListResponse:
        """List all domains for the project."""
        response: DomainListResponse = self._client.request(method="GET", path="/api/domains")
        return response

    def get(self, id: str) -> DomainRecord:
        """Fetch a single domain."""
        envelope = self._client.request(
            method="GET", path=f"/api/domains/{encode_path_segment(id)}"
        )
        record: DomainRecord = self._client.unwrap(envelope)
        return record

    def verify(self, id: str) -> DomainVerificationStatus:
        """Trigger SES verification for a domain."""
        envelope = self._client.request(
            method="POST", path=f"/api/domains/{encode_path_segment(id)}/verify"
        )
        status: DomainVerificationStatus = self._client.unwrap(envelope)
        return status

    def get_verification(self, id: str) -> DomainVerificationStatus:
        """Read current SES verification status for a domain."""
        envelope = self._client.request(
            method="GET", path=f"/api/domains/{encode_path_segment(id)}/verify"
        )
        status: DomainVerificationStatus = self._client.unwrap(envelope)
        return status

    def start_setup(self, id: str) -> DomainSetupSession:
        """Start the guided DNS setup hand-off for a domain.

        Returns the session as the route returns it: a ``connectUrl`` to open in
        a browser, the ``token`` that url carries, and ``expiresAt``. Nothing is
        derived or reshaped -- finishing setup means a person visiting that url
        and authorising the change at their registrar, so the SDK's job is to
        hand back the link, not to model the flow behind it.
        """
        envelope = self._client.request(
            method="POST", path=f"/api/domains/{encode_path_segment(id)}/dodomain-session"
        )
        session: DomainSetupSession = self._client.unwrap(envelope)
        return session

    def delete(self, id: str) -> None:
        """Delete a domain."""
        self._client.request(method="DELETE", path=f"/api/domains/{encode_path_segment(id)}")
