"""Contacts resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyNotFoundError
from support import Recorder, empty_response, json_response, make_client


def test_create_posts_and_unwraps_data():
    rec = Recorder(json_response(201, {"success": True, "data": {"id": "c_1", "email": "x@y.com"}}))
    client = make_client(rec)
    result = client.contacts.create({"email": "x@y.com", "subscribed": True})
    assert str(rec.request.url) == "http://localhost/api/contacts"
    assert result["id"] == "c_1"


def test_upsert_posts_upsert_path_with_body():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "c_2", "email": "a@b.com"}}))
    client = make_client(rec)
    client.contacts.upsert({"email": "a@b.com", "subscribed": True, "data": {"plan": "pro"}})
    assert str(rec.request.url) == "http://localhost/api/contacts/upsert"
    body = json.loads(rec.request.content)
    assert body["email"] == "a@b.com"
    assert body["data"] == {"plan": "pro"}


def test_list_serializes_search_and_cursor_params():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.contacts.list({"limit": 50, "search": "foo", "subscribed": "true"})
    url = str(rec.request.url)
    assert "limit=50" in url
    assert "search=foo" in url
    assert "subscribed=true" in url


def test_update_patches_contact_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "c_3", "email": "a@b.com"}}))
    client = make_client(rec)
    client.contacts.update("c_3", {"data": {"plan": "enterprise"}})
    assert str(rec.request.url) == "http://localhost/api/contacts/c_3"
    assert rec.request.method == "PATCH"


def test_delete_sends_delete_and_resolves_on_204():
    rec = Recorder(empty_response(204))
    client = make_client(rec)
    assert client.contacts.delete("c_4") is None
    assert rec.request.method == "DELETE"


def test_get_raises_not_found_on_404():
    rec = Recorder(
        json_response(404, {"error": {"message": "no such contact", "code": "not_found"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyNotFoundError):
        client.contacts.get("c_missing")


def test_bulk_create_posts_bulk_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"created": 2}}))
    client = make_client(rec)
    client.contacts.bulk_create(
        {"contacts": [{"email": "a@b.com", "subscribed": True}, {"email": "b@c.com"}]}
    )
    assert str(rec.request.url) == "http://localhost/api/contacts/bulk"


def test_bulk_delete_sends_delete_with_body():
    rec = Recorder(json_response(200, {"success": True, "data": {"deleted": 1}}))
    client = make_client(rec)
    client.contacts.bulk_delete({"emails": ["a@b.com"]})
    assert str(rec.request.url) == "http://localhost/api/contacts/bulk"
    assert rec.request.method == "DELETE"
    assert json.loads(rec.request.content) == {"emails": ["a@b.com"]}
