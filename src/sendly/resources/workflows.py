"""Workflows resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment
from sendly.resources._pagination import iterate_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sendly.client import Sendly
    from sendly.types import (
        Body,
        JSONDict,
        Query,
        WorkflowDeleted,
        WorkflowExecutionList,
        WorkflowExecutionRecord,
        WorkflowGraphV1,
        WorkflowList,
        WorkflowRecord,
        WorkflowStateChangeV1,
        WorkflowStats,
    )


class WorkflowsResource:
    """Event-triggered automations and their per-contact executions.

    A workflow fires when its ``event_name`` arrives for a contact (see
    :meth:`~sendly.resources.events.EventsResource.record`); ``allow_reentry``
    decides whether a contact already running the workflow can start it again.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self, query: Query | None = None) -> WorkflowList:
        """List workflows.

        Accepts ``limit`` (1-100, default 20) and ``after`` (opaque cursor), and
        answers ``{data, has_more, next_cursor}``. Keep the filters identical for
        every page of one walk — changing them invalidates the cursor and the API
        answers 422 ``validation_error`` telling you to restart from the first
        page.
        """
        response: WorkflowList = self._client.request(
            method="GET", path="/api/v1/workflows", query=query
        )
        return response

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every workflow across pages, following the cursor for you."""
        return iterate_cursor(self.list, query)

    def create(self, body: Body) -> WorkflowRecord:
        """Create a workflow. Requires ``name`` and ``event_name``."""
        response: WorkflowRecord = self._client.request(
            method="POST", path="/api/v1/workflows", body=body
        )
        return response

    def get(self, id: str) -> WorkflowRecord:
        """Fetch a single workflow."""
        response: WorkflowRecord = self._client.request(
            method="GET", path=f"/api/v1/workflows/{encode_path_segment(id)}"
        )
        return response

    def update(self, id: str, body: Body) -> WorkflowRecord:
        """Patch a workflow — including ``enabled``, which is how you pause one."""
        response: WorkflowRecord = self._client.request(
            method="PATCH", path=f"/api/v1/workflows/{encode_path_segment(id)}", body=body
        )
        return response

    def delete(self, id: str) -> WorkflowDeleted:
        """Delete a workflow. Returns the ``{id, deleted}`` confirmation body."""
        response: WorkflowDeleted = self._client.request(
            method="DELETE", path=f"/api/v1/workflows/{encode_path_segment(id)}"
        )
        return response

    def list_executions(self, id: str, query: Query | None = None) -> WorkflowExecutionList:
        """List one workflow's executions.

        Cursor-paginated (``limit`` / ``after``) and filterable by ``status``.
        As with every v1 listing, a filter you change mid-walk invalidates the
        cursor — restart from the first page instead.
        """
        response: WorkflowExecutionList = self._client.request(
            method="GET",
            path=f"/api/v1/workflows/{encode_path_segment(id)}/executions",
            query=query,
        )
        return response

    def iter_list_executions(self, id: str, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every execution of a workflow across pages."""
        return iterate_cursor(lambda params: self.list_executions(id, params), query)

    def start_execution(self, id: str, body: Body) -> WorkflowExecutionRecord:
        """Start the workflow for one contact, bypassing its event trigger.

        ``body`` is required and must carry ``contact_id`` — an execution always
        belongs to a contact. It may also carry a ``context`` object the
        workflow's steps can read.
        """
        response: WorkflowExecutionRecord = self._client.request(
            method="POST",
            path=f"/api/v1/workflows/{encode_path_segment(id)}/executions",
            body=body,
        )
        return response

    def cancel_execution(self, execution_id: str) -> WorkflowExecutionRecord:
        """Cancel one in-flight execution.

        Addressed by execution id alone — the route is
        ``/api/v1/workflows/executions/{execution_id}/cancel``, not nested under
        the workflow — so a caller holding an execution id needs nothing else.
        """
        response: WorkflowExecutionRecord = self._client.request(
            method="POST",
            path=f"/api/v1/workflows/executions/{encode_path_segment(execution_id)}/cancel",
        )
        return response

    def stats(self, id: str, query: Query | None = None) -> WorkflowStats:
        """Execution totals, completion rate, and attributed email/conversion counts.

        Accepts ``from`` to bound the window.
        """
        response: WorkflowStats = self._client.request(
            method="GET",
            path=f"/api/v1/workflows/{encode_path_segment(id)}/stats",
            query=query,
        )
        return response

    def get_graph(self, id: str) -> WorkflowGraphV1:
        """Every step in the workflow, its ``TRIGGER`` entry node included, plus
        the directed transitions between them.

        A step's ``config`` comes back exactly as stored, camelCase keys and
        all, rather than projected into the snake_case used elsewhere on v1: the
        same document is authored by the visual editor, and renaming its keys on
        the way out would silently drop any key this API does not know on the
        way back in.

        ``version`` is the workflow's version at the time of the read, so a
        different number on a later read means somebody edited the graph in
        between. This body is accepted verbatim by :meth:`replace_graph` -- read
        a graph, change one step, send it back.
        """
        response: WorkflowGraphV1 = self._client.request(
            method="GET", path=f"/api/v1/workflows/{encode_path_segment(id)}/graph"
        )
        return response

    def replace_graph(self, id: str, body: Body) -> WorkflowGraphV1:
        """Replace the whole graph in one transaction.

        A ``PUT`` and not a ``PATCH``, and that is the point: a graph is nodes
        *plus* the edges between them, so a partial edit to a step list has no
        meaning without the transitions that reference it -- half-applied, it
        would leave steps pointing at steps that no longer exist.

        Ids decide the outcome per step: one you send is kept and updated in
        place, a fresh uuid creates a step, and an id you omit deletes that step
        *and its run history*. Exactly one step must be a ``TRIGGER``, every
        transition must name steps in the same document, and no step may point
        at itself.

        Refused with 409 ``conflict`` while the workflow has running executions
        -- those runs are standing on the steps being replaced. :meth:`pause`
        first.
        """
        response: WorkflowGraphV1 = self._client.request(
            method="PUT",
            path=f"/api/v1/workflows/{encode_path_segment(id)}/graph",
            body=body,
        )
        return response

    def clone(self, id: str, body: Body) -> WorkflowRecord:
        """Copy a workflow and its whole graph as a new workflow.

        The copy is always created disabled, whatever the original was: a clone
        exists to be reviewed, and one that started live would match the same
        trigger events as its original from the moment it appeared. Pass
        ``{"name": ...}`` to name it; it otherwise becomes ``Copy of <original
        name>``.
        """
        response: WorkflowRecord = self._client.request(
            method="POST",
            path=f"/api/v1/workflows/{encode_path_segment(id)}/clone",
            body=body,
        )
        return response

    def pause(self, id: str) -> WorkflowStateChangeV1:
        """Disable the workflow *and cancel every* ``RUNNING``/``WAITING``
        execution in it, returning ``{workflow, cancelled_executions}``.

        That is what separates this from ``update(id, {"enabled": False})``,
        which only stops new runs starting and leaves every in-flight contact
        walking the graph -- the next delay still expires, the next email still
        sends.

        The cancellation is terminal: :meth:`resume` re-opens the workflow to
        new runs, it does not put the cancelled contacts back where they were.
        """
        response: WorkflowStateChangeV1 = self._client.request(
            method="POST", path=f"/api/v1/workflows/{encode_path_segment(id)}/pause"
        )
        return response

    def resume(self, id: str) -> WorkflowStateChangeV1:
        """Re-enable the workflow so its trigger matches again.

        ``cancelled_executions`` is always 0 here -- resuming starts nothing and
        stops nothing. Refused with 422 ``validation_error`` while any step is
        still unconfigured, the same rule ``update(id, {"enabled": True})``
        enforces: an enabled workflow accepts contacts immediately and would
        otherwise fail only once one reached the broken step.
        """
        response: WorkflowStateChangeV1 = self._client.request(
            method="POST", path=f"/api/v1/workflows/{encode_path_segment(id)}/resume"
        )
        return response
