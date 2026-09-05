"""Email validation resource tests (``/api/v1``)."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import Recorder, SequenceRecorder, json_response, make_client, problem_response


def validation(email: str, verdict: str) -> dict[str, object]:
    """One address's verdict, with the evidence behind it."""
    return {
        "email": email,
        "verdict": verdict,
        "is_disposable": False,
        "is_role_address": False,
        "is_personal": True,
        "has_mx_records": verdict != "undeliverable",
        "reasons": [],
        "contact_id": None,
    }


def results_page(items: list[dict[str, object]], *, cursor: str | None = None) -> dict[str, object]:
    """One page of a run's results.

    Deliberately not ``support.cursor_page``: this endpoint names the next page
    ``cursor``, not ``next_cursor``, so the shared builder would describe a shape
    the API never sends.
    """
    return {"data": items, "cursor": cursor, "has_more": cursor is not None}


def test_validate_emails_posts_the_batch():
    batch = {"results": [validation("a@example.com", "deliverable")]}
    rec = Recorder(json_response(200, batch))
    client = make_client(rec)

    assert client.validation.validate_emails({"emails": ["a@example.com"]}) == batch
    assert str(rec.request.url) == "http://localhost/api/v1/email-validations"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"emails": ["a@example.com"]}


def test_unknown_is_carried_through_as_its_own_verdict():
    # A DNS timeout is `unknown`, never `undeliverable`: acting on the two
    # together deletes live contacts over a network hiccup.
    rec = Recorder(
        json_response(
            200,
            {
                "results": [
                    validation("timeout@example.com", "unknown"),
                    validation("nope@example.com", "undeliverable"),
                ]
            },
        )
    )
    client = make_client(rec)

    batch = client.validation.validate_emails(
        {"emails": ["timeout@example.com", "nope@example.com"]}
    )

    assert [r["verdict"] for r in batch["results"]] == ["unknown", "undeliverable"]


def test_a_batch_over_the_fifty_address_ceiling_raises_the_validation_error():
    rec = Recorder(
        problem_response(
            422,
            {
                "type": "https://docs.sendly.now/errors/validation_error",
                "title": "Validation Error",
                "status": 422,
                "code": "validation_error",
                "detail": "`emails` must contain at most 50 items.",
                "errors": [
                    {"pointer": "/emails", "code": "too_many_items", "message": "at most 50"}
                ],
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyValidationError) as caught:
        client.validation.validate_emails({"emails": [f"u{i}@example.com" for i in range(51)]})
    assert caught.value.field_errors[0]["pointer"] == "/emails"


def test_get_run_hits_the_run_id_path():
    run = {"id": "vrun_1", "status": "running", "processed_count": 12}
    rec = Recorder(json_response(200, run))
    client = make_client(rec)

    assert client.validation.get_run("vrun_1") == run
    assert str(rec.request.url) == "http://localhost/api/v1/validation-runs/vrun_1"
    assert rec.request.method == "GET"


def test_list_results_serializes_limit_verdict_and_the_cursor_parameter():
    page = results_page([validation("a@example.com", "undeliverable")])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    # Returned as-is: the envelope, not its `data` array.
    assert (
        client.validation.list_results(
            "vrun_1", {"limit": 50, "verdict": "undeliverable", "cursor": "cur_1"}
        )
        == page
    )
    url = str(rec.request.url)
    assert url == (
        "http://localhost/api/v1/validation-runs/vrun_1/results"
        "?limit=50&verdict=undeliverable&cursor=cur_1"
    )
    assert "after=" not in url


def test_iter_list_results_pages_on_cursor_not_after():
    rec = SequenceRecorder(
        json_response(
            200, results_page([validation("a@example.com", "undeliverable")], cursor="cur_2")
        ),
        json_response(200, results_page([validation("b@example.com", "undeliverable")])),
    )
    client = make_client(rec)

    emails = [
        r["email"]
        for r in client.validation.iter_list_results("vrun_1", {"verdict": "undeliverable"})
    ]

    assert emails == ["a@example.com", "b@example.com"]
    assert rec.urls == [
        "http://localhost/api/v1/validation-runs/vrun_1/results?verdict=undeliverable",
        "http://localhost/api/v1/validation-runs/vrun_1/results?verdict=undeliverable&cursor=cur_2",
    ]


def test_iter_list_results_stops_on_the_last_page():
    # SequenceRecorder fails the test on an extra request, so a generator that
    # ignored `has_more` would error rather than loop.
    rec = SequenceRecorder(
        json_response(200, results_page([validation("a@example.com", "deliverable")]))
    )
    client = make_client(rec)

    assert [r["email"] for r in client.validation.iter_list_results("vrun_1")] == ["a@example.com"]
    assert len(rec.requests) == 1
