"""Events resource tests — legacy ``/api/track`` and the ``/api/v1/events`` surface."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
    problem_response,
)


def test_track_posts_track_with_bearer_and_body():
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {
                    "contact": "11111111-1111-1111-1111-111111111111",
                    "event": "22222222-2222-2222-2222-222222222222",
                    "timestamp": "2026-01-01T00:00:00.000Z",
                },
            },
        )
    )
    client = make_client(rec)
    result = client.events.track({"event": "signup", "email": "user@example.com"})
    req = rec.request
    assert str(req.url) == "http://localhost/api/track"
    assert req.method == "POST"
    assert req.headers["authorization"] == "Bearer sk_test_key"
    assert req.headers["content-type"] == "application/json"
    body = json.loads(req.content)
    assert body["event"] == "signup"
    assert body["email"] == "user@example.com"
    # Response is unwrapped to the envelope's `data` payload.
    assert result["contact"] == "11111111-1111-1111-1111-111111111111"
    assert result["timestamp"] == "2026-01-01T00:00:00.000Z"


def test_track_forwards_optional_data_and_subscribed():
    rec = Recorder(
        json_response(
            200, {"success": True, "data": {"contact": "c", "event": "e", "timestamp": "t"}}
        )
    )
    client = make_client(rec)
    client.events.track(
        {"event": "purchase", "email": "a@b.com", "subscribed": True, "data": {"amount": 42}}
    )
    body = json.loads(rec.request.content)
    assert body["subscribed"] is True
    assert body["data"] == {"amount": 42}


def test_track_raises_validation_error_on_400():
    rec = Recorder(
        json_response(400, {"error": {"message": "reserved event name", "code": "invalid_body"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyValidationError):
        client.events.track({"event": "email.sent", "email": "a@b.com"})


# --------------------------------------------------------------------------- #
# /api/v1/events                                                               #
# --------------------------------------------------------------------------- #

EVENT = {
    "id": "evt_1",
    "name": "signup.completed",
    "contact_id": "con_1",
    "data": {"plan": "pro"},
    "created_at": "2026-08-18T10:00:00.000Z",
}


def test_record_posts_to_v1_and_returns_the_bare_event():
    rec = Recorder(json_response(201, EVENT))
    client = make_client(rec)

    result = client.events.record({"name": "signup.completed", "contact_id": "con_1"})

    assert str(rec.request.url) == "http://localhost/api/v1/events"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content)["name"] == "signup.completed"
    # v1 is not enveloped: the event body arrives as-is, no `data` unwrap.
    assert result == EVENT


def test_record_sends_no_idempotency_key():
    # Events are the highest-volume write on the surface and append-only, so the
    # API deliberately does not ledger them. `record` therefore takes no key.
    rec = Recorder(json_response(201, EVENT))
    client = make_client(rec)
    client.events.record({"name": "signup.completed"})
    assert "Idempotency-Key" not in rec.request.headers


def test_track_and_record_stay_separate_surfaces():
    # The legacy method keeps its own path and its own envelope handling.
    rec = Recorder(json_response(200, {"success": True, "data": {"event": "e"}}))
    client = make_client(rec)
    client.events.track({"event": "signup", "email": "a@b.com"})
    assert str(rec.request.url) == "http://localhost/api/track"


def test_list_forwards_the_event_name_filter_and_returns_the_cursor_envelope():
    page = cursor_page([EVENT], next_cursor="cur_2")
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    result = client.events.list({"event_name": "signup.completed", "limit": 20})

    url = str(rec.request.url)
    assert url.startswith("http://localhost/api/v1/events?")
    assert "event_name=signup.completed" in url
    assert "limit=20" in url
    assert result == page


def test_iter_list_walks_every_page_and_preserves_the_filter():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "evt_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "evt_2"}])),
    )
    client = make_client(rec)

    ids = [e["id"] for e in client.events.iter_list({"event_name": "signup.completed"})]

    assert ids == ["evt_1", "evt_2"]
    assert rec.urls == [
        "http://localhost/api/v1/events?event_name=signup.completed",
        "http://localhost/api/v1/events?event_name=signup.completed&after=cur_2",
    ]


def test_list_names_returns_the_distinct_names():
    rec = Recorder(json_response(200, {"data": ["signup.completed", "purchase.made"]}))
    client = make_client(rec)

    result = client.events.list_names()

    assert str(rec.request.url) == "http://localhost/api/v1/events/names"
    assert result["data"] == ["signup.completed", "purchase.made"]


def test_stats_forwards_the_window():
    payload = {
        "data": [{"name": "signup.completed", "count": 42}],
        "window": {"from": "2026-08-01"},
    }
    rec = Recorder(json_response(200, payload))
    client = make_client(rec)

    assert client.events.stats({"from": "2026-08-01"}) == payload
    assert str(rec.request.url) == "http://localhost/api/v1/events/stats?from=2026-08-01"


def test_record_raises_validation_error_from_a_problem_document():
    rec = Recorder(
        problem_response(
            422,
            {
                "type": "https://docs.sendly.now/errors/validation_error",
                "title": "Validation Error",
                "status": 422,
                "code": "validation_error",
                "detail": "`name` is a reserved system event name.",
                "request_id": "req_evt",
                "errors": [
                    {"pointer": "/name", "code": "reserved", "message": "reserved event name"}
                ],
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyValidationError) as caught:
        client.events.record({"name": "email.sent"})

    assert caught.value.error_code == "validation_error"
    assert caught.value.request_id == "req_evt"
    assert caught.value.field_errors[0]["pointer"] == "/name"
