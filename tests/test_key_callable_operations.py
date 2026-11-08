"""Request mapping and response unwrapping for the operations added with the
2026-11 contract re-sync.

Every method here used to sit in ``NOT_YET_IMPLEMENTED`` in ``test_contract.py``.
The contract test proves each one targets a real spec operation; this file proves
what it SENDS (verb, path, query, JSON body) and what it hands BACK (the legacy
``{success, data}`` envelope unwrapped, or the bare ``/api/v1`` body untouched).

The table is deliberately flat, one row per method, so adding an operation is one
line. Behaviour that is not a plain call -- pagination, multipart uploads, a DELETE
that carries a body -- has its own test below.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from sendly import Sendly, SendlyConflictError, SendlyError, SendlyNotFoundError
from support import (
    Recorder,
    SequenceRecorder,
    json_response,
    make_client,
    problem_response,
)

Call = Callable[[Sendly], Any]

#: (label, call, verb, path-with-query, expected JSON body or None)
LEGACY_CASES: list[tuple[str, Call, str, str, Any]] = [
    # --- activity feed, audit log, analytics, inbox ---
    (
        "activity.list",
        lambda c: c.activity.list({"limit": 25, "types": "email.sent,email.bounced"}),
        "GET",
        "/api/activity?limit=25&types=email.sent%2Cemail.bounced",
        None,
    ),
    (
        "activity.recent_count",
        lambda c: c.activity.recent_count({"minutes": 15}),
        "GET",
        "/api/activity/recent-count?minutes=15",
        None,
    ),
    (
        "activity.stats",
        lambda c: c.activity.stats({"startDate": "2026-11-01"}),
        "GET",
        "/api/activity/stats?startDate=2026-11-01",
        None,
    ),
    (
        "activity.upcoming",
        lambda c: c.activity.upcoming({"daysAhead": 7}),
        "GET",
        "/api/activity/upcoming?daysAhead=7",
        None,
    ),
    (
        "analytics.top_events",
        lambda c: c.analytics.top_events({"limit": 5}),
        "GET",
        "/api/analytics/top-events?limit=5",
        None,
    ),
    (
        "audit_log.list",
        lambda c: c.audit_log.list({"action": "contact."}),
        "GET",
        "/api/audit-log?action=contact.",
        None,
    ),
    (
        "inbox.list_conversations",
        lambda c: c.inbox.list_conversations({"view": "spam", "status": "all"}),
        "GET",
        "/api/inbox/conversations?view=spam&status=all",
        None,
    ),
    # --- campaigns ---
    (
        "campaigns.duplicate",
        lambda c: c.campaigns.duplicate("cmp_1"),
        "POST",
        "/api/campaigns/cmp_1/duplicate",
        None,
    ),
    # --- contacts ---
    (
        "contacts.queue_bulk_delete",
        lambda c: c.contacts.queue_bulk_delete({"contactIds": ["c1", "c2"]}),
        "POST",
        "/api/contacts/bulk-delete",
        {"contactIds": ["c1", "c2"]},
    ),
    (
        "contacts.queue_bulk_purge",
        lambda c: c.contacts.queue_bulk_purge({"contactIds": ["c1"]}),
        "POST",
        "/api/contacts/bulk-purge",
        {"contactIds": ["c1"]},
    ),
    (
        "contacts.queue_bulk_subscribe",
        lambda c: c.contacts.queue_bulk_subscribe({"contactIds": ["c1"]}),
        "POST",
        "/api/contacts/bulk-subscribe",
        {"contactIds": ["c1"]},
    ),
    (
        "contacts.queue_bulk_unsubscribe",
        lambda c: c.contacts.queue_bulk_unsubscribe({"contactIds": ["c1"]}),
        "POST",
        "/api/contacts/bulk-unsubscribe",
        {"contactIds": ["c1"]},
    ),
    (
        "contacts.list_fields",
        lambda c: c.contacts.list_fields(),
        "GET",
        "/api/contacts/fields",
        None,
    ),
    (
        "contacts.get_field_usage",
        lambda c: c.contacts.get_field_usage("plan"),
        "GET",
        "/api/contacts/fields/plan/usage",
        None,
    ),
    (
        "contacts.list_field_values",
        lambda c: c.contacts.list_field_values("plan", {"limit": 50}),
        "GET",
        "/api/contacts/fields/plan/values?limit=50",
        None,
    ),
    (
        "contacts.delete_field",
        lambda c: c.contacts.delete_field("plan"),
        "DELETE",
        "/api/contacts/fields/plan",
        None,
    ),
    (
        "contacts.lookup",
        lambda c: c.contacts.lookup({"emails": ["a@b.com"]}),
        "POST",
        "/api/contacts/lookup",
        {"emails": ["a@b.com"]},
    ),
    (
        "contacts.purge",
        lambda c: c.contacts.purge("ct_1"),
        "POST",
        "/api/contacts/ct_1/purge",
        None,
    ),
    # --- domains ---
    (
        "domains.get_connect_status",
        lambda c: c.domains.get_connect_status("dom_1"),
        "GET",
        "/api/domains/dom_1/dodomain-check",
        None,
    ),
    (
        "domains.reverify_connection",
        lambda c: c.domains.reverify_connection("dom_1"),
        "POST",
        "/api/domains/dom_1/dodomain-reverify",
        None,
    ),
    (
        "domains.get_warmup",
        lambda c: c.domains.get_warmup("dom_1"),
        "GET",
        "/api/domains/dom_1/warmup",
        None,
    ),
    (
        "domains.manage_warmup",
        lambda c: c.domains.manage_warmup("dom_1", {"action": "restart"}),
        "POST",
        "/api/domains/dom_1/warmup",
        {"action": "restart"},
    ),
    # --- emails ---
    (
        "emails.reschedule",
        lambda c: c.emails.reschedule("em_1", {"scheduledAt": "2026-12-01T09:00:00Z"}),
        "PATCH",
        "/api/emails/em_1",
        {"scheduledAt": "2026-12-01T09:00:00Z"},
    ),
    # --- events ---
    (
        "events.list_for_contact",
        lambda c: c.events.list_for_contact("ct_1", {"limit": 10}),
        "GET",
        "/api/events/contact/ct_1?limit=10",
        None,
    ),
    (
        "events.get_usage",
        lambda c: c.events.get_usage("order.paid"),
        "GET",
        "/api/events/order.paid/usage",
        None,
    ),
    (
        "events.delete",
        lambda c: c.events.delete("order.paid"),
        "DELETE",
        "/api/events/order.paid",
        None,
    ),
    # --- lists ---
    (
        "lists.list_members",
        lambda c: c.lists.list_members("lst_1", {"status": "SUBSCRIBED", "limit": 50}),
        "GET",
        "/api/lists/lst_1/members?status=SUBSCRIBED&limit=50",
        None,
    ),
    # --- mailboxes ---
    (
        "mailboxes.delete_conversation",
        lambda c: c.mailboxes.delete_conversation("mb_1", "cv_1"),
        "DELETE",
        "/api/mailboxes/mb_1/conversations/cv_1",
        None,
    ),
    (
        "mailboxes.get_conversation_contact",
        lambda c: c.mailboxes.get_conversation_contact("mb_1", "cv_1"),
        "GET",
        "/api/mailboxes/mb_1/conversations/cv_1/contact",
        None,
    ),
    (
        "mailboxes.set_conversation_spam",
        lambda c: c.mailboxes.set_conversation_spam("mb_1", "cv_1", {"spam": True}),
        "POST",
        "/api/mailboxes/mb_1/conversations/cv_1/spam",
        {"spam": True},
    ),
    (
        "mailboxes.set_conversation_status",
        lambda c: c.mailboxes.set_conversation_status(
            "mb_1", "cv_1", {"status": "CLOSED", "assigneeId": None}
        ),
        "PATCH",
        "/api/mailboxes/mb_1/conversations/cv_1/status",
        {"status": "CLOSED", "assigneeId": None},
    ),
    # --- projects ---
    (
        "projects.get_security",
        lambda c: c.projects.get_security("prj_1"),
        "GET",
        "/api/projects/prj_1/security",
        None,
    ),
    (
        "projects.get_setup_state",
        lambda c: c.projects.get_setup_state("prj_1"),
        "GET",
        "/api/projects/prj_1/setup-state",
        None,
    ),
    # --- segments ---
    (
        "segments.compute",
        lambda c: c.segments.compute("seg_1"),
        "POST",
        "/api/segments/seg_1/compute",
        None,
    ),
    (
        "segments.refresh",
        lambda c: c.segments.refresh("seg_1"),
        "POST",
        "/api/segments/seg_1/refresh",
        None,
    ),
    (
        "segments.add_members",
        lambda c: c.segments.add_members(
            "seg_1", {"emails": ["a@b.com"], "createMissing": True, "subscribed": False}
        ),
        "POST",
        "/api/segments/seg_1/members",
        {"emails": ["a@b.com"], "createMissing": True, "subscribed": False},
    ),
    (
        "segments.remove_members",
        lambda c: c.segments.remove_members("seg_1", {"emails": ["a@b.com"]}),
        "DELETE",
        "/api/segments/seg_1/members",
        {"emails": ["a@b.com"]},
    ),
    # --- templates ---
    (
        "templates.duplicate",
        lambda c: c.templates.duplicate("tpl_1"),
        "POST",
        "/api/templates/tpl_1/duplicate",
        None,
    ),
    (
        "templates.get_usage",
        lambda c: c.templates.get_usage("tpl_1"),
        "GET",
        "/api/templates/tpl_1/usage",
        None,
    ),
    (
        "templates.list_versions",
        lambda c: c.templates.list_versions("tpl_1"),
        "GET",
        "/api/templates/tpl_1/versions",
        None,
    ),
    (
        "templates.revert_version",
        lambda c: c.templates.revert_version("tpl_1", 3),
        "POST",
        "/api/templates/tpl_1/versions/3/revert",
        None,
    ),
    # --- webhooks ---
    (
        "webhooks.retry_call",
        lambda c: c.webhooks.retry_call("wh_1", "call_1"),
        "POST",
        "/api/webhooks/wh_1/calls/call_1/retry",
        None,
    ),
    (
        "webhooks.replay_failed",
        lambda c: c.webhooks.replay_failed("wh_1", {"since": "2026-11-01T00:00:00Z", "limit": 10}),
        "POST",
        "/api/webhooks/wh_1/replay-failed",
        {"since": "2026-11-01T00:00:00Z", "limit": 10},
    ),
    (
        "webhooks.test",
        lambda c: c.webhooks.test("wh_1", {"eventType": "email.delivered"}),
        "POST",
        "/api/webhooks/wh_1/test",
        {"eventType": "email.delivered"},
    ),
    # --- workflows ---
    (
        "workflows.list_fields",
        lambda c: c.workflows.list_fields({"eventName": "order.paid"}),
        "GET",
        "/api/workflows/fields?eventName=order.paid",
        None,
    ),
    (
        "workflows.list_conversion_goals",
        lambda c: c.workflows.list_conversion_goals("wf_1"),
        "GET",
        "/api/workflows/wf_1/conversion-goals",
        None,
    ),
    (
        "workflows.create_conversion_goal",
        lambda c: c.workflows.create_conversion_goal(
            "wf_1", {"name": "Paid", "eventType": "order.paid", "windowDays": 30}
        ),
        "POST",
        "/api/workflows/wf_1/conversion-goals",
        {"name": "Paid", "eventType": "order.paid", "windowDays": 30},
    ),
    (
        "workflows.delete_conversion_goal",
        lambda c: c.workflows.delete_conversion_goal("wf_1", "goal_1"),
        "DELETE",
        "/api/workflows/wf_1/conversion-goals/goal_1",
        None,
    ),
    (
        "workflows.cancel_all_executions",
        lambda c: c.workflows.cancel_all_executions("wf_1"),
        "POST",
        "/api/workflows/wf_1/executions/cancel-all",
        None,
    ),
    (
        "workflows.get_execution",
        lambda c: c.workflows.get_execution("wf_1", "ex_1"),
        "GET",
        "/api/workflows/wf_1/executions/ex_1",
        None,
    ),
    (
        "workflows.add_step",
        lambda c: c.workflows.add_step(
            "wf_1", {"type": "SEND_EMAIL", "templateId": "tpl_1", "autoConnect": True}
        ),
        "POST",
        "/api/workflows/wf_1/steps",
        {"type": "SEND_EMAIL", "templateId": "tpl_1", "autoConnect": True},
    ),
    (
        "workflows.update_step",
        lambda c: c.workflows.update_step("wf_1", "st_1", {"name": "Welcome"}),
        "PATCH",
        "/api/workflows/wf_1/steps/st_1",
        {"name": "Welcome"},
    ),
    (
        "workflows.delete_step",
        lambda c: c.workflows.delete_step("wf_1", "st_1", {"splice": "true"}),
        "DELETE",
        "/api/workflows/wf_1/steps/st_1?splice=true",
        None,
    ),
    (
        "workflows.create_transition",
        lambda c: c.workflows.create_transition(
            "wf_1",
            {"fromStepId": "st_1", "toStepId": "st_2", "condition": {"branch": "yes"}},
        ),
        "POST",
        "/api/workflows/wf_1/transitions",
        {"fromStepId": "st_1", "toStepId": "st_2", "condition": {"branch": "yes"}},
    ),
    (
        "workflows.delete_transition",
        lambda c: c.workflows.delete_transition("wf_1", "tr_1"),
        "DELETE",
        "/api/workflows/wf_1/transitions/tr_1",
        None,
    ),
    (
        "workflows.list_versions",
        lambda c: c.workflows.list_versions("wf_1"),
        "GET",
        "/api/workflows/wf_1/versions",
        None,
    ),
    (
        "workflows.revert_version",
        lambda c: c.workflows.revert_version("wf_1", 2),
        "POST",
        "/api/workflows/wf_1/versions/2/revert",
        None,
    ),
]

#: The /api/v1 operations answer a bare body: no envelope to unwrap.
V1_CASES: list[tuple[str, Call, str, str, Any]] = [
    ("billing.get", lambda c: c.billing.get(), "GET", "/api/v1/billing", None),
    ("billing.list_plans", lambda c: c.billing.list_plans(), "GET", "/api/v1/billing/plans", None),
    ("connections.list", lambda c: c.connections.list(), "GET", "/api/v1/connections", None),
    (
        "connections.create_links",
        lambda c: c.connections.create_links({"provider": "dodomain", "domainId": "dom_1"}),
        "POST",
        "/api/v1/connections/links",
        {"provider": "dodomain", "domainId": "dom_1"},
    ),
    (
        "support.list_tickets",
        lambda c: c.support.list_tickets(),
        "GET",
        "/api/v1/support/tickets",
        None,
    ),
    (
        "support.create_ticket",
        lambda c: c.support.create_ticket(
            {"subject": "Bounce spike", "body": "Details", "wantsReply": False}
        ),
        "POST",
        "/api/v1/support/tickets",
        {"subject": "Bounce spike", "body": "Details", "wantsReply": False},
    ),
]


def _assert_request(rec: Recorder, verb: str, target: str, body: Any) -> None:
    assert rec.request.method == verb
    assert str(rec.request.url) == f"http://localhost{target}"
    if body is None:
        assert rec.request.content == b""
    else:
        assert json.loads(rec.request.content) == body
        assert rec.request.headers["content-type"] == "application/json"
    assert rec.request.headers["authorization"] == "Bearer sk_test_key"


@pytest.mark.parametrize(
    ("label", "call", "verb", "target", "body"),
    LEGACY_CASES,
    ids=[case[0] for case in LEGACY_CASES],
)
def test_legacy_operation_maps_the_request_and_unwraps_the_envelope(
    label: str, call: Call, verb: str, target: str, body: Any
):
    rec = Recorder(json_response(200, {"success": True, "data": {"marker": label}}))
    result = call(make_client(rec))
    _assert_request(rec, verb, target, body)
    assert len(rec.requests) == 1
    assert result == {"marker": label}


@pytest.mark.parametrize(
    ("label", "call", "verb", "target", "body"),
    V1_CASES,
    ids=[case[0] for case in V1_CASES],
)
def test_v1_operation_maps_the_request_and_returns_the_bare_body(
    label: str, call: Call, verb: str, target: str, body: Any
):
    rec = Recorder(json_response(200, {"marker": label, "items": []}))
    result = call(make_client(rec))
    _assert_request(rec, verb, target, body)
    assert result == {"marker": label, "items": []}


def test_every_row_covers_a_distinct_method():
    labels = [case[0] for case in LEGACY_CASES + V1_CASES]
    assert len(labels) == len(set(labels))
    # 67 operations in the contract; the four that are not a plain call (the CSV
    # import, the image upload, campaign test sends and the file export link) are
    # tested individually below.
    assert len(labels) == 63


# --------------------------------------------------------------------------- #
# Operations that are not a plain call                                         #
# --------------------------------------------------------------------------- #


def test_campaign_send_test_posts_the_address_as_the_body():
    rec = Recorder(json_response(200, {"success": True, "message": "Test email sent to a@b.com"}))
    result = make_client(rec).campaigns.send_test("cmp_1", "a@b.com")
    assert rec.request.method == "POST"
    assert str(rec.request.url) == "http://localhost/api/campaigns/cmp_1/test"
    assert json.loads(rec.request.content) == {"email": "a@b.com"}
    # No `data` in this envelope, so there is nothing to unwrap: the caller gets it whole.
    assert result == {"success": True, "message": "Test email sent to a@b.com"}


def test_contacts_export_link_forwards_filters_and_returns_the_download_link_untouched():
    link = {
        "status": "action_required",
        "url": "https://api.sendly.now/go/abc",
        "expires_in": 900,
        "what": "Contacts CSV",
        "instruction": "Open this link while signed in.",
    }
    rec = Recorder(json_response(200, link))
    result = make_client(rec).contacts.export_link({"search": "acme", "subscribed": True})
    assert rec.request.method == "GET"
    assert (
        str(rec.request.url) == "http://localhost/api/contacts/export?search=acme&subscribed=true"
    )
    assert result == link


def test_contacts_import_csv_sends_multipart_under_the_field_file():
    rec = Recorder(json_response(202, {"success": True, "data": {"message": "queued"}}))
    result = make_client(rec).contacts.import_csv(
        "email,plan\na@b.com,pro\n", filename="people.csv"
    )
    request = rec.request
    assert request.method == "POST"
    assert str(request.url) == "http://localhost/api/contacts/import"
    assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="people.csv"' in request.content
    assert b"Content-Type: text/csv" in request.content
    assert b"email,plan\na@b.com,pro\n" in request.content
    assert result == {"message": "queued"}


def test_contacts_import_csv_accepts_bytes_and_defaults_the_filename():
    rec = Recorder(json_response(202, {"success": True, "data": {}}))
    make_client(rec).contacts.import_csv(b"email\na@b.com\n")
    assert b'filename="contacts.csv"' in rec.request.content


def test_uploads_image_sends_multipart_under_the_field_image():
    png = b"\x89PNG\r\n\x1a\nrest"
    rec = Recorder(
        json_response(
            200,
            {
                "url": "https://cdn.example/a.png",
                "key": "k",
                "filename": "a.png",
                "contentType": "image/png",
                "size": 12,
            },
        )
    )
    result = make_client(rec).uploads.image(png, filename="a.png", content_type="image/png")
    request = rec.request
    assert request.method == "POST"
    assert str(request.url) == "http://localhost/api/uploads/image"
    assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="image"; filename="a.png"' in request.content
    assert b"Content-Type: image/png" in request.content
    assert png in request.content
    assert result["url"] == "https://cdn.example/a.png"


def test_connections_create_links_with_no_argument_sends_an_empty_object():
    rec = Recorder(json_response(200, {"links": []}))
    make_client(rec).connections.create_links()
    assert json.loads(rec.request.content) == {}
    assert rec.request.headers["content-type"] == "application/json"


def test_top_events_returns_the_unwrapped_list():
    events = [{"eventName": "order.paid", "count": 9}, {"eventName": "signup", "count": 4}]
    rec = Recorder(json_response(200, {"success": True, "data": events}))
    result = make_client(rec).analytics.top_events({"limit": 2})
    assert result == events


def test_inbox_walk_stops_on_a_repeated_next_cursor():
    def page(item: str) -> Any:
        return json_response(
            200, {"success": True, "data": {"items": [{"id": item}], "nextCursor": "c1"}}
        )

    rec = SequenceRecorder(page("a"), page("b"))
    items = list(make_client(rec).inbox.iter_list_conversations())
    assert [i["id"] for i in items] == ["a", "b"]
    assert len(rec.requests) == 2


def test_uploads_image_guesses_the_type_from_the_filename():
    rec = Recorder(json_response(200, {"url": "https://cdn.example/logo.png"}))
    make_client(rec).uploads.image(b"\x89PNGrest", filename="logo.png")
    assert b"Content-Type: image/png" in rec.request.content


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("LOGO.PNG", b"Content-Type: image/png"),
        ("a.webp", b"Content-Type: image/webp"),
        ("p.JPG", b"Content-Type: image/jpeg"),
        ("p.jpeg", b"Content-Type: image/jpeg"),
        ("a.gif", b"Content-Type: image/gif"),
    ],
)
def test_uploads_image_maps_extensions_explicitly(filename: str, expected: bytes):
    rec = Recorder(json_response(200, {"url": "https://cdn.example/x"}))
    make_client(rec).uploads.image(b"data", filename=filename)
    assert expected in rec.request.content


@pytest.mark.parametrize("filename", ["logo.svg", "notes.txt", "pic.bmp"])
def test_uploads_image_refuses_extensions_the_server_would_refuse(filename: str):
    rec = Recorder(json_response(200, {}))
    with pytest.raises(ValueError, match="pass `content_type`"):
        make_client(rec).uploads.image(b"data", filename=filename)
    assert rec.requests == []


def test_uploads_image_refuses_an_unguessable_type_before_sending():
    rec = Recorder(json_response(200, {}))
    with pytest.raises(ValueError, match="pass `content_type`"):
        make_client(rec).uploads.image(b"data", filename="logo.unknownext")
    assert rec.requests == []


def test_a_request_cannot_carry_both_a_json_body_and_files():
    client = make_client(Recorder(json_response(200, {})))
    with pytest.raises(SendlyError, match="both `body` and `files`"):
        client.request(
            method="POST", path="/x", body={"a": 1}, files={"f": ("f.txt", b"x", "text/plain")}
        )


def test_remove_members_sends_a_json_body_on_delete():
    rec = Recorder(json_response(200, {"success": True, "data": {"removed": 1}}))
    make_client(rec).segments.remove_members("seg_1", {"emails": ["a@b.com"]})
    assert rec.request.method == "DELETE"
    assert rec.request.headers["content-type"] == "application/json"


def test_replay_failed_and_test_send_an_empty_object_when_given_no_body():
    # The routes read the body as optional, but a POST with no content-type is the
    # one shape some proxies mangle; an explicit `{}` is accepted by both routes.
    for call in (
        lambda c: c.webhooks.replay_failed("wh_1"),
        lambda c: c.webhooks.test("wh_1"),
    ):
        rec = Recorder(json_response(200, {"success": True, "data": {}}))
        call(make_client(rec))
        assert json.loads(rec.request.content) == {}


def test_path_segments_are_percent_encoded():
    rec = Recorder(json_response(200, {"success": True, "data": {}}))
    client = make_client(rec)
    client.events.get_usage("a b/c")
    client.contacts.get_field_usage("first name")
    assert str(rec.requests[0].url) == "http://localhost/api/events/a%20b%2Fc/usage"
    assert str(rec.requests[1].url) == "http://localhost/api/contacts/fields/first%20name/usage"


# --------------------------------------------------------------------------- #
# Pagination: the legacy cursor dialects                                       #
# --------------------------------------------------------------------------- #


def _data_page(items: list[dict[str, str]], cursor: str | None, has_more: bool) -> Any:
    page: dict[str, Any] = {"data": items, "hasMore": has_more}
    if cursor is not None:
        page["cursor"] = cursor
    return json_response(200, {"success": True, "data": page})


@pytest.mark.parametrize(
    ("label", "start", "path"),
    [
        ("activity", lambda c: c.activity.iter_list({"limit": 1}), "/api/activity"),
        ("audit_log", lambda c: c.audit_log.iter_list({"limit": 1}), "/api/audit-log"),
        (
            "lists",
            lambda c: c.lists.iter_list_members("lst_1", {"limit": 1}),
            "/api/lists/lst_1/members",
        ),
    ],
)
def test_data_cursor_listings_iterate_until_has_more_runs_out(label: str, start: Any, path: str):
    rec = SequenceRecorder(
        _data_page([{"id": "1"}], "cur_1", True),
        _data_page([{"id": "2"}], "cur_2", True),
        _data_page([{"id": "3"}], None, False),
    )
    items = list(start(make_client(rec)))
    assert [item["id"] for item in items] == ["1", "2", "3"]
    urls = [str(request.url) for request in rec.requests]
    assert urls == [
        f"http://localhost{path}?limit=1",
        f"http://localhost{path}?limit=1&cursor=cur_1",
        f"http://localhost{path}?limit=1&cursor=cur_2",
    ]


def test_data_cursor_walk_stops_on_a_repeated_cursor():
    rec = SequenceRecorder(
        _data_page([{"id": "1"}], "cur_1", True),
        _data_page([{"id": "2"}], "cur_1", True),
    )
    items = list(make_client(rec).activity.iter_list())
    assert [item["id"] for item in items] == ["1", "2"]
    assert len(rec.requests) == 2


def test_inbox_iterates_the_items_and_next_cursor_dialect():
    def page(items: list[dict[str, str]], next_cursor: str | None) -> Any:
        return json_response(
            200, {"success": True, "data": {"items": items, "nextCursor": next_cursor}}
        )

    rec = SequenceRecorder(page([{"id": "c1"}], "c1"), page([{"id": "c2"}], None))
    items = list(make_client(rec).inbox.iter_list_conversations({"view": "inbox"}))
    assert [item["id"] for item in items] == ["c1", "c2"]
    assert str(rec.requests[0].url) == "http://localhost/api/inbox/conversations?view=inbox"
    assert (
        str(rec.requests[1].url) == "http://localhost/api/inbox/conversations?view=inbox&cursor=c1"
    )


def test_iterators_end_on_a_malformed_page():
    rec = SequenceRecorder(json_response(200, {"success": True, "data": {"unexpected": True}}))
    assert list(make_client(rec).audit_log.iter_list()) == []


# --------------------------------------------------------------------------- #
# Errors keep their typed mapping through the new methods                      #
# --------------------------------------------------------------------------- #


def test_a_legacy_error_envelope_raises_the_typed_error():
    rec = Recorder(
        json_response(409, {"success": False, "error": {"code": "EMAIL_NOT_RESCHEDULABLE"}})
    )
    with pytest.raises(SendlyConflictError) as caught:
        make_client(rec).emails.reschedule("em_1", {"scheduledAt": None})
    assert caught.value.error_code == "EMAIL_NOT_RESCHEDULABLE"


def test_a_v1_problem_document_raises_the_typed_error():
    rec = Recorder(
        problem_response(
            404,
            {
                "type": "https://docs.sendly.now/errors/not_found",
                "title": "Not Found",
                "status": 404,
                "code": "not_found",
                "detail": "No such ticket.",
            },
        )
    )
    with pytest.raises(SendlyNotFoundError):
        make_client(rec).support.list_tickets()
