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

    def delete(self, id: str) -> None:
        """Delete a domain."""
        self._client.request(method="DELETE", path=f"/api/domains/{encode_path_segment(id)}")
