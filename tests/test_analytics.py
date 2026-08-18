"""Analytics resource tests (``/api/v1``)."""

from __future__ import annotations

import pytest

from sendly import SendlyPermissionError
from support import Recorder, json_response, make_client, problem_response

WINDOW = {"from": "2026-08-01", "to": "2026-08-18"}


def test_timeseries_forwards_the_window_and_returns_the_bare_body():
    payload = {"data": [{"date": "2026-08-01", "sent": 120}], "window": WINDOW}
    rec = Recorder(json_response(200, payload))
    client = make_client(rec)

    result = client.analytics.timeseries({"from": "2026-08-01", "to": "2026-08-18"})

    assert str(rec.request.url) == (
        "http://localhost/api/v1/analytics/timeseries?from=2026-08-01&to=2026-08-18"
    )
    # Not a cursor envelope: the resolved window comes back instead, so the
    # caller can see what the API measured when it defaulted the range.
    assert result == payload
    assert result["window"] == WINDOW


def test_campaigns_returns_totals_and_average_rates():
    payload = {"total": 12, "active": 2, "average_open_rate": 0.41, "window": WINDOW}
    rec = Recorder(json_response(200, payload))
    client = make_client(rec)

    assert client.analytics.campaigns() == payload
    assert str(rec.request.url) == "http://localhost/api/v1/analytics/campaigns"


def test_top_campaigns_forwards_the_limit():
    payload = {"data": [{"id": "cmp_1", "open_rate": 0.62}], "window": WINDOW}
    rec = Recorder(json_response(200, payload))
    client = make_client(rec)

    assert client.analytics.top_campaigns({"limit": 5}) == payload
    assert str(rec.request.url) == "http://localhost/api/v1/analytics/top-campaigns?limit=5"


def test_analytics_has_no_iterators():
    # These endpoints answer a bounded aggregate with no cursor; an iterator over
    # one would silently yield a single page.
    client = make_client(Recorder(json_response(200, {})))
    assert not [name for name in dir(client.analytics) if name.startswith("iter_")]


def test_a_key_without_the_analytics_scope_raises_a_permission_error():
    rec = Recorder(
        problem_response(
            403,
            {
                "type": "https://docs.sendly.now/errors/scope_missing",
                "title": "Scope Missing",
                "status": 403,
                "code": "scope_missing",
                "detail": "This API key lacks the analytics:read scope.",
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyPermissionError) as caught:
        client.analytics.timeseries()
    assert caught.value.error_code == "scope_missing"
