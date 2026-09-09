"""Contacts resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyNotFoundError, SendlyValidationError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
)

CONTACT_V1 = {
    "id": "con_1",
    "email": "x@y.com",
    "subscribed": True,
    "custom_fields": {"plan": "pro"},
    "created_at": "2026-01-01T00:00:00.000Z",
    "updated_at": "2026-01-01T00:00:00.000Z",
}


def test_create_posts_and_unwraps_data():
    rec = Recorder(json_response(201, {"success": True, "data": {"id": "c_1", "email": "x@y.com"}}))
    client = make_client(rec)
    result = client.contacts.create({"email": "x@y.com", "subscribed": True})
    assert str(rec.request.url) == "http://localhost/api/contacts"
    assert result["id"] == "c_1"


def test_upsert_posts_upsert_path_with_body():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "c_2", "email": "a@b.com"}}))
    client = make_client(rec)
    client.contacts.upsert({"email": "a@b.com", "subscribed": True, "data": {"plan": "pro"}})
    assert str(rec.request.url) == "http://localhost/api/contacts/upsert"
    body = json.loads(rec.request.content)
    assert body["email"] == "a@b.com"
    assert body["data"] == {"plan": "pro"}


def test_list_serializes_search_and_cursor_params():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.contacts.list({"limit": 50, "search": "foo", "subscribed": "true"})
    url = str(rec.request.url)
    assert "limit=50" in url
    assert "search=foo" in url
    assert "subscribed=true" in url


def test_update_patches_contact_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "c_3", "email": "a@b.com"}}))
    client = make_client(rec)
    client.contacts.update("c_3", {"data": {"plan": "enterprise"}})
    assert str(rec.request.url) == "http://localhost/api/contacts/c_3"
    assert rec.request.method == "PATCH"


def test_delete_sends_delete_and_discards_200_id_body():
    # The API returns 200 with {success, data: {id}}; the SDK discards it -> None.
    rec = Recorder(json_response(200, {"success": True, "data": {"id": "c_4"}}))
    client = make_client(rec)
    assert client.contacts.delete("c_4") is None
    assert rec.request.method == "DELETE"


def test_bulk_delete_raises_validation_error_on_422():
    # Bulk ops on an unresolved project now return 422 VALIDATION_ERROR (was NO_PROJECT).
    rec = Recorder(
        json_response(
            422,
            {
                "success": False,
                "error": {"message": "No project", "code": "VALIDATION_ERROR"},
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyValidationError):
        client.contacts.bulk_delete({"emails": ["a@b.com"]})


def test_get_raises_not_found_on_404():
    rec = Recorder(
        json_response(404, {"error": {"message": "no such contact", "code": "not_found"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyNotFoundError):
        client.contacts.get("c_missing")


def test_bulk_create_posts_bulk_path():
    rec = Recorder(json_response(200, {"success": True, "data": {"created": 2}}))
    client = make_client(rec)
    client.contacts.bulk_create(
        {"contacts": [{"email": "a@b.com", "subscribed": True}, {"email": "b@c.com"}]}
    )
    assert str(rec.request.url) == "http://localhost/api/contacts/bulk"


def test_bulk_delete_sends_delete_with_body():
    rec = Recorder(json_response(200, {"success": True, "data": {"deleted": 1}}))
    client = make_client(rec)
    client.contacts.bulk_delete({"emails": ["a@b.com"]})
    assert str(rec.request.url) == "http://localhost/api/contacts/bulk"
    assert rec.request.method == "DELETE"
    assert json.loads(rec.request.content) == {"emails": ["a@b.com"]}


def test_create_v1_posts_the_bare_body_and_returns_it_unwrapped():
    rec = Recorder(json_response(201, CONTACT_V1))
    client = make_client(rec)

    result = client.contacts.create_v1({"email": "x@y.com", "custom_fields": {"plan": "pro"}})

    assert str(rec.request.url) == "http://localhost/api/v1/contacts"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {
        "email": "x@y.com",
        "custom_fields": {"plan": "pro"},
    }
    # v1 answers a bare body -- nothing is unwrapped, the whole document arrives.
    assert result == CONTACT_V1


def test_get_update_and_delete_v1_hit_the_id_path():
    rec = Recorder(json_response(200, CONTACT_V1))
    client = make_client(rec)
    assert client.contacts.get_v1("con_1") == CONTACT_V1
    assert str(rec.request.url) == "http://localhost/api/v1/contacts/con_1"
    assert rec.request.method == "GET"

    rec = Recorder(json_response(200, CONTACT_V1))
    client = make_client(rec)
    client.contacts.update_v1("con_1", {"custom_fields": {"plan": "enterprise"}})
    assert str(rec.request.url) == "http://localhost/api/v1/contacts/con_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"custom_fields": {"plan": "enterprise"}}

    # Unlike the legacy delete, the acknowledgement is handed back, not discarded.
    rec = Recorder(json_response(200, {"id": "con_1", "deleted": True}))
    client = make_client(rec)
    assert client.contacts.delete_v1("con_1") == {"id": "con_1", "deleted": True}
    assert rec.request.method == "DELETE"


def test_list_v1_serializes_search_subscribed_and_cursor_params():
    page = cursor_page([CONTACT_V1])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.contacts.list_v1({"limit": 10, "search": "ada", "subscribed": "false"}) == page
    assert (
        str(rec.request.url)
        == "http://localhost/api/v1/contacts?limit=10&search=ada&subscribed=false"
    )


def test_topic_preferences_gets_the_topics_sub_path():
    preferences = {
        "contact_id": "con_1",
        "subscribed": False,
        "topics": [
            {
                "topic_id": "top_1",
                "key": "product-news",
                "name": "Product news",
                "subscribed": True,
                "pending": False,
            }
        ],
    }
    rec = Recorder(json_response(200, preferences))
    client = make_client(rec)

    result = client.contacts.topic_preferences("con_1")

    assert str(rec.request.url) == "http://localhost/api/v1/contacts/con_1/topics"
    assert rec.request.method == "GET"
    # The global opt-out outranks the per-topic answers; both must survive the trip.
    assert result["subscribed"] is False
    assert result["topics"][0]["key"] == "product-news"


def test_iter_list_v1_walks_every_page_and_carries_the_filter_forward():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "con_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "con_2"}])),
    )
    client = make_client(rec)

    assert [c["id"] for c in client.contacts.iter_list_v1({"search": "ada"})] == [
        "con_1",
        "con_2",
    ]
    assert rec.urls == [
        "http://localhost/api/v1/contacts?search=ada",
        "http://localhost/api/v1/contacts?search=ada&after=cur_2",
    ]


def test_contact_id_is_percent_encoded_into_the_v1_path():
    rec = Recorder(json_response(200, CONTACT_V1))
    client = make_client(rec)
    client.contacts.get_v1("a/b")
    assert str(rec.request.url) == "http://localhost/api/v1/contacts/a%2Fb"


def test_get_v1_raises_not_found_on_a_404_problem_document():
    rec = Recorder(
        json_response(404, {"error": {"message": "no such contact", "code": "not_found"}})
    )
    client = make_client(rec)
    with pytest.raises(SendlyNotFoundError):
        client.contacts.get_v1("con_missing")
