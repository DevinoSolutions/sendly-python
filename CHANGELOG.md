# Changelog

All notable changes to `sendly-python` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-05

Four new resources, the `/api/v1` half of six that only had a legacy one, and a
set of renames the platform made on the wire. Most of this release is additive,
but the renames are breaking, so it is a major-in-spirit minor: 1.1 talks to an
API that 1.0 did not.

> **Do not publish or deploy 1.1 before the platform deploy that ships the
> renamed wire has gone out.** An SDK sending `emailCategory` at an API that
> still expects `type` is answered `422 validation_error` on every template and
> campaign write. The order is: platform deploy first, then publish the SDKs.

### Breaking

- **`Template.type` and `Campaign.type` are now `emailCategory`** on the legacy
  dialect and `email_category` on v1. It affects `templates.create`,
  `templates.update`, the `emailCategory` filter on `templates.list`, and
  `campaigns.create`. Rename the key in the body; the values are unchanged
  except that the enum member **`HEADLESS` is now `SELF_MANAGED_UNSUBSCRIBE`** —
  the old name said how the mail was built, the new one says what the recipient
  gets, which is the fact a caller is choosing between.

  Nothing is accepted under both names, deliberately: an alias would let a
  half-migrated codebase keep working while the two spellings drifted apart.

- **`events.record`'s payload field is now `payload`, not `data`.** Only the v1
  write moved. **`events.track` is unaffected** and still takes `data`, because
  it is the legacy `POST /api/track` and its body is a different schema that was
  not part of this rename. The SDK documents what each endpoint actually accepts
  rather than smoothing the two together — a shared name here would be a lie
  about one of them.

- **`Domain.mailFromStatus` is now `mailFromDomainStatus`** (and
  `mail_from_domain_status` on the v1 document). It sits beside `mailFromDomain`
  and is the status *of that domain*, which the old name did not say.

- **`emails.get` returns a different body — read this one.** It used to hand
  back the whole database row plus an `events` array that was the **wrong
  relation**: the custom analytics events a caller records with `events.record`,
  not the delivery history the operation has always promised. A caller polling
  it for delivery state was reading somebody else's data and, if their project
  recorded no custom events, an empty list that looked like "nothing has
  happened yet".

  It now returns an explicit field list, `events` as the delivery timeline
  (oldest first), and `to` filled from the joined contact — a field the spec had
  always declared and the response had never carried.

  Keys that used to leak out of it and no longer do: `bodyHash`, `dedupKey`,
  `idempotencyKey`, `linkMap`, `sesMessageId`, `sesInboundMessageId`, `body` and
  `headers`. Four of those are ledger keys for deduplication and idempotency and
  the rest are internal routing state or the rendered message; none was ever
  documented. What to change: read `events.list` if you wanted custom events,
  and keep your own copy of the body if you were reading it back out of here.

- **Engagement left the delivery status.** `OPENED`, `CLICKED` and `COMPLAINED`
  are no longer delivery states, so they no longer appear in `email["status"]`
  and are no longer accepted by the `status` filter on `emails.list`. The
  remaining values are `PENDING`, `SENDING`, `SENT`, `DELIVERED`, `RECEIVED`,
  `BOUNCED`, `FAILED`, `REJECTED`, `RENDERING_FAILURE`, `DELIVERY_DELAY` and
  `CANCELLED`.

  Read engagement from `openedAt` / `clickedAt` / `complainedAt` and the `opens`
  / `clicks` counters instead. The two were one enum, which meant a message that
  had been opened stopped reporting that it had been delivered — a status can
  only hold one value, and delivery and engagement are not alternatives.

- **The double-opt-in confirmation route moved** from `/api/lists/confirm` to
  `/api/lists/confirm-subscription`. `lists.subscribe` documents that URL
  because Sendly does not send the confirmation email — your application does —
  so a caller who builds it by hand must change the path. The `confirmToken` in
  the response is unchanged.

### Added

