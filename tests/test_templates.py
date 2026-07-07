"""Templates resource tests."""

from __future__ import annotations

import pytest

from sendly import SendlyConflictError
from support import Recorder, empty_response, json_response, make_client


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


def test_list_serializes_page_and_page_size():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.templates.list({"page": 2, "pageSize": 25})
    url = str(rec.request.url)
    assert "page=2" in url
    assert "pageSize=25" in url


def test_update_patches_template():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    client.templates.update("t_1", {"name": "New name"})
    assert rec.request.method == "PATCH"


def test_delete_resolves_on_204():
    rec = Recorder(empty_response(204))
    client = make_client(rec)
    assert client.templates.delete("t_1") is None


def test_delete_raises_conflict_on_409():
    rec = Recorder(
        json_response(409, {"error": {"message": "template in use", "code": "conflict"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyConflictError):
        client.templates.delete("t_1")
