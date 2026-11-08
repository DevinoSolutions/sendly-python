"""Billing resource (``/api/v1``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import BillingStatus, PlanList


class BillingResource:
    """The project's plan and spending, read-only. Needs ``billing:read``.

    Changing a plan is not here: it needs a person to approve the charge.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def get(self) -> BillingStatus:
        """The project's plan (``free`` or ``payg``), its Stripe subscription state
        and renewal date, its spending limits and this month's usage.

        For a person caller the body also reports their mobile Pro entitlement;
        for an API key ``pro`` is ``None``.
        """
        response: BillingStatus = self._client.request(method="GET", path="/api/v1/billing")
        return response

    def list_plans(self) -> PlanList:
        """The plans that exist, as ``{plans}``, each with its volume tiers and the
        channels it can be bought through."""
        response: PlanList = self._client.request(method="GET", path="/api/v1/billing/plans")
        return response
