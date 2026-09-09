"""Workflows resource tests (``/api/v1``)."""

from __future__ import annotations

import json

import pytest

from sendly import SendlyConflictError, SendlyNotFoundError
from support import (
    Recorder,
    SequenceRecorder,
    cursor_page,
    json_response,
    make_client,
    problem_response,
)

WORKFLOW = {
    "id": "wf_1",
    "name": "Welcome series",
    "enabled": True,
    "trigger_type": "EVENT",
    "event_name": "signup.completed",
    "version": 3,
}

EXECUTION = {
    "id": "exe_1",
    "workflow_id": "wf_1",
    "contact_id": "con_1",
    "status": "RUNNING",
}


def test_list_and_create_hit_the_collection_path():
    page = cursor_page([WORKFLOW])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)
    assert client.workflows.list() == page
    assert str(rec.request.url) == "http://localhost/api/v1/workflows"

    rec = Recorder(json_response(201, WORKFLOW))
    client = make_client(rec)
    result = client.workflows.create({"name": "Welcome series", "event_name": "signup.completed"})
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content)["event_name"] == "signup.completed"
    assert result == WORKFLOW


def test_get_update_and_delete_hit_the_id_path():
    rec = Recorder(json_response(200, WORKFLOW))
    client = make_client(rec)
    assert client.workflows.get("wf_1") == WORKFLOW
    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1"

    rec = Recorder(json_response(200, {**WORKFLOW, "enabled": False}))
    client = make_client(rec)
    # Disabling is how a workflow is paused -- there is no separate action.
    assert client.workflows.update("wf_1", {"enabled": False})["enabled"] is False
    assert rec.request.method == "PATCH"

    rec = Recorder(json_response(200, {"id": "wf_1", "deleted": True}))
    client = make_client(rec)
    assert client.workflows.delete("wf_1") == {"id": "wf_1", "deleted": True}


def test_list_executions_forwards_the_status_filter():
    page = cursor_page([EXECUTION])
    rec = Recorder(json_response(200, page))
    client = make_client(rec)

    assert client.workflows.list_executions("wf_1", {"status": "RUNNING"}) == page
    assert (
        str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/executions?status=RUNNING"
    )


def test_start_execution_posts_the_contact_to_the_nested_path():
    rec = Recorder(json_response(201, EXECUTION))
    client = make_client(rec)

    result = client.workflows.start_execution("wf_1", {"contact_id": "con_1", "context": {"a": 1}})

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/executions"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"contact_id": "con_1", "context": {"a": 1}}
    assert result == EXECUTION


def test_cancel_execution_is_addressed_by_execution_id_alone():
    # The route is /api/v1/workflows/executions/{execution_id}/cancel -- NOT
    # nested under the workflow id.
    rec = Recorder(json_response(200, {**EXECUTION, "status": "CANCELLED"}))
    client = make_client(rec)

    result = client.workflows.cancel_execution("exe_1")

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/executions/exe_1/cancel"
    assert rec.request.method == "POST"
    assert result["status"] == "CANCELLED"


def test_cancel_execution_percent_encodes_the_execution_id():
    rec = Recorder(json_response(200, EXECUTION))
    client = make_client(rec)
    client.workflows.cancel_execution("exe/1")
    assert str(rec.request.url) == "http://localhost/api/v1/workflows/executions/exe%2F1/cancel"


def test_stats_forwards_the_window_filter():
    stats = {"workflow_id": "wf_1", "total": 120, "completion_rate": 0.85}
    rec = Recorder(json_response(200, stats))
    client = make_client(rec)

    assert client.workflows.stats("wf_1", {"from": "2026-08-01"}) == stats
    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/stats?from=2026-08-01"


def test_cancel_execution_raises_not_found_from_a_problem_document():
    rec = Recorder(
        problem_response(
            404,
            {
                "type": "https://docs.sendly.now/errors/resource_not_found",
                "title": "Resource Not Found",
                "status": 404,
                "code": "resource_not_found",
            },
        )
    )
    client = make_client(rec)
    with pytest.raises(SendlyNotFoundError):
        client.workflows.cancel_execution("exe_missing")


def test_iter_list_walks_every_page():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "wf_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "wf_2"}])),
    )
    client = make_client(rec)
    assert [w["id"] for w in client.workflows.iter_list()] == ["wf_1", "wf_2"]


