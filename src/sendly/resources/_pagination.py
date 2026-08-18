"""Auto-pagination over the ``/api/v1`` cursor envelope.

Every v1 list endpoint answers with ``{data, has_more, next_cursor}``: an opaque
forward-only cursor and no total (deliberately — counting a project's rows is a
scan the API refuses to pay for on every page). :func:`iterate_cursor` walks that
shape so callers can treat a multi-page listing as one stream of items.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sendly.types import JSONDict, Query


def iterate_cursor(
    fetch: Callable[[dict[str, Any]], Any],
    query: Query | None = None,
) -> Iterator[JSONDict]:
    """Yield every item across the pages ``fetch`` returns.

    ``fetch`` receives the query for one page — the caller's own filters, plus
    the ``after`` cursor from page two onward — and returns the raw cursor
    envelope. Iteration stops when ``has_more`` is false or ``next_cursor`` is
    ``None``, and also when a page carries no ``data`` list, so a malformed
    response ends the walk instead of looping forever.

    The caller's filters are held fixed for the whole walk on purpose: changing
    them mid-pagination invalidates the cursor and the API answers ``422
    validation_error`` telling you to restart from the first page.
    """
    params = dict(query or {})
    while True:
        page = fetch(params)
        if not isinstance(page, dict):
            return
        items = page.get("data")
        if not isinstance(items, list):
            return
        yield from items
        if not page.get("has_more"):
            return
        cursor = page.get("next_cursor")
        if not cursor:
            return
        params = {**params, "after": cursor}
