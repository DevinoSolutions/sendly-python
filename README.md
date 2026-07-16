# Sendly Python SDK

Official Python SDK for the [Sendly](https://sendly.now) REST API — transactional
email, contacts, events, domains, templates, email verification, webhooks, and
suppression.

[![CI](https://github.com/DevinoSolutions/sendly-python/actions/workflows/ci.yml/badge.svg)](https://github.com/DevinoSolutions/sendly-python/actions/workflows/ci.yml)

- Full type hints (ships `py.typed`), `mypy --strict` clean.
- One small runtime dependency: [`httpx`](https://www.python-httpx.org/).
- Fail-loud by design: no silent fallbacks, no degraded mode.

## Installation

```bash
pip install py-sendly
```

The distribution is published as `py-sendly`; the import name is unchanged:

```python
import sendly
```

Alternatively, install the latest `main` directly from GitHub:

```bash
pip install git+https://github.com/DevinoSolutions/sendly-python.git
```

Requires Python 3.10+.

## Quickstart

The client reads your API key from the `SENDLY_API_KEY` environment variable:

```python
from sendly import Sendly

sendly = Sendly()  # reads SENDLY_API_KEY

result = sendly.emails.send(
    {
        "from": "hello@yourdomain.com",
        "to": "customer@example.com",
        "subject": "Welcome aboard",
        "body": "<h1>Thanks for signing up!</h1>",
    }
)
print(result["id"])
```

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
# Single send (pass idempotency_key to dedupe replays for 24h)
sendly.emails.send({"from": "a@you.com", "to": "b@them.com", "subject": "Hi", "body": "<p>Hi</p>"},
                   idempotency_key="order-42-receipt")

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
sendly.domains.delete("d_123")
```

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

Only a synchronous client ships in v0.1. An `httpx.AsyncClient`-backed async
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

## Documentation

Full API reference: <https://docs.sendly.now>

## License

MIT — see [LICENSE](LICENSE).
