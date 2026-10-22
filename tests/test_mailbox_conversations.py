"""Mailbox mail: reading threads, answering them, and downloading attachments."""

from __future__ import annotations

import json

import httpx
import pytest

from sendly import SendlyPermissionError
from support import Recorder, SequenceRecorder, json_response, make_client, problem_response


def _page(items: list[dict[str, str]], next_cursor: str | None) -> httpx.Response:
    return json_response(
        200, {"success": True, "data": {"items": items, "nextCursor": next_cursor}}
    )


def test_list_conversations_sends_the_filters_and_unwraps_the_page():
    rec = Recorder(_page([{"id": "c1"}], "c1"))
    client = make_client(rec)

    page = client.mailboxes.list_conversations(
        "mb_1", {"view": "spam", "status": "open", "limit": 1}
    )

    assert str(rec.request.url) == (
        "http://localhost/api/mailboxes/mb_1/conversations?view=spam&status=open&limit=1"
    )
    assert page == {"items": [{"id": "c1"}], "nextCursor": "c1"}


def test_iter_list_conversations_follows_next_cursor_as_cursor_keeping_the_filters():
    rec = SequenceRecorder(
        _page([{"id": "c1"}, {"id": "c2"}], "c2"),
        _page([{"id": "c3"}], None),
    )
    client = make_client(rec)

    ids = [
        item["id"] for item in client.mailboxes.iter_list_conversations("mb_1", {"q": "invoice"})
    ]

    assert ids == ["c1", "c2", "c3"]
    assert [str(request.url) for request in rec.requests] == [
        "http://localhost/api/mailboxes/mb_1/conversations?q=invoice",
        "http://localhost/api/mailboxes/mb_1/conversations?q=invoice&cursor=c2",
    ]


def test_iter_list_conversations_stops_on_a_page_that_repeats_its_cursor():
    # SequenceRecorder fails on a third request, so a walker that kept going would error.
    rec = SequenceRecorder(_page([{"id": "c1"}], "c1"), _page([{"id": "c1"}], "c1"))
    client = make_client(rec)

    ids = [item["id"] for item in client.mailboxes.iter_list_conversations("mb_1")]

    assert ids == ["c1", "c1"]
    assert len(rec.requests) == 2


def test_get_conversation_returns_the_messages():
    rec = Recorder(json_response(200, {"success": True, "data": [{"id": "m1"}, {"id": "m2"}]}))
    client = make_client(rec)

    messages = client.mailboxes.get_conversation("mb_1", "c1")

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1/conversations/c1"
    assert [message["id"] for message in messages] == ["m1", "m2"]


def test_reply_posts_only_the_body_and_names_no_recipient_or_sender():
    rec = Recorder(
        json_response(200, {"success": True, "data": {"submitted": True, "status": "queued"}})
    )
    client = make_client(rec)

    reply = client.mailboxes.reply_to_conversation("mb_1", "c1", {"body": "Thanks, sorted."})

    assert rec.request.method == "POST"
    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1/conversations/c1/reply"
    assert json.loads(rec.request.content) == {"body": "Thanks, sorted."}
    assert reply == {"submitted": True, "status": "queued"}


def test_a_key_without_the_opt_in_scope_gets_a_permission_error_not_an_empty_inbox():
    rec = Recorder(
        problem_response(
            403, {"type": "about:blank", "title": "Forbidden", "code": "forbidden", "status": 403}
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyPermissionError):
        client.mailboxes.list_conversations("mb_1")


def test_download_attachment_returns_the_raw_bytes_and_the_senders_headers():
    # Not valid UTF-8: reading this as text would replace bytes with U+FFFD.
    raw = bytes([0x89, 0x50, 0x4E, 0x47, 0xFF, 0xFE, 0x00, 0x80])
    rec = Recorder(
        httpx.Response(
            200,
            content=raw,
            headers={
                "content-type": "image/png",
                "content-disposition": 'attachment; filename="logo.png"',
            },
        )
    )
    client = make_client(rec)

    file = client.mailboxes.download_attachment("mb_1", "att_1")

    assert str(rec.request.url) == "http://localhost/api/mailboxes/mb_1/attachments/att_1"
    assert rec.request.headers["accept"] == "*/*"
    assert file.data == raw
    assert file.content_type == "image/png"
    assert file.content_disposition == 'attachment; filename="logo.png"'


def test_a_refused_download_raises_the_same_typed_error():
    rec = Recorder(
        problem_response(
            403, {"type": "about:blank", "title": "Forbidden", "code": "forbidden", "status": 403}
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyPermissionError):
        client.mailboxes.download_attachment("mb_1", "att_1")
