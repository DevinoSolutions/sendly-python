"""Projects resource tests (``/api/v1``)."""

from __future__ import annotations

import pytest

from sendly import SendlyAuthenticationError
from support import Recorder, json_response, make_client, problem_response

PROJECT = {
    "id": "proj_1",
    "name": "Acme",
    "disabled": False,
    "sandbox_address": "sandbox.proj_1@sendly.now",
    "ses_region": "eu-west-1",
    "tracking": "ENABLED",
    "language": "en",
    "created_at": "2026-09-01T00:00:00.000Z",
}


def test_get_requests_the_projects_path_and_returns_the_bare_body():
    rec = Recorder(json_response(200, PROJECT))
    client = make_client(rec)

    project = client.projects.get()

    assert str(rec.request.url) == "http://localhost/api/v1/projects"
    assert rec.request.method == "GET"
    # No id argument: the project is whichever one the key belongs to.
    assert rec.request.content == b""
    assert project == PROJECT


def test_sandbox_address_is_present_so_a_test_send_is_discoverable():
    rec = Recorder(json_response(200, PROJECT))
    client = make_client(rec)

    assert client.projects.get()["sandbox_address"] == "sandbox.proj_1@sendly.now"


def test_invalid_key_raises_authentication_error():
    rec = Recorder(
        problem_response(
            401,
            {
                "type": "https://docs.sendly.now/errors/invalid_api_key",
                "title": "Invalid API key",
                "status": 401,
                "code": "invalid_api_key",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyAuthenticationError) as caught:
        client.projects.get()
    assert caught.value.error_code == "invalid_api_key"
