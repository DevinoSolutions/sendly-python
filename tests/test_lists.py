"""Lists resource tests (legacy ``/api/lists`` subscribe / unsubscribe)."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyConflictError
from support import Recorder, json_response, make_client


def test_subscribe_posts_the_email_and_unwraps_the_membership():
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {
                    "membershipId": "mem_1",
                    "status": "CONFIRMED",
                    "created": True,
                    "previousStatus": None,
                },
            },
        )
    )
    client = make_client(rec)

    result = client.lists.subscribe("lst_1", {"email": "a@b.com"})

    assert str(rec.request.url) == "http://localhost/api/lists/lst_1/subscribe"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"email": "a@b.com"}
    # Legacy dialect: the {success, data} envelope is unwrapped for the caller.
    assert result["membershipId"] == "mem_1"
    assert result["previousStatus"] is None


def test_subscribe_to_a_double_opt_in_list_returns_pending_and_a_confirm_token():
    # Sendly does not send the confirmation email -- the caller must deliver the
    # token, so it has to reach them intact.
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {
                    "membershipId": "mem_2",
                    "status": "PENDING",
                    "created": True,
                    "previousStatus": None,
                    "confirmToken": "tok_abc",
                },
            },
        )
    )
    client = make_client(rec)

    result = client.lists.subscribe("lst_1", {"email": "a@b.com"})

    assert result["status"] == "PENDING"
    assert result["confirmToken"] == "tok_abc"


def test_resubscribing_an_opted_out_address_conflicts_without_allow_resubscribe():
    rec = Recorder(
        json_response(
            409,
            {
                "success": False,
                "error": {
                    "message": "This address previously unsubscribed.",
                    "code": "RESUBSCRIBE_CONFIRMATION_REQUIRED",
                },
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyConflictError) as caught:
        client.lists.subscribe("lst_1", {"email": "a@b.com"})
    assert caught.value.error_code == "RESUBSCRIBE_CONFIRMATION_REQUIRED"


def test_allow_resubscribe_is_forwarded_in_the_body():
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {
                    "membershipId": "mem_1",
                    "status": "CONFIRMED",
                    "created": False,
                    "previousStatus": "UNSUBSCRIBED",
                },
            },
        )
    )
    client = make_client(rec)

    result = client.lists.subscribe("lst_1", {"email": "a@b.com", "allowResubscribe": True})

    assert json.loads(rec.request.content)["allowResubscribe"] is True
    assert result["previousStatus"] == "UNSUBSCRIBED"


def test_unsubscribe_posts_to_the_unsubscribe_path_and_echoes_the_address():
    rec = Recorder(json_response(200, {"success": True, "data": {"email": "a@b.com"}}))
    client = make_client(rec)

    result = client.lists.unsubscribe("lst_1", {"email": "a@b.com"})

    assert str(rec.request.url) == "http://localhost/api/lists/lst_1/unsubscribe"
    assert result == {"email": "a@b.com"}


def test_list_id_is_percent_encoded_into_the_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"email": "a@b.com"}}))
    client = make_client(rec)
    client.lists.unsubscribe("lst/1", {"email": "a@b.com"})
    assert str(rec.request.url) == "http://localhost/api/lists/lst%2F1/unsubscribe"
