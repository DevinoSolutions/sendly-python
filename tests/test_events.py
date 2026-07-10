"""Events resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import Recorder, json_response, make_client


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
