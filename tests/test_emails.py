"""Emails resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import Recorder, empty_response, json_response, make_client

V1_RECEIPT = {"id": "em_1", "status": "PENDING", "to": "user@example.com", "from": "hi@acme.com"}


def test_send_v1_posts_the_versioned_path_and_returns_a_delivery_status():
    rec = Recorder(json_response(202, V1_RECEIPT))
    client = make_client(rec)

    receipt = client.emails.send_v1(
        {"to": "user@example.com", "subject": "hi", "body": "<p>hi</p>"}
    )

    assert str(rec.request.url) == "http://localhost/api/v1/emails"
    assert rec.request.method == "POST"
    # The whole reason this exists: the legacy send reports no delivery status.
    assert receipt["status"] == "PENDING"


def test_send_v1_forwards_an_idempotency_key():
    rec = Recorder(json_response(202, V1_RECEIPT))
    client = make_client(rec)

    client.emails.send_v1({"to": "user@example.com"}, idempotency_key="key-123")

    assert rec.request.headers["Idempotency-Key"] == "key-123"


def test_send_v1_leaves_the_legacy_send_pointed_at_the_old_path():
    # Additive, not a migration: repointing send() would change what existing
    # callers receive, and that is a breaking change taken deliberately or not
    # at all. This is what makes "additive" checkable rather than claimed.
    rec = Recorder(json_response(200, {"success": True, "data": {"emails": [], "timestamp": "t"}}))
    client = make_client(rec)

    client.emails.send({"to": "user@example.com"})

    assert str(rec.request.url) == "http://localhost/api/emails"


def test_send_test_v1_posts_to_the_sandbox_route():
    rec = Recorder(
        json_response(
            202,
            {
                "id": "em_t1",
                "status": "PENDING",
                "to": "sandbox.proj_1@sendly.now",
                "from": "hi@acme.com",
                "sandbox": True,
            },
        )
    )
    client = make_client(rec)

    receipt = client.emails.send_test_v1({"subject": "hi", "body": "<p>hi</p>"})

    assert str(rec.request.url) == "http://localhost/api/v1/emails/test"
    assert json.loads(rec.request.content) == {"subject": "hi", "body": "<p>hi</p>"}
    assert receipt["sandbox"] is True


def test_send_posts_emails_with_bearer_and_body():
    rec = Recorder(
        json_response(200, {"success": True, "data": {"id": "em_1", "status": "PENDING"}})
    )
    client = make_client(rec)
    result = client.emails.send(
        {"from": "a@b.com", "to": "c@d.com", "subject": "hi", "body": "<p>hi</p>"}
    )
    req = rec.request
    assert str(req.url) == "http://localhost/api/emails"
    assert req.method == "POST"
    assert req.headers["content-type"] == "application/json"
    body = json.loads(req.content)
    assert body["from"] == "a@b.com"
    assert body["subject"] == "hi"
    assert result["id"] == "em_1"


def test_send_forwards_idempotency_key_header():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "em_2"}}))
    client = make_client(rec)
    client.emails.send(
        {"from": "a@b.com", "to": "c@d.com", "subject": "hi", "body": "x"},
        idempotency_key="idem-123",
    )
    assert rec.request.headers["idempotency-key"] == "idem-123"


def test_send_omits_idempotency_key_when_not_given():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "em_3"}}))
    client = make_client(rec)
    client.emails.send({"from": "a@b.com", "to": "c@d.com", "subject": "hi", "body": "x"})
    assert "idempotency-key" not in rec.request.headers


def test_send_raises_validation_error_on_400():
    rec = Recorder(json_response(400, {"error": {"message": "bad email", "code": "invalid_body"}}))
    client = make_client(rec)
    with pytest.raises(SendlyValidationError):
        client.emails.send({"from": "a", "to": "b", "subject": "x", "body": "y"})


def test_list_serializes_query_params():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.emails.list({"limit": 5, "tag": "newsletter", "status": "DELIVERED"})
    url = str(rec.request.url)
    assert rec.request.method == "GET"
    assert "limit=5" in url
    assert "tag=newsletter" in url
    assert "status=DELIVERED" in url


def test_get_builds_email_path():
    rec = Recorder(json_response(200, {"success": True, "data": {}}))
    client = make_client(rec)
    client.emails.get("em_42")
    assert str(rec.request.url) == "http://localhost/api/emails/em_42"


def test_cancel_schedule_deletes_schedule_path():
    rec = Recorder(json_response(200, {"success": True}))
    client = make_client(rec)
    client.emails.cancel_schedule("em_42")
    assert str(rec.request.url) == "http://localhost/api/emails/em_42/schedule"
    assert rec.request.method == "DELETE"


def test_batch_posts_batch_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"results": []}}))
    client = make_client(rec)
    client.emails.batch(
        {"emails": [{"from": "a@b.com", "to": "c@d.com", "subject": "s", "body": "h"}]}
    )
    assert str(rec.request.url) == "http://localhost/api/emails/batch"
    assert rec.request.method == "POST"


def test_cancel_schedule_supports_204():
    rec = Recorder(empty_response(204))
    client = make_client(rec)
    assert client.emails.cancel_schedule("em_x") is None
