"""Campaigns resource tests (``/api/v1``)."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyConflictError, SendlyNotFoundError, SendlyRateLimitError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
    problem_response,
)

CAMPAIGN = {
    "id": "cmp_1",
    "name": "Launch",
    "status": "DRAFT",
    "subject": "We are live",
    "audience_type": "ALL",
    "stats": {"sent": 0},
}


def test_list_returns_the_cursor_envelope_unwrapped_by_nobody():
    # v1 answers a bare body: has_more/next_cursor must survive to the caller.
    page = cursor_page([CAMPAIGN], next_cursor="cur_2")
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    result = client.campaigns.list({"limit": 1})

    assert str(rec.request.url) == "http://localhost/api/v1/campaigns?limit=1"
    assert result == page
    assert result["has_more"] is True
    assert result["next_cursor"] == "cur_2"


def test_create_posts_the_body_and_returns_the_bare_campaign():
    rec = Recorder(json_response(201, CAMPAIGN))
    client = make_client(rec)

    result = client.campaigns.create(
        {
            "name": "Launch",
            "subject": "We are live",
            "body": "<p>hi</p>",
            "from": "team@sendly.now",
            "audience_type": "ALL",
        }
    )

    assert str(rec.request.url) == "http://localhost/api/v1/campaigns"
    assert json.loads(rec.request.content)["audience_type"] == "ALL"
    assert result == CAMPAIGN


def test_create_forwards_the_idempotency_key_header():
    rec = Recorder(json_response(201, CAMPAIGN))
    client = make_client(rec)

    client.campaigns.create({"name": "Launch"}, idempotency_key="key_123")

    assert rec.request.headers["Idempotency-Key"] == "key_123"


def test_create_omits_the_idempotency_header_when_no_key_is_given():
    rec = Recorder(json_response(201, CAMPAIGN))
    client = make_client(rec)

    client.campaigns.create({"name": "Launch"})

    assert "Idempotency-Key" not in rec.request.headers


def test_get_and_update_and_delete_hit_the_id_path():
    rec = Recorder(json_response(200, CAMPAIGN))
    client = make_client(rec)
    assert client.campaigns.get("cmp_1") == CAMPAIGN
    assert str(rec.request.url) == "http://localhost/api/v1/campaigns/cmp_1"

    rec = Recorder(json_response(200, CAMPAIGN))
    client = make_client(rec)
    client.campaigns.update("cmp_1", {"subject": "New subject"})
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"subject": "New subject"}

    rec = Recorder(json_response(200, {"id": "cmp_1", "deleted": True}))
    client = make_client(rec)
    # v1 deletes return a real body, unlike the legacy deletes that yield None.
    assert client.campaigns.delete("cmp_1") == {"id": "cmp_1", "deleted": True}
    assert rec.request.method == "DELETE"


def test_id_is_percent_encoded_into_the_path():
    rec = Recorder(json_response(200, CAMPAIGN))
    client = make_client(rec)
    client.campaigns.get("cmp/../secret")
    assert str(rec.request.url) == "http://localhost/api/v1/campaigns/cmp%2F..%2Fsecret"


def test_send_without_a_body_sends_immediately():
    rec = Recorder(json_response(200, {**CAMPAIGN, "status": "SENDING"}))
    client = make_client(rec)

    result = client.campaigns.send("cmp_1")

    assert str(rec.request.url) == "http://localhost/api/v1/campaigns/cmp_1/send"
    assert rec.request.method == "POST"
    assert rec.request.content == b""
    assert result["status"] == "SENDING"


def test_send_schedules_when_given_a_scheduled_for_body_and_keys_the_replay():
    rec = Recorder(json_response(200, {**CAMPAIGN, "status": "SCHEDULED"}))
    client = make_client(rec)

    client.campaigns.send(
        "cmp_1", {"scheduled_for": "2026-09-01T10:00:00Z"}, idempotency_key="send_1"
    )

    assert json.loads(rec.request.content) == {"scheduled_for": "2026-09-01T10:00:00Z"}
    assert rec.request.headers["Idempotency-Key"] == "send_1"


def test_a_replayed_send_surfaces_the_idempotency_conflict():
    rec = Recorder(
        problem_response(
            409,
            {
                "type": "https://docs.sendly.now/errors/idempotency_key_reused",
                "title": "Idempotency Key Reused",
                "status": 409,
                "code": "idempotency_key_reused",
                "detail": "This key was used with a different request body.",
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyConflictError) as caught:
        client.campaigns.send("cmp_1", idempotency_key="send_1")
    assert caught.value.error_code == "idempotency_key_reused"


@pytest.mark.parametrize("action", ["cancel", "pause", "resume"])
def test_lifecycle_actions_post_to_their_own_subpath(action):
    rec = Recorder(json_response(200, CAMPAIGN))
    client = make_client(rec)

    getattr(client.campaigns, action)("cmp_1")

    assert str(rec.request.url) == f"http://localhost/api/v1/campaigns/cmp_1/{action}"
    assert rec.request.method == "POST"


def test_stats_returns_the_counter_body():
    stats = {"total_recipients": 10, "sent": 10, "opened": 4, "open_rate": 0.4}
    rec = Recorder(json_response(200, stats))
    client = make_client(rec)

    assert client.campaigns.stats("cmp_1") == stats
    assert str(rec.request.url) == "http://localhost/api/v1/campaigns/cmp_1/stats"


def test_get_raises_not_found_from_a_problem_document():
    rec = Recorder(
        problem_response(
            404,
            {
                "type": "https://docs.sendly.now/errors/resource_not_found",
                "title": "Resource Not Found",
                "status": 404,
                "code": "resource_not_found",
                "detail": "No campaign with id cmp_missing.",
                "request_id": "req_404",
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyNotFoundError) as caught:
        client.campaigns.get("cmp_missing")
    assert caught.value.message == "No campaign with id cmp_missing."
    assert caught.value.request_id == "req_404"


# --------------------------------------------------------------------------- #
# Auto-pagination                                                              #
# --------------------------------------------------------------------------- #


def test_iter_list_walks_every_page_and_threads_the_cursor():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "cmp_1"}, {"id": "cmp_2"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "cmp_3"}], next_cursor="cur_3")),
        json_response(200, cursor_page([{"id": "cmp_4"}])),
    )
    client = make_client(rec)

    ids = [campaign["id"] for campaign in client.campaigns.iter_list({"limit": 2})]

    assert ids == ["cmp_1", "cmp_2", "cmp_3", "cmp_4"]
    assert rec.urls == [
        "http://localhost/api/v1/campaigns?limit=2",
        "http://localhost/api/v1/campaigns?limit=2&after=cur_2",
        "http://localhost/api/v1/campaigns?limit=2&after=cur_3",
    ]


def test_iter_list_stops_on_the_last_page_without_requesting_another():
    # SequenceRecorder fails the test on an unqueued request, so a paginator that
    # ignores has_more shows up here rather than looping.
    rec = SequenceRecorder(json_response(200, cursor_page([{"id": "cmp_1"}])))
    client = make_client(rec)

    assert [c["id"] for c in client.campaigns.iter_list()] == ["cmp_1"]
    assert len(rec.requests) == 1


def test_iter_list_stops_when_has_more_is_true_but_the_cursor_is_missing():
    # A truncated page must end the walk rather than re-request page one forever.
    rec = SequenceRecorder(
        json_response(200, {"data": [{"id": "cmp_1"}], "has_more": True, "next_cursor": None})
    )
    client = make_client(rec)

    assert [c["id"] for c in client.campaigns.iter_list()] == ["cmp_1"]
    assert len(rec.requests) == 1


def test_iter_list_is_lazy_and_fetches_nothing_until_iterated():
    rec = SequenceRecorder(json_response(200, cursor_page([{"id": "cmp_1"}])))
    client = make_client(rec)

    iterator = client.campaigns.iter_list()
    assert rec.requests == []
    assert next(iterator)["id"] == "cmp_1"


def test_iter_list_surfaces_a_mid_walk_error_instead_of_swallowing_it():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "cmp_1"}], next_cursor="cur_2")),
        problem_response(
            429,
            {
                "type": "https://docs.sendly.now/errors/rate_limited",
                "title": "Rate Limited",
                "status": 429,
                "code": "rate_limited",
            },
        ),
    )
    client = make_client(rec)

    iterator = client.campaigns.iter_list()
    assert next(iterator)["id"] == "cmp_1"
    with pytest.raises(SendlyRateLimitError) as caught:
        next(iterator)
    assert caught.value.error_code == "rate_limited"
