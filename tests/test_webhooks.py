"""Webhooks resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyRateLimitError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
)

WEBHOOK_V1 = {
    "id": "wh_1",
    "url": "https://example.com/hook",
    "event_types": ["email.delivered"],
    "status": "ACTIVE",
}


def test_create_posts_webhooks():
    rec = Recorder(
        json_response(
            201,
            {
                "success": True,
                "data": {
                    "webhook": {"id": "w_1", "url": "https://example.com/hook"},
                    "secret": "whsec_xx",
                },
            },
        )
    )
    client = make_client(rec)
    client.webhooks.create({"url": "https://example.com/hook", "eventTypes": ["email.delivered"]})
    assert str(rec.request.url) == "http://localhost/api/webhooks"


def test_rotate_secret_posts_rotate_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"secret": "whsec_yy"}}))
    client = make_client(rec)
    client.webhooks.rotate_secret("w_1")
    assert str(rec.request.url) == "http://localhost/api/webhooks/w_1/rotate-secret"
    assert rec.request.method == "POST"


def test_list_calls_gets_calls_with_cursor_query():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.webhooks.list_calls("w_1", {"limit": 20, "cursor": "abc"})
    url = str(rec.request.url)
    assert url.startswith("http://localhost/api/webhooks/w_1/calls?")
    assert "limit=20" in url
    assert "cursor=abc" in url
    assert rec.request.method == "GET"


def test_create_raises_rate_limit_on_429():
    rec = Recorder(json_response(429, {"error": {"message": "slow down", "code": "rate_limited"}}))
    client = make_client(rec)
    with pytest.raises(SendlyRateLimitError):
        client.webhooks.create({"url": "https://x", "eventTypes": ["email.delivered"]})


def test_update_patches_webhook():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "w_1"}}))
    client = make_client(rec)
    client.webhooks.update("w_1", {"status": "PAUSED"})
    assert rec.request.method == "PATCH"


def test_delete_sends_delete():
    rec = Recorder(json_response(200, {"success": True}))
    client = make_client(rec)
    client.webhooks.delete("w_1")
    assert rec.request.method == "DELETE"


def test_create_v1_posts_the_bare_body_and_hands_back_the_one_time_secret():
    rec = Recorder(json_response(201, {"webhook": WEBHOOK_V1, "secret": "whsec_created"}))
    client = make_client(rec)

    created = client.webhooks.create_v1(
        {"url": "https://example.com/hook", "event_types": ["email.delivered"]}
    )

    assert str(rec.request.url) == "http://localhost/api/v1/webhooks"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {
        "url": "https://example.com/hook",
        "event_types": ["email.delivered"],
    }
    # This response and rotate_secret_v1 are the only two that carry the secret.
    assert created["secret"] == "whsec_created"
    assert created["webhook"]["id"] == "wh_1"


def test_v1_reads_return_the_bare_body_and_never_the_secret():
    rec = Recorder(json_response(200, WEBHOOK_V1))
    client = make_client(rec)

    # A v1 body has no `data` key to unwrap, so unwrapping would lose the record.
    fetched = client.webhooks.get_v1("wh_1")

    assert fetched == WEBHOOK_V1
    assert "secret" not in fetched
    assert str(rec.request.url) == "http://localhost/api/v1/webhooks/wh_1"
    assert rec.request.method == "GET"


def test_update_v1_patches_with_the_replacement_event_list():
    rec = Recorder(json_response(200, {**WEBHOOK_V1, "event_types": ["email.bounced"]}))
    client = make_client(rec)

    updated = client.webhooks.update_v1(
        "wh_1", {"event_types": ["email.bounced"], "status": "ACTIVE"}
    )

    assert str(rec.request.url) == "http://localhost/api/v1/webhooks/wh_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {
        "event_types": ["email.bounced"],
        "status": "ACTIVE",
    }
    # `event_types` replaces rather than merges -- `email.delivered` is gone.
    assert updated["event_types"] == ["email.bounced"]


def test_delete_v1_returns_the_deletion_receipt():
    rec = Recorder(json_response(200, {"id": "wh_1", "deleted": True}))
    client = make_client(rec)

    assert client.webhooks.delete_v1("wh_1") == {"id": "wh_1", "deleted": True}
    assert str(rec.request.url) == "http://localhost/api/v1/webhooks/wh_1"
    assert rec.request.method == "DELETE"


def test_rotate_secret_v1_posts_the_rotate_subpath_and_names_the_overlap_deadline():
    rec = Recorder(
        json_response(
            200,
            {
                "secret": "whsec_rotated",
                "previous_secret_expires_at": "2026-09-06T00:00:00.000Z",
            },
        )
    )
    client = make_client(rec)

    rotated = client.webhooks.rotate_secret_v1("wh_1")

    assert str(rec.request.url) == "http://localhost/api/v1/webhooks/wh_1/rotate-secret"
    assert rec.request.method == "POST"
    assert rotated["secret"] == "whsec_rotated"
    # Both signatures ship until this moment; after it the old secret is rejected.
    assert rotated["previous_secret_expires_at"] == "2026-09-06T00:00:00.000Z"


def test_list_v1_serializes_the_cursor_query():
    page = cursor_page([WEBHOOK_V1])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.webhooks.list_v1({"limit": 25, "after": "cur_wh"}) == page
    assert str(rec.request.url) == "http://localhost/api/v1/webhooks?limit=25&after=cur_wh"


def test_iter_list_v1_walks_every_page():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "wh_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "wh_2"}, {"id": "wh_3"}])),
    )
    client = make_client(rec)

    ids = [w["id"] for w in client.webhooks.iter_list_v1({"limit": 1})]

    assert ids == ["wh_1", "wh_2", "wh_3"]
    assert rec.urls == [
        "http://localhost/api/v1/webhooks?limit=1",
        "http://localhost/api/v1/webhooks?limit=1&after=cur_2",
    ]
