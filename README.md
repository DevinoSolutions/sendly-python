# Sendly Python SDK

Official Python SDK for the [Sendly](https://sendly.now) REST API — transactional
email, contacts, events, domains, templates, email verification, webhooks,
suppression, and mailbox and project reads.

[![CI](https://github.com/DevinoSolutions/sendly-python/actions/workflows/ci.yml/badge.svg)](https://github.com/DevinoSolutions/sendly-python/actions/workflows/ci.yml)

- Full type hints (ships `py.typed`), `mypy --strict` clean.
- One small runtime dependency: [`httpx`](https://www.python-httpx.org/).
- Fail-loud by design: no silent fallbacks, no degraded mode.

## Installation

```bash
pip install sendly-python
```

The distribution is published as `sendly-python`; the import name is unchanged:

```python
import sendly
```

Alternatively, install the latest `main` directly from GitHub:

```bash
pip install git+https://github.com/DevinoSolutions/sendly-python.git
```

Requires Python 3.10+.

## Already on Resend, SendGrid, Postmark, Mailgun, or Plunk?

You don't even need this SDK to try Sendly. The API also speaks the
transactional-send dialect of those providers — keep the vendor SDK you already
run and change **two things**: the base URL and the API key.

```python
import resend  # your existing Resend integration

resend.api_key = "sk_your_sendly_key"
resend.api_url = "https://api.sendly.now/api/compat/resend"
# resend.Emails.send(...) now sends through Sendly — same code, same shapes.
```

Every compat request runs through the same pipeline as the native API (domain
verification, suppression, limits), and anything a dialect can express that
Sendly doesn't support returns a clean error in that vendor's own error shape.
Per-provider guides: [docs.sendly.now/migrate](https://docs.sendly.now/migrate).

## Quickstart

The client reads your API key from the `SENDLY_API_KEY` environment variable:

```python
from sendly import Sendly

sendly = Sendly()  # reads SENDLY_API_KEY

receipt = sendly.emails.send(
    {
        "from": "hello@yourdomain.com",
        "to": "customer@example.com",
        "subject": "Welcome aboard",
        "body": "<h1>Thanks for signing up!</h1>",
    }
)

# `status` is a real delivery state; poll `emails.get(receipt["id"])` for the
# events behind it.
print(receipt["id"], receipt["status"])
```

### Upgrading from 0.x

**1.0 repoints `emails.send` to the versioned `POST /api/v1/emails`.** It now
takes one recipient (`cc`/`bcc` copy others) and returns the `202` receipt
`{id, status, to, from}`, where `status` is a real delivery state. Before 1.0 it
posted to the legacy `POST /api/emails`, fanned an array `to` out to several
recipients, and returned `{emails, timestamp}` with no delivery status.

The old behaviour is kept, unchanged, as `emails.send_legacy`. Two ways to
upgrade:

- **Keep the old shapes:** rename the call. `send(...)` → `send_legacy(...)`.
  Done.
- **Take the new default:** read the receipt instead of the envelope
  (`receipt["id"]` / `receipt["status"]` in place of
  `result["emails"][0]["email"]`), send to one recipient per call, and note that
  failures now carry the v1 error fields (`err.error_code` is lowercase,
  `err.request_id` and `err.field_errors` are set) — the exception classes are
  the same, so `except` blocks stand.

Nothing else changed shape. See [CHANGELOG.md](./CHANGELOG.md) for the full
1.0.0 entry.

Or pass the key explicitly:

```python
sendly = Sendly(api_key="sk_live_...")
```

If neither an explicit key nor `SENDLY_API_KEY` is set, the constructor raises a
`SendlyError` immediately.

### Options

```python
sendly = Sendly(
    api_key="sk_live_...",
    base_url="https://api.sendly.now",  # override for staging/self-hosted
    timeout=30.0,                        # per-request seconds; 0 or None disables
    default_headers={"X-Trace-Id": "..."},
)
```

The client holds an internal connection pool. Reuse a single instance, and close
it when done (or use it as a context manager):

```python
with Sendly() as sendly:
    sendly.emails.send({...})
```

## Usage by resource

### Emails

```python
# Single send on /api/v1 (pass idempotency_key to dedupe replays for 24h).
# One recipient in `to`; `cc` / `bcc` copy others. Returns {id, status, to, from}.
receipt = sendly.emails.send({"from": "a@you.com", "to": "b@them.com", "subject": "Hi", "body": "<p>Hi</p>"},
                             idempotency_key="order-42-receipt")

# The pre-1.0 send: legacy /api/emails, an array `to` fans out, answers
# {emails, timestamp} with no delivery status.
sendly.emails.send_legacy({"from": "a@you.com", "to": ["b@them.com", "c@them.com"],
                           "subject": "Hi", "body": "<p>Hi</p>"})

# Batch send (up to 100)
sendly.emails.batch({"emails": [{"from": "a@you.com", "to": "b@them.com", "subject": "Hi", "body": "<p>Hi</p>"}]})

# List, get, cancel a scheduled send
sendly.emails.list({"limit": 20, "status": "DELIVERED"})
sendly.emails.get("em_123")
sendly.emails.cancel_schedule("em_123")
```

### Contacts

```python
sendly.contacts.create({"email": "user@example.com", "subscribed": True})
sendly.contacts.upsert({"email": "user@example.com", "data": {"plan": "pro"}})
sendly.contacts.list({"limit": 50, "search": "example.com"})
sendly.contacts.get("c_123")
sendly.contacts.update("c_123", {"data": {"plan": "enterprise"}})
sendly.contacts.delete("c_123")
sendly.contacts.bulk_create({"contacts": [{"email": "a@x.com"}, {"email": "b@x.com"}]})
sendly.contacts.bulk_delete({"emails": ["a@x.com"]})
```

### Events

```python
# Track a custom event for a contact (accepts sk_* and pk_* keys)
result = sendly.events.track({"event": "signup", "email": "user@example.com"})
print(result["contact"], result["timestamp"])

# Attach an arbitrary payload and set subscription state
sendly.events.track({"event": "purchase", "email": "user@example.com",
                     "subscribed": True, "data": {"plan": "pro", "amount": 42}})
```

### Domains

```python
sendly.domains.create({"domain": "mail.yourdomain.com", "region": "us-east-1"})
sendly.domains.list()
sendly.domains.get("d_123")
sendly.domains.verify("d_123")
sendly.domains.get_verification("d_123")
sendly.domains.start_setup("d_123")  # -> {"token", "connectUrl", "expiresAt"}
sendly.domains.delete("d_123")
```

`start_setup` returns the hand-off as the API returns it. Open `connectUrl` in a
browser to finish DNS setup at the registrar.

### Mailboxes

Reads only — see [What the SDK does not expose](#what-the-sdk-does-not-expose).

```python
sendly.mailboxes.list()          # -> [mailbox, ...], not paginated
detail = sendly.mailboxes.get("mb_123")

# `settings` carries the IMAP and SMTP host, port, security and username.
print(detail["settings"]["imap"]["host"], detail["settings"]["imap"]["port"])

# Metadata only — `lastFour` is the one fragment of the secret that survives
# creation, so a credential can be identified but not rebuilt.
for pw in sendly.mailboxes.list_app_passwords("mb_123"):
    print(pw["name"], pw["lastFour"], pw["lastUsedAt"])
```

This lists the mailboxes themselves, never their contents — received messages
are not part of the public API. The mailbox **password** is never returned by
any of these reads; mailbox credentials are app passwords, created from the
dashboard and shown once. `list_app_passwords` returns only the passwords that
are still active — a revoked one drops out, so this is not an audit history.

**The per-project cap is 10 mailboxes.** It counts only those holding, or
mid-way to holding, a real account — `PROVISIONING`, `ACTIVE` and `SUSPENDED`.
`FAILED` rows are excluded on purpose, so that a burst of failed provisions
cannot eat a project's allowance and turn an outage into "you have reached your
mailbox limit"; they are still returned by `list()`, so a project that has had
failures can list more than 10. Exceeding the cap is a `409`
(`SendlyConflictError`) from whatever creates the mailbox — which is not this
SDK, since mailbox creation needs a signed-in user.

### Templates

```python
sendly.templates.create({"name": "Welcome", "subject": "Welcome", "body": "<p>Hi</p>",
                         "from": "a@you.com", "type": "MARKETING"})
sendly.templates.list({"limit": 25})  # cursor pagination: pass {"cursor": ...} for the next page
sendly.templates.get("t_123")
sendly.templates.update("t_123", {"name": "Welcome v2"})
sendly.templates.delete("t_123")
```

### Verify

```python
# Validate an email address (syntax, MX, disposable domains, plus-addressing).
# Open endpoint — the SDK still sends your API key, which the API ignores.
result = sendly.verify.email({"email": "user@example.com"})
if not result["valid"]:
    print("Rejected:", result.get("reason"))
```

### Webhooks

```python
created = sendly.webhooks.create({"url": "https://you.com/hook", "eventTypes": ["email.delivered"]})
# Store the signing secret now — it is only returned in full at creation/rotation.
sendly.webhooks.list()
sendly.webhooks.get("w_123")
sendly.webhooks.update("w_123", {"status": "PAUSED"})
sendly.webhooks.rotate_secret("w_123")
sendly.webhooks.list_calls("w_123", {"limit": 20})
sendly.webhooks.delete("w_123")
```

### Suppression

```python
sendly.suppression.add({"email": "bounce@example.com", "reason": "MANUAL"})
sendly.suppression.list({"reason": "MANUAL", "limit": 100})
sendly.suppression.get("bounce@example.com")
sendly.suppression.remove("bounce@example.com")
```

### Lists

```python
# Both calls accept sending-only (pk_*) keys, so they can back a public form.
result = sendly.lists.subscribe("l_123", {"email": "user@example.com"})

# On a double opt-in list the membership is PENDING and carries a confirmToken.
# Sendly does NOT send the confirmation email — deliver this link yourself.
if result["status"] == "PENDING":
    confirm_url = f"https://api.sendly.now/api/lists/confirm?token={result['confirmToken']}"

# Re-subscribing an address that opted out needs an explicit opt-in, or the call
# fails with 409 RESUBSCRIBE_CONFIRMATION_REQUIRED.
sendly.lists.subscribe("l_123", {"email": "user@example.com", "allowResubscribe": True})

sendly.lists.unsubscribe("l_123", {"email": "user@example.com"})
```

## The v1 API

`campaigns`, `segments`, `workflows`, `analytics` and `usage` — plus the v1
methods on `events` — speak Sendly's `/api/v1` surface. Same client, same API
key; two differences worth knowing:

- **Responses are bare resource bodies.** There is no `{success, data}` envelope
  to unwrap, so what the API documents is exactly what you get.
- **Errors are RFC 9457 problem documents.** They raise the same exception
  classes as the legacy surface, with two extra fields — see
  [Error handling](#error-handling).

### Campaigns

```python
campaign = sendly.campaigns.create(
    {
        "name": "August launch",
        "subject": "We are live",
        "body": "<p>Hello</p>",
        "from": "team@you.com",
        "audience_type": "ALL",
    },
    idempotency_key="august-launch",
)

# Send now, or schedule it. Key the replay — a duplicate send mails the audience twice.
sendly.campaigns.send(campaign["id"], idempotency_key="august-launch-send")
sendly.campaigns.send(campaign["id"], {"scheduled_for": "2026-09-01T10:00:00Z"})

sendly.campaigns.pause(campaign["id"])
sendly.campaigns.resume(campaign["id"])
sendly.campaigns.cancel(campaign["id"])

stats = sendly.campaigns.stats(campaign["id"])
print(stats["delivered"], stats["open_rate"])
```

### Pagination

Every v1 list answers `{data, has_more, next_cursor}` — an opaque forward-only
cursor, and no total. Page it yourself with `limit` (1–100, default 20) and
`after`:

```python
page = sendly.campaigns.list({"limit": 50})
while page["has_more"]:
    page = sendly.campaigns.list({"limit": 50, "after": page["next_cursor"]})
```

…or let the `iter_*` companion do it. It yields individual items and follows the
cursor until the last page:

```python
for campaign in sendly.campaigns.iter_list({"limit": 100}):
    print(campaign["name"], campaign["status"])

for contact in sendly.segments.iter_list_contacts("seg_123"):
    print(contact["email"])
```

Keep your filters identical for every page of one walk. Changing them
mid-pagination invalidates the cursor and the API answers `422 validation_error`
telling you to restart from the first page — which is exactly why `iter_*` holds
the query fixed and only advances `after`.

Available on the six cursor-paginated listings: `campaigns.iter_list`,
`segments.iter_list`, `segments.iter_list_contacts`, `workflows.iter_list`,
`workflows.iter_list_executions`, `events.iter_list`. The analytics endpoints and
`events.list_names` / `events.stats` return a bounded aggregate rather than a
cursor, so they have no iterator.

### Segments, workflows, events, analytics, usage, projects

```python
segment = sendly.segments.create({"name": "Power users", "type": "DYNAMIC",
                                  "condition": {"field": "plan", "op": "eq", "value": "pro"}})
sendly.segments.list_contacts(segment["id"], {"limit": 50})

workflow = sendly.workflows.create({"name": "Welcome", "event_name": "signup.completed"})
sendly.workflows.start_execution(workflow["id"], {"contact_id": "c_123"})
# Executions are cancelled by execution id alone — not nested under the workflow.
sendly.workflows.cancel_execution("exe_123")
sendly.workflows.stats(workflow["id"], {"from": "2026-08-01"})

# events.record is the v1 counterpart of the legacy events.track. Same effect,
# v1 dialect. It takes no idempotency_key: events are append-only and the API
# deliberately does not ledger them.
sendly.events.record({"name": "signup.completed", "contact_id": "c_123", "data": {"plan": "pro"}})
sendly.events.list({"event_name": "signup.completed", "limit": 20})
sendly.events.list_names()
sendly.events.stats({"from": "2026-08-01", "to": "2026-08-31"})

sendly.analytics.timeseries({"from": "2026-08-01", "to": "2026-08-31"})
sendly.analytics.campaigns()
sendly.analytics.top_campaigns({"limit": 5})

usage = sendly.usage.get()
print(usage["plan"], usage["monthly"])

project = sendly.projects.get()
print(project["sandbox_address"])
```

### Emails: `send` vs `send_legacy`

The same split as `events.track` / `events.record`, resolved the other way
round: since 1.0, `emails.send` IS the versioned send. It posts to
`/api/v1/emails` and answers `202` with `{id, status, to, from}`, where `status`
is a real delivery state you can poll on. It takes one recipient — use
`cc`/`bcc` to copy others — instead of fanning an array out.
`emails.send_legacy` is the pre-1.0 send on `POST /api/emails`, unchanged: row
ids, **no delivery status**, array `to` fanned out. See
[Upgrading from 0.x](#upgrading-from-0x).

```python
receipt = sendly.emails.send(
    {"to": "user@example.com", "subject": "hi", "body": "<p>hi</p>"},
    idempotency_key="order-42",
)
print(receipt["status"])
```

### Test sends

`emails.send_test` proves the send path works without touching a live
recipient. Two things about it are easy to get backwards:

- **The sandbox address is the *sender*, not the destination.** It is resolved
  server-side, and naming a `from` yourself is **refused** rather than ignored —
  so a request expecting a different sender never gets a success it would
  misread. `projects.get()["sandbox_address"]` tells you what it sends *from*;
  the response's `from` says the same thing.
- **It lands in the project owner's own inbox.** `to` is optional and defaults
  to the project owner's verified account email, which is the only address a
  sandbox send may reach — any other value is refused.

```python
test = sendly.emails.send_test({"subject": "hi", "body": "<p>hi</p>"})
print(test["to"], test["from"], test["sandbox"])  # sandbox is always True here
```

Everything else applies unchanged: the same rendering, the same content scan,
and the same daily and trust-tier caps as a real send. It takes no
`idempotency_key` — the recipient is the caller's own inbox, a daily cap already
bounds it, and "send me another one" is the normal second call rather than a
mistake worth deduplicating.

### What the SDK does not expose

An API key resolves no user, and a handful of routes resolve the acting project
admin from the session before reading any scope — so they answer `401` to any
key, however broad its scopes. The contract states this: those operations publish
`SessionAuth` without `ApiKeyAuth`.

Rather than ship methods that could never succeed, they are listed in
`tests/test_contract.py`'s `NOT_SDK_CALLABLE` and checked against the spec's own
declarations, in both directions. They are: creating and deleting a mailbox,
creating and revoking an app password, all four API-key operations, and creating
a project. Use the dashboard or an OAuth connection for those.

Mailbox **reads** are exposed — their membership check is conditional, so a key
really can call them.

## Error handling

Every non-2xx response raises a `SendlyError` subclass carrying `status_code`,
`error_code`, `message`, and the raw `body`:

```python
from sendly import Sendly, SendlyValidationError, SendlyRateLimitError, SendlyError

sendly = Sendly()
try:
    sendly.emails.send({"from": "a@you.com", "to": "b@them.com", "subject": "Hi", "body": "<p>Hi</p>"})
except SendlyValidationError as err:
    print("Bad request:", err.error_code, err.message)
except SendlyRateLimitError:
    print("Slow down and retry with backoff")
except SendlyError as err:
    print("Sendly error", err.status_code, err.message)
```

| Exception | HTTP status |
| --- | --- |
| `SendlyValidationError` | 400, 422 |
| `SendlyAuthenticationError` | 401 |
| `SendlyPermissionError` | 403 |
| `SendlyNotFoundError` | 404 |
| `SendlyConflictError` | 409 |
| `SendlyRateLimitError` | 429 |
| `SendlyServerError` | 5xx |
| `SendlyConnectionError` | transport failure (status `0`) |

All inherit from `SendlyError`.

Invalid input raises `SendlyValidationError`. Migrated routes report it as HTTP
`422` with `error_code == "VALIDATION_ERROR"` and a per-field breakdown under
`err.body["error"]["details"]["errors"]`; legacy/malformed requests still use
`400`. Both surface as `SendlyValidationError`.

### v1 errors (RFC 9457)

The `/api/v1` surface reports failures as `application/problem+json` documents.
They raise the **same** exception classes, keyed off the same statuses, so
existing `except` blocks keep working. Three things move:

- `error_code` comes from the problem's `code` — a lowercase, machine-readable
  value like `scope_missing`, `quota_exhausted`, or `idempotency_key_reused`.
- `err.request_id` carries the correlation id. Quote it in support requests.
- `err.field_errors` carries the per-field breakdown on a `validation_error`,
  each entry `{pointer, code, message}` with an RFC 6901 JSON Pointer.

```python
from sendly import Sendly, SendlyValidationError, SendlyRateLimitError

sendly = Sendly()
try:
    sendly.campaigns.create({"name": "Launch"})
except SendlyValidationError as err:
    print(err.error_code, err.message, err.request_id)
    for field in err.field_errors or []:
        print(f"  {field['pointer']}: {field['message']}")
except SendlyRateLimitError as err:
    # Two different failures share this class — check the code before retrying.
    if err.error_code == "quota_exhausted":
        print("Plan limit reached; backing off will not help")
    else:
        print("Too fast — retry with backoff")
```

The full problem document stays on `err.body`, so `type`, `title` and `instance`
remain reachable. On the legacy surface `request_id` and `field_errors` are
`None`.

## Verifying webhooks

Every delivery is signed. Verify it against the **raw** request body — do not
parse the JSON first. Two headers are sent:

- `X-Sendly-Signature` — bare lowercase hex HMAC-SHA256 of `"{timestamp}.{body}"`
  (no `sha256=` prefix).
- `X-Sendly-Timestamp` — the signing time as a **millisecond** Unix epoch.

`verify_signature` also enforces replay protection: a delivery whose timestamp is
more than `DEFAULT_TOLERANCE_MS` (5 minutes) from now is rejected. Pass
`tolerance_ms=math.inf` to disable that check.

```python
import os
from flask import Flask, request
from sendly import construct_event

app = Flask(__name__)

@app.post("/webhook")
def webhook():
    payload = request.get_data()  # raw bytes
    signature = request.headers.get("X-Sendly-Signature", "")
    timestamp = request.headers.get("X-Sendly-Timestamp", "")
    secret = os.environ["SENDLY_WEBHOOK_SECRET"]
    try:
        event = construct_event(payload, signature, timestamp, secret)
    except ValueError:
        return "Invalid signature", 400
    # handle event["event"], event["data"], ...
    return "", 200
```

`verify_signature(payload, signature, timestamp, secret, *, tolerance_ms=...) -> bool`
is also exported if you only need the boolean check. Both use a constant-time
comparison and reject a stale or non-numeric timestamp.

## Async

Only a synchronous client ships today. An `httpx.AsyncClient`-backed async
variant is planned.

## Development

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

ruff check .
ruff format --check .
mypy src
pytest
```

Tests are fully hermetic (httpx `MockTransport`) and hit no network.

### Refreshing the vendored OpenAPI spec

`tests/fixtures/openapi.json` is a committed snapshot of Sendly's OpenAPI
contract; the contract suite (`tests/test_contract.py`) verifies the SDK surface
against it and never touches the network.

`scripts/sync_spec.py` requires `SENDLY_OPENAPI_URL`. There is **no default**,
and in particular it does not default to production:

```bash
SENDLY_OPENAPI_URL=/path/to/sendly/apps/web/openapi/openapi.json \
    python scripts/sync_spec.py

SENDLY_OPENAPI_URL=... python scripts/sync_spec.py --check   # is the copy stale?
```

`SENDLY_OPENAPI_URL` accepts a filesystem path (the normal case — the committed
contract in the Sendly platform monorepo at `apps/web/openapi/openapi.json`) or
an `http(s)://` URL of a local or staging API. Running the script with it unset
exits non-zero and prints what to set.

**Do not point it at `https://api.sendly.now`.** Vendoring the spec from the
deployed API makes the SDK mirror what is *running* rather than what the repo
*declares*, so any drift between the platform's code and its committed contract
is laundered into "correct" on the way in — the SDK re-vendors to match the
deployment and the mismatch vanishes silently. That destroys the vendored spec's
only job: it is the fixed reference `tests/test_contract.py` compares against, so
an SDK synced from production can no longer detect the very drift it exists to
catch. It is also unreproducible and unreviewable.

This is not hard-blocked — "what does production actually serve?" is a legitimate
one-off. Doing it prints an unmissable warning (and a CI annotation), because
*quiet* is what made the old default dangerous, not the host. Never commit the
result, and never wire that host into CI or any unattended job.

`--check` is the exception to the fail-loud rule: it never runs unattended
against an unknown source, so with `SENDLY_OPENAPI_URL` unset it skips with a
notice and exits 0, keeping CI and fork pull requests green.

## Documentation

Full API reference: <https://docs.sendly.now>

## License

MIT — see [LICENSE](LICENSE).
