# Sendly Python SDK

Official Python SDK for the [Sendly](https://sendly.now) REST API —
transactional email, contacts, lists, topics, events, domains, templates,
snippets, email verification, address validation, deliverability reporting,
webhooks, suppression, and mailbox reads plus the two composition calls an API
key may drive.

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

### Upgrading from 1.0

1.1 is mostly additive — four new resources and the `/api/v1` half of six more —
but it also tracks a set of **wire-visible renames** that landed in the
platform, so it is a breaking release. Do not deploy 1.1 against an API that has
not taken the renamed wire yet: sending `type` where the API now expects
`emailCategory` is a `422`, not a shrug.

What to change, in the order a codebase usually hits it:

- **`type` → `emailCategory` (legacy) / `email_category` (v1)** on templates and
  campaigns. Affects `templates.create`, `templates.update`, the
  `emailCategory` filter on `templates.list`, and `campaigns.create`. The enum
  member `HEADLESS` is now `SELF_MANAGED_UNSUBSCRIBE`; `MARKETING` and
  `TRANSACTIONAL` are unchanged.
- **`data` → `payload`** in the body of `events.record` (the v1 write). The
  legacy `events.track` is untouched and still takes `data` — the two endpoints
  were renamed on different schedules, and this SDK reports what each one
  actually accepts rather than papering over the difference.
- **`mailFromStatus` → `mailFromDomainStatus`** on a domain, and
  `mail_from_domain_status` on the v1 document.
- **`emails.get` returns a different body** — see below.
- **The double-opt-in confirmation route moved** from `/api/lists/confirm` to
  `/api/lists/confirm-subscription`. Sendly has never sent that email for you,
  so if you build the URL yourself — and `lists.subscribe` is documented on the
  assumption that you do — change the path.

#### `emails.get`, specifically

It used to hand back the whole database row together with an `events` array that
was the **wrong relation**: the custom analytics events a caller records with
`events.record`, not the delivery history the operation has always promised.

It now returns an explicit field list plus `events` as the delivery timeline
(oldest first), and it fills `to` from the joined contact — which the spec had
always declared and the response had never carried.

Keys that used to leak out of it and no longer do: `bodyHash`, `dedupKey`,
`idempotencyKey`, `linkMap`, `sesMessageId`, `sesInboundMessageId`, `body` and
`headers`. Four of those are ledger keys for deduplication and idempotency; the
rest are internal routing state or the rendered message itself. None of them was
ever documented, and a caller reading them was reading Sendly's bookkeeping.

If you were reading `events` from this call expecting custom events, read
`events.list` instead. If you were reading the message body back out of it, keep
your own copy — it is not published here.

#### Engagement left the delivery status

`OPENED`, `CLICKED` and `COMPLAINED` are no longer delivery states, so they no
longer appear in `email["status"]` and are no longer accepted by the `status`
filter on `emails.list`. A message is `PENDING`, `SENDING`, `SENT`,
`DELIVERED`, `RECEIVED`, `BOUNCED`, `FAILED`, `REJECTED`, `RENDERING_FAILURE`,
`DELIVERY_DELAY` or `CANCELLED`. Engagement is a separate axis:

```python
email = sendly.emails.get(email_id)["data"]
delivered = email["status"] == "DELIVERED"           # a delivery fact
engaged = email["openedAt"] is not None or email["clicks"] > 0  # an engagement fact
```

The two used to be one enum, which meant an opened message stopped reporting
that it had been delivered.

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

## The resources

Every resource hangs off the client. A `_v1` suffix means the method speaks the
versioned dialect; the unsuffixed method of the same name on the same resource
speaks the legacy one — see [Both dialects, one client](#both-dialects-one-client).

| `sendly.*` | Methods |
| --- | --- |
| `emails` | `send`, `send_legacy`, `send_test`, `batch`, `list`, `get`, `cancel_schedule` |
| `contacts` | `create`, `upsert`, `bulk_create`, `bulk_delete`, `list`, `get`, `update`, `delete`, `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`, `delete_v1`, `topic_preferences` |
| `lists` | `subscribe`, `unsubscribe`, `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`, `delete_v1`, `start_validation_run` |
| `topics` | `list`, `iter_list`, `create`, `get`, `update`, `set_subscription` |
| `templates` | `create`, `list`, `get`, `update`, `delete`, `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`, `delete_v1` |
| `snippets` | `create`, `list`, `get`, `update`, `delete` |
| `domains` | `create`, `list`, `get`, `verify`, `get_verification`, `start_setup`, `assign_stream`, `delete`, `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `verify_v1`, `delete_v1` |
| `webhooks` | `create`, `list`, `get`, `update`, `delete`, `rotate_secret`, `list_calls`, `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `update_v1`, `delete_v1`, `rotate_secret_v1` |
| `suppression` | `add`, `list`, `get`, `remove`, `list_v1`, `iter_list_v1`, `create_v1`, `get_v1`, `delete_v1` |
| `events` | `track`, `record`, `list`, `iter_list`, `list_names`, `stats` |
| `campaigns` | `list`, `iter_list`, `create`, `get`, `update`, `delete`, `send`, `cancel`, `pause`, `resume`, `stats`, `list_failures`, `iter_list_failures`, `retry_failed` |
| `segments` | `list`, `iter_list`, `create`, `get`, `update`, `delete`, `list_contacts`, `iter_list_contacts` |
| `workflows` | `list`, `iter_list`, `create`, `get`, `update`, `delete`, `list_executions`, `iter_list_executions`, `start_execution`, `cancel_execution`, `stats`, `get_graph`, `replace_graph`, `clone`, `pause`, `resume` |
| `mailboxes` | `list`, `get`, `list_app_passwords`, `send_message`, `draft_message` |
| `validation` | `validate_emails`, `get_run`, `list_results`, `iter_list_results` |
| `deliverability` | `diagnose`, `list_domain_stats`, `iter_list_domain_stats`, `list_dmarc_reports`, `iter_list_dmarc_reports` |
| `analytics` | `timeseries`, `campaigns`, `top_campaigns` |
| `usage` | `get` |
| `projects` | `get` |
| `verify` | `email` |

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
page = sendly.emails.list({"limit": 20, "status": "DELIVERED"})
for email in page["data"]:
    print(email["id"], email["to"], email["status"])

sendly.emails.cancel_schedule("em_123")
```

`emails.get` returns the email together with its **delivery** history, oldest
first — not the custom events you record with `events.record`, which are read
from `events.list`:

```python
email = sendly.emails.get("em_123")["data"]

print(email["to"], email["status"], email["opens"], email["clicks"])
for event in email["events"]:
    print(event["timestamp"], event["status"])
```

`status` filters and reports the delivery lifecycle only. To find the messages
somebody opened, read `openedAt` / `opens` on the rows — engagement is not a
status.

### Contacts

```python
sendly.contacts.create({"email": "user@example.com", "subscribed": True})
sendly.contacts.upsert({"email": "user@example.com", "customFields": {"plan": "pro"}})
sendly.contacts.list({"limit": 50, "search": "example.com"})
sendly.contacts.get("c_123")
sendly.contacts.update("c_123", {"customFields": {"plan": "enterprise"}})
sendly.contacts.delete("c_123")
sendly.contacts.bulk_create({"contacts": [{"email": "a@x.com"}, {"email": "b@x.com"}]})
sendly.contacts.bulk_delete({"emails": ["a@x.com"]})
```

The `_v1` half manages the same contacts with snake_case bodies, cursor
pagination and RFC 9457 errors:

```python
sendly.contacts.create_v1({"email": "user@example.com", "custom_fields": {"plan": "pro"}})
sendly.contacts.get_v1("c_123")
sendly.contacts.update_v1("c_123", {"custom_fields": {"plan": "enterprise"}})
sendly.contacts.delete_v1("c_123")

# `subscribed` is the string "true" / "false" here, not a bool — it is a query
# parameter with three states, and omitting it means "both".
for contact in sendly.contacts.iter_list_v1({"subscribed": "true"}):
    print(contact["email"], contact["custom_fields"])
```

Two things about `update_v1` catch people out: `email` is not patchable at all
(an address is the contact's identity, and rewriting it in place would change
who every earlier send was addressed to), and `custom_fields` is **replaced, not
merged** — send back every key you mean to keep.

`topic_preferences` reads everything one contact has said they want:

```python
prefs = sendly.contacts.topic_preferences("c_123")

# prefs["subscribed"] is the global marketing opt-out and OUTRANKS every topic:
# False means no marketing reaches them whatever the rows below say.
for topic in prefs["topics"]:
    print(topic["key"], topic["subscribed"], topic["pending"])
```

Each topic's `subscribed` is the effective answer the send path reaches today,
with the topic's `default_opt_in` already folded in, so a contact who has never
answered still reads correctly.

### Topics

The consent vocabulary a project mails against. A contact subscribes to a topic
rather than to a campaign, so switching one off silences a whole audience.

```python
topic = sendly.topics.create({
    "key": "product-updates",   # stable; survives a rename of `name`, not patchable
    "name": "Product updates",
    "default_opt_in": True,
})

result = sendly.topics.set_subscription(topic["id"], {"contact_id": "c_123", "subscribed": True})
```

**Subscribing somebody through the API does not bypass confirmation.**
`"subscribed": True` parks the contact at `pending` and returns a
`confirmation_url`; nothing is mailed on this topic until someone opens that
link, and there is no parameter to skip it — a subscription a caller asserts is
not evidence the mailbox holder agreed. Sendly does not send that email; **your
application** delivers `result["confirmation_url"]`, from your own verified
domain. `"subscribed": False` records the opt-out immediately.

```python
if result["status"] == "pending":
    send_your_own_confirmation_email(result["confirmation_url"])
```

`default_opt_in` decides what silence means for a contact who never answers:
True for a topic introduced over a list that already consented to hear from you,
False for anything a person has to ask for.

There is no `topics.delete`. A topic is where people's answers are recorded, so
deleting it would delete the choices they made; archiving is the retire button
and keeps them:

```python
sendly.topics.update(topic["id"], {"archived": True})
for t in sendly.topics.iter_list({"include_archived": True}):
    print(t["key"], t["archived"], t["subscribed_count"])
```

### Events

```python
# Legacy /api/track — payload goes in `data`. Accepts sk_* and pk_* keys.
result = sendly.events.track({"event": "signup", "email": "user@example.com"})
print(result["contact"], result["timestamp"])

sendly.events.track({"event": "purchase", "email": "user@example.com",
                     "subscribed": True, "data": {"plan": "pro", "amount": 42}})

# The v1 counterpart — payload goes in `payload`, and `contact_id` must already
# exist: unlike the legacy endpoint, this one never creates contacts.
sendly.events.record({"name": "purchase", "contact_id": "c_123",
                      "payload": {"plan": "pro", "amount": 42}})
```

New integrations should prefer `record`, which also unlocks `events.list`,
`events.list_names` and `events.stats`.

### Domains

```python
domain = sendly.domains.create({"domain": "mail.yourdomain.com", "region": "us-east-1"})
# Publish each token as a CNAME record before verification can succeed.
print(domain["dkimTokens"])

sendly.domains.list()
sendly.domains.get("d_123")
sendly.domains.verify("d_123")

status = sendly.domains.get_verification("d_123")
# One status per record type, not one verdict for the domain.
print(status["dkimStatus"], status["spfStatus"], status["dmarcStatus"])

sendly.domains.start_setup("d_123")  # -> {"token", "connectUrl", "expiresAt"}
sendly.domains.delete("d_123")
```

A domain reports each DNS record type separately — `dkimStatus`, `spfStatus` and
`dmarcStatus` are each `NOT_CHECKED`, `PENDING`, `VERIFIED` or `FAILED`, and
`lastHealthCheckAt` says when they were last filled. `status` on the verification
response is a different thing: SES's own raw DKIM state (`Success`, `Pending`),
which is why both are published rather than collapsed into one.
`receivingEnabled` says whether inbound mail for the domain is routed to Sendly
mailboxes.

`start_setup` returns the hand-off as the API returns it. Open `connectUrl` in a
browser to finish DNS setup at the registrar.

`assign_stream` points a verified identity at one kind of traffic:

```python
sendly.domains.assign_stream("d_123", {
    "stream": "TRANSACTIONAL",
    "streamDefault": True,
    "defaultFromAddress": "receipts@mail.yourdomain.com",
})
```

Streams are enforced, not labelled: once assigned, a send of the other kind from
this identity is refused with 403 — which is what keeps a campaign's complaint
rate off the identity your password resets go out on. `"stream": None` unassigns
it, returning it to carrying both. `streamDefault` demotes whichever identity
currently holds the default for that stream, and `defaultFromAddress` has to be
an address on this identity's own host.

The `_v1` half is the same domains in the versioned dialect:

```python
domain = sendly.domains.create_v1({"domain": "mail.yourdomain.com", "region": "us-east-1"})
sendly.domains.verify_v1(domain["id"])   # re-reads SES and DNS, then persists the answer
for d in sendly.domains.iter_list_v1():
    print(d["domain"], d["verified"], d["dkim_verified"])
```

`verified` is SES's verdict on the identity and is what decides whether mail can
leave from this domain; `dkim_verified` is a separate fact — what the DNS health
refresh last read — so the two disagree while a re-check is in flight and
neither is a spelling of the other. `verify_v1` verifies nothing itself:
verification happens in the domain's DNS when its owner publishes the DKIM
records SES minted at creation, and this call asks SES what it currently sees.

### Mailboxes

Receiving mailboxes on the project's verified domains. The reads are reads; the
two composition calls are not — `send_message` really sends. See
[What the SDK does not expose](#what-the-sdk-does-not-expose) for what stays out
of reach.

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

**`send_message` sends real mail**, from the mailbox in the path, over its own
domain, and the recipient can reply to it:

```python
sent = sendly.mailboxes.send_message("mb_123", {
    "to": ["customer@example.com"],
    "subject": "Re: your order",
    "body": "Shipping tomorrow — tracking to follow.",
})
print(sent["conversationId"], sent["messageId"])
```

There is no `from` field, on purpose: a route that sends under a customer's own
identity must not take that identity as an argument. `body` is plain text and
HTML is refused — Sendly renders the HTML part itself, escaping as it goes, so
text becomes markup in exactly one place. Bcc recipients are delivered to but
appear in no header, so the copy filed in the Sent folder does not record them.
Refusals worth handling by name: 422 `RECIPIENT_SUPPRESSED`, 422
`CONTENT_REFUSED`, and 503 `CONTENT_SCAN_UNAVAILABLE` (no verdict yet for a
young project — nothing was sent, retry shortly). A mailbox may send 60 messages
an hour here.

**`draft_message` sends nothing.** It asks Sendly's assistant to write text and
hands it back for you to review:

```python
draft = sendly.mailboxes.draft_message("mb_123", {
    "mode": "draft",   # or "rewrite", or "subject"
    "brief": "Tell the customer their order ships tomorrow and apologise for the delay.",
    "tone": "apologetic",
})
print(draft["subject"], draft["body"], draft["sent"])  # sent is always False
```

`sent: False` is reported rather than assumed, so a draft cannot be mistaken for
a send. It stores nothing, reads no correspondence, and needs only
`mailboxes:read` where sending needs `mailboxes:send` — a client that may draft
is not thereby a client that may mail your customers. Everything you pass is
treated strictly as data describing what to write, never as instructions to the
model. Capped at 120 requests an hour per project; 502 means the model was
unreachable.

### Templates and snippets

```python
sendly.templates.create({"name": "Welcome", "subject": "Welcome", "body": "<p>Hi</p>{{> footer }}",
                         "from": "a@you.com", "emailCategory": "MARKETING"})
sendly.templates.list({"limit": 25})  # cursor pagination: pass {"cursor": ...} for the next page
sendly.templates.get("t_123")
sendly.templates.update("t_123", {"name": "Welcome v2"})
sendly.templates.delete("t_123")
```

`emailCategory` — `type` before 1.1 — is `MARKETING`, `TRANSACTIONAL` or
`SELF_MANAGED_UNSUBSCRIBE` (the member that used to be called `HEADLESS`). It
defaults to `MARKETING`, and it is also the legacy list filter:
`templates.list({"emailCategory": "MARKETING"})`.

A template carries `currentVersion`, a counter an update increments only when it
changes the **rendered content** — a rename leaves it alone. A campaign records
the version it sent, so comparing the two is how you tell "the template changed
since this went out" from "somebody retitled it".

On the `_v1` methods the same field is `email_category`:

```python
template = sendly.templates.create_v1({"name": "Welcome", "subject": "Welcome",
                                       "body": "<p>Hi</p>", "from": "a@you.com",
                                       "email_category": "MARKETING"})
for t in sendly.templates.iter_list_v1({"search": "welcome"}):
    print(t["name"], t["version"])
```

Touching `subject`, `body`, `from`, `from_name` or `reply_to` in `update_v1`
snapshots the previous content into version history and increments `version`;
touching only `name`, `description` or `email_category` does not, because
neither is content a send would have rendered. `delete_v1` is refused with 409
`conflict` while a workflow step or an active campaign still points at the
template.

A **snippet** is a reusable fragment a template pulls in with `{{> name}}`.
`name` is the literal identifier templates include, unique within the project,
so a clash answers 409:

```python
sendly.snippets.create({"name": "footer", "description": "Address block",
                        "body": "<hr /><p>Acme Inc, 1 Example Way</p>"})
page = sendly.snippets.list({"limit": 25, "search": "footer"})
print(len(page["data"]["data"]), page["data"]["hasMore"])

sendly.snippets.get("s_123")
sendly.snippets.update("s_123", {"body": "<hr /><p>Acme Inc</p>"})
sendly.snippets.delete("s_123")
```

Snippets are gated by the same `templates:*` scopes as the templates that
include them, because a snippet is part of a template body rather than a
resource with an audience of its own. Deleting one does not break the templates
that include it — an absent snippet renders as an empty string, like an absent
variable.

### Verify and validate

`verify.email` is the free single-address check — syntax, MX, disposable
domains, plus-addressing:

```python
result = sendly.verify.email({"email": "user@example.com"})
if not result["valid"]:
    print("Rejected:", result.get("reason"))
```

`validation` is the other thing entirely, and **it is billed per address
checked**. Every entry in `emails` costs money, so looping it over a contact
list is looping over your invoice:

```python
batch = sendly.validation.validate_emails({"emails": ["user@example.com", "typo@exmaple.com"]})

for result in batch["results"]:
    # Branch on `verdict`, never on the flags: `is_personal` (Gmail, Outlook) and
    # `is_role_address` (support@) describe ordinary, deliverable addresses.
    print(result["email"], result["verdict"])
```

At most 50 addresses per call. That ceiling is a latency bound, not a payload
one: every distinct domain in the batch costs a DNS round trip. To check a whole
list, start the background run instead — one call, then poll:

```python
run = sendly.lists.start_validation_run("l_123")

progress = sendly.validation.get_run(run["id"])
# Finished when status is "completed" or "failed" — never when a percentage
# reaches 100, because there is deliberately no total to divide by: a list
# changes size while a run walks it.
print(progress["status"], progress["processed_count"], progress["undeliverable_count"])

for result in sendly.validation.iter_list_results(run["id"], {"verdict": "undeliverable"}):
    print(result["email"], result["contact_id"], result["reasons"])
```

A verdict of `unknown` is deliberately a separate value from `undeliverable`: it
means DNS did not answer in time, so that address was **not checked**. Deleting
a contact on `unknown` deletes a live one over a network hiccup. `undeliverable`
is the page to read before acting on a run; `unknown` is the one never to act
on.

### Deliverability

```python
diagnosis = sendly.deliverability.diagnose({
    "domain": "mail.yourdomain.com",  # required — this endpoint answers about one domain
    "address": "user@example.com",    # optional RECIPIENT to check alongside it
    "window_days": 7,
})

# `findings` is worst first, and an empty list means nothing here explains a
# delivery problem. Branch on a finding's `code`, never on its prose.
for finding in diagnosis["findings"]:
    print(finding["severity"], finding["code"], finding["remedy"])
```

Nothing there is looked up live: the DNS statuses are the verification refresh
job's cached results, and `identity.last_checked_at` says when they were filled.
`recent_delivery` is project-wide rather than per-domain — its own `scope` field
says so — because an email row records no sending domain.

`list_domain_stats` is the axis `diagnose` cannot report: outcomes broken out by
**recipient** domain and UTC day. These are the domains you send **to** —
`gmail.com`, `outlook.com` — not the domains you send from, and they are how you
catch one provider refusing nearly everything while the rest of your mail is
healthy.

```python
for row in sendly.deliverability.iter_list_domain_stats({"limit": 100}):
    print(row["day"], row["domain"], row["delivered"], row["bounced"], row["computed_at"])
```

The counts come from an hourly rollup over a rolling 30-day window, not from a
query run on request; each row's `computed_at` says when it was last rebuilt. No
rate is published, because a rate over three sends is not information.

`list_dmarc_reports` returns the DMARC aggregate (RUA) reports receiving
providers have sent about your domains. **An empty list is the correct answer,
not a bug**, until a policy domain is registered in this project and its DMARC
record names an address we receive — and receivers send on their own schedule,
typically once a day.

```python
reports = sendly.deliverability.list_dmarc_reports({"limit": 20})

# Which kind of empty is this? False means no intake mailbox exists, so no
# report can ever arrive — the feature is off, your domains are not "clean".
if not reports["intake_configured"]:
    print("DMARC report intake is not configured on this deployment")

for report in reports["data"]:
    print(report["org_name"], report["policy_domain"], report["pass_count"], report["fail_count"])
```

`intake_configured` exists because the two empty lists are otherwise
indistinguishable, and reporting "no DMARC failures" off a feature that was never
switched on is the worse of the two mistakes. Read the flag before you tell
anyone the domains are healthy.

`pass_count` counts DMARC **alignment** taken from `policy_evaluated`, not raw
authentication results — a message can pass SPF for a domain that is not the one
in its From header, which is exactly the case DMARC exists to catch.

### Webhooks

```python
created = sendly.webhooks.create({"url": "https://you.com/hook", "eventTypes": ["email.delivered"]})
# Store the signing secret now — it is only returned in full at creation/rotation.
print(created["data"]["secret"])
# The endpoint sits beside it rather than spread around it.
print(created["data"]["webhook"]["id"])

sendly.webhooks.list()
sendly.webhooks.get("w_123")
sendly.webhooks.update("w_123", {"status": "PAUSED"})
sendly.webhooks.rotate_secret("w_123")
sendly.webhooks.list_calls("w_123", {"limit": 20})
sendly.webhooks.delete("w_123")
```

On v1 the same registration returns the secret beside the webhook, and rotation
tells you when the outgoing one stops working:

```python
created = sendly.webhooks.create_v1({"url": "https://you.com/hook",
                                     "event_types": ["email.delivered", "email.bounced"]})
webhook, secret = created["webhook"], created["secret"]

rotated = sendly.webhooks.rotate_secret_v1(webhook["id"])
print(rotated["secret"], rotated["previous_secret_expires_at"])
```

`create_v1` and `rotate_secret_v1` are the only two responses that ever carry a
signing secret; no read endpoint hands it back, so a secret you lose is replaced
by rotating rather than recovered. The outgoing secret is not cut off at once —
it keeps verifying until `previous_secret_expires_at`, and every delivery inside
that window carries **both** signatures, so a verifier can be redeployed without
dropping an event. On `update_v1`, `event_types` **replaces** the stored
subscription list rather than merging into it, so an event you omit is
unsubscribed.

A webhook record carries `domains` — the sending domains this endpoint is scoped
to, where an empty list means every domain on the project — and, while a rotation
is in flight, `previousSecretExpiresAt`. A record never carries a secret or any
fragment of one.

### Suppression

```python
sendly.suppression.add({"email": "bounce@example.com", "reason": "MANUAL"})

# Alone among the legacy reads, this one answers no {"success", "data"}
# envelope — the page IS the body.
page = sendly.suppression.list({"reason": "MANUAL", "limit": 100})
for record in page["items"]:
    print(record["email"], record["reason"], record["scope"])

sendly.suppression.get("bounce@example.com")   # -> {"suppressed": False} when it is not
sendly.suppression.remove("bounce@example.com")
```

`scope` is `PROJECT` on every record this API creates or returns today; `GLOBAL`
is reserved for a platform-wide block recorded outside your project.

The `_v1` half addresses a record by the **address itself** and answers
definitively either way — 200 means suppressed and says why, 404
`resource_not_found` means it is not on the list. That is the difference from
the legacy `suppression.get`, which answers `200 {"suppressed": False}` for an
address nobody suppressed:

```python
from sendly import SendlyNotFoundError

try:
    record = sendly.suppression.get_v1("bounce@example.com")
    print("suppressed:", record["reason"], record["source"])
except SendlyNotFoundError:
    pass  # not suppressed — mail may flow
```

Suppressing is idempotent and the first `reason` wins: an already-suppressed
address answers with the existing record, so a later manual entry cannot
overwrite what an SES bounce recorded. `source` is not accepted in the body — it
is derived from the credential, so a record's provenance cannot be dressed up as
a deliverability fact.

`delete_v1` is the one call on this surface that can put mail back into an inbox
that asked you to stop, and it does **not** clear AWS SES's own account-level
suppression list: an address SES suppressed after a hard bounce stays
undeliverable through SES even once this record is gone.

### Lists

```python
# Both calls accept sending-only (pk_*) keys, so they can back a public form.
result = sendly.lists.subscribe("l_123", {"email": "user@example.com"})

# On a double opt-in list the membership is PENDING and carries a confirmToken.
# Sendly does NOT send the confirmation email — deliver this link yourself.
if result["status"] == "PENDING":
    confirm_url = (
        f"https://api.sendly.now/api/lists/confirm-subscription?token={result['confirmToken']}"
    )

# Re-subscribing an address that opted out needs an explicit opt-in, or the call
# fails with 409 RESUBSCRIBE_CONFIRMATION_REQUIRED.
sendly.lists.subscribe("l_123", {"email": "user@example.com", "allowResubscribe": True})

sendly.lists.unsubscribe("l_123", {"email": "user@example.com"})
```

The path is `/api/lists/confirm-subscription` as of 1.1; it was
`/api/lists/confirm` before. The token is valid for 24 hours.

Managing the lists themselves is the `_v1` half:

```python
lst = sendly.lists.create_v1({"name": "Newsletter", "double_opt_in": True})
sendly.lists.update_v1(lst["id"], {"redirect_url": "https://you.com/thanks"})
sendly.lists.get_v1(lst["id"])
sendly.lists.delete_v1(lst["id"])   # removes the list, not its contacts

for l in sendly.lists.iter_list_v1({"limit": 50}):
    print(l["name"], l["member_count"])
```

Turning `double_opt_in` on does not make Sendly send anything — it only changes
`subscribe` to create the membership as `PENDING` and hand back the
`confirmToken` your application delivers. `member_count` counts memberships in
*any* status, `PENDING` and `UNSUBSCRIBED` included, so it is not the size of
the audience a campaign would reach.

## The v1 API

`campaigns`, `segments`, `workflows`, `topics`, `validation`, `deliverability`,
`analytics` and `usage` — plus the v1 methods on `events`, `contacts`, `lists`,
`templates`, `domains`, `webhooks` and `suppression` — speak Sendly's `/api/v1`
surface. Same client, same API key; two differences worth knowing:

- **Responses are bare resource bodies.** There is no `{success, data}` envelope
  to unwrap, so what the API documents is exactly what you get.
- **Errors are RFC 9457 problem documents.** They raise the same exception
  classes as the legacy surface, with two extra fields — see
  [Error handling](#error-handling).

### Both dialects, one client

Six resources — contacts, lists, templates, domains, webhooks and suppression —
answer on both surfaces, so their v1 methods carry a `_v1` suffix:
`contacts.list` is the legacy one, `contacts.list_v1` the versioned one.

The suffix is not decoration. The two methods answer the same question with
different envelopes, different field cases and different error bodies, and a
call site that mixes them up reads a `data` that is not there:

```python
legacy = sendly.contacts.list({"limit": 20})
legacy["data"]["data"]         # the contacts, inside the {success, data} envelope
legacy["data"]["nextCursor"]   # camelCase

v1 = sendly.contacts.list_v1({"limit": 20})
v1["data"]         # the contacts — the bare body IS the list envelope
v1["next_cursor"]  # snake_case
```

Legacy methods keep working and nothing about them changed in 1.1. New code
should reach for the `_v1` ones: they are the surface the contract is versioned
against, and they carry `request_id` on every failure.

### Campaigns

```python
campaign = sendly.campaigns.create(
    {
        "name": "August launch",
        "subject": "We are live",
        "body": "<p>Hello</p>",
        "from": "team@you.com",
        "audience_type": "ALL",
        "email_category": "MARKETING",   # was `type` before 1.1
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

`stats` says how many sends failed; only `list_failures` says who:

```python
failures = sendly.campaigns.list_failures(campaign["id"], {"limit": 100})
print(failures["total"], "recipients did not receive it")

for failure in sendly.campaigns.iter_list_failures(campaign["id"]):
    print(failure["email"], failure["reason"], failure["failed_at"])

retry = sendly.campaigns.retry_failed(campaign["id"])
print("re-queued", retry["queued"])
```

`reason` comes from a fixed vocabulary rather than the underlying error text, so
it is stable enough to branch on; it is `None` on rows recorded before reasons
were captured.

`retry_failed` re-drives **only** the recipients whose send failed — nobody who
already received the campaign is mailed a second time, because each ledger row
is claimed before it is touched and a row whose email exists already is
re-queued rather than re-sent. The walk runs in the background, so the call
returns as soon as it is queued, reporting how many failed rows it was started
for. Only a `SENT` campaign qualifies; a retry already running answers 409
`conflict`.

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
the query fixed and only advances the cursor.

Through 1.0 there were two dialects: `topics.list` and
`validation.list_results` took `cursor` and answered `cursor` where every other
v1 list took `after`. The platform collapsed that for 1.1, so there is one shape
to learn and one to write. If you were driving either of those two by hand, pass
`after` and read `next_cursor`. (The LEGACY `/api/*` lists are a separate
surface and still take `cursor` — that has not changed.)

The seventeen iterators: `campaigns.iter_list`, `campaigns.iter_list_failures`,
`contacts.iter_list_v1`, `deliverability.iter_list_dmarc_reports`,
`deliverability.iter_list_domain_stats`, `domains.iter_list_v1`,
`events.iter_list`, `lists.iter_list_v1`, `segments.iter_list`,
`segments.iter_list_contacts`, `suppression.iter_list_v1`,
`templates.iter_list_v1`, `topics.iter_list`, `validation.iter_list_results`,
`webhooks.iter_list_v1`, `workflows.iter_list` and
`workflows.iter_list_executions`. The analytics endpoints and
`events.list_names` / `events.stats` return a bounded aggregate rather than a
cursor, so they have no iterator. `campaigns.list_failures` is the one cursor
list that also carries `total`, because `retry_failed` acts on that number and
`has_more` alone cannot tell you whether 3 or 30,000 sends failed.

### Segments, events, analytics, usage, projects

```python
segment = sendly.segments.create({
    "name": "Power users",
    "type": "DYNAMIC",
    "condition": {
        "logic": "AND",
        "groups": [
            {"filters": [{"field": "customFields.plan", "operator": "equals", "value": "pro"}]}
        ],
    },
})
sendly.segments.list_contacts(segment["id"], {"limit": 50})

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

### Workflows

```python
workflow = sendly.workflows.create({"name": "Welcome", "event_name": "signup.completed"})
sendly.workflows.start_execution(workflow["id"], {"contact_id": "c_123"})
# Executions are cancelled by execution id alone — not nested under the workflow.
sendly.workflows.cancel_execution("exe_123")
sendly.workflows.stats(workflow["id"], {"from": "2026-08-01"})
```

`get_graph` returns every step — including the `TRIGGER` entry node — plus the
directed transitions between them, and that body is accepted verbatim by
`replace_graph`:

```python
graph = sendly.workflows.get_graph(workflow["id"])
graph["steps"][0]["config"]   # stored exactly as authored, camelCase keys and all

sendly.workflows.replace_graph(workflow["id"], {
    "steps": graph["steps"],
    "transitions": graph["transitions"],
})
```

`replace_graph` is a **PUT**, and that is the point: a graph is nodes *plus* the
edges between them, so a partial edit to a step list has no meaning without the
transitions that reference it — half-applied, it would leave steps pointing at
steps that no longer exist. Ids decide the outcome per step: one you send is
updated in place, a fresh uuid creates a step, and an id you omit deletes that
step *and its run history*. Exactly one step must be a `TRIGGER`, every
transition must name steps in the same document, and no step may point at
itself. It is refused with 409 `conflict` while the workflow has running
executions — those runs are standing on the steps being replaced.

`clone` copies a workflow and its whole graph. The copy is **always created
disabled**, whatever the original was: a clone exists to be reviewed, and one
that started live would match the same trigger events as its original from the
moment it appeared.

```python
copy = sendly.workflows.clone(workflow["id"], {"name": "Welcome (v2 test)"})
```

`pause` and `resume` are deliberately asymmetric:

```python
paused = sendly.workflows.pause(workflow["id"])
print("cancelled", paused["cancelled_executions"], "in-flight runs")

resumed = sendly.workflows.resume(workflow["id"])
print(resumed["cancelled_executions"])  # always 0
```

**Pausing cancels every `RUNNING`/`WAITING` execution** and reports how many —
that is what separates it from `update(id, {"enabled": False})`, which only
stops new runs starting and leaves every in-flight contact walking the graph,
next delay still expiring, next email still sending. **Resuming re-opens the
workflow to new runs and does not restore the cancelled ones.** The cancellation
is terminal; there is no undo, so pause when you mean to stop the sends already
in flight and disable when you only mean to close the door. `resume` is refused
with `422 validation_error` while any step is still unconfigured.

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

### Idempotency

Pass `idempotency_key` on the writes that accept one — `emails.send`,
`emails.send_legacy`, `emails.batch`, `contacts.create`, `contacts.upsert`,
`contacts.bulk_create`, `campaigns.create` and `campaigns.send`. Replays within
24 hours return the original result instead of acting twice.

Nothing added in 1.1 takes a key. The v1 creates are either naturally idempotent
on their own key or cheap to repeat, and `campaigns.retry_failed` is guarded
instead by a 409 on a retry already running — the thing to prevent there is two
concurrent walks, not a replayed request. `events.record` takes none because
events are append-only and high-volume; `emails.send_test` takes none for the
reason above.

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

Mailbox **lifecycle** is what stays out of reach — not the mailbox resource as a
whole. The three reads have a conditional membership check, and `send_message` /
`draft_message` publish `ApiKeyAuth` outright, so a key really can call all five.

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

Note that `SendlyNotFoundError` from `suppression.get_v1` is an ordinary answer,
not a failure: it is how that route says "this address is not suppressed". Catch
it rather than logging it.

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
