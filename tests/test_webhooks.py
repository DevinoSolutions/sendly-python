"""Webhooks resource tests."""

from __future__ import annotations

import pytest

from sendly import SendlyRateLimitError
from support import Recorder, json_response, make_client


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
