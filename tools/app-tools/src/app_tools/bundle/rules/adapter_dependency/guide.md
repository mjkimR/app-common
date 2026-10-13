# [RULE-app-adapter-dependency] Adapters Do Not Import Sibling Adapters

## 1. Overview

Each adapter package (`packages/adapters/<name>/`) is installed on its own; an import of a sibling adapter
works in the app-common checkout and fails for a consumer that installed only one of them.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: files under an adapter's `src/` among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). An absolute import of the top-level module of another
  adapter (a package under `packages/adapters/*/src/`) is reported; the adapter's own module and relative
  imports are not.

## 2. Cause of Violation

- An adapter imports a sibling adapter: `Adapter package '<module>' imports sibling adapter '<other>'.`

## 3. Remediation

Compose the adapters in the application, or move the shared code to `app-layer-base`. Package roles are in the
`app-common` skill's `references/backend/index.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-adapter-dependency] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
