"""Usage resource tests (``/api/v1``)."""

from __future__ import annotations

import pytest

from sendly import SendlyRateLimitError
from support import Recorder, json_response, make_client, problem_response

USAGE = {
    "plan": {"name": "pro", "monthly_email_limit": 100_000},
    "monthly": {"emails_sent": 12_500, "remaining": 87_500},
    "daily": {"emails_sent": 900},
}


def test_get_requests_the_usage_path_and_returns_the_bare_body():
    rec = Recorder(json_response(200, USAGE))
    client = make_client(rec)

    result = client.usage.get()

    assert str(rec.request.url) == "http://localhost/api/v1/usage"
    assert rec.request.method == "GET"
    assert result == USAGE
    assert result["monthly"]["remaining"] == 87_500


def test_get_sends_no_body_and_no_query():
    rec = Recorder(json_response(200, USAGE))
    client = make_client(rec)
    client.usage.get()
    assert rec.request.content == b""
    assert rec.request.url.query == b""


def test_quota_exhausted_is_a_rate_limit_error_distinguished_by_its_code():
    # 429 quota_exhausted is not fixed by backing off, unlike 429 rate_limited.
    rec = Recorder(
        problem_response(
            429,
            {
                "type": "https://docs.sendly.now/errors/quota_exhausted",
                "title": "Quota Exhausted",
                "status": 429,
                "code": "quota_exhausted",
                "detail": "Monthly email quota reached for this plan.",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyRateLimitError) as caught:
        client.usage.get()
    assert caught.value.error_code == "quota_exhausted"
    assert caught.value.message == "Monthly email quota reached for this plan."
