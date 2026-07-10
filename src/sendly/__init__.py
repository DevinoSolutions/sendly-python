"""Official Sendly Python SDK.

Example:
    >>> from sendly import Sendly
    >>> sendly = Sendly()  # reads SENDLY_API_KEY
    >>> sendly.emails.send(
    ...     {"from": "a@b.com", "to": "c@d.com", "subject": "hi", "body": "<p>hi</p>"}
    ... )
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
from sendly.resources.contacts import ContactsResource
from sendly.resources.domains import DomainsResource
from sendly.resources.emails import EmailsResource
from sendly.resources.events import EventsResource
from sendly.resources.suppression import SuppressionResource
from sendly.resources.templates import TemplatesResource
from sendly.resources.verify import VerifyResource
from sendly.resources.webhooks import WebhooksResource
from sendly.webhook_utils import DEFAULT_TOLERANCE_MS, construct_event, verify_signature

__version__ = SDK_VERSION

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TOLERANCE_MS",
    "SDK_VERSION",
    "ContactsResource",
    "DomainsResource",
    "EmailsResource",
    "EventsResource",
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
    "VerifyResource",
    "WebhooksResource",
    "__version__",
    "construct_event",
    "verify_signature",
]
