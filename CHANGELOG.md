# Changelog

All notable changes to `py-sendly` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
