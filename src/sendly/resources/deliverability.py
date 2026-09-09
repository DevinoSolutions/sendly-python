"""Deliverability resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        DeliverabilityDiagnosisV1,
        DmarcReportListV1,
        JSONDict,
        Query,
        RecipientDomainStatsListV1,
    )


class DeliverabilityResource:
    """Why mail from your domains is, or is not, arriving.

    Responses are bare ``/api/v1`` bodies -- no ``{success, data}`` envelope --
    and errors are RFC 9457 problem documents.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def diagnose(self, query: Query) -> DeliverabilityDiagnosisV1:
        """Diagnose one of your SENDING domains.

        Answers with its DNS identity, the project's recent delivery outcomes,
        optionally one recipient's suppression state, and the ``findings`` drawn
        from them, worst first. Branch on a finding's ``code``, never on its
        prose.

        ``domain`` is required -- the endpoint answers about one domain. The
        optional ``address`` is a RECIPIENT to check alongside it, because being
        suppressed is the single most common reason one person stops receiving
        mail while everyone else still does. ``window_days`` (1-30, default 7)
        only moves the delivery counters.

        Nothing here is looked up live: the DNS statuses are the verification
        refresh job's cached results, and ``identity.last_checked_at`` says when
        they were filled. ``recent_delivery`` is project-wide rather than
        per-domain -- its own ``scope`` field says so -- because an email row
        records no sending domain.
        """
        response: DeliverabilityDiagnosisV1 = self._client.request(
            method="GET", path="/api/v1/deliverability/diagnose", query=query
        )
        return response

    def list_domain_stats(self, query: Query | None = None) -> RecipientDomainStatsListV1:
        """Delivery outcomes by RECIPIENT domain and UTC day, newest day first.

        These are the domains you send TO -- ``gmail.com``, ``outlook.com`` --
        not the domains you send FROM. That is the axis :meth:`diagnose` cannot
        report: its project-wide rates hide the case that matters most, one
        recipient domain refusing nearly everything while the rest of your mail
        is healthy.

        Cursor-paginated on ``limit`` + ``after``. The counts come from an hourly
        rollup job over a rolling 30-day window, not from a query run on request;
        each row's ``computed_at`` says when it was last rebuilt. No rate is
        published, because a rate over three sends is not information.
        """
        response: RecipientDomainStatsListV1 = self._client.request(
            method="GET", path="/api/v1/deliverability/domains", query=query
        )
        return response

    def iter_list_domain_stats(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every recipient-domain row across pages, one day-and-domain at a time."""
        return iterate_cursor(self.list_domain_stats, query)

    def list_dmarc_reports(self, query: Query | None = None) -> DmarcReportListV1:
        """DMARC aggregate (RUA) reports about your domains, newest window first.

        Cursor-paginated on ``limit`` + ``after``.

        An empty list is the correct answer, not a bug, until a policy domain is
        registered in this project and its DMARC record names an address we
        receive: only reports about a registered domain are stored, and receivers
        send them on their own schedule (typically once a day).

        ``intake_configured`` says which kind of empty you are looking at. When
        it is ``False`` this deployment has no DMARC report intake mailbox at
        all, so no report can ever arrive and an empty ``data`` means the
        feature is off -- not that your domains are clean. The two are otherwise
        indistinguishable, so read the flag before reporting "no DMARC failures"
        to anyone.

        ``pass_count`` counts DMARC ALIGNMENT taken from ``policy_evaluated``,
        not raw authentication results -- a message can pass SPF for a domain
        that is not the one in its From header, which is exactly the case DMARC
        exists to catch.
        """
        response: DmarcReportListV1 = self._client.request(
            method="GET", path="/api/v1/deliverability/dmarc", query=query
        )
        return response

    def iter_list_dmarc_reports(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every DMARC report across pages, one report at a time."""
        return iterate_cursor(self.list_dmarc_reports, query)
