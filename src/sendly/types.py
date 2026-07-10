"""Type aliases for the Sendly SDK.

The Sendly API speaks JSON. The reference TypeScript SDK layers precise
OpenAPI-generated types over that JSON but performs no runtime validation — the
request core simply serializes the body and returns the parsed response. This
Python port keeps the same thin-client contract: request inputs are accepted as
loose mappings (so any valid API field flows through without the SDK rejecting
it) and responses are returned as parsed ``dict`` objects.

The response aliases below are intentionally ``dict[str, Any]`` but are named to
mirror the TypeScript SDK's ``types.ts`` exports, so the public surface reads the
same across both SDKs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# ---------- Generic JSON ----------

JSONValue = Any
JSONDict = dict[str, Any]

# ---------- Request inputs (typed loosely, like the TS request core) ----------

Body = Mapping[str, Any]
Query = Mapping[str, Any]
Headers = Mapping[str, str]

# ---------- Generic envelopes ----------

SuccessEmpty = JSONDict
Pagination = JSONDict

# ---------- Emails ----------

SendEmailData = JSONDict
SendEmailResponse = JSONDict
BatchSendResponse = JSONDict
EmailRecord = JSONDict
EmailListResponse = JSONDict
EmailGetResponse = JSONDict

# ---------- Contacts ----------

ContactRecord = JSONDict
ContactListResponse = JSONDict

# ---------- Domains ----------

DomainRecord = JSONDict
DomainListResponse = JSONDict
DomainVerificationStatus = JSONDict

# ---------- Templates ----------

TemplateRecord = JSONDict
TemplateListResponse = JSONDict

# ---------- Webhooks ----------

WebhookRecord = JSONDict
WebhookCreateResponse = JSONDict
WebhookGetResponse = JSONDict
WebhookListResponse = JSONDict
WebhookRotateSecretResponse = JSONDict
WebhookCallsListResponse = JSONDict

# ---------- Suppression ----------

SuppressionRecord = JSONDict
SuppressionListResponse = JSONDict
SuppressionCheckResponse = JSONDict

# ---------- Events ----------

TrackEventData = JSONDict
TrackEventResponse = JSONDict

# ---------- Verify ----------

VerifyEmailData = JSONDict
VerifyEmailResponse = JSONDict
