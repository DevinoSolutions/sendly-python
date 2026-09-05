"""Suppression resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyNotFoundError, SendlyServerError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    empty_response,
    json_response,
    make_client,
    problem_response,
)

SUPPRESSION_V1 = {
    "email": "spam@x.com",
    "reason": "MANUAL",
    "source": "API",
    "created_at": "2026-01-01T00:00:00.000Z",
}


def test_add_posts_suppression():
    rec = Recorder(
        json_response(201, {"success": True, "data": {"id": "s_1", "email": "spam@x.com"}})
    )
    client = make_client(rec)
    client.suppression.add({"email": "spam@x.com", "reason": "MANUAL"})
    assert str(rec.request.url) == "http://localhost/api/suppression"


def test_list_serializes_reason_filter():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.suppression.list({"reason": "MANUAL", "limit": 100})
    url = str(rec.request.url)
    assert "reason=MANUAL" in url
    assert "limit=100" in url


def test_get_percent_encodes_email_path_segment():
    rec = Recorder(json_response(200, {"success": True, "data": {"suppressed": False}}))
    client = make_client(rec)
    client.suppression.get("user+tag@example.com")
    url = str(rec.request.url)
    # The email is a single path segment and must be percent-encoded, not passed raw.
    assert url == "http://localhost/api/suppression/user%2Btag%40example.com"


def test_remove_deletes_and_resolves_on_204():
    rec = Recorder(empty_response(204))
    client = make_client(rec)
    assert client.suppression.remove("a@b.com") is None
    assert rec.request.method == "DELETE"


def test_add_raises_server_error_on_500():
    rec = Recorder(json_response(500, {"error": {"message": "oops", "code": "server_error"}}))
    client = make_client(rec)
    with pytest.raises(SendlyServerError):
        client.suppression.add({"email": "x@y.com", "reason": "MANUAL"})


def test_create_v1_posts_the_plural_path_and_returns_the_bare_record():
    rec = Recorder(json_response(201, SUPPRESSION_V1))
    client = make_client(rec)

    result = client.suppression.create_v1({"email": "spam@x.com", "reason": "COMPLAINT"})

    # The v1 path segment is plural, unlike the legacy `/api/suppression`.
    assert str(rec.request.url) == "http://localhost/api/v1/suppressions"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"email": "spam@x.com", "reason": "COMPLAINT"}
    # v1 answers a bare body — nothing is unwrapped out of a {success, data} envelope.
    assert result == SUPPRESSION_V1


def test_get_v1_percent_encodes_the_address_so_a_plus_stays_in_the_local_part():
    rec = Recorder(json_response(200, SUPPRESSION_V1))
    client = make_client(rec)

    client.suppression.get_v1("user+tag@example.com")

    # `+` must survive as %2B; an encoder that leaves it raw addresses a space instead.
    assert str(rec.request.url) == "http://localhost/api/v1/suppressions/user%2Btag%40example.com"
    assert rec.request.method == "GET"


def test_get_v1_hands_back_the_whole_bare_body():
    rec = Recorder(json_response(200, SUPPRESSION_V1))
    client = make_client(rec)

    assert client.suppression.get_v1("spam@x.com") == SUPPRESSION_V1


def test_get_v1_on_an_unsuppressed_address_raises_the_definite_404():
    rec = Recorder(
        problem_response(
            404,
            {
                "type": "https://docs.sendly.now/errors/resource_not_found",
                "title": "Not Found",
                "status": 404,
                "code": "resource_not_found",
                "detail": "No suppression record for clean@example.com.",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyNotFoundError):
        client.suppression.get_v1("clean@example.com")


def test_delete_v1_encodes_the_address_and_returns_the_acknowledgement():
    rec = Recorder(json_response(200, {"email": "user+tag@example.com", "deleted": True}))
    client = make_client(rec)

    deleted = client.suppression.delete_v1("user+tag@example.com")

    assert deleted == {"email": "user+tag@example.com", "deleted": True}
    assert str(rec.request.url) == "http://localhost/api/v1/suppressions/user%2Btag%40example.com"
    assert rec.request.method == "DELETE"


def test_list_v1_serializes_the_cursor_params_and_the_reason_filter():
    page = cursor_page([SUPPRESSION_V1])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.suppression.list_v1({"limit": 5, "reason": "HARD_BOUNCE"}) == page
    url = str(rec.request.url)
    assert url == "http://localhost/api/v1/suppressions?limit=5&reason=HARD_BOUNCE"


def test_iter_list_v1_walks_every_page_and_keeps_the_filter():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"email": "one@x.com"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"email": "two@x.com"}])),
    )
    client = make_client(rec)

    emails = [s["email"] for s in client.suppression.iter_list_v1({"reason": "COMPLAINT"})]

    assert emails == ["one@x.com", "two@x.com"]
    assert rec.urls == [
        "http://localhost/api/v1/suppressions?reason=COMPLAINT",
        "http://localhost/api/v1/suppressions?reason=COMPLAINT&after=cur_2",
    ]
