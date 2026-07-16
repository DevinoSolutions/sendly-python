"""Request-core tests: auth headers, URL building, envelope + error mapping."""

from __future__ import annotations

import httpx
import pytest

from sendly import (
    Sendly,
    SendlyAuthenticationError,
    SendlyConnectionError,
    SendlyError,
    SendlyServerError,
    SendlyValidationError,
)
from support import Recorder, json_response, make_client


def test_constructor_raises_without_api_key_or_env(monkeypatch):
    monkeypatch.delenv("SENDLY_API_KEY", raising=False)
    with pytest.raises(SendlyError):
        Sendly()


def test_constructor_raises_on_empty_api_key(monkeypatch):
    monkeypatch.delenv("SENDLY_API_KEY", raising=False)
    with pytest.raises(SendlyError):
        Sendly(api_key="")


def test_empty_api_key_does_not_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("SENDLY_API_KEY", "sk_env")
    with pytest.raises(SendlyError):
        Sendly(api_key="")


def test_constructor_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("SENDLY_API_KEY", "sk_env_key")
    rec = Recorder(json_response(200, {"success": True}))
    client = Sendly(
        base_url="http://localhost", client=httpx.Client(transport=httpx.MockTransport(rec))
    )
    client.request(method="GET", path="/api/domains")
    assert rec.request.headers["authorization"] == "Bearer sk_env_key"


def test_attaches_auth_accept_user_agent_headers():
    rec = Recorder(json_response(200, {"success": True}))
    client = make_client(rec)
    client.request(method="GET", path="/api/domains")
    headers = rec.request.headers
    assert str(rec.request.url) == "http://localhost/api/domains"
    assert headers["authorization"] == "Bearer sk_test_key"
    assert headers["accept"] == "application/json"
    assert headers["user-agent"].startswith("sendly-python/")


def test_strips_trailing_slash_from_base_url():
    rec = Recorder(json_response(200, {"success": True}))
    client = Sendly(
        api_key="sk",
        base_url="http://localhost///",
        client=httpx.Client(transport=httpx.MockTransport(rec)),
        timeout=0,
    )
    client.request(method="GET", path="/api/domains")
    assert str(rec.request.url) == "http://localhost/api/domains"


def test_serializes_query_and_skips_none_and_empty():
    rec = Recorder(json_response(200, {"success": True}))
    client = make_client(rec)
    client.request(
        method="GET",
        path="/api/emails",
        query={"limit": 10, "tag": "welcome", "skip": None, "blank": ""},
    )
    url = str(rec.request.url)
    assert "limit=10" in url
    assert "tag=welcome" in url
    assert "skip=" not in url
    assert "blank=" not in url


def test_query_list_value_appends_repeated_keys():
    rec = Recorder(json_response(200, {"success": True}))
    client = make_client(rec)
    client.request(method="GET", path="/api/emails", query={"status": ["SENT", "DELIVERED"]})
    url = str(rec.request.url)
    assert "status=SENT" in url
    assert "status=DELIVERED" in url


def test_query_bool_is_lowercased_like_js():
    rec = Recorder(json_response(200, {"success": True}))
    client = make_client(rec)
    client.request(method="GET", path="/api/contacts", query={"subscribed": True})
    assert "subscribed=true" in str(rec.request.url)


def test_maps_400_to_validation_error_with_envelope():
    rec = Recorder(json_response(400, {"error": {"message": "bad input", "code": "invalid_body"}}))
    client = make_client(rec)
    with pytest.raises(SendlyValidationError) as excinfo:
        client.request(method="GET", path="/api/emails")
    err = excinfo.value
    assert err.status_code == 400
    assert err.error_code == "invalid_body"
    assert err.message == "bad input"
    assert str(err) == "bad input"


def test_maps_422_to_validation_error_with_details():
    # Migrated routes return 422 VALIDATION_ERROR (with error.details.errors)
    # for invalid input; it must map to SendlyValidationError like a 400.
    rec = Recorder(
        json_response(
            422,
            {
                "success": False,
                "error": {
                    "message": "Invalid body",
                    "code": "VALIDATION_ERROR",
                    "details": {"errors": [{"path": "email", "message": "required"}]},
                },
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyValidationError) as excinfo:
        client.request(method="POST", path="/api/contacts", body={})
    err = excinfo.value
    assert err.status_code == 422
    assert err.error_code == "VALIDATION_ERROR"
    assert err.body["error"]["details"]["errors"][0]["path"] == "email"


def test_maps_401_to_authentication_error():
    rec = Recorder(json_response(401, {"error": {"message": "no key", "code": "unauthorized"}}))
    client = make_client(rec)
    with pytest.raises(SendlyAuthenticationError):
        client.request(method="GET", path="/api/emails")


def test_non_json_error_body_uses_invalid_response_code():
    rec = Recorder(json_response(500, "not json at all"))
    client = make_client(rec)
    with pytest.raises(SendlyServerError) as excinfo:
        client.request(method="GET", path="/api/emails")
    assert excinfo.value.status_code == 500
    assert excinfo.value.error_code == "invalid_response"


def test_json_error_without_envelope_uses_http_status_code():
    rec = Recorder(json_response(503, {"weird": "shape"}))
    client = make_client(rec)
    with pytest.raises(SendlyServerError) as excinfo:
        client.request(method="GET", path="/api/emails")
    assert excinfo.value.error_code == "http_503"


def test_non_json_success_returns_raw_text():
    rec = Recorder(httpx.Response(200, text="pong", headers={"content-type": "text/plain"}))
    client = make_client(rec)
    result = client.request(method="GET", path="/api/ping")
    assert result == "pong"


def test_wraps_transport_error_as_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = make_client(handler)
    with pytest.raises(SendlyConnectionError):
        client.request(method="GET", path="/api/emails")


def test_rejects_non_rooted_path():
    client = make_client(Recorder(json_response(200, {"success": True})))
    with pytest.raises(SendlyError, match="must start with"):
        client.request(method="GET", path="api/no/leading/slash")


def test_validation_error_is_sendly_error_subclass():
    rec = Recorder(json_response(400, {"error": {"message": "x", "code": "y"}}))
    client = make_client(rec)
    with pytest.raises(SendlyValidationError) as excinfo:
        client.request(method="GET", path="/api/emails")
    assert isinstance(excinfo.value, SendlyError)
