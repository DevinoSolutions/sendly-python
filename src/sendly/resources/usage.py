"""Usage resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import UsageSummary


class UsageResource:
    """The caller's plan and its current quota consumption."""

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def get(self) -> UsageSummary:
        """Current ``plan`` plus ``monthly`` and ``daily`` usage against its limits.

        Read this before a large send to see the headroom the API would enforce:
        exceeding a quota answers 429 ``quota_exhausted``, which is a different
        failure from 429 ``rate_limited`` (too fast, retry) and is not fixed by
        backing off.
        """
        response: UsageSummary = self._client.request(method="GET", path="/api/v1/usage")
        return response
