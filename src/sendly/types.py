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

# The versioned send. Distinct from the legacy aliases above, which post to
# ``/api/emails`` and answer with row ids and no delivery status.
EmailV1 = JSONDict
EmailTestV1 = JSONDict

# ---------- Contacts ----------

ContactRecord = JSONDict
ContactListResponse = JSONDict

# ---------- Domains ----------

DomainRecord = JSONDict
DomainListResponse = JSONDict
DomainVerificationStatus = JSONDict
#: ``{token, connectUrl, expiresAt}`` -- the link a person opens to finish setup.
DomainSetupSession = JSONDict

# ---------- Mailboxes ----------

MailboxRecord = JSONDict
#: A mailbox plus the IMAP/SMTP host, port and username a mail client needs.
MailboxDetail = JSONDict
AppPasswordRecord = JSONDict
#: The list aliases are not decoration: inside ``MailboxesResource`` the name
#: ``list`` is the resource's own method, so a bare ``list[MailboxRecord]``
#: annotation resolves to that method and fails type checking. Naming the list
#: types here sidesteps the shadowing and keeps the annotations readable.
MailboxList = list[JSONDict]
AppPasswordList = list[JSONDict]

# ---------- Projects (v1) ----------

ProjectRecordV1 = JSONDict

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

# ---------- Lists ----------

ListSubscribeData = JSONDict
ListUnsubscribeData = JSONDict

# ---------- Events ----------

TrackEventData = JSONDict
TrackEventResponse = JSONDict

# ---------- Verify ----------

VerifyEmailData = JSONDict
VerifyEmailResponse = JSONDict

# ---------- /api/v1 ----------
#
# The v1 surface returns bare resource bodies (no {success, data} envelope) and
# a uniform list envelope: {data, has_more, next_cursor}. The ``*List`` aliases
# below name that envelope; the iterator methods yield the items inside ``data``.

CursorList = JSONDict

CampaignRecord = JSONDict
CampaignList = CursorList
CampaignStats = JSONDict
CampaignDeleted = JSONDict

SegmentRecord = JSONDict
SegmentList = CursorList
SegmentDeleted = JSONDict
ContactList = CursorList

WorkflowRecord = JSONDict
WorkflowList = CursorList
WorkflowDeleted = JSONDict
WorkflowStats = JSONDict
WorkflowExecutionRecord = JSONDict
WorkflowExecutionList = CursorList

EventRecord = JSONDict
EventList = CursorList
EventNameList = JSONDict
EventStats = JSONDict

AnalyticsTimeseries = JSONDict
CampaignAnalytics = JSONDict
TopCampaignList = JSONDict

UsageSummary = JSONDict
