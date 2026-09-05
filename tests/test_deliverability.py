"""Deliverability resource tests (``/api/v1``)."""

from __future__ import annotations

from support import Recorder, SequenceRecorder, cursor_page, json_response, make_client

DIAGNOSIS = {
    "domain": "example.com",
    "address": None,
    "checked_at": "2026-09-01T00:00:00.000Z",
    "identity": {"registered": True, "verified": False, "dkim_status": "FAILED"},
    "suppression": None,
    "recent_delivery": {"window_days": 7, "scope": "project", "sent": 500, "bounced": 40},
    "findings": [
        {
            "code": "dkim_failed",
            "severity": "critical",
            "summary": "DKIM is failing.",
            "remedy": "Re-add the DNS records.",
        }
    ],
}


def domain_stats(domain: str, day: str) -> dict[str, object]:
    """One recipient domain's outcomes on one UTC day."""
    return {
        "domain": domain,
        "day": day,
        "sent": 100,
        "delivered": 92,
        "bounced": 7,
        "complained": 1,
        "opened": 40,
        "computed_at": "2026-09-01T00:00:00.000Z",
    }


def dmarc_report(id: str) -> dict[str, object]:
    """One DMARC aggregate report."""
    return {
        "id": id,
        "report_id": f"rpt_{id}",
        "org_name": "google.com",
        "policy_domain": "example.com",
        "range_begin": "2026-09-01T00:00:00.000Z",
        "range_end": "2026-09-02T00:00:00.000Z",
        "total_count": 10,
        "pass_count": 9,
        "fail_count": 1,
        "sources": [],
        "received_at": "2026-09-02T06:00:00.000Z",
    }


def test_diagnose_serializes_every_query_parameter():
    rec = Recorder(json_response(200, DIAGNOSIS))
    client = make_client(rec)

    result = client.deliverability.diagnose(
        {"domain": "example.com", "address": "person@gmail.com", "window_days": 14}
    )

    assert result == DIAGNOSIS
    assert str(rec.request.url) == (
        "http://localhost/api/v1/deliverability/diagnose"
        "?domain=example.com&address=person%40gmail.com&window_days=14"
    )
    assert rec.request.method == "GET"


def test_diagnose_reports_findings_and_a_project_wide_delivery_scope():
    rec = Recorder(json_response(200, DIAGNOSIS))
    client = make_client(rec)

    result = client.deliverability.diagnose({"domain": "example.com"})

    assert result["findings"][0]["code"] == "dkim_failed"
    # `recent_delivery` is project-wide, and says so in its own field.
    assert result["recent_delivery"]["scope"] == "project"


def test_list_domain_stats_hits_the_recipient_domain_rollup_with_its_filters():
    page = cursor_page([domain_stats("gmail.com", "2026-09-01")])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    # Returned as-is: the envelope, not its `data` array.
    assert (
        client.deliverability.list_domain_stats({"limit": 50, "days": 7, "domain": "gmail.com"})
        == page
    )
    assert str(rec.request.url) == (
        "http://localhost/api/v1/deliverability/domains?limit=50&days=7&domain=gmail.com"
    )


def test_iter_list_domain_stats_walks_two_pages_on_after():
    rec = SequenceRecorder(
        json_response(
            200, cursor_page([domain_stats("gmail.com", "2026-09-02")], next_cursor="cur_2")
        ),
        json_response(200, cursor_page([domain_stats("outlook.com", "2026-09-02")])),
    )
    client = make_client(rec)

    domains = [row["domain"] for row in client.deliverability.iter_list_domain_stats({"days": 2})]

    assert domains == ["gmail.com", "outlook.com"]
    assert rec.urls == [
        "http://localhost/api/v1/deliverability/domains?days=2",
        "http://localhost/api/v1/deliverability/domains?days=2&after=cur_2",
    ]


def test_list_dmarc_reports_hits_the_dmarc_path_with_its_filters():
    page = cursor_page([dmarc_report("dmr_1")])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert (
        client.deliverability.list_dmarc_reports({"limit": 10, "days": 90, "domain": "example.com"})
        == page
    )
    assert str(rec.request.url) == (
        "http://localhost/api/v1/deliverability/dmarc?limit=10&days=90&domain=example.com"
    )


def test_an_empty_dmarc_page_is_a_well_formed_answer():
    # No reports are stored for a domain the project has not registered, so the
    # correct-and-empty page is not a bug.
    rec = Recorder(json_response(200, cursor_page([])))
    client = make_client(rec)

    page = client.deliverability.list_dmarc_reports()

    assert page["data"] == []
    assert page["has_more"] is False


def test_iter_list_dmarc_reports_walks_two_pages_and_stops():
    rec = SequenceRecorder(
        json_response(200, cursor_page([dmarc_report("dmr_1")], next_cursor="cur_2")),
        json_response(200, cursor_page([dmarc_report("dmr_2")])),
    )
    client = make_client(rec)

    assert [r["id"] for r in client.deliverability.iter_list_dmarc_reports()] == ["dmr_1", "dmr_2"]
    assert rec.urls == [
        "http://localhost/api/v1/deliverability/dmarc",
        "http://localhost/api/v1/deliverability/dmarc?after=cur_2",
    ]
