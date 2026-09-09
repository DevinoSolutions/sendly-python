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

#: One transition in a message's delivery history -- the append-only record
#: behind ``status``. ``status`` says where the message is now; these say how it
#: got there.
EmailEvent = JSONDict
#: An email together with its delivery history, oldest first.
EmailWithEvents = JSONDict
#: A single email with no history -- what ``emails.cancel_schedule`` answers.
#: Was ``EmailGetResponse``, which named the operation rather than the shape and
#: was then reused by an operation that is not a GET.
EmailResponse = JSONDict
#: ``emails.get`` -- one email plus its delivery events.
EmailDetailResponse = JSONDict

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

# ---------- Snippets ----------
#
# Reusable body fragments a template includes with ``{{> name}}``. Gated by the
# same ``templates:*`` scopes as the templates that include them.

SnippetRecord = JSONDict
SnippetListResponse = JSONDict

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

# ---------- Contacts (v1) ----------

ContactV1 = JSONDict
ContactListV1 = CursorList
ContactDeletedV1 = JSONDict
#: Everything one contact has said they want, topic by topic.
ContactTopicPreferencesV1 = JSONDict

# ---------- Lists (v1) ----------

ListV1 = JSONDict
ListListV1 = CursorList
ListDeletedV1 = JSONDict

# ---------- Templates (v1) ----------

TemplateV1 = JSONDict
TemplateListV1 = CursorList
TemplateDeletedV1 = JSONDict

# ---------- Domains (v1) ----------

DomainV1 = JSONDict
DomainListV1 = CursorList
DomainDeletedV1 = JSONDict

# ---------- Webhooks (v1) ----------

WebhookV1 = JSONDict
WebhookListV1 = CursorList
WebhookDeletedV1 = JSONDict
#: The create response, and the only time the signing secret is readable.
WebhookCreatedV1 = JSONDict
#: Rotation answers the new secret once, for the same reason.
WebhookSecretRotatedV1 = JSONDict

# ---------- Suppressions (v1) ----------

SuppressionV1 = JSONDict
SuppressionListV1 = CursorList
SuppressionDeletedV1 = JSONDict

# ---------- Topics (v1) ----------

TopicV1 = JSONDict
TopicListV1 = CursorList
TopicSubscriptionV1 = JSONDict

# ---------- Email validation (v1) ----------

EmailValidationBatchV1 = JSONDict
EmailValidationRunV1 = JSONDict
EmailValidationResultListV1 = CursorList

# ---------- Deliverability (v1) ----------

DeliverabilityDiagnosisV1 = JSONDict
RecipientDomainStatsV1 = JSONDict
RecipientDomainStatsListV1 = CursorList
DmarcReportV1 = JSONDict
DmarcReportListV1 = CursorList

# ---------- Campaign failures (v1) ----------

CampaignFailureV1 = JSONDict
CampaignFailureListV1 = CursorList
CampaignRetryFailedV1 = JSONDict

# ---------- Workflow graph and lifecycle (v1) ----------

WorkflowGraphV1 = JSONDict
WorkflowStateChangeV1 = JSONDict