def test_iter_list_executions_keeps_the_workflow_id_and_filter_across_pages():
    rec = SequenceRecorder(
        json_response(200, cursor_page([{"id": "exe_1"}], next_cursor="cur_2")),
        json_response(200, cursor_page([{"id": "exe_2"}])),
    )
    client = make_client(rec)

    ids = [e["id"] for e in client.workflows.iter_list_executions("wf_1", {"status": "RUNNING"})]

    assert ids == ["exe_1", "exe_2"]
    assert rec.urls == [
        "http://localhost/api/v1/workflows/wf_1/executions?status=RUNNING",
        "http://localhost/api/v1/workflows/wf_1/executions?status=RUNNING&after=cur_2",
    ]


TRIGGER_STEP = {
    "id": "st_1",
    "name": "Signed up",
    "position": {"x": 0, "y": 0},
    "type": "TRIGGER",
    "config": {"eventName": "signup"},
}

GRAPH = {
    "workflow_id": "wf_1",
    "version": 7,
    "steps": [{**TRIGGER_STEP, "template_id": None}],
    "transitions": [],
}


def test_get_graph_reads_the_graph_subpath_and_returns_the_bare_body():
    rec = Recorder(json_response(200, GRAPH))
    client = make_client(rec)

    graph = client.workflows.get_graph("wf_1")

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/graph"
    assert rec.request.method == "GET"
    # A v1 body arrives bare: `version` sits at the top level, not under `data`.
    assert graph == GRAPH
    assert graph["version"] == 7


def test_replace_graph_issues_a_put_not_a_patch_and_sends_the_whole_document():
    rec = Recorder(json_response(200, {**GRAPH, "version": 8}))
    client = make_client(rec)

    body = {"steps": [TRIGGER_STEP], "transitions": []}
    graph = client.workflows.replace_graph("wf_1", body)

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/graph"
    assert rec.request.method == "PUT"
    assert rec.request.method != "PATCH"
    assert json.loads(rec.request.content) == body
    assert graph["version"] == 8


def test_replace_graph_raises_conflict_while_executions_are_running():
    rec = Recorder(
        problem_response(
            409,
            {
                "type": "https://docs.sendly.now/errors/conflict",
                "title": "Conflict",
                "status": 409,
                "detail": "Workflow has running executions.",
                "code": "conflict",
            },
        )
    )
    client = make_client(rec)

    with pytest.raises(SendlyConflictError) as caught:
        client.workflows.replace_graph("wf_1", {"steps": [TRIGGER_STEP], "transitions": []})
    assert caught.value.error_code == "conflict"


def test_clone_posts_the_name_and_returns_a_copy_that_is_always_disabled():
    rec = Recorder(json_response(201, {"id": "wf_2", "name": "Onboarding v2", "enabled": False}))
    client = make_client(rec)

    copy = client.workflows.clone("wf_1", {"name": "Onboarding v2"})

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/clone"
    assert rec.request.method == "POST"
    assert json.loads(rec.request.content) == {"name": "Onboarding v2"}
    assert copy["id"] == "wf_2"
    assert copy["enabled"] is False


def test_pause_reports_the_runs_it_cancelled():
    rec = Recorder(json_response(200, {"workflow": {"id": "wf_1"}, "cancelled_executions": 23}))
    client = make_client(rec)

    paused = client.workflows.pause("wf_1")

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/pause"
    assert rec.request.method == "POST"
    # This count is what makes pause different from update({"enabled": False}).
    assert paused["cancelled_executions"] == 23


def test_resume_reports_zero_cancellations():
    rec = Recorder(json_response(200, {"workflow": {"id": "wf_1"}, "cancelled_executions": 0}))
    client = make_client(rec)

    resumed = client.workflows.resume("wf_1")

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf_1/resume"
    assert rec.request.method == "POST"
    assert resumed["cancelled_executions"] == 0


def test_graph_routes_percent_encode_the_workflow_id():
    rec = Recorder(json_response(200, GRAPH))
    client = make_client(rec)

    client.workflows.get_graph("wf/../evil")

    assert str(rec.request.url) == "http://localhost/api/v1/workflows/wf%2F..%2Fevil/graph"
