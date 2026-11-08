"""Projects resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sendly.resources._helpers import encode_path_segment

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import (
        ProjectRecordV1,
        ProjectSecurity,
        ProjectSetupState,
    )


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

    def get_security(self, id: str) -> ProjectSecurity:
        """The project's sending health and security status, including any
        suspension. Needs ``projects:read``. Legacy ``{success, data}`` dialect,
        unwrapped by the SDK.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/projects/{encode_path_segment(id)}/security"
        )
        security: ProjectSecurity = self._client.unwrap(envelope)
        return security

    def get_setup_state(self, id: str) -> ProjectSetupState:
        """Which onboarding steps the project has finished: ``hasSubscription``,
        ``hasVerifiedDomain``, ``contactCount``, ``lastCampaignSentAt`` and
        ``hasEnabledWorkflow``. Needs ``projects:read``.
        """
        envelope = self._client.request(
            method="GET", path=f"/api/projects/{encode_path_segment(id)}/setup-state"
        )
        state: ProjectSetupState = self._client.unwrap(envelope)
        return state
