"""Contract tests: the SDK surface must match the vendored OpenAPI spec.

These tests load the *committed* spec (``tests/fixtures/openapi.json``) and never
touch the network -- refresh it with ``python scripts/sync_spec.py``. They assert
bidirectional coverage, fail-closed:

* every spec operation is either implemented by a resource method or explicitly
  listed in :data:`NOT_YET_IMPLEMENTED` (and listed entries must be real,
  still-unimplemented spec operations -- stale entries fail the suite);
* every SDK call site maps to a real spec operation (catches SDK-vs-API drift);
* the core send/create operations forward a request body and the spec still
  declares the required field each depends on.

SDK operations are discovered by introspection: resources are read off a live
:class:`~sendly.Sendly` instance, and each public method's HTTP verb + path are
extracted from its single ``self._client.request(method=..., path=...)`` call via
the ``ast`` module. Path parameters (``{id}``/``{email}``) are normalized to a
name-agnostic ``{}`` on both sides before comparison.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from sendly import Sendly

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "openapi.json"

#: HTTP verbs that denote an operation inside an OpenAPI path item.
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})

_PARAM_RE = re.compile(r"\{[^}]*\}")

#: Spec operations the SDK intentionally does not expose yet. Every entry is
#: asserted to (a) exist in the vendored spec and (b) NOT be implemented by any
#: resource method, so a stale entry -- added by mistake or left behind after the
#: SDK grows a wrapper -- fails the suite. Empty: the whole spec surface is wrapped.
NOT_YET_IMPLEMENTED: set[tuple[str, str]] = set()


# --------------------------------------------------------------------------- #
# Spec side                                                                    #
# --------------------------------------------------------------------------- #


def _normalize_path(path: str) -> str:
    """Collapse ``{id}``/``{email}`` path params to a name-agnostic ``{}``."""
    return _PARAM_RE.sub("{}", path)


def _load_spec() -> dict[str, Any]:
    assert FIXTURE_PATH.exists(), (
        f"vendored spec missing at {FIXTURE_PATH}; run `python scripts/sync_spec.py`"
    )
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        spec: Any = json.load(handle)
    assert isinstance(spec, dict) and "paths" in spec, (
        "vendored spec is not a valid OpenAPI document"
    )
    return spec


def _spec_operations(spec: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Every spec operation as ``(VERB, original_path, normalized_path)``."""
    operations: list[tuple[str, str, str]] = []
    for path, item in spec.get("paths", {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() in HTTP_METHODS and isinstance(operation, dict):
                operations.append((method.upper(), path, _normalize_path(path)))
    return operations


def _resolve_ref(spec: dict[str, Any], node: Any) -> Any:
    """Follow local ``$ref`` pointers within the spec (cycle-safe)."""
    seen: set[str] = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or ref in seen:
            break
        seen.add(ref)
        target: Any = spec
        for part in ref.lstrip("#/").split("/"):
            target = target[part]
        node = target
    return node


#: Members that identify the ``/api/v1`` cursor-list envelope. No ``total`` --
#: the API deliberately does not count a project's rows on every page.
CURSOR_ENVELOPE = frozenset({"data", "has_more", "next_cursor"})


def _cursor_list_operations(spec: dict[str, Any]) -> set[tuple[str, str]]:
    """Spec operations answering the cursor envelope, as ``(VERB, normalized_path)``.

    These -- and only these -- are the operations an ``iter_*`` companion can
    walk. The other v1 listings (analytics, event names/stats) return a bounded
    aggregate with no cursor.
    """
    cursor_ops: set[tuple[str, str]] = set()
    for verb, path, norm in _spec_operations(spec):
        operation = spec["paths"][path][verb.lower()]
        for code, response in operation.get("responses", {}).items():
            if not code.startswith("2"):
                continue
            resolved = _resolve_ref(spec, response)
            for media in resolved.get("content", {}).values():
                schema = _resolve_ref(spec, media.get("schema", {}))
                properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
                if CURSOR_ENVELOPE.issubset(properties):
                    cursor_ops.add((verb, norm))
    return cursor_ops


def _required_fields(spec: dict[str, Any], path: str, method: str) -> set[str]:
    operation = spec["paths"][path][method]
    schema = _resolve_ref(spec, operation["requestBody"]["content"]["application/json"]["schema"])
    required = schema.get("required", []) if isinstance(schema, dict) else []
    return set(required)


# --------------------------------------------------------------------------- #
# SDK side (introspection)                                                     #
# --------------------------------------------------------------------------- #


def _param_name(node: ast.expr) -> str:
    """Best-effort parameter name for an f-string interpolation."""
    if isinstance(node, ast.Call):
        for arg in node.args:
            if isinstance(arg, ast.Name):
                return arg.id
    if isinstance(node, ast.Name):
        return node.id
    return "param"


def _path_template(node: ast.expr, label: str) -> str:
    """Reconstruct the URL path from a string or f-string ``path=`` argument."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{" + _param_name(value.value) + "}")
            else:
                parts.append("{param}")
        return "".join(parts)
    raise AssertionError(f"{label}: unsupported path expression {ast.dump(node)}")


def _request_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "request"
    ]


def _verb_and_path(call: ast.Call, label: str) -> tuple[str, str]:
    keywords = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    method_node = keywords.get("method")
    path_node = keywords.get("path")
    if not isinstance(method_node, ast.Constant) or not isinstance(method_node.value, str):
        raise AssertionError(f"{label}: request() has no literal method= argument")
    if path_node is None:
        raise AssertionError(f"{label}: request() has no path= argument")
    return method_node.value.upper(), _path_template(path_node, label)


def _discover_resources() -> dict[str, type]:
    """Map public resource attribute name -> resource class, off a live client."""
    resources: dict[str, type] = {}
    with Sendly(api_key="sk_test_contract", base_url="http://localhost") as client:
        for attr, value in vars(client).items():
            klass = type(value)
            if klass.__name__.endswith("Resource"):
                resources[attr] = klass
    return resources


def _sdk_operations() -> list[tuple[str, str, str]]:
    """Every SDK call site as ``(VERB, normalized_path, 'resource.method')``."""
    operations: list[tuple[str, str, str]] = []
    for attr, klass in sorted(_discover_resources().items()):
        for name, func in inspect.getmembers(klass, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
            for call in _request_calls(tree):
                verb, path = _verb_and_path(call, f"{klass.__name__}.{name}")
                operations.append((verb, _normalize_path(path), f"{attr}.{name}"))
    return operations


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


def test_introspection_is_not_vacuous():
    # A broken fixture or extractor would make the coverage checks pass trivially.
    # The floor tracks the real surface (legacy /api/* plus /api/v1/*) with enough
    # slack that a single retired endpoint does not fail the suite here -- the
    # coverage tests below are what catch drift.
    spec = _load_spec()
    assert len(_spec_operations(spec)) >= 60
    assert len(_sdk_operations()) >= 60


def test_every_spec_operation_is_implemented_or_listed():
    spec = _load_spec()
    implemented = {(verb, norm) for verb, norm, _ in _sdk_operations()}
    listed = {(verb, _normalize_path(path)) for verb, path in NOT_YET_IMPLEMENTED}
    unhandled = sorted(
        f"{verb} {path}"
        for verb, path, norm in _spec_operations(spec)
        if (verb, norm) not in implemented and (verb, norm) not in listed
    )
    assert not unhandled, (
        "Spec operations neither implemented by the SDK nor listed in "
        "NOT_YET_IMPLEMENTED. Add a resource method or list them explicitly:\n  "
        + "\n  ".join(unhandled)
    )


def test_not_yet_implemented_entries_are_real_and_unimplemented():
    spec = _load_spec()
    spec_ops = {(verb, norm) for verb, _path, norm in _spec_operations(spec)}
    implemented = {(verb, norm) for verb, norm, _ in _sdk_operations()}
    for verb, path in sorted(NOT_YET_IMPLEMENTED):
        norm = _normalize_path(path)
        assert (verb, norm) in spec_ops, (
            f"NOT_YET_IMPLEMENTED lists {verb} {path}, which is absent from the "
            "vendored spec. Remove the stale entry (or re-sync the spec)."
        )
        assert (verb, norm) not in implemented, (
            f"NOT_YET_IMPLEMENTED lists {verb} {path}, but the SDK now implements "
            "it. Remove it from NOT_YET_IMPLEMENTED."
        )


def test_every_sdk_method_matches_a_spec_operation():
    spec = _load_spec()
    spec_ops = {(verb, norm) for verb, _path, norm in _spec_operations(spec)}
    drift = sorted(
        f"{label} -> {verb} {norm}"
        for verb, norm, label in _sdk_operations()
        if (verb, norm) not in spec_ops
    )
    assert not drift, (
        "SDK methods whose (method, path) is absent from the vendored spec. "
        "The SDK drifted from the API, or the spec needs a re-sync:\n  " + "\n  ".join(drift)
    )


def test_every_cursor_paginated_list_has_an_iterator():
    spec = _load_spec()
    cursor_ops = _cursor_list_operations(spec)
    # campaigns, segments, segment contacts, workflows, workflow executions, events.
    assert len(cursor_ops) >= 6, "cursor-envelope detection found nothing -- spec shape changed?"

    resources = _discover_resources()
    missing = sorted(
        f"{label} (add {label.split('.', 1)[0]}.iter_{label.split('.', 1)[1]})"
        for verb, norm, label in _sdk_operations()
        if (verb, norm) in cursor_ops
        and not hasattr(resources[label.split(".", 1)[0]], f"iter_{label.split('.', 1)[1]}")
    )
    assert not missing, (
        "Cursor-paginated list methods with no auto-pagination companion:\n  "
        + "\n  ".join(missing)
    )


def test_every_iterator_wraps_a_cursor_paginated_list():
    # The reverse guard: an iterator over a response that carries no cursor would
    # silently yield one page and stop.
    spec = _load_spec()
    cursor_ops = _cursor_list_operations(spec)
    cursor_labels = {label for verb, norm, label in _sdk_operations() if (verb, norm) in cursor_ops}

    stray = sorted(
        f"{attr}.{name}"
        for attr, klass in _discover_resources().items()
        for name, _func in inspect.getmembers(klass, predicate=inspect.isfunction)
        if name.startswith("iter_") and f"{attr}.{name[len('iter_') :]}" not in cursor_labels
    )
    assert not stray, (
        "Iterator methods whose underlying list operation is not cursor-paginated "
        "in the spec:\n  " + "\n  ".join(stray)
    )


def test_v1_methods_never_unwrap_an_envelope():
    # /api/v1 returns the resource body directly. Calling unwrap() on a v1 list
    # would strip has_more/next_cursor and hand back the data array alone.
    offenders: list[str] = []
    for attr, klass in sorted(_discover_resources().items()):
        for name, func in inspect.getmembers(klass, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
            calls = _request_calls(tree)
            paths = [_verb_and_path(call, f"{klass.__name__}.{name}")[1] for call in calls]
            if not any(path.startswith("/api/v1") for path in paths):
                continue
            unwraps = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "unwrap"
            ]
            if unwraps:
                offenders.append(f"{attr}.{name}")
    assert not offenders, (
        "v1 methods calling unwrap(); v1 responses are not enveloped:\n  " + "\n  ".join(offenders)
    )


def test_core_operations_forward_a_body_and_match_required_fields():
    spec = _load_spec()
    resources = _discover_resources()
    assert "emails" in resources and "contacts" in resources
    # Thin client: request bodies are opaque Mapping[str, Any] payloads forwarded
    # verbatim (no per-field TypedDicts), so the spot-check confirms each entry
    # point forwards a body and that the spec still declares the core required
    # field the caller's body must carry.
    assert "body" in inspect.signature(resources["emails"].send).parameters
    assert "body" in inspect.signature(resources["contacts"].create).parameters
    assert "to" in _required_fields(spec, "/api/emails", "post"), (
        "sendEmail no longer requires 'to' in the spec -- revisit emails.send."
    )
    assert "email" in _required_fields(spec, "/api/contacts", "post"), (
        "createContact no longer requires 'email' in the spec -- revisit contacts.create."
    )


def test_a_required_request_body_is_a_required_python_argument():
    # A body the spec marks required must not be defaulted to None, or a caller
    # can send an empty request the API is guaranteed to reject.
    spec = _load_spec()
    resources = _discover_resources()
    checks = [
        ("workflows", "start_execution", "/api/v1/workflows/{id}/executions", "contact_id"),
        ("segments", "create", "/api/v1/segments", "name"),
        ("events", "record", "/api/v1/events", "name"),
    ]
    for attr, method, path, field in checks:
        operation = spec["paths"][path]["post"]
        assert operation["requestBody"].get("required") is True, (
            f"{path} no longer requires a request body -- revisit {attr}.{method}."
        )
        assert field in _required_fields(spec, path, "post"), (
            f"{path} no longer requires '{field}' -- revisit {attr}.{method}."
        )
        parameter = inspect.signature(getattr(resources[attr], method)).parameters["body"]
        assert parameter.default is inspect.Parameter.empty, (
            f"{attr}.{method} defaults its body, but the spec requires one."
        )


def test_a_parameterless_operation_takes_no_query_argument():
    # The spec declares no parameters on these, so a query argument would invite
    # callers to send filters the API silently ignores.
    spec = _load_spec()
    resources = _discover_resources()
    for attr, method, verb, path in [("events", "list_names", "get", "/api/v1/events/names")]:
        assert not spec["paths"][path][verb].get("parameters"), (
            f"{verb.upper()} {path} now declares parameters -- revisit {attr}.{method}."
        )
        parameters = inspect.signature(getattr(resources[attr], method)).parameters
        assert list(parameters) == ["self"], (
            f"{attr}.{method} accepts {list(parameters)[1:]}, but the spec declares no parameters."
        )
