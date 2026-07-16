"""Templates resource tests."""

from __future__ import annotations

import pytest

from sendly import SendlyConflictError
from support import Recorder, json_response, make_client


def test_create_posts_templates():
    rec = Recorder(json_response(201, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    client.templates.create(
        {
            "name": "Welcome",
            "subject": "Welcome",
            "body": "<p>hi</p>",
            "from": "a@b.com",
            "type": "MARKETING",
        }
    )
    assert str(rec.request.url) == "http://localhost/api/templates"


def test_list_serializes_cursor_and_limit():
    rec = Recorder(json_response(200, {"success": True, "data": {"data": [], "total": 0}}))
    client = make_client(rec)
    client.templates.list({"limit": 25, "cursor": "t_50", "type": "MARKETING"})
    url = str(rec.request.url)
    assert "limit=25" in url
    assert "cursor=t_50" in url
    assert "type=MARKETING" in url


def test_update_patches_template():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    client.templates.update("t_1", {"name": "New name"})
    assert rec.request.method == "PATCH"


def test_delete_discards_200_id_body():
    # The API returns 200 with {success, data: {id}}; the SDK discards it -> None.
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    assert client.templates.delete("t_1") is None


def test_delete_raises_conflict_on_409():
    rec = Recorder(
        json_response(409, {"error": {"message": "template in use", "code": "conflict"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyConflictError):
        client.templates.delete("t_1")
