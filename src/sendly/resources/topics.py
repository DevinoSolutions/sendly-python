"""Topics resource (``/api/v1``)."""

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
        TopicListV1,
        TopicSubscriptionV1,
        TopicV1,
    )


class TopicsResource:
    """The consent vocabulary a project mails against.

    A contact subscribes to a topic rather than to a campaign, so switching one
    off silences a whole audience. Responses are bare v1 bodies (no
    ``{success, data}`` envelope) and errors are RFC 9457 problem documents.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def list(self, query: Query | None = None) -> TopicListV1:
        """List topics, newest first.

        Accepts ``limit`` (1-100), ``after`` and ``include_archived``, the
        same pagination parameters as every other v1 list. Archived topics are
        omitted unless you ask for them; there is no delete, because a topic is
        where people's answers are recorded.
        """
        response: TopicListV1 = self._client.request(
            method="GET", path="/api/v1/topics", query=query
        )
        return response

    def iter_list(self, query: Query | None = None) -> Iterator[JSONDict]:
        """Iterate every topic across pages, following the cursor for you.

        This was written out through 1.0, because the endpoint named its cursor
        ``cursor`` on both sides where every other v1 list takes ``after`` and
        answers ``next_cursor`` -- so the shared walker would have sent a
        parameter the route ignored and read a field it never returned. The
        route speaks the one dialect now.
        """
        return iterate_cursor(self.list, query)

    def create(self, body: Body) -> TopicV1:
        """Create a topic. Requires ``key`` and ``name``.

        ``key`` is the stable name every preference form and integration refers
        to, so it survives a rename of ``name`` and cannot be changed later.

        ``default_opt_in`` decides what silence means for a contact who never
        answers: true for a topic introduced over a list that already consented
        to hear from you, false for anything a person has to ask for.
        """
        response: TopicV1 = self._client.request(method="POST", path="/api/v1/topics", body=body)
        return response

    def get(self, id: str) -> TopicV1:
        """Fetch a single topic, including its subscribed and unsubscribed counts."""
        response: TopicV1 = self._client.request(
            method="GET", path=f"/api/v1/topics/{encode_path_segment(id)}"
        )
        return response

    def update(self, id: str, body: Body) -> TopicV1:
        """Patch a topic's name, description, ``default_opt_in``, or archived flag.

        ``key`` is not patchable, and ``archived: True`` stands in for the
        delete that does not exist: it drops the topic from the preference
        centre and from new sends while every opt-out recorded against it
        survives.
        """
        response: TopicV1 = self._client.request(
            method="PATCH", path=f"/api/v1/topics/{encode_path_segment(id)}", body=body
        )
        return response

    def set_subscription(self, id: str, body: Body) -> TopicSubscriptionV1:
        """Record what one contact wants on one topic. The two directions differ.

        ``subscribed: True`` does NOT subscribe anybody: it parks the contact at
        ``pending`` and answers a ``confirmation_url``, and nothing is mailed on
        this topic until someone opens that link. There is no parameter to skip
        it -- a caller asserting a subscription is not evidence the mailbox
        holder agreed. Sendly does not send the confirmation email; you do, from
        your own verified domain.

        ``subscribed: False`` records the opt-out immediately.
        """
        response: TopicSubscriptionV1 = self._client.request(
            method="POST",
            path=f"/api/v1/topics/{encode_path_segment(id)}/subscriptions",
            body=body,
        )
        return response
