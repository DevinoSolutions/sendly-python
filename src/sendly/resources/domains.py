"""Domains resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        DomainDeletedV1,
        DomainListResponse,
        DomainListV1,
        DomainRecord,
        DomainSetupSession,
        DomainV1,
        DomainVerificationStatus,
        JSONDict,
        Query,
    )


class DomainsResource:
    """Register and verify sending domains, on both surfaces.

    The unsuffixed methods speak the legacy ``/api/*`` dialect -- camelCase
    bodies inside a ``{success, data}`` envelope the SDK unwraps. The
    ``_v1``-suffixed methods speak ``/api/v1``: bare snake_case bodies, cursor
    pagination, and RFC 9457 problem documents on error. Both answer the same
    questions, so the suffix is there to keep a call site from confusing one for
    the other.
    """

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

    def assign_stream(self, id: str, body: Body) -> DomainRecord:
        """Assign this sending identity to transactional or marketing traffic.

        Streams are enforced, not labelled: once assigned, a send of the other
        kind from this identity is refused with 403 -- which is what keeps a
        campaign's complaint rate off the identity your password resets go out
        on. Pass ``stream: None`` to unassign, returning it to carrying both.

        ``streamDefault`` demotes whichever identity currently holds the default
        for that stream, and ``defaultFromAddress`` has to be an address on this
        identity's own host. Every field is optional; an omitted one is left
        alone.

        Legacy dialect: camelCase body, and the updated domain arrives inside
        the ``{success, data}`` envelope this method unwraps for you.
        """
        envelope = self._client.request(
            method="PATCH", path=f"/api/domains/{encode_path_segment(id)}", body=body
        )
        record: DomainRecord = self._client.unwrap(envelope)
        return record

    def delete(self, id: str) -> None:
        """Delete a domain."""
        self._client.request(method="DELETE", path=f"/api/domains/{encode_path_segment(id)}")

    def list_v1(self, query: Query | None = None) -> DomainListV1:
        """List sending domains, newest first.

        Accepts ``limit`` (1-100, default 20) and ``after`` (opaque cursor), and
        answers ``{data, has_more, next_cursor}``. :meth:`iter_list_v1` drives
        that walk for you.

        ``verified`` is SES's verdict on the identity and is what decides
        whether mail can leave from this domain; ``dkim_verified`` is a separate
        fact -- what the DNS health refresh last read for the DKIM records -- so
        the two disagree while a re-check is in flight and neither is a spelling
        of the other.
        """
        response: DomainListV1 = self._client.request(
            method="GET", path="/api/v1/domains", query=query
        )
        return response

    def iter_list_v1(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every sending domain across pages, following the cursor for you."""
        return iterate_cursor(self.list_v1, query)

    def create_v1(self, body: Body) -> DomainV1:
        """Register a sending domain and start SES DKIM verification.

        The identity comes back with ``verified`` false -- nothing is verified
        until the DKIM records are published in the domain's own DNS and SES
        resolves them, so poll :meth:`verify_v1` after publishing them.

        The first domain a project adds LOCKS the project's SES ``region``;
        every later domain must match it. ``stream_default`` requires
        ``stream``, and sending it alone is answered with 422
        ``validation_error`` rather than ignored.
        """
        response: DomainV1 = self._client.request(method="POST", path="/api/v1/domains", body=body)
        return response

    def get_v1(self, id: str) -> DomainV1:
        """Fetch a single sending domain by id."""
        response: DomainV1 = self._client.request(
            method="GET", path=f"/api/v1/domains/{encode_path_segment(id)}"
        )
        return response

    def verify_v1(self, id: str) -> DomainV1:
        """Re-read the domain's state from SES and DNS, and return it refreshed.

        This does not verify anything and changes none of the domain's own
        fields. Verification happens in the domain's DNS, when its owner
        publishes the DKIM records SES minted at creation, and Amazon decides
        when those resolve. What this call does is ask SES what it currently
        sees, re-check SPF and DMARC, and persist that answer -- so a caller
        polling after a DNS change learns the outcome without waiting for the
        periodic sweep. Calling it on a domain whose records are not published
        yet is not an error and does not hurry anything.

        A POST rather than a GET because the refreshed state is persisted and a
        verified/unverified transition notifies the project.
        """
        response: DomainV1 = self._client.request(
            method="POST", path=f"/api/v1/domains/{encode_path_segment(id)}/verify"
        )
        return response

    def delete_v1(self, id: str) -> DomainDeletedV1:
        """Remove a sending domain. Returns the ``{id, deleted}`` confirmation body.

        Refused with 409 ``conflict`` while a template, workflow step or active
        campaign still sends from an address on this host. The SES identity goes
        too unless another project holds the same host -- and its DKIM keys with
        it, so re-adding later mints records that must be published again.
        """
        response: DomainDeletedV1 = self._client.request(
            method="DELETE", path=f"/api/v1/domains/{encode_path_segment(id)}"
        )
        return response
