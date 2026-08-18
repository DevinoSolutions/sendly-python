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
        WorkflowList,
        WorkflowRecord,
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

    def start_execution(self, id: str, body: Body | None = None) -> WorkflowExecutionRecord:
        """Start the workflow for one contact, bypassing its event trigger.

        ``body`` requires ``contact_id`` and may carry a ``context`` object the
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
