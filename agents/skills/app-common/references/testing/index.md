# Testing with app-testing-base

Choose the fixture model first. Read [examples](examples.md) when adding a test
suite or needing a concrete fixture, seeder, or base-class pattern.

## Application-owned stores or HTTP-only tests

Load `app_testing_base.http_plugin` in top-level `tests/conftest.py` and provide an
`app` fixture. Its synchronous `http_client` enters/exits app lifespan, closes on
failure, and uses optional `client_headers` (empty by default). Request errors
propagate as with FastAPI `TestClient`.

This plugin does not request a DB session, create tables, or install dependency
overrides. Preserve application-owned fixtures for connections, commits, isolation,
multiple apps, workspaces, and CLI connectors. Use ordinary test functions rather
than the DB-aware `E2ETest` base. The package still depends on SQLAlchemy/app-layer-base;
using the HTTP plugin does not require adopting their application architecture.

For non-CRUD registry/DTO contracts, use `assert_command_contracts`; for a
consumer-owned context/store, use `assert_transaction_scope_contract`. See
[command features](../backend/commands.md). These helpers own no DB fixtures.
Keep real-backend tests for commit visibility, rollback, joined transactions,
locks, callbacks, failed writes, and concurrent writers.

## DB-aware tests

The following conventions apply to `app_testing_base.plugin`, not the HTTP-only
path above. Load it in top-level `tests/conftest.py`.

| Scope | Directory | Use for |
| --- | --- | --- |
| Integration (default) | `tests/integration/` | UseCase, Service, Repository behavior and DB queries |
| In-process API integration | `tests/integration/` | Routing, serialization, status codes, authentication |
| Unit | `tests/unit/` | Pure calculations/parsers with external boundaries doubled |
| E2E | `tests/e2e/` | Running process or browser user journeys |

- With `asyncio_mode = "auto"`, omit redundant `@pytest.mark.asyncio`.
- Resolve nested services/usecases with `resolve_dependency(..., state={"db": session})`.
  Use `mocker` for external-service isolation in unit tests.
- Keep DB-backed API tests in integration and preserve `real_commit`: requests can commit.
  Legacy `E2ETest` still applies `e2e`/`real_commit` and provides `client`, `session`,
  `url()`, `refresh()`. `IntegrationTest` still applies `integrate` and provides
  `session`, `resolve()`, `refresh()`. These compatibility names do not change the
  directory's boundary classification. Prefer explicit fixtures for new suites.
- Mirror source ownership below each tier and keep shared builders in local
  `tests/support/`. A small temporary input file does not make a parser integration;
  real DB, Git, filesystem-adapter, local vector-store and app-lifespan contracts do.
- Use unit plus relevant integration while iterating; preserve full checks before
  completion. Docker/PostgreSQL selection is independent of the test tier.
- After API/worker writes, use `await refresh_get(session, Model, id)` (or the base
  class's `refresh`) to avoid stale identity-map reads.
- Prefer `assert_status_code`, `assert_json_contains`, `assert_paginated_response`,
  and `assert_error_response` for API assertions.

## Test data

Use explicit schema-valid defaults with `defaults | overrides` in a small seeder.
Do not generate arbitrary values for constrained fields. Use app-testing-base's
`random_string`/`random_email` for valid unique defaults; pass fixed values when
asserting exact results. Seed batches with the same helper. For negative validation
tests, construct invalid input inline rather than passing it through a valid DTO.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Expected success, got 422 | Required fields, formats, and enums in the input schema |
| Duplicate unique key | Unique defaults in the seeder; use the shared random helpers |
| Stale DB result after API call | Refresh/expire the test session's identity map |
| `DependencyResolutionError` | `Annotated[T, Depends()]` or an explicit `overrides={T: mock}` |
| App cannot be discovered | Provide an `app` fixture in top-level `tests/conftest.py` |
