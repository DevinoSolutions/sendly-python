"""Templates resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyConflictError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
    problem_response,
)

TEMPLATE_V1 = {
    "id": "tpl_1",
    "name": "Welcome",
    "description": None,
    "subject": "Welcome aboard",
    "body": "<p>hi</p>",
    "from": "a@b.com",
    "from_name": None,
    "reply_to": None,
    "email_category": "MARKETING",
    "version": 1,
}


def test_create_posts_templates():
    rec = Recorder(json_response(201, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    client.templates.create(
        {
            "name": "Welcome",
            "subject": "Welcome",
            "body": "<p>hi</p>",
            "from": "a@b.com",
            # `emailCategory` since 1.1. `type` said nothing about which of a
            # template's several kinds it named.
            "emailCategory": "MARKETING",
        }
    )
    assert str(rec.request.url) == "http://localhost/api/templates"
    assert json.loads(rec.request.content)["emailCategory"] == "MARKETING"


def test_list_serializes_cursor_and_limit():
    rec = Recorder(json_response(200, {"success": True, "data": {"data": [], "total": 0}}))
    client = make_client(rec)
    client.templates.list(
        {"limit": 25, "cursor": "t_50", "emailCategory": "SELF_MANAGED_UNSUBSCRIBE"}
    )
    url = str(rec.request.url)
    assert "limit=25" in url
    assert "cursor=t_50" in url
    # `SELF_MANAGED_UNSUBSCRIBE` is the 1.1 name for the value once called `HEADLESS`.
    assert "emailCategory=SELF_MANAGED_UNSUBSCRIBE" in url
    assert "type=" not in url


def test_update_patches_template():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    client.templates.update("t_1", {"name": "New name"})
    assert rec.request.method == "PATCH"


def test_delete_discards_200_id_body():
    # The API returns 200 with {success, data: {id}}; the SDK discards it -> None.
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "t_1"}}))
    client = make_client(rec)
    assert client.templates.delete("t_1") is None


def test_delete_raises_conflict_on_409():
    rec = Recorder(
        json_response(409, {"error": {"message": "template in use", "code": "conflict"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyConflictError):
        client.templates.delete("t_1")


def test_create_v1_posts_the_bare_body_and_returns_the_bare_template():
    rec = Recorder(json_response(201, TEMPLATE_V1))
    client = make_client(rec)

    result = client.templates.create_v1(
        {
            "name": "Welcome",
            "subject": "Welcome aboard",
            "body": "<p>hi</p>",
            "from": "a@b.com",
            "email_category": "MARKETING",
        }
    )

    assert str(rec.request.url) == "http://localhost/api/v1/templates"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content)["email_category"] == "MARKETING"
    # v1 answers a bare body — nothing is unwrapped out of a {success, data} envelope.
    assert result == TEMPLATE_V1


def test_get_v1_hands_back_the_whole_bare_body():
    rec = Recorder(json_response(200, TEMPLATE_V1))
    client = make_client(rec)

    result = client.templates.get_v1("tpl_1")

    assert str(rec.request.url) == "http://localhost/api/v1/templates/tpl_1"
    assert rec.request.method == "GET"
    assert result == TEMPLATE_V1


def test_update_v1_patches_only_the_fields_sent():
    rec = Recorder(json_response(200, TEMPLATE_V1))
    client = make_client(rec)

    client.templates.update_v1("tpl_1", {"email_category": "TRANSACTIONAL"})

    assert str(rec.request.url) == "http://localhost/api/v1/templates/tpl_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"email_category": "TRANSACTIONAL"}


def test_delete_v1_returns_the_acknowledgement_the_legacy_delete_discards():
    rec = Recorder(json_response(200, {"id": "tpl_1", "deleted": True}))
    client = make_client(rec)

    assert client.templates.delete_v1("tpl_1") == {"id": "tpl_1", "deleted": True}
    assert str(rec.request.url) == "http://localhost/api/v1/templates/tpl_1"
    assert rec.request.method == "DELETE"


def test_delete_v1_surfaces_the_rfc_9457_conflict_for_a_template_still_in_use():
    rec = Recorder(
        problem_response(
            409,
            {
                "type": "https://docs.sendly.now/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "code": "conflict",
                "detail": "Template is referenced by 1 scheduled campaign.",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyConflictError):
        client.templates.delete_v1("tpl_1")


def test_list_v1_serializes_the_cursor_params_and_the_snake_case_category_filter():
    page = cursor_page([TEMPLATE_V1])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.templates.list_v1({"limit": 5, "search": "welcome"}) == page
    url = str(rec.request.url)
    assert url.startswith("http://localhost/api/v1/templates?")
    assert "limit=5" in url
    assert "search=welcome" in url


def test_iter_list_v1_walks_every_page_and_keeps_the_filter():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "tpl_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "tpl_2"}])),
    )
    client = make_client(rec)

    ids = [t["id"] for t in client.templates.iter_list_v1({"email_category": "MARKETING"})]

    assert ids == ["tpl_1", "tpl_2"]
    assert rec.urls == [
        "http://localhost/api/v1/templates?email_category=MARKETING",
        "http://localhost/api/v1/templates?email_category=MARKETING&after=cur_2",
    ]