- **The `/api/v1` half of six resources that had only a legacy one.** Both
  dialects stay reachable, so the versioned methods carry a `_v1` suffix:
  - `contacts` — `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`,
    `delete_v1`, and `topic_preferences`.
  - `lists` — `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`,
    `delete_v1`, and `start_validation_run`.
  - `templates` — `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`,
    `update_v1`, `delete_v1`.
  - `domains` — `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `verify_v1`,
    `delete_v1`, plus the legacy `assign_stream`.
  - `webhooks` — `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`,
    `delete_v1`, `rotate_secret_v1`.
  - `suppression` — `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`,
    `delete_v1`.

  The suffix is not decoration. The two halves answer the same question with
  different envelopes (`{success, data}` versus the bare body), different field
  cases (camelCase versus snake_case) and different error bodies (the legacy
  envelope versus RFC 9457), so a call site that mixes them up reads a `data`
  that is not there and raises a `KeyError` a long way from the mistake. Naming
  them apart is what makes that impossible.

  One difference inside suppression is worth knowing before you swap: the v1
  path parameter is an **address**, and v1 answers `404 resource_not_found` for
  an address that is not suppressed, where the legacy `suppression.get` answers
  `200 {"suppressed": False}`. Both are definite; only one of them raises.

- **`sendly.topics`** — `list`, `iter_list`, `create`, `get`, `update`,
  `set_subscription`. The consent vocabulary a project mails against: a contact
  subscribes to a topic rather than to a campaign, so switching one off silences
  a whole audience. Two things a caller needs:
  - **Subscribing somebody through the API does not bypass confirmation.**
    `set_subscription(id, {"subscribed": True})` parks the contact at `pending`
    and returns a `confirmation_url` that **your** application delivers, from
    your own verified domain; nothing is mailed on the topic until someone opens
    it. There is no parameter to skip that, because a subscription an API caller
    asserts is not evidence the mailbox holder agreed.
  - **A topic is archived, never deleted.** There is no `delete` method because
    there is no delete route: a topic is where people's answers are recorded, so
    deleting it would delete the choices they made against it.
    `update(id, {"archived": True})` retires it and keeps them.

- **`sendly.snippets`** — `create`, `list`, `get`, `update`, `delete`. Reusable
  body fragments a template includes with `{{> name}}`, on the legacy dialect,
  gated by the same `templates:*` scopes as the templates that include them — a
  snippet is part of a template body rather than a resource with an audience of
  its own. Deleting one does not break its templates: an absent snippet renders
  as an empty string, like an absent variable.

- **`sendly.validation`** — `validate_emails`, `get_run`, `list_results`,
  `iter_list_results`. **Billed per address checked**: every entry in
  `validate_emails({"emails": [...]})` costs money, so looping it over a contact
  list is looping over your invoice. Validate a whole list with
  `lists.start_validation_run`, a background job, and poll it with `get_run`.

  A verdict of `unknown` is deliberately a distinct value from `undeliverable`:
  it means DNS did not answer in time, so the address was **not checked**. That
  separation exists so a DNS timeout is never grounds for deleting a contact.

- **`sendly.deliverability`** — `diagnose`, `list_domain_stats`,
  `iter_list_domain_stats`, `list_dmarc_reports`, `iter_list_dmarc_reports`.
  `list_domain_stats` is per **recipient** domain (`gmail.com`, `outlook.com`) —
  the domains you send **to** — which is the axis `diagnose` cannot report: its
  project-wide rates hide one provider refusing nearly everything while the rest
  of your mail is healthy. DMARC reports arrive only for a policy domain the
  project has registered, and receivers send them on their own schedule, so **an
  empty list is correct rather than broken**.

- **`campaigns.list_failures`, `campaigns.iter_list_failures` and
  `campaigns.retry_failed`.** `stats` says how many sends failed; only these say
  who, and `reason` comes from a fixed vocabulary rather than the underlying
  error text so it is stable enough to branch on. `retry_failed` re-drives
  **only** the recipients whose send failed — nobody who already received the
  campaign is mailed again, because each ledger row is claimed before it is
  touched and a row whose email exists already is re-queued rather than re-sent.
  Uniquely among v1 lists, `list_failures` also carries `total`: `retry_failed`
  acts on that number, and `has_more` alone cannot tell you whether 3 or 30,000
  sends failed.

- **`workflows.get_graph`, `workflows.replace_graph`, `workflows.clone`,
  `workflows.pause` and `workflows.resume`.**
  - `replace_graph` is a `PUT` because a graph is replaced whole: nodes *plus*
    the edges between them, so a partial edit to a step list has no meaning
    without the transitions that reference it. An id you omit deletes that step
    and its run history; it is refused with `409 conflict` while executions are
    running.
  - `clone` always creates the copy **disabled**, whatever the original was — a
    clone exists to be reviewed, and one that started live would match the same
    trigger events as its original from the moment it appeared.
  - `pause` cancels every `RUNNING`/`WAITING` execution and reports how many in
    `cancelled_executions`. `resume` re-opens the workflow to new runs and does
    **not** restore the cancelled ones (`cancelled_executions` is always 0
    there). That asymmetry is the point of having both:
    `update(id, {"enabled": False})` stops new runs and leaves every in-flight
    contact walking the graph, `pause` stops the sends already in flight, and
    nothing puts them back.

- **`mailboxes.send_message` and `mailboxes.draft_message`.** The mailbox
  resource is no longer read-only.
  - `send_message` **really sends**, as that mailbox's own address, over its own
    domain, and the recipient can reply. There is no `from` field on purpose: a
    route that sends under a customer's identity must not take that identity as
    an argument. `body` is plain text and HTML is refused, so text becomes
    markup in exactly one place. Needs `mailboxes:send`.
  - `draft_message` asks Sendly's assistant to **write** text and hands it back.
    It stores nothing and sends nothing — the response reports `sent: False`,
    and no argument changes that — so it needs only `mailboxes:read`. A client
    that may draft is not thereby a client that may mail your customers.

- **Auto-pagination for every new cursor list.** The `iter_*` companions now
  number seventeen: the six from 0.2.0 plus `campaigns.iter_list_failures`,
  `contacts.iter_list_v1`, `deliverability.iter_list_dmarc_reports`,
  `deliverability.iter_list_domain_stats`, `domains.iter_list_v1`,
  `lists.iter_list_v1`, `suppression.iter_list_v1`, `templates.iter_list_v1`,
  `topics.iter_list`, `validation.iter_list_results` and
  `webhooks.iter_list_v1`.

### Fixed

- **README: `contacts.upsert` and `contacts.update` were documented with a
  `data` key.** The legacy contact body's custom-field map is `customFields`;
  `data` was silently ignored, so the example looked like it worked and stored
  nothing. (`lists.subscribe` really does take `data` — that one is unchanged.)
- **README: the `segments.create` example's `condition` was not a filter
  condition.** It showed `{"field": ..., "op": ..., "value": ...}`; the API
  takes `{"logic", "groups"}`, each group holding `filters` of
  `{"field", "operator", "value"}` with `operator` from a fixed vocabulary
  (`equals`, `contains`, …). Copying the old example produced a `422`.
- **README: the mailbox resource was described as read-only** in two places. It
  is not, since `send_message` and `draft_message`; what stays out of reach is
  the mailbox *lifecycle*, which is a different claim.

### Notes

- **Pagination is not uniform, and the exception is worth knowing.** Most v1
  lists take `after` and answer `next_cursor`. **`topics.list` and
  `validation.list_results` take `cursor` and answer `cursor`.** Both kinds are
  forward-only opaque cursors and both stop on `has_more: False`; only the
  parameter names differ. `topics.iter_list` and `validation.iter_list_results`
  hide it — they are written out by hand rather than routed through the shared
  cursor helper, which sends `after` and reads `next_cursor` and would otherwise
  re-fetch page one forever. A caller driving pages by hand needs to know which
  endpoint speaks which.
- **`NOT_SDK_CALLABLE` is unchanged.** Creating and deleting a mailbox, creating
  and revoking an app password, the four API-key operations, and creating a
  project still resolve the acting user from a session and answer `401` to any
  API key. The two new mailbox methods are the opposite case — they publish
  `ApiKeyAuth` outright.
- **Nothing added here takes an `idempotency_key`.** The set of writes that
  accept one is the same as in 1.0: `emails.send`, `emails.send_legacy`,
  `emails.batch`, `contacts.create`, `contacts.upsert`, `contacts.bulk_create`,
  `campaigns.create` and `campaigns.send`. `campaigns.retry_failed` is guarded
  instead by a `409 conflict` on a retry already running, which is a better fit:
  the thing to prevent is two concurrent walks, not a replayed request.

## [1.0.0] - 2026-09-02

The default send moves to the versioned API. Everything else in this release is
additive: the operations an API key can actually reach that the SDK did not yet
expose.

### Breaking

- **`emails.send()` now posts to `POST /api/v1/emails`** and returns the bare
  `202` receipt, `{id, status, to, from}`, where `status` is a real delivery
  state. Before 1.0 it posted to the legacy `POST /api/emails`, which answered
  with row ids and **no** delivery status, and fanned an array `to` out to
  several recipients. What changes for a caller:
  - one recipient in `to`, with `cc` / `bcc` to copy others (an array `to` is
    no longer accepted);
  - the result is the receipt, not `{emails, timestamp}` — read
    `receipt["id"]` and `receipt["status"]` instead of
    `result["emails"][0]["email"]`;
  - failures arrive as RFC 9457 problem documents, raised as the **same**
    exception classes, so `except` blocks are unchanged; `err.error_code` is now
    the lowercase v1 registry value (`validation_error`, not
    `VALIDATION_ERROR`) and `err.request_id` / `err.field_errors` are populated.

  The pre-1.0 behaviour is kept, unchanged, as **`emails.send_legacy()`** — the
  escape hatch for a caller that depends on the fan-out or the envelope.
  Renaming a call from `send` to `send_legacy` is a complete migration; adopting
  the new default means reading the receipt instead of the envelope.

  Why now: the legacy send cannot tell a caller whether a message went anywhere,
  and the versioned one can. Nothing is published against 0.x, so the cost of
  the move is lowest today and only rises.

### Added

- **`emails.send_legacy()`** — the pre-1.0 `send()`, byte for byte. See Breaking.
- **`emails.send_test()`** — sandbox test send. The sandbox address is the
  *sender*; the mail lands in the project owner's own verified inbox. Naming a
  `from` is refused rather than ignored. Takes no `idempotency_key`.
- **`mailboxes` resource, reads only** — `list()`, `get(id)` (which carries the
  IMAP/SMTP `settings` a mail client needs) and `list_app_passwords(id)`
  (metadata only; the secret is never returned). The mailbox *writes* are not
  missing but unreachable — see Notes.
- **`projects.get()`** — the project the credential resolves to. Takes no id.
  Carries `sandbox_address`, which no public route published before.
- **`domains.start_setup(id)`** — begins the guided DNS hand-off and returns the
  route's own `{token, connectUrl, expiresAt}`. Finishing setup means a person
  opening `connectUrl`, so the SDK hands back the link rather than modelling the
  flow behind it.

### Notes

- **`send_v1` and `send_test_v1` never shipped.** They existed briefly on `main`
  between 0.2.0 and this release as the additive step before the repoint, and
  are folded into `send` and `send_test` here. If you installed from GitHub in
  that window, rename the calls.
- **Some operations are permanently not SDK-callable.** Creating and deleting a
  mailbox, creating and revoking an app password, the API-key operations, and
  creating a project all resolve the acting user from a session and answer `401`
  to any API key. They are recorded in `tests/test_contract.py`'s
  `NOT_SDK_CALLABLE`, which the suite asserts equals the set the contract itself
  declares — in both directions. Use the dashboard or an OAuth connection.
- **A project is capped at 10 mailboxes**, counting only ``PROVISIONING``,
  ``ACTIVE`` and ``SUSPENDED``. ``FAILED`` rows are excluded from the cap but
  are still returned by ``mailboxes.list()``, so a project that has had failed
  provisions can list more than 10 — the ``list()`` docstring said "at most 10"
  without that distinction and now states it.

## [0.2.0]

Adds Sendly's `/api/v1` surface. Purely additive — every existing method keeps
its name, signature, and behaviour.

### Added

- **New resources for the `/api/v1` surface**, wired onto the same client:
  `sendly.campaigns`, `sendly.segments`, `sendly.workflows`, `sendly.analytics`
  and `sendly.usage`, covering all 33 v1 operations. Unlike the legacy `/api/*`
  resources, these return **bare resource bodies** — there is no
  `{success, data}` envelope to unwrap.
- **v1 methods on the existing `events` resource**: `events.record` (the v1
  counterpart of `events.track`, which is unchanged), `events.list`,
  `events.list_names` and `events.stats`. `record` takes no `idempotency_key`:
  events are append-only and the API deliberately does not ledger them.
- **Auto-pagination.** Each of the six cursor-paginated v1 listings gains an
  `iter_*` companion yielding individual items and following the cursor for you:
  `campaigns.iter_list`, `segments.iter_list`, `segments.iter_list_contacts`,
  `workflows.iter_list`, `workflows.iter_list_executions`, `events.iter_list`.
  The v1 list envelope is `{data, has_more, next_cursor}` with `limit` (1-100,
  default 20) and `after` — no total, deliberately. Changing filters
  mid-pagination invalidates the cursor and returns `422 validation_error`, so
  the iterators hold the query fixed and only advance `after`.
- **RFC 9457 error support.** `application/problem+json` responses from `/api/v1`
  map to the **same** exception classes as the legacy envelope, keyed off the
  same statuses — existing `except` blocks are unaffected. The problem's `code`
  becomes `err.error_code` (e.g. `scope_missing`, `quota_exhausted`,
  `idempotency_key_reused`) and its `detail` (falling back to `title`) becomes
  `err.message`. Two fields are new on `SendlyError`:
  - `err.request_id` — correlation id from the problem document, `None` on the
    legacy surface;
  - `err.field_errors` — per-field `{pointer, code, message}` entries from a v1
    `validation_error`, `None` when absent. The legacy per-field breakdown stays
    at `err.body["error"]["details"]["errors"]`.
- **`sendly.lists`** — `lists.subscribe(id, body)` and
  `lists.unsubscribe(id, body)` wrap the newly published
  `POST /api/lists/{id}/subscribe` and `.../unsubscribe` operations. Both accept
  sending-only (`pk_*`) keys so they can back a public form. On a double opt-in
  list, subscribe returns `PENDING` with a `confirmToken` and Sendly does **not**
  send the confirmation email — the caller delivers it. Re-subscribing an address
  that opted out needs `allowResubscribe: true` or fails with
  `409 RESUBSCRIBE_CONFIRMATION_REQUIRED`.

### Changed

- Re-synced the vendored OpenAPI spec (`tests/fixtures/openapi.json`) to the
  committed monorepo contract. The client stays thin (opaque `Mapping` bodies),
  so these are contract/behaviour clarifications rather than method-signature
  changes:
  - **Deletes now return HTTP `200` with the deleted resource's id** (was `204`
    No Content) for `contacts.delete` and `templates.delete`. The SDK still
    discards the body and returns `None` — no consumer change.
  - **Invalid input now raises `SendlyValidationError` from HTTP `422`**
    (`error_code == "VALIDATION_ERROR"`) with a per-field breakdown at
    `err.body["error"]["details"]["errors"]`. Previously invalid input came back
    as `400`. Both `400` and `422` map to `SendlyValidationError`, so
    `except SendlyValidationError` continues to catch validation failures.
  - **Contacts bulk ops (`bulk_create`, `bulk_delete`) against an unresolved
    project now return `422 VALIDATION_ERROR`** (was a `NO_PROJECT` error).
  - **`templates.list` is cursor-paginated** (`limit` / `cursor`) — the former
    `page` / `pageSize` query params are gone. `contacts.list` was already
    cursor-based and is unchanged.
  - Error envelopes on migrated routes now include `success: false` alongside
    `error.{message,code}`; error parsing reads `message`/`code` and is
    unaffected by the additive fields.
