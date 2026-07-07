"""Domains resource tests."""

from __future__ import annotations

import pytest

from sendly import SendlyPermissionError
from support import Recorder, json_response, make_client


def test_create_posts_domains_and_unwraps():
    rec = Recorder(
        json_response(201, {"success": True, "data": {"id": "d_1", "name": "mail.example.com"}})
    )
    client = make_client(rec)
    result = client.domains.create({"domain": "mail.example.com"})
    assert str(rec.request.url) == "http://localhost/api/domains"
    assert result["id"] == "d_1"


def test_list_gets_domains():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.domains.list()
    assert rec.request.method == "GET"
    assert str(rec.request.url) == "http://localhost/api/domains"


def test_verify_posts_verify_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"status": "PENDING"}}))
    client = make_client(rec)
    client.domains.verify("d_1")
    assert str(rec.request.url) == "http://localhost/api/domains/d_1/verify"
    assert rec.request.method == "POST"


def test_get_verification_gets_verify_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"status": "VERIFIED"}}))
    client = make_client(rec)
    client.domains.get_verification("d_1")
    assert str(rec.request.url) == "http://localhost/api/domains/d_1/verify"
    assert rec.request.method == "GET"


def test_create_raises_permission_error_on_403():
    rec = Recorder(
        json_response(
            403, {"error": {"message": "pk key cannot create domains", "code": "forbidden"}}
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyPermissionError):
        client.domains.create({"domain": "x.com"})
