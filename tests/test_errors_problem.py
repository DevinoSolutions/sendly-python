"""RFC 9457 problem+json error mapping, and the legacy dialect it must not disturb.

The ``/api/v1`` surface reports failures as problem documents while the legacy
``/api/*`` surface keeps its ``{success, error}`` envelope. Both dialects land on
the same exception classes, keyed off the HTTP status, so a caller's
``except SendlyValidationError`` works against either.
"""

from __future__ import annotations

import pytest

from sendly import (
    SendlyAuthenticationError,
    SendlyConflictError,
    SendlyError,
    SendlyNotFoundError,
    SendlyPermissionError,
    SendlyRateLimitError,
    SendlyServerError,
    SendlyValidationError,
)
from support import Recorder, json_response, make_client, problem_response


def problem(status: int, code: str, **extra: object) -> dict[str, object]:
    """A minimally complete problem document for ``status`` / ``code``."""
    return {
        "type": f"https://docs.sendly.now/errors/{code}",
        "title": code.replace("_", " ").title(),
        "status": status,
        "code": code,
        **extra,
    }


# --------------------------------------------------------------------------- #
# Status -> exception class                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (401, "invalid_api_key", SendlyAuthenticationError),
        (401, "invalid_session", SendlyAuthenticationError),
        (403, "scope_missing", SendlyPermissionError),
        (403, "project_access_denied", SendlyPermissionError),
        (403, "project_disabled", SendlyPermissionError),
        (404, "resource_not_found", SendlyNotFoundError),
        (409, "conflict", SendlyConflictError),
        (409, "idempotency_key_reused", SendlyConflictError),
        (422, "validation_error", SendlyValidationError),
        (429, "rate_limited", SendlyRateLimitError),
        (429, "quota_exhausted", SendlyRateLimitError),
        (500, "internal_error", SendlyServerError),
        (500, "enqueue_failed", SendlyServerError),
    ],
)
def test_problem_document_maps_to_the_class_for_its_status(status, code, expected):
    client = make_client(Recorder(problem_response(status, problem(status, code))))
    with pytest.raises(expected) as caught:
        client.campaigns.list()
    assert caught.value.status_code == status
    assert caught.value.error_code == code


def test_error_code_comes_from_the_problem_code_not_the_type_uri():
    client = make_client(Recorder(problem_response(403, problem(403, "scope_missing"))))
    with pytest.raises(SendlyPermissionError) as caught:
        client.campaigns.list()
    assert caught.value.error_code == "scope_missing"
    assert caught.value.body["type"] == "https://docs.sendly.now/errors/scope_missing"


# --------------------------------------------------------------------------- #
# Message, request_id, field errors                                            #
# --------------------------------------------------------------------------- #


def test_message_prefers_detail_over_title():
    document = problem(422, "validation_error", detail="`limit` must be between 1 and 100.")
    client = make_client(Recorder(problem_response(422, document)))
    with pytest.raises(SendlyValidationError) as caught:
        client.campaigns.list({"limit": 500})
    assert caught.value.message == "`limit` must be between 1 and 100."


def test_message_falls_back_to_title_when_detail_is_absent():
    client = make_client(Recorder(problem_response(500, problem(500, "internal_error"))))
    with pytest.raises(SendlyServerError) as caught:
        client.campaigns.list()
    assert caught.value.message == "Internal Error"


def test_request_id_and_field_errors_are_exposed_on_the_error():
    document = problem(
        422,
        "validation_error",
        detail="The request body did not match the schema.",
        request_id="req_01HZY",
        instance="/api/v1/campaigns",
        errors=[
            {"pointer": "/subject", "code": "required", "message": "subject is required"},
            {"pointer": "/from", "code": "invalid_email", "message": "from is not an email"},
        ],
    )
    client = make_client(Recorder(problem_response(422, document)))
    with pytest.raises(SendlyValidationError) as caught:
        client.campaigns.create({"name": "Launch"})

    error = caught.value
    assert error.request_id == "req_01HZY"
    assert error.field_errors is not None
    assert [item["pointer"] for item in error.field_errors] == ["/subject", "/from"]
    assert error.field_errors[0]["code"] == "required"
    # The whole document stays reachable for members the SDK does not promote.
    assert error.body["instance"] == "/api/v1/campaigns"


def test_request_id_and_field_errors_are_none_when_the_problem_omits_them():
    client = make_client(Recorder(problem_response(404, problem(404, "resource_not_found"))))
    with pytest.raises(SendlyNotFoundError) as caught:
        client.campaigns.get("cmp_missing")
    assert caught.value.request_id is None
    assert caught.value.field_errors is None


# --------------------------------------------------------------------------- #
# Detection                                                                    #
# --------------------------------------------------------------------------- #


def test_problem_is_detected_by_shape_when_the_content_type_is_rewritten():
    # A proxy that normalizes the media type must not downgrade a v1 error into
    # the generic http_<status> path.
    document = problem(429, "rate_limited", detail="Slow down.")
    client = make_client(Recorder(json_response(429, document)))
    with pytest.raises(SendlyRateLimitError) as caught:
        client.campaigns.list()
    assert caught.value.error_code == "rate_limited"
    assert caught.value.message == "Slow down."


def test_problem_content_type_wins_even_when_members_are_missing():
    client = make_client(Recorder(problem_response(503, {"status": 503})))
    with pytest.raises(SendlyServerError) as caught:
        client.usage.get()
    assert caught.value.error_code == "http_503"
    assert caught.value.message == "Sendly request failed with status 503"


# --------------------------------------------------------------------------- #
# Legacy dialect regression                                                    #
# --------------------------------------------------------------------------- #


def test_legacy_envelope_still_maps_to_the_same_classes():
    rec = Recorder(
        json_response(
            422,
            {
                "success": False,
                "error": {
                    "message": "Invalid email",
                    "code": "VALIDATION_ERROR",
                    "details": {"errors": [{"path": "email"}]},
                },
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyValidationError) as caught:
        client.contacts.create({"email": "nope"})

    error = caught.value
    assert error.error_code == "VALIDATION_ERROR"
    assert error.message == "Invalid email"
    # The legacy breakdown stays where it always was; the problem-only fields
    # are simply absent.
    assert error.body["error"]["details"]["errors"] == [{"path": "email"}]
    assert error.request_id is None
    assert error.field_errors is None


def test_legacy_envelope_is_never_mistaken_for_a_problem_document():
    rec = Recorder(json_response(500, {"success": False, "error": {"message": "boom"}}))
    client = make_client(rec)
    with pytest.raises(SendlyServerError) as caught:
        client.emails.list()
    assert caught.value.error_code == "http_500"
    assert caught.value.message == "boom"


def test_transport_and_option_errors_carry_the_new_fields_as_none():
    error = SendlyError(0, "invalid_options", "no key")
    assert error.request_id is None
    assert error.field_errors is None
