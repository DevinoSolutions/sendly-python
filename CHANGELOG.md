# Changelog

All notable changes to `sendly-python` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Covers the operations an API key can actually reach that the SDK did not yet
expose. Purely additive — every existing method keeps its name, signature and
behaviour.

### Added

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
- **`emails.send_v1()`** — the versioned send. Answers `202` with
  `{id, status, to, from}`, so a caller can learn whether the message went
  anywhere. Takes one recipient (`cc`/`bcc` copy others) and an optional
  `idempotency_key`.
- **`emails.send_test_v1()`** — sandbox test send. The sandbox address is the
  *sender*; the mail lands in the project owner's own verified inbox. Naming a
  `from` is refused rather than ignored. Takes no `idempotency_key`.

### Notes

- **`emails.send` is unchanged** and still posts to the legacy `POST /api/emails`,
  which reports no delivery status. `send_v1` is added *beside* it, not in place
  of it: the two return different things, so repointing the default would break
  existing callers. Which becomes the default is a deliberate decision that has
  not been taken. A test pins `send()` to the legacy path.
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
