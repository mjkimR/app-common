# [RULE-app-db-factory-in-layer] Routers and Services Use the Configured Session

## 1. Overview

The application's engine and session factory are configured once and injected. A router or service that
builds its own opens connections outside that pool and outside the request's transaction.

- **Phase and severity**: `linter`, `warning`: reported by `devkit rules check` without failing it.
- **What is checked**: router and service modules (a file named `router.py`, `routes.py`, `service.py` or `services.py`, or a path
  component `api` or `services`) of packages that declare `app-layer-base`, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Calls of
  SQLAlchemy's `create_engine`, `create_async_engine`, `async_sessionmaker` and `sessionmaker` are reported.

## 2. Cause of Violation

- `Router/service constructs its own DB engine or session factory.`

## 3. Remediation

Inject the configured session through `get_session`. A separate database with its own lifecycle belongs in
infrastructure code, not in a router or service. See the `app-common` skill's `references/backend/session.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-db-factory-in-layer] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
