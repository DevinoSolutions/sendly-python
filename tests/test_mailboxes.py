"""Mailboxes resource tests."""

from __future__ import annotations

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
