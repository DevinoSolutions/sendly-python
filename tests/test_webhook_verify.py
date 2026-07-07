"""Webhook signature verification tests.

Mirrors the reference scheme: bare-hex HMAC_SHA256(secret, f"{timestamp}.{body}")
carried in X-Sendly-Signature, X-Sendly-Timestamp as a millisecond Unix epoch,
with a replay-protection tolerance window. Test vectors are built directly with
hmac/hashlib and real current timestamps — no clock mocking.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import time

import pytest

from sendly import DEFAULT_TOLERANCE_MS, construct_event, verify_signature

SECRET = "whsec_test_secret"


def _now_ms() -> str:
    return str(int(time.time() * 1000))


def _sign(body: str, timestamp: str, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


def test_default_tolerance_is_five_minutes():
    assert DEFAULT_TOLERANCE_MS == 5 * 60 * 1000


def test_accepts_server_built_signature_str_payload():
    ts = _now_ms()
    body = '{"event":"email.sent","data":{}}'
    assert verify_signature(body, _sign(body, ts), ts, SECRET) is True


def test_accepts_server_built_signature_bytes_payload():
    ts = _now_ms()
    body = '{"event":"email.sent","data":{}}'
    assert verify_signature(body.encode(), _sign(body, ts), ts, SECRET) is True


def test_rejects_tampered_body():
    ts = _now_ms()
    body = '{"event":"email.sent"}'
    sig = _sign(body, ts)
    assert verify_signature('{"event":"email.opened"}', sig, ts, SECRET) is False


def test_rejects_wrong_secret():
    ts = _now_ms()
    body = '{"event":"email.sent"}'
    sig = _sign(body, ts, "whsec_other_secret")
    assert verify_signature(body, sig, ts, SECRET) is False


def test_rejects_signature_computed_over_different_timestamp():
    ts = _now_ms()
    other_ts = str(int(ts) - 1000)  # still fresh, but a different timestamp
    body = '{"event":"email.sent"}'
    sig = _sign(body, other_ts)
    assert verify_signature(body, sig, ts, SECRET) is False


def test_rejects_legacy_sha256_prefixed_format():
    ts = _now_ms()
    body = '{"event":"email.sent"}'
    legacy = "sha256=" + _sign(body, ts)
    assert verify_signature(body, legacy, ts, SECRET) is False


def test_rejects_timestamp_older_than_tolerance():
    body = '{"event":"email.sent"}'
    stale_ts = str(int(time.time() * 1000) - (DEFAULT_TOLERANCE_MS + 60_000))
    sig = _sign(body, stale_ts)  # signature is valid for that timestamp
    assert verify_signature(body, sig, stale_ts, SECRET) is False


def test_accepts_stale_timestamp_when_tolerance_is_infinite():
    body = '{"event":"email.sent"}'
    stale_ts = str(int(time.time() * 1000) - (DEFAULT_TOLERANCE_MS + 60_000))
    sig = _sign(body, stale_ts)
    assert verify_signature(body, sig, stale_ts, SECRET, tolerance_ms=math.inf) is True


def test_rejects_non_numeric_timestamp():
    body = '{"event":"email.sent"}'
    sig = _sign(body, "not-a-number")
    assert verify_signature(body, sig, "not-a-number", SECRET) is False


def test_rejects_non_ascii_signature_without_raising():
    ts = _now_ms()
    body = '{"event":"email.sent"}'
    assert verify_signature(body, "\xff" * 64, ts, SECRET) is False
    assert verify_signature(body, "\ud800" + "a" * 63, ts, SECRET) is False


def test_construct_event_returns_parsed_event():
    ts = _now_ms()
    body = '{"event":"email.delivered","data":{"id":"em_1"}}'
    event = construct_event(body, _sign(body, ts), ts, SECRET)
    assert event["event"] == "email.delivered"
    assert event["data"]["id"] == "em_1"


def test_construct_event_raises_value_error_on_bad_signature():
    ts = _now_ms()
    body = '{"event":"email.delivered"}'
    with pytest.raises(ValueError, match="Invalid webhook signature"):
        construct_event(body, "deadbeef", ts, SECRET)
