"""Lists resource tests (legacy subscribe / unsubscribe, plus the ``/api/v1`` half)."""

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

LIST_V1 = {
    "id": "lst_1",
    "name": "Weekly digest",
    "description": None,
    "double_opt_in": True,
    "confirmation_template_id": None,
    "redirect_url": None,
    "member_count": 3,
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}


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


def test_create_v1_posts_the_bare_body_and_returns_it_unwrapped():
    rec = Recorder(json_response(201, LIST_V1))
    client = make_client(rec)

    result = client.lists.create_v1({"name": "Weekly digest", "double_opt_in": True})

    assert str(rec.request.url) == "http://localhost/api/v1/lists"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"name": "Weekly digest", "double_opt_in": True}
    # v1 answers a bare body -- nothing is unwrapped, the whole document arrives.
    assert result == LIST_V1


def test_get_update_and_delete_v1_hit_the_id_path():
    rec = Recorder(json_response(200, LIST_V1))
    client = make_client(rec)
    assert client.lists.get_v1("lst_1") == LIST_V1
    assert str(rec.request.url) == "http://localhost/api/v1/lists/lst_1"
    assert rec.request.method == "GET"

    rec = Recorder(json_response(200, LIST_V1))
    client = make_client(rec)
    client.lists.update_v1("lst_1", {"name": "Renamed", "redirect_url": None})
    assert str(rec.request.url) == "http://localhost/api/v1/lists/lst_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"name": "Renamed", "redirect_url": None}

    rec = Recorder(json_response(200, {"id": "lst_1", "deleted": True}))
    client = make_client(rec)
    assert client.lists.delete_v1("lst_1") == {"id": "lst_1", "deleted": True}
    assert rec.request.method == "DELETE"


def test_list_v1_serializes_the_cursor_params():
    page = cursor_page([LIST_V1])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.lists.list_v1({"limit": 25, "after": "cur_lst"}) == page
    assert str(rec.request.url) == "http://localhost/api/v1/lists?limit=25&after=cur_lst"


def test_iter_list_v1_walks_every_page_and_carries_the_filter_forward():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "lst_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "lst_2"}])),
    )
    client = make_client(rec)

    assert [item["id"] for item in client.lists.iter_list_v1({"limit": 1})] == ["lst_1", "lst_2"]
    assert rec.urls == [
        "http://localhost/api/v1/lists?limit=1",
        "http://localhost/api/v1/lists?limit=1&after=cur_2",
    ]


def test_start_validation_run_posts_the_validation_runs_sub_path():
    run = {
        "id": "vrun_1",
        "list_id": "lst_1",
        "status": "pending",
        "processed_count": 0,
        "deliverable_count": 0,
        "undeliverable_count": 0,
        "risky_count": 0,
        "started_at": None,
        "completed_at": None,
        "failure_reason": None,
        "created_at": "2026-01-01T00:00:00.000Z",
    }
    rec = Recorder(json_response(202, run))
    client = make_client(rec)

    started = client.lists.start_validation_run("lst_1")

    assert str(rec.request.url) == "http://localhost/api/v1/lists/lst_1/validation-runs"
    assert rec.request.method == "POST"
    # Billed per address checked, so the caller must see the run it just paid to start.
    assert started == run


def test_list_id_is_percent_encoded_into_the_v1_paths():
    rec = Recorder(json_response(200, LIST_V1))
    client = make_client(rec)
    client.lists.get_v1("lst/1")
    assert str(rec.request.url) == "http://localhost/api/v1/lists/lst%2F1"

    rec = Recorder(json_response(202, {"id": "vrun_1"}))
    client = make_client(rec)
    client.lists.start_validation_run("lst/1")
    assert str(rec.request.url) == "http://localhost/api/v1/lists/lst%2F1/validation-runs"


def test_delete_v1_surfaces_a_409_problem_document_as_a_conflict():
    rec = Recorder(
        problem_response(
            409,
            {
                "type": "https://docs.sendly.now/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "code": "conflict",
                "detail": "List is referenced by 1 campaign.",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyConflictError) as caught:
        client.lists.delete_v1("lst_1")
    assert caught.value.error_code == "conflict"
