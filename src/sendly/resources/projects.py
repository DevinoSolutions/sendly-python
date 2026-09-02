"""Projects resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import ProjectRecordV1


class ProjectsResource:
    """The project the credential resolves to.

    There is no ``create`` here. Creating a project resolves the owner from the
    session user and refuses an API key with 401, so it is recorded in
    ``tests/test_contract.py``'s ``NOT_SDK_CALLABLE`` rather than shipped as a
    method that cannot work.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def get(self) -> ProjectRecordV1:
        """Read the current project.

        Takes no id: the project is whichever one the API key belongs to.
        Carries ``sandbox_address``, which is where a test send arrives --
        without it a test send is undiscoverable, since the caller cannot say
        where to look for it.
        """
        response: ProjectRecordV1 = self._client.request(method="GET", path="/api/v1/projects")
        return response
