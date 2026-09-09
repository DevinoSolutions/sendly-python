"""Domains resource tests."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyConflictError, SendlyPermissionError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
    problem_response,
)

DOMAIN_V1 = {
    "id": "dom_1",
    "domain": "mail.example.com",
    "verified": True,
    "dkim_verified": False,
    "mail_from_domain": "sendly.mail.example.com",
    "mail_from_domain_status": "Success",
    "stream": "TRANSACTIONAL",
    "stream_default": True,
}


def test_start_setup_posts_the_session_route_and_returns_the_link_verbatim():
    session = {
        "token": "tok_abc",
        "connectUrl": "https://dodomain.com/connect?token=tok_abc",
        "expiresAt": "2026-09-01T01:00:00.000Z",
    }
    rec = Recorder(json_response(200, {"success": True, "data": session}))
    client = make_client(rec)

    result = client.domains.start_setup("dom_1")

    assert str(rec.request.url) == "http://localhost/api/domains/dom_1/dodomain-session"
    assert rec.request.method == "POST"
    # Handed back as the route returns it -- the caller opens `connectUrl`.
    assert result == session


def test_create_posts_domains_and_unwraps():
    rec = Recorder(
        json_response(201, {"success": True, "data": {"id": "d_1", "domain": "mail.example.com"}})
    )
    client = make_client(rec)
    result = client.domains.create({"domain": "mail.example.com"})
    assert str(rec.request.url) == "http://localhost/api/domains"
    assert result["id"] == "d_1"


def test_list_gets_domains():
    rec = Recorder(json_response(200, {"success": True, "data": {"items": []}}))
    client = make_client(rec)
    client.domains.list()
    assert rec.request.method == "GET"
    assert str(rec.request.url) == "http://localhost/api/domains"


def test_verify_posts_verify_path():
    # `status` is SES's own raw DKIM state; the per-record checks are their own fields.
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {
                    "domain": "mail.example.com",
                    "status": "Pending",
                    "verified": False,
                    "dkimStatus": "PENDING",
                    "spfStatus": "NOT_CHECKED",
                    "dmarcStatus": "NOT_CHECKED",
                    "mailFromDomain": None,
                },
            },
        )
    )
    client = make_client(rec)
    client.domains.verify("d_1")
    assert str(rec.request.url) == "http://localhost/api/domains/d_1/verify"
    assert rec.request.method == "POST"


def test_get_verification_reports_each_record_type():
    rec = Recorder(
        json_response(
            200,
            {
                "success": True,
                "data": {
                    "domain": "mail.example.com",
                    "status": "Success",
                    "verified": True,
                    "dkimStatus": "VERIFIED",
                    "spfStatus": "VERIFIED",
                    "dmarcStatus": "NOT_CHECKED",
                    "mailFromDomain": "bounce.mail.example.com",
                },
            },
        )
    )
    client = make_client(rec)
    status = client.domains.get_verification("d_1")
    assert str(rec.request.url) == "http://localhost/api/domains/d_1/verify"
    assert rec.request.method == "GET"
    # DMARC unchecked while DKIM and SPF pass -- one status per record type, not one verdict.
    assert status["dkimStatus"] == "VERIFIED"
    assert status["dmarcStatus"] == "NOT_CHECKED"


def test_create_raises_permission_error_on_403():
    rec = Recorder(
        json_response(
            403, {"error": {"message": "pk key cannot create domains", "code": "forbidden"}}
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyPermissionError):
        client.domains.create({"domain": "x.com"})


def test_assign_stream_patches_the_legacy_path_with_the_camel_case_body():
    record = {
        "id": "d_1",
        "domain": "mail.example.com",
        "stream": "MARKETING",
        "streamDefault": True,
    }
    rec = Recorder(json_response(200, {"success": True, "data": record}))
    client = make_client(rec)

    client.domains.assign_stream(
        "d_1",
        {
            "stream": "MARKETING",
            "streamDefault": True,
            "defaultFromAddress": "news@mail.example.com",
        },
    )

    assert str(rec.request.url) == "http://localhost/api/domains/d_1"
    assert rec.request.method == "PATCH"
    assert json.loads(rec.request.content) == {
        "stream": "MARKETING",
        "streamDefault": True,
        "defaultFromAddress": "news@mail.example.com",
    }


def test_assign_stream_unwraps_the_legacy_envelope():
    record = {"id": "d_1", "stream": None, "streamDefault": False}
    rec = Recorder(json_response(200, {"success": True, "data": record}))
    client = make_client(rec)

    # The `{success, data}` wrapper is peeled off -- the record itself is returned.
    assert client.domains.assign_stream("d_1", {"stream": None}) == record


def test_create_v1_posts_the_bare_body():
    rec = Recorder(json_response(201, {**DOMAIN_V1, "verified": False}))
    client = make_client(rec)

    created = client.domains.create_v1({"domain": "mail.example.com", "region": "eu-west-1"})

    assert str(rec.request.url) == "http://localhost/api/v1/domains"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {
        "domain": "mail.example.com",
        "region": "eu-west-1",
    }
    # Nothing is verified until the DKIM records resolve.
    assert created["verified"] is False


def test_v1_reads_return_the_bare_body_without_unwrapping():
    rec = Recorder(json_response(200, DOMAIN_V1))
    client = make_client(rec)

    # A v1 body has no `data` key to unwrap, so unwrapping would lose the record.
    assert client.domains.get_v1("dom_1") == DOMAIN_V1
    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1"
    assert rec.request.method == "GET"


def test_verify_v1_posts_the_verify_subpath_with_no_body():
    rec = Recorder(json_response(200, {**DOMAIN_V1, "dkim_verified": True}))
    client = make_client(rec)

    refreshed = client.domains.verify_v1("dom_1")

    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1/verify"
    assert rec.request.method == "POST"
    # It reports what SES now sees; it edits none of the domain's own fields.
    assert rec.request.content == b""
    assert refreshed["dkim_verified"] is True


def test_delete_v1_returns_the_deletion_receipt():
    rec = Recorder(json_response(200, {"id": "dom_1", "deleted": True}))
    client = make_client(rec)

    assert client.domains.delete_v1("dom_1") == {"id": "dom_1", "deleted": True}
    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1"
    assert rec.request.method == "DELETE"


def test_list_v1_serializes_the_cursor_query():
    page = cursor_page([DOMAIN_V1])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.domains.list_v1({"limit": 10, "after": "cur_dom"}) == page
    assert str(rec.request.url) == "http://localhost/api/v1/domains?limit=10&after=cur_dom"


def test_iter_list_v1_walks_every_page():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "dom_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "dom_2"}, {"id": "dom_3"}])),
    )
    client = make_client(rec)

    ids = [d["id"] for d in client.domains.iter_list_v1({"limit": 1})]

    assert ids == ["dom_1", "dom_2", "dom_3"]
    assert rec.urls == [
        "http://localhost/api/v1/domains?limit=1",
        "http://localhost/api/v1/domains?limit=1&after=cur_2",
    ]


def test_delete_v1_raises_conflict_while_the_domain_is_still_sending():
    rec = Recorder(
        problem_response(
            409,
            {
                "type": "https://docs.sendly.now/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "code": "conflict",
                "detail": "Domain is still used by 1 active campaign.",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyConflictError):
        client.domains.delete_v1("dom_1")
