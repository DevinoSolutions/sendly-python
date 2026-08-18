"""Official Sendly Python SDK.

Example:
    >>> from sendly import Sendly
    >>> sendly = Sendly()  # reads SENDLY_API_KEY
    >>> sendly.emails.send(
    ...     {"from": "a@b.com", "to": "c@d.com", "subject": "hi", "body": "<p>hi</p>"}
    ... )

The same client also speaks the ``/api/v1`` surface — campaigns, segments,
workflows, analytics, usage, and the v1 event methods:

    >>> for campaign in sendly.campaigns.iter_list({"limit": 100}):
    ...     print(campaign["name"], campaign["status"])
"""

from __future__ import annotations

from sendly.client import DEFAULT_BASE_URL, SDK_VERSION, Sendly
from sendly.errors import (
    SendlyAuthenticationError,
    SendlyConflictError,
    SendlyConnectionError,
    SendlyError,
    SendlyNotFoundError,
    SendlyPermissionError,
    SendlyRateLimitError,
    SendlyServerError,
    SendlyValidationError,
)
from sendly.resources.analytics import AnalyticsResource
from sendly.resources.campaigns import CampaignsResource
from sendly.resources.contacts import ContactsResource
from sendly.resources.domains import DomainsResource
from sendly.resources.emails import EmailsResource
from sendly.resources.events import EventsResource
from sendly.resources.lists import ListsResource
from sendly.resources.segments import SegmentsResource
from sendly.resources.suppression import SuppressionResource
from sendly.resources.templates import TemplatesResource
from sendly.resources.usage import UsageResource
from sendly.resources.verify import VerifyResource
from sendly.resources.webhooks import WebhooksResource
from sendly.resources.workflows import WorkflowsResource
from sendly.webhook_utils import DEFAULT_TOLERANCE_MS, construct_event, verify_signature

__version__ = SDK_VERSION

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TOLERANCE_MS",
    "SDK_VERSION",
    "AnalyticsResource",
    "CampaignsResource",
    "ContactsResource",
    "DomainsResource",
    "EmailsResource",
    "EventsResource",
    "ListsResource",
    "SegmentsResource",
    "Sendly",
    "SendlyAuthenticationError",
    "SendlyConflictError",
    "SendlyConnectionError",
    "SendlyError",
    "SendlyNotFoundError",
    "SendlyPermissionError",
    "SendlyRateLimitError",
    "SendlyServerError",
    "SendlyValidationError",
    "SuppressionResource",
    "TemplatesResource",
    "UsageResource",
    "VerifyResource",
    "WebhooksResource",
    "WorkflowsResource",
    "__version__",
    "construct_event",
    "verify_signature",
]
