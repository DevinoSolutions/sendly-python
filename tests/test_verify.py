"""Verify resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import Recorder, json_response, make_client


def test_email_posts_verify_with_body():
    rec = Recorder(
        json_response(
            200,
            {"success": True, "data": {"email": "user@example.com", "valid": True, "reason": "ok"}},
        )
    )
    client = make_client(rec)
    result = client.verify.email({"email": "user@example.com"})
    req = rec.request
    assert str(req.url) == "http://localhost/api/verify"
    assert req.method == "POST"
    assert req.headers["content-type"] == "application/json"
    body = json.loads(req.content)
    assert body["email"] == "user@example.com"
    # Response is unwrapped to the envelope's `data` payload.
    assert result["valid"] is True
    assert result["email"] == "user@example.com"
    assert result["reason"] == "ok"


def test_email_still_sends_auth_header_despite_open_endpoint():
    rec = Recorder(
        json_response(200, {"success": True, "data": {"email": "a@b.com", "valid": False}})
    )
    client = make_client(rec)
    result = client.verify.email({"email": "a@b.com"})
    # The endpoint is open server-side, but the SDK still attaches its bearer token.
    assert rec.request.headers["authorization"] == "Bearer sk_test_key"
    assert result["valid"] is False


def test_email_raises_validation_error_on_400():
    rec = Recorder(
        json_response(400, {"error": {"message": "email is required", "code": "invalid_body"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyValidationError):
        client.verify.email({})
