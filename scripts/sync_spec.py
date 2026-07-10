#!/usr/bin/env python3
"""Sync the vendored Sendly OpenAPI spec.

Fetches the live OpenAPI document from the public API and writes a
pretty-printed, deterministic copy to ``tests/fixtures/openapi.json``. The
contract test suite (``tests/test_contract.py``) reads that committed copy and
never touches the network, so this script is the single place where the vendored
spec is refreshed.

Usage::

    python scripts/sync_spec.py            # fetch + overwrite the vendored copy
    python scripts/sync_spec.py --check    # fail if the vendored copy is stale

The spec URL can be overridden with the ``SENDLY_OPENAPI_URL`` environment
variable (useful for staging or self-hosted deployments). Standard-library only
-- no third-party dependencies -- so the script runs in a bare Python 3.10+
environment.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, NoReturn

#: Live OpenAPI 3.1 document for the public Sendly REST API.
DEFAULT_SPEC_URL = "https://api.sendly.now/api/openapi.json"

#: Committed copy consumed by the contract tests. Kept relative to this file so
#: the script works from any working directory.
SPEC_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "openapi.json"

#: HTTP verbs that denote an operation in an OpenAPI path item.
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})

_TIMEOUT_SECONDS = 30


def spec_url() -> str:
    """Resolve the spec URL, honouring the ``SENDLY_OPENAPI_URL`` override."""
    return os.environ.get("SENDLY_OPENAPI_URL", DEFAULT_SPEC_URL)


def _fail(message: str) -> NoReturn:
    print(f"sync_spec: {message}", file=sys.stderr)
    raise SystemExit(1)


def fetch_spec(url: str) -> dict[str, Any]:
    """Fetch and parse the live OpenAPI document. Fail loud on any error."""
    request = urllib.request.Request(url, headers={"User-Agent": "sendly-spec-sync"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                _fail(f"{url} returned HTTP {status}")
            payload = response.read().decode("utf-8")
    except (OSError, ValueError) as exc:
        _fail(f"could not fetch {url}: {exc}")
    try:
        spec: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        _fail(f"{url} did not return valid JSON: {exc}")
    if not isinstance(spec, dict) or "openapi" not in spec or "paths" not in spec:
        _fail(f"{url} did not return a valid OpenAPI document")
    return spec


def render(spec: dict[str, Any]) -> str:
    """Serialize the spec to the canonical vendored form (2-space, trailing newline)."""
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def _operation_count(spec: dict[str, Any]) -> int:
    paths = spec.get("paths", {})
    return sum(
        1
        for item in paths.values()
        if isinstance(item, dict)
        for method in item
        if method.lower() in HTTP_METHODS
    )


def write_spec() -> None:
    """Fetch the live spec and overwrite the vendored copy."""
    spec = fetch_spec(spec_url())
    text = render(spec)
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the vendored copy byte-identical on every platform
    # (Windows text-mode writes would otherwise emit CRLF).
    SPEC_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"sync_spec: wrote {SPEC_PATH} "
        f"({len(text)} bytes, {len(spec['paths'])} paths, {_operation_count(spec)} operations)"
    )


def check_spec() -> None:
    """Fail (exit 1) if the vendored copy differs from the live spec."""
    if not SPEC_PATH.exists():
        _fail(f"vendored spec missing at {SPEC_PATH}; run `python scripts/sync_spec.py`")
    live = render(fetch_spec(spec_url()))
    vendored = SPEC_PATH.read_text(encoding="utf-8")
    if live == vendored:
        print(f"sync_spec: vendored spec is in sync with {spec_url()}")
        return
    sys.stdout.writelines(
        difflib.unified_diff(
            vendored.splitlines(keepends=True),
            live.splitlines(keepends=True),
            fromfile="vendored tests/fixtures/openapi.json",
            tofile=f"live {spec_url()}",
        )
    )
    _fail("vendored spec is STALE -- run `python scripts/sync_spec.py` and commit the result")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sync the vendored Sendly OpenAPI spec.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the vendored copy is up to date instead of rewriting it",
    )
    args = parser.parse_args(argv)
    if args.check:
        check_spec()
    else:
        write_spec()


if __name__ == "__main__":
    main()
