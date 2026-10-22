"""The sender logo (BIMI) on /api/v1 domains: bare bodies, no envelope."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyValidationError
from support import Recorder, json_response, make_client, problem_response

LOGO = {
    "domain_id": "dom_1",
    "source": "uploaded",
    "url": "https://api.sendly.now/bimi/dom_1.svg",
    "serving": True,
}


def test_get_logo_returns_the_document_as_is():
    rec = Recorder(json_response(200, LOGO))
    client = make_client(rec)

    logo = client.domains.get_logo_v1("dom_1")

    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1/logo"
    assert logo == LOGO


def test_upload_logo_puts_the_svg_source_as_json():
    rec = Recorder(json_response(200, LOGO))
    client = make_client(rec)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'

    client.domains.upload_logo_v1("dom_1", {"svg": svg})

    assert rec.request.method == "PUT"
    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1/logo"
    assert json.loads(rec.request.content) == {"svg": svg}


def test_a_logo_that_cannot_be_rebuilt_is_a_validation_error_naming_what_to_change():
    rec = Recorder(
        problem_response(
            422,
            {
                "type": "https://docs.sendly.now/errors/validation_error",
                "title": "Validation error",
                "code": "validation_error",
                "status": 422,
                "detail": "Convert the text to outlines: <text> is not allowed in SVG Tiny PS.",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyValidationError) as caught:
        client.domains.upload_logo_v1("dom_1", {"svg": "<svg><text>Acme</text></svg>"})

    assert "outlines" in str(caught.value)


def test_delete_logo_returns_the_logo_now_served():
    rec = Recorder(json_response(200, {**LOGO, "source": "default"}))
    client = make_client(rec)

    logo = client.domains.delete_logo_v1("dom_1")

    assert rec.request.method == "DELETE"
    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1/logo"
    assert logo["source"] == "default"


def test_get_logo_readiness_reads_the_checklist():
    rec = Recorder(json_response(200, {"domain_id": "dom_1", "items": [], "providers": []}))
    client = make_client(rec)

    readiness = client.domains.get_logo_readiness_v1("dom_1")

    assert str(rec.request.url) == "http://localhost/api/v1/domains/dom_1/logo/readiness"
    assert readiness["domain_id"] == "dom_1"
