"""Sendly webhook signature verification.

Ported 1:1 from the reference implementation (``webhook-utils.ts``). Every
Sendly webhook delivery is signed and carries two headers:

* ``X-Sendly-Signature`` — the bare (no ``sha256=`` prefix) lowercase hex
  HMAC-SHA256 of ``f"{timestamp}.{body}"`` using your signing secret.
* ``X-Sendly-Timestamp`` — the signing time as a **millisecond** Unix epoch
  (decimal string).

Verification recomputes the HMAC and, by default, rejects deliveries whose
timestamp is more than :data:`DEFAULT_TOLERANCE_MS` away from now (replay
protection). Always pass the RAW request body — do not parse JSON first.

Usage::

    from sendly import verify_signature, construct_event

    @app.route("/webhook", methods=["POST"])
    def webhook():
        payload = request.get_data()  # raw bytes
        signature = request.headers.get("X-Sendly-Signature", "")
        timestamp = request.headers.get("X-Sendly-Timestamp", "")
        secret = os.environ["SENDLY_WEBHOOK_SECRET"]
        try:
            event = construct_event(payload, signature, timestamp, secret)
        except ValueError:
            return "Invalid signature", 400
        if event["event"] == "email.sent":
            ...
        return "", 200
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import Any, Final

#: Default replay-protection window: a delivery whose ``X-Sendly-Timestamp`` is
#: more than this many milliseconds from now is rejected. Pass ``math.inf`` for
#: ``tolerance_ms`` to disable the freshness check.
DEFAULT_TOLERANCE_MS: Final = 5 * 60 * 1000

_TIMESTAMP_PATTERN: Final = re.compile(r"[0-9]+")


def verify_signature(
    payload: bytes | str,
    signature: str,
    timestamp: str,
    secret: str,
    *,
    tolerance_ms: float = DEFAULT_TOLERANCE_MS,
) -> bool:
    """Return ``True`` if *signature* is valid and *timestamp* is fresh.

    Verification order: reject a non-numeric timestamp, then reject a timestamp
    outside *tolerance_ms* of now, then constant-time compare the recomputed
    HMAC. A length mismatch (e.g. a legacy ``sha256=``-prefixed value) compares
    as ``False``, as does any non-ASCII value — this function returns ``bool``
    for every str input and never raises on malformed headers.

    Args:
        payload: Raw request body (``bytes`` or ``str``). Do NOT parse JSON
            first — pass the body exactly as received.
        signature: Value of the ``X-Sendly-Signature`` header (bare hex).
        timestamp: Value of the ``X-Sendly-Timestamp`` header (ms Unix epoch).
        secret: Webhook signing secret from your Sendly dashboard.
        tolerance_ms: Maximum allowed difference, in milliseconds, between the
            timestamp and now. Defaults to :data:`DEFAULT_TOLERANCE_MS`. Pass
            ``math.inf`` to disable the freshness check.
    """
    if _TIMESTAMP_PATTERN.fullmatch(timestamp) is None:
        return False

    now_ms = int(time.time() * 1000)
    if abs(now_ms - int(timestamp)) > tolerance_ms:
        return False

    body = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.{body}".encode(),
        hashlib.sha256,
    ).hexdigest()
    # Compare as bytes: `hmac.compare_digest` on *str* raises TypeError for any
    # non-ASCII character, and the signature is attacker-controlled header data.
    expected_bytes = expected.encode()
    try:
        signature_bytes = signature.encode()
    except UnicodeEncodeError:  # lone surrogates can never be a valid hex digest
        return False
    return hmac.compare_digest(signature_bytes, expected_bytes)


def construct_event(
    payload: bytes | str,
    signature: str,
    timestamp: str,
    secret: str,
    *,
    tolerance_ms: float = DEFAULT_TOLERANCE_MS,
) -> dict[str, Any]:
    """Verify the signature + timestamp, then parse *payload* as JSON.

    Args:
        payload: Raw request body (``bytes`` or ``str``). Do NOT parse JSON first.
        signature: Value of the ``X-Sendly-Signature`` header.
        timestamp: Value of the ``X-Sendly-Timestamp`` header (ms Unix epoch).
        secret: Webhook signing secret from your Sendly dashboard.
        tolerance_ms: See :func:`verify_signature`.

    Returns:
        The decoded event object.

    Raises:
        ValueError: If the signature or timestamp does not verify.
    """
    if not verify_signature(payload, signature, timestamp, secret, tolerance_ms=tolerance_ms):
        raise ValueError("Invalid webhook signature")
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    event: dict[str, Any] = json.loads(text)
    return event
