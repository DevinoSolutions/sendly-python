#!/usr/bin/env python3
"""Sync the vendored Sendly OpenAPI spec.

Reads the Sendly OpenAPI contract and writes a pretty-printed, deterministic copy
to ``tests/fixtures/openapi.json``. The contract test suite
(``tests/test_contract.py``) reads that committed copy and never touches the
network, so this script is the single place where the vendored spec is refreshed.

The source is **required** and comes from the ``SENDLY_OPENAPI_URL`` environment
variable.

WHY PRODUCTION IS BANNED AS A SOURCE -- this is the reason, not a superstition,
and it is written down so nobody deletes the guardrail for lack of one:

    Vendoring the spec from the deployed API makes the SDK mirror whatever is
    RUNNING rather than what the repo DECLARES. Any drift between the platform's
    code and its committed contract is then laundered into "correct" on the way
    in -- the SDK re-vendors itself to match the deployment and the mismatch
    disappears silently. That destroys the one job the vendored spec has: it is
    the fixed reference ``tests/test_contract.py`` compares against, so an SDK
    synced from production can no longer detect the very drift it exists to
    catch. It is also unreproducible (two maintainers on the same commit can get
    different files) and unreviewable (the diff traces to no merged change).

So there is deliberately no default, and a script that silently picks *some*
remote when unconfigured is the same class of bug. Production is NOT hard-blocked
-- "what does production actually serve?" is a legitimate one-off check. It is
made LOUD instead (see ``warn_if_production``), because quiet is the property
that made the old default dangerous, not the host itself.

``SENDLY_OPENAPI_URL`` accepts either form:

* a filesystem path (absolute or relative) to a committed spec  -- normal case
* an ``http(s)://`` URL of a local or staging API               -- occasional

Usage::

    SENDLY_OPENAPI_URL=/path/to/sendly/apps/web/openapi/openapi.json \\
        python scripts/sync_spec.py            # overwrite the vendored copy

    SENDLY_OPENAPI_URL=... python scripts/sync_spec.py --check
                                               # fail if the vendored copy is stale

Standard-library only -- no third-party dependencies -- so the script runs in a
bare Python 3.10+ environment.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlparse
from urllib.request import url2pathname

#: Environment variable naming the OpenAPI source. No default -- see module docstring.
SPEC_SOURCE_ENV = "SENDLY_OPENAPI_URL"

#: Canonical location of the contract inside the Sendly platform monorepo.
MONOREPO_SPEC_PATH = "apps/web/openapi/openapi.json"

#: Host of the deployed production API. Never a legitimate unattended source.
PRODUCTION_HOST = "api.sendly.now"

#: Shown when no source is configured. Kept in step with sendly-js's
#: scripts/spec-source.mjs so both SDKs report the same missing configuration
#: the same way.
UNCONFIGURED_MESSAGE = "\n".join(
    [
        f"{SPEC_SOURCE_ENV} is not set, and there is no default.",
        "",
        "Point it at the committed contract in the Sendly platform monorepo:",
        f"  {SPEC_SOURCE_ENV}=/path/to/sendly/{MONOREPO_SPEC_PATH} python scripts/sync_spec.py",
        "",
        "An http(s):// URL of a local or staging API works too. Do NOT point it at",
        "production (https://api.sendly.now): the SDK spec is synced from the committed",
        "contract, never live-synced from the deployed API.",
    ]
)

#: Committed copy consumed by the contract tests. Kept relative to this file so
#: the script works from any working directory.
SPEC_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "openapi.json"

#: HTTP verbs that denote an operation in an OpenAPI path item.
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})

_TIMEOUT_SECONDS = 30


def _fail(message: str) -> NoReturn:
    print(f"sync_spec: {message}", file=sys.stderr)
    raise SystemExit(1)


def spec_source() -> str:
    """Resolve the configured spec source, or fail loudly naming what to set."""
    raw = os.environ.get(SPEC_SOURCE_ENV, "").strip()
    if not raw:
        _fail(UNCONFIGURED_MESSAGE)
    return raw


def _is_http(source: str) -> bool:
    return source.lower().startswith(("http://", "https://"))


def _as_local_path(source: str) -> Path:
    """Interpret a non-http source as a path on disk.

    A ``file://`` URL is accepted alongside a plain path because it is what a
    shell completion or a URL-shaped habit tends to produce.
    """
    if source.lower().startswith("file://"):
        return Path(url2pathname(urlparse(source).path))
    return Path(source)


def is_production_source(source: str) -> bool:
    """True when the source is the deployed production API."""
    if not _is_http(source):
        return False
    return (urlparse(source).hostname or "").lower() == PRODUCTION_HOST


def warn_if_production(source: str) -> bool:
    """Shout -- do not refuse -- when the resolved source is production.

    A refusal would block the legitimate "verify what production actually
    serves" one-off. What must not happen is this occurring QUIETLY, which is
    exactly how the old default went unnoticed while running on every push,
    every PR and a weekly cron. So it is unmissable in a scrolling log, and it
    annotates the run when it happens inside GitHub Actions.
    """
    if not is_production_source(source):
        return False

    banner = "\n".join(
        [
            "!!!===========================================================================!!!",
            "!!!  WARNING: reading the OpenAPI spec from PRODUCTION                        !!!",
            f"!!!  {source}",
            "!!!                                                                          !!!",
            "!!!  This is the BANNED path. Vendoring a spec from the deployed API makes    !!!",
            "!!!  the SDK mirror what is RUNNING instead of what the repo DECLARES, which  !!!",
            "!!!  launders code-vs-contract drift into 'correct' and destroys the SDK's    !!!",
            "!!!  ability to detect the very drift it exists to catch.                     !!!",
            "!!!                                                                          !!!",
            "!!!  Only ever do this as a DELIBERATE one-off (e.g. 'what does production    !!!",
            "!!!  actually serve right now?'). NEVER commit the result, and never wire     !!!",
            "!!!  this host into CI or any unattended job.                                 !!!",
            "!!!===========================================================================!!!",
        ]
    )
    print(banner, file=sys.stderr)

    if os.environ.get("GITHUB_ACTIONS"):
        print(
            f"::warning title=OpenAPI spec read from PRODUCTION::{source} is the deployed API. "
            'Syncing an SDK spec from production is banned -- it launders code-vs-contract drift into "correct". '
            "An unattended job must never be pointed at this host."
        )
    return True


def load_spec(source: str) -> dict[str, Any]:
    """Read and parse the OpenAPI document from ``source``. Fail loud on any error."""
    if _is_http(source):
        request = urllib.request.Request(source, headers={"User-Agent": "sendly-spec-sync"})
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    _fail(f"{source} returned HTTP {status}")
                payload = response.read().decode("utf-8")
        except (OSError, ValueError) as exc:
            _fail(f"could not fetch {source}: {exc}")
    else:
        path = _as_local_path(source)
        try:
            payload = path.read_text(encoding="utf-8")
        except OSError as exc:
            _fail(f"could not read {path}: {exc}")

    try:
        spec: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        _fail(f"{source} did not contain valid JSON: {exc}")
    if not isinstance(spec, dict) or "openapi" not in spec or "paths" not in spec:
        _fail(f"{source} is not a valid OpenAPI document")
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
    """Read the configured spec and overwrite the vendored copy."""
    source = spec_source()
    # Loud, but not a refusal -- see warn_if_production.
    warn_if_production(source)
    spec = load_spec(source)
    text = render(spec)
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the vendored copy byte-identical on every platform
    # (Windows text-mode writes would otherwise emit CRLF).
    SPEC_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"sync_spec: wrote {SPEC_PATH} "
        f"({len(text)} bytes, {len(spec['paths'])} paths, {_operation_count(spec)} operations) "
        f"from {source}"
    )


def _print_diff(lines: Iterable[str]) -> None:
    """Print a unified diff without dying on the console's encoding.

    The spec contains non-ASCII characters (e.g. U+21D2 in descriptions) that a
    legacy Windows console codepage cannot encode, which turned every drifted
    ``--check`` on Windows into a UnicodeEncodeError traceback instead of the
    diff it exists to show.
    """
    text = "".join(lines)
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        sys.stdout.write(text.encode(encoding, "replace").decode(encoding))


def check_spec() -> None:
    """Report whether the vendored copy differs from the configured source.

    Unlike a write, an unconfigured ``--check`` SKIPS (exit 0) rather than
    failing: it runs unattended in CI on every pull request, including from forks
    that cannot supply a source, and a red step there would report a
    configuration gap as if it were spec drift.
    """
    source = os.environ.get(SPEC_SOURCE_ENV, "").strip()
    if not source:
        print(
            f"sync_spec: skipped -- {SPEC_SOURCE_ENV} is not set. Set it to the committed "
            f"contract ({MONOREPO_SPEC_PATH} in the platform monorepo) to compare."
        )
        return
    # This one matters most: it is the step that runs unattended in CI, so a
    # production source here is precisely the thing that must never be quiet.
    warn_if_production(source)
    if not SPEC_PATH.exists():
        _fail(f"vendored spec missing at {SPEC_PATH}; run `python scripts/sync_spec.py`")
    current = render(load_spec(source))
    vendored = SPEC_PATH.read_text(encoding="utf-8")
    if current == vendored:
        print(f"sync_spec: vendored spec is in sync with {source}")
        return
    _print_diff(
        difflib.unified_diff(
            vendored.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile="vendored tests/fixtures/openapi.json",
            tofile=f"source {source}",
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
