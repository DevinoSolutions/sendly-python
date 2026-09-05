"""Topics resource tests (``/api/v1``)."""

from __future__ import annotations

import json

from support import Recorder, SequenceRecorder, cursor_page, json_response, make_client

TOPIC = {
    "id": "top_1",
    "key": "product_news",
    "name": "Product news",
    "description": None,
    "default_opt_in": False,
    "archived": False,
    "subscribed_count": 12,
    "unsubscribed_count": 3,
    "created_at": "2026-01-01T00:00:00.000Z",
}


def topic_page(items: list[object], *, cursor: str | None = None) -> dict[str, object]:
    """One page of the topics list envelope.

    ``support.cursor_page`` under a local name. Through 1.0 this was its own
    builder, because topics answered the next page under ``cursor`` where the
    rest of v1 answers ``next_cursor`` -- and a local fixture is exactly how a
    second dialect stays invisible, so it delegates now rather than repeating
    the shape.
    """
    return cursor_page(items, next_cursor=cursor)


def test_list_returns_the_bare_page_envelope_and_all():
    page = topic_page([TOPIC])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    # v1 does not wrap, so the page itself comes back -- not its "data" list.
    assert client.topics.list() == page
    assert str(rec.request.url) == "http://localhost/api/v1/topics"


def test_list_serializes_limit_after_and_include_archived():
    rec = Recorder(json_response(200, topic_page([])))
    client = make_client(rec)

    client.topics.list({"limit": 10, "after": "cur_top", "include_archived": True})

    url = str(rec.request.url)
    assert "limit=10" in url
    assert "after=cur_top" in url
    assert "include_archived=true" in url or "include_archived=True" in url
    # `cursor` was this endpoint's own parameter through 1.0 and is not one now.
    assert "cursor=" not in url


def test_create_posts_the_key_and_opt_in_default():
    rec = Recorder(json_response(201, TOPIC))
    client = make_client(rec)

    result = client.topics.create(
        {"key": "product_news", "name": "Product news", "default_opt_in": False}
    )

    assert str(rec.request.url) == "http://localhost/api/v1/topics"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {
        "key": "product_news",
        "name": "Product news",
        "default_opt_in": False,
    }
    assert result == TOPIC


def test_get_and_update_hit_the_id_path():
    rec = Recorder(json_response(200, TOPIC))
    client = make_client(rec)
    assert client.topics.get("top_1") == TOPIC
    assert str(rec.request.url) == "http://localhost/api/v1/topics/top_1"
    assert rec.request.method == "GET"

    # Archiving is the retire path -- there is no DELETE to exercise.
    rec = Recorder(json_response(200, {**TOPIC, "archived": True}))
    client = make_client(rec)
    updated = client.topics.update("top_1", {"archived": True})
    assert str(rec.request.url) == "http://localhost/api/v1/topics/top_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {"archived": True}
    assert updated["archived"] is True


def test_set_subscription_parks_the_contact_at_pending():
    rec = Recorder(
        json_response(
            200,
            {
                "topic_id": "top_1",
                "contact_id": "con_1",
                "status": "pending",
                "confirmed_at": None,
                "confirmation_url": "https://sendly.now/c/tok_1",
            },
        )
    )
    client = make_client(rec)

    subscription = client.topics.set_subscription(
        "top_1", {"contact_id": "con_1", "subscribed": True}
    )

    assert str(rec.request.url) == "http://localhost/api/v1/topics/top_1/subscriptions"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"contact_id": "con_1", "subscribed": True}
    # Asking to subscribe starts a double opt-in; it does not subscribe anyone.
    assert subscription["status"] == "pending"
    assert subscription["confirmation_url"] == "https://sendly.now/c/tok_1"


def test_iter_list_walks_every_page_and_stops():
    rec = SequenceRecorder(
        json_response(200, topic_page([{"id": "top_1"}], cursor="cur_2")),
        json_response(200, topic_page([{"id": "top_2"}, {"id": "top_3"}])),
    )
    client = make_client(rec)

    assert [t["id"] for t in client.topics.iter_list()] == ["top_1", "top_2", "top_3"]
    assert len(rec.requests) == 2


def test_iter_list_follows_after_the_one_v1_page_parameter():
    rec = SequenceRecorder(
        json_response(200, topic_page([{"id": "top_1"}], cursor="cur_2")),
        json_response(200, topic_page([{"id": "top_2"}])),
    )
    client = make_client(rec)

    assert [t["id"] for t in client.topics.iter_list({"limit": 1})] == ["top_1", "top_2"]
    assert rec.urls == [
        "http://localhost/api/v1/topics?limit=1",
        "http://localhost/api/v1/topics?limit=1&after=cur_2",
    ]


def test_iter_list_stops_when_a_page_repeats_the_cursor_it_was_handed():
    # SequenceRecorder fails the test on a third request, so a walk that ignored
    # the repeat would surface as an error rather than an infinite loop.
    rec = SequenceRecorder(json_response(200, topic_page([{"id": "top_1"}], cursor="cur_stuck")))
    client = make_client(rec)

    assert [t["id"] for t in client.topics.iter_list({"after": "cur_stuck"})] == ["top_1"]
    assert len(rec.requests) == 1
