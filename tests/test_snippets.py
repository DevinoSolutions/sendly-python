"""Snippets resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyConflictError
from support import Recorder, json_response, make_client

SNIPPET = {
    "id": "snp_1",
    "projectId": "prj_1",
    "name": "footer",
    "description": None,
    "body": "<p>Unsubscribe</p>",
    "createdAt": "2026-01-01T00:00:00.000Z",
    "updatedAt": "2026-01-01T00:00:00.000Z",
}


def test_create_posts_snippets_and_unwraps_the_envelope():
    rec = Recorder(json_response(201, {"success": True, "data": SNIPPET}))
    client = make_client(rec)

    created = client.snippets.create({"name": "footer", "body": "<p>Unsubscribe</p>"})

    assert str(rec.request.url) == "http://localhost/api/snippets"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"name": "footer", "body": "<p>Unsubscribe</p>"}
    # Legacy dialect: the caller gets the record, never the {success, data} wrapper.
    assert created == SNIPPET


def test_list_serializes_limit_cursor_and_search():
    rec = Recorder(
        json_response(200, {"success": True, "data": {"data": [], "total": 0, "hasMore": False}})
    )
    client = make_client(rec)

    client.snippets.list({"limit": 25, "cursor": "snp_50", "search": "footer"})

    url = str(rec.request.url)
    assert "limit=25" in url
    assert "cursor=snp_50" in url
    assert "search=footer" in url


def test_list_keeps_the_envelope():
    body = {
        "success": True,
        "data": {"data": [SNIPPET], "total": 1, "cursor": "snp_1", "hasMore": True},
    }
    rec = Recorder(json_response(200, body))
    client = make_client(rec)

    # Unlike create/get/update, the list response is returned whole.
    assert client.snippets.list() == body
    assert rec.request.method == "GET"


def test_get_unwraps_to_the_record_at_the_id_path():
    rec = Recorder(json_response(200, {"success": True, "data": SNIPPET}))
    client = make_client(rec)

    assert client.snippets.get("snp_1") == SNIPPET
    assert str(rec.request.url) == "http://localhost/api/snippets/snp_1"
    assert rec.request.method == "GET"


def test_update_patches_and_unwraps():
    rec = Recorder(json_response(200, {"success": True, "data": {**SNIPPET, "name": "footer_v2"}}))
    client = make_client(rec)

    updated = client.snippets.update("snp_1", {"name": "footer_v2"})

    assert str(rec.request.url) == "http://localhost/api/snippets/snp_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"name": "footer_v2"}
    assert updated["name"] == "footer_v2"


def test_delete_discards_200_id_body():
    # The API returns 200 with {success, data: {id}}; the SDK discards it -> None.
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "snp_1"}}))
    client = make_client(rec)

    assert client.snippets.delete("snp_1") is None
    assert str(rec.request.url) == "http://localhost/api/snippets/snp_1"
    assert rec.request.method == "DELETE"


def test_create_raises_conflict_when_the_name_is_taken():
    rec = Recorder(
        json_response(
            409, {"error": {"message": "snippet name already exists", "code": "conflict"}}
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyConflictError):
        client.snippets.create({"name": "footer", "body": "x"})
