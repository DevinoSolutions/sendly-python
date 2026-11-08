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
        DomainConnectStatus,
        DomainDeletedV1,
        DomainListResponse,
        DomainListV1,
        DomainLogoReadinessV1,
        DomainLogoV1,
        DomainRecord,
        DomainSetupSession,
        DomainV1,
        DomainVerificationStatus,
        DomainWarmupStatus,
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
        subsequent calls must match.

        The response carries ``dkimTokens`` -- the SES DKIM tokens to publish as
        CNAME records before the domain can verify -- alongside ``dkimStatus``,
        ``spfStatus`` and ``dmarcStatus``, each the result of the last DNS check
        for that record type.
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
        """Trigger SES verification for a domain.

        ``status`` is SES's own raw DKIM verification state (``Success``,
        ``Pending``), while ``dkimStatus``, ``spfStatus`` and ``dmarcStatus``
        are this platform's own DNS check per record type. ``tokens`` carries
        the DKIM tokens SES has still to report and is absent once verification
        has resolved.
        """
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

    def get_logo_v1(self, id: str) -> DomainLogoV1:
        """The logo this identity serves to inboxes (BIMI), the
        ``default._bimi`` TXT record that makes them fetch it (``bimi_record``),
        and a fresh DNS reading of whether they will show it today.

        The URL never changes, so the record is published once. Until a logo is
        uploaded it serves a default (the domain's initial), and it serves
        nothing until the identity verifies. Providers decide whether to show a
        logo; Gmail also needs a VMC or CMC certificate, which Sendly neither
        issues nor checks. :meth:`get_logo_readiness_v1` is the full checklist.
        """
        response: DomainLogoV1 = self._client.request(
            method="GET", path=f"/api/v1/domains/{encode_path_segment(id)}/logo"
        )
        return response

    def upload_logo_v1(self, id: str, body: Body) -> DomainLogoV1:
        """Replace the logo with an SVG: ``{"svg": "<svg ...>"}``.

        It is rebuilt into SVG Tiny PS, the profile BIMI requires: square, shapes
        rather than ``<text>``, nothing referenced outside itself, at most 32 KB
        once rebuilt. A file that cannot be rebuilt answers 422
        ``validation_error`` with a ``detail`` naming what to change, and the
        previous logo stays in place.
        """
        response: DomainLogoV1 = self._client.request(
            method="PUT", path=f"/api/v1/domains/{encode_path_segment(id)}/logo", body=body
        )
        return response

    def delete_logo_v1(self, id: str) -> DomainLogoV1:
        """Remove the uploaded logo, so the URL serves the default again.

        Returns the logo now served; removing one that was never uploaded is not
        an error. The DNS record does not change.
        """
        response: DomainLogoV1 = self._client.request(
            method="DELETE", path=f"/api/v1/domains/{encode_path_segment(id)}/logo"
        )
        return response

    def get_logo_readiness_v1(self, id: str) -> DomainLogoReadinessV1:
        """How ready the identity is to show its logo as the inbox avatar.

        Each step (DMARC at enforcement on the host and its organizational
        domain, the BIMI record, the logo file, the mark certificate) comes back
        ``met``, ``missing``, ``unknown`` or ``not_applicable`` with a
        plain-English ``reason``, plus one checklist per inbox (Gmail, Yahoo,
        Apple Mail, Fastmail). For the certificate only "the URL answers with a
        PEM file" is checked; its chain is not validated.
        """
        response: DomainLogoReadinessV1 = self._client.request(
            method="GET", path=f"/api/v1/domains/{encode_path_segment(id)}/logo/readiness"
        )
        return response

    def get_connect_status(self, id: str) -> DomainConnectStatus:
        """Whether the domain's DNS provider supports one-click setup through
        DoDomain, and which method it would use. Needs ``domains:read``.

        Stateless and free on every plan (unlike :meth:`start_setup`, which mints a
        metered session), so it is safe to call just to decide what to offer.
        The answer is cached for 10 minutes per domain.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/domains/{encode_path_segment(id)}/dodomain-check"
        )
        status: DomainConnectStatus = self._client.unwrap(envelope)
        return status

    def reverify_connection(self, id: str) -> JSONDict:
        """Ask DoDomain to re-check the domain's DNS now. Needs ``domains:write``.

        Answers 202 ``{status: "accepted"}`` with NO verdict: the re-check runs at
        DoDomain and its answer arrives as a ``connection.verified`` or
        ``connection.failed`` webhook a few minutes later. A second call inside the
        60-second cooldown is refused with 429.
        """
        envelope = self._client.request(
            method="POST", path=f"/api/domains/{encode_path_segment(id)}/dodomain-reverify"
        )
        accepted: JSONDict = self._client.unwrap(envelope)
        return accepted

    def get_warmup(self, id: str) -> DomainWarmupStatus:
        """Where a new domain is in its warm-up ramp and how much it has sent today.

        Needs ``domains:read``. Its own call, not a field on :meth:`get`, because
        today's counter moves with every send.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/domains/{encode_path_segment(id)}/warmup"
        )
        status: DomainWarmupStatus = self._client.unwrap(envelope)
        return status

    def manage_warmup(self, id: str, body: Body) -> DomainWarmupStatus:
        """End a domain's warm-up early or start it again from day one.

        ``body`` is ``{"action": "finish"}`` or ``{"action": "restart"}``. Needs
        ``domains:write``. Finishing early on a domain that has never sent risks its
        reputation; the ramp exists to prevent exactly that. Returns the new
        warm-up status.
        """
        envelope = self._client.request(
            method="POST", path=f"/api/domains/{encode_path_segment(id)}/warmup", body=body
        )
        status: DomainWarmupStatus = self._client.unwrap(envelope)
        return status
