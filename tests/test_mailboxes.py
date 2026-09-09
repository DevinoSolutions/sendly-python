"""Mailboxes resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyNotFoundError
from support import Recorder, json_response, make_client

MAILBOX = {
    "id": "mb_1",
    "address": "support@example.com",
    "displayName": "Support",
    "status": "ACTIVE",
    "quotaBytes": None,
    "domainId": "dom_1",
    "createdAt": "2026-09-01T00:00:00.000Z",
}

SETTINGS = {
    "imap": {
        "host": "mail.example.com",
        "port": 993,
        "security": "SSL/TLS",
        "username": "support@example.com",
    },
    "smtp": {
        "host": "mail.example.com",
        "port": 465,
        "security": "SSL/TLS",
        "username": "support@example.com",
    },
}


def test_list_unwraps_the_legacy_envelope_to_a_plain_list():
    rec = Recorder(json_response(200, {"success": True, "data": [MAILBOX]}))
    client = make_client(rec)

    mailboxes = client.mailboxes.list()

    assert str(rec.request.url) == "http://localhost/api/mailboxes"
    assert rec.request.method == "GET"
    # The caller gets the list itself, not the {success, data} wrapper.
    assert mailboxes == [MAILBOX]


def test_get_returns_connection_settings_and_never_a_password():
    detail = {**MAILBOX, "settings": SETTINGS}
    rec = Recorder(json_response(200, {"success": True, "data": detail}))
    client = make_client(rec)

    mailbox = client.mailboxes.get("mb_1")

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1"
    assert mailbox["settings"]["imap"]["port"] == 993
    assert mailbox["settings"]["smtp"]["port"] == 465
    # The secret is never on this endpoint -- app passwords carry it, once.
    assert "password" not in mailbox["settings"]["imap"]


def test_list_app_passwords_returns_metadata_only():
    password = {
        "id": "ap_1",
        "name": "Thunderbird",
        "scopes": ["imap", "smtp"],
        "lastFour": "9x2k",
        "lastUsedAt": None,
        "createdAt": "2026-09-01T00:00:00.000Z",
    }
    rec = Recorder(json_response(200, {"success": True, "data": [password]}))
    client = make_client(rec)

    passwords = client.mailboxes.list_app_passwords("mb_1")

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1/app-passwords"
    assert passwords[0]["lastFour"] == "9x2k"
    assert "password" not in passwords[0]


def test_ids_are_percent_encoded_rather_than_spliced_into_the_path():
    rec = Recorder(json_response(200, {"success": True, "data": []}))
    client = make_client(rec)

    client.mailboxes.list_app_passwords("mb/../evil")

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb%2F..%2Fevil/app-passwords"


def test_unknown_mailbox_raises_not_found():
    rec = Recorder(
        json_response(
            404, {"success": False, "error": {"message": "Mailbox not found", "code": "NOT_FOUND"}}
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyNotFoundError):
        client.mailboxes.get("nope")


def test_send_message_posts_the_composed_body_and_unwraps_the_envelope():
    receipt = {"submitted": True, "conversationId": "cv_1", "messageId": "msg_1"}
    rec = Recorder(json_response(201, {"success": True, "data": receipt}))
    client = make_client(rec)

    submitted = client.mailboxes.send_message(
        "mb_1",
        {
            "to": ["customer@example.com"],
            "subject": "Your order",
            "body": "It shipped this morning.",
        },
    )

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1/messages"
    assert rec.request.method == "POST"
    # Unlike the v1 resources, this legacy route's {success, data} wrapper is stripped.
    assert submitted == receipt


def test_send_message_takes_no_from_field__the_mailbox_in_the_path_is_the_sender():
    rec = Recorder(
        json_response(
            201,
            {
                "success": True,
                "data": {"submitted": True, "conversationId": "cv_1", "messageId": "msg_1"},
            },
        )
    )
    client = make_client(rec)

    body = {
        "to": ["customer@example.com"],
        "bcc": ["archive@example.com"],
        "subject": "Your order",
        "body": "It shipped this morning.",
    }
    client.mailboxes.send_message("mb_1", body)

    sent = json.loads(rec.request.content)
    assert sent == body
    assert "from" not in sent


def test_draft_message_posts_to_drafts_unwraps_and_reports_sent_false():
    draft = {"subject": "Your order shipped", "body": "Hi there --", "subjects": [], "sent": False}
    rec = Recorder(json_response(200, {"success": True, "data": draft}))
    client = make_client(rec)

    result = client.mailboxes.draft_message("mb_1", {"mode": "draft", "brief": "order shipped"})

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1/drafts"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"mode": "draft", "brief": "order shipped"}
    # The whole safety story of this pair: drafting never mails anybody.
    assert result == draft
    assert result["sent"] is False


def test_draft_message_in_subject_mode_returns_alternatives_not_a_send_receipt():
    draft = {
        "subject": None,
        "body": None,
        "subjects": ["Shipped!", "On its way"],
        "sent": False,
    }
    rec = Recorder(json_response(200, {"success": True, "data": draft}))
    client = make_client(rec)

    result = client.mailboxes.draft_message(
        "mb_1", {"mode": "subject", "draft": "your order shipped"}
    )

    assert result["subjects"] == ["Shipped!", "On its way"]
    # A draft carries no conversation or message id -- nothing was created.
    assert "messageId" not in result


def test_composition_routes_percent_encode_the_mailbox_id_too():
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {"subject": None, "body": None, "subjects": [], "sent": False},
            },
        )
    )
    client = make_client(rec)

    client.mailboxes.draft_message("mb/../evil", {"mode": "draft"})

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb%2F..%2Fevil/drafts"
