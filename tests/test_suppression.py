"""Suppression resource tests."""

from __future__ import annotations

import pytest

from sendly import SendlyServerError
from support import Recorder, empty_response, json_response, make_client


def test_add_posts_suppression():
    rec = Recorder(
        json_response(201, {"success": True, "data": {"id": "s_1", "email": "spam@x.com"}})
    )
    client = make_client(rec)
    client.suppression.add({"email": "spam@x.com", "reason": "MANUAL"})
    assert str(rec.request.url) == "http://localhost/api/suppression"


def test_list_serializes_reason_filter():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.suppression.list({"reason": "MANUAL", "limit": 100})
    url = str(rec.request.url)
    assert "reason=MANUAL" in url
    assert "limit=100" in url


def test_get_percent_encodes_email_path_segment():
    rec = Recorder(json_response(200, {"success": True, "data": {"suppressed": False}}))
    client = make_client(rec)
    client.suppression.get("user+tag@example.com")
    url = str(rec.request.url)
    # The email is a single path segment and must be percent-encoded, not passed raw.
    assert url == "http://localhost/api/suppression/user%2Btag%40example.com"


def test_remove_deletes_and_resolves_on_204():
    rec = Recorder(empty_response(204))
    client = make_client(rec)
    assert client.suppression.remove("a@b.com") is None
    assert rec.request.method == "DELETE"


def test_add_raises_server_error_on_500():
    rec = Recorder(json_response(500, {"error": {"message": "oops", "code": "server_error"}}))
    client = make_client(rec)
    with pytest.raises(SendlyServerError):
        client.suppression.add({"email": "x@y.com", "reason": "MANUAL"})
