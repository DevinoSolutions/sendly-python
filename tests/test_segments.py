"""Segments resource tests (``/api/v1``)."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
    problem_response,
)

SEGMENT = {
    "id": "seg_1",
    "name": "Power users",
    "type": "DYNAMIC",
    "condition": {"field": "plan", "op": "eq", "value": "pro"},
    "member_count": 42,
}


def test_list_returns_the_cursor_envelope():
    page = cursor_page([SEGMENT])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.segments.list() == page
    assert str(rec.request.url) == "http://localhost/api/v1/segments"


def test_create_posts_the_body_and_sends_no_idempotency_key():
    # Creating a segment neither sends mail nor consumes quota, so the API
    # deliberately does not ledger it.
    rec = Recorder(json_response(201, SEGMENT))
    client = make_client(rec)

    result = client.segments.create({"name": "Power users", "type": "DYNAMIC"})

    assert str(rec.request.url) == "http://localhost/api/v1/segments"
    assert json.loads(rec.request.content)["name"] == "Power users"
    assert "Idempotency-Key" not in rec.request.headers
    assert result == SEGMENT


def test_get_update_and_delete_hit_the_id_path():
    rec = Recorder(json_response(200, SEGMENT))
    client = make_client(rec)
    assert client.segments.get("seg_1") == SEGMENT
    assert str(rec.request.url) == "http://localhost/api/v1/segments/seg_1"

    rec = Recorder(json_response(200, SEGMENT))
    client = make_client(rec)
    client.segments.update("seg_1", {"name": "Renamed"})
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"name": "Renamed"}

    rec = Recorder(json_response(200, {"id": "seg_1", "deleted": True}))
    client = make_client(rec)
    assert client.segments.delete("seg_1") == {"id": "seg_1", "deleted": True}
    assert rec.request.method == "DELETE"


def test_an_invalid_dynamic_condition_fails_the_create_with_field_errors():
    rec = Recorder(
        problem_response(
            422,
            {
                "type": "https://docs.sendly.now/errors/validation_error",
                "title": "Validation Error",
                "status": 422,
                "code": "validation_error",
                "detail": "`condition` is not a valid segment condition.",
                "errors": [
                    {"pointer": "/condition/op", "code": "invalid_enum", "message": "unknown op"}
                ],
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyValidationError) as caught:
        client.segments.create({"name": "Broken", "type": "DYNAMIC", "condition": {"op": "??"}})
    assert caught.value.field_errors[0]["pointer"] == "/condition/op"


def test_list_contacts_hits_the_nested_path_with_pagination_params():
    page = cursor_page([{"id": "con_1", "email": "a@b.com"}])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.segments.list_contacts("seg_1", {"limit": 50}) == page
    assert str(rec.request.url) == "http://localhost/api/v1/segments/seg_1/contacts?limit=50"


def test_iter_list_walks_every_page():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "seg_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "seg_2"}])),
    )
    client = make_client(rec)

    assert [s["id"] for s in client.segments.iter_list()] == ["seg_1", "seg_2"]
    assert rec.urls[1] == "http://localhost/api/v1/segments?after=cur_2"


def test_iter_list_contacts_keeps_the_segment_id_and_filters_across_pages():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "con_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "con_2"}])),
    )
    client = make_client(rec)

    ids = [c["id"] for c in client.segments.iter_list_contacts("seg_1", {"limit": 1})]

    assert ids == ["con_1", "con_2"]
    assert rec.urls == [
        "http://localhost/api/v1/segments/seg_1/contacts?limit=1",
        "http://localhost/api/v1/segments/seg_1/contacts?limit=1&after=cur_2",
    ]
