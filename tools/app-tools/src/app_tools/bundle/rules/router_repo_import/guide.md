# [RULE-app-router-repo-import] Routers Do Not Import Repositories

## 1. Overview

A router that reaches a repository directly skips the usecase or service that owns validation, hooks and the
transaction, so the same endpoint behaves differently from every other entry point.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: router and API modules (a path component `api` below the workspace root, or a file named `router.py` or
  `routes.py`) among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). An import counts when its module path has a `repos` component:
  `from x.repos import ...`, `from x import repos`, `from . import repos` and `import x.repos.y`.
  `app_layer_base.base.repos.query_options` is a value object generated routers use and is allowed.

## 2. Cause of Violation

- A router or API module imports a repository module:
  `Router/API module directly imports repository '<module>'.`

## 3. Remediation

Call a usecase or service from the router and let it use the repository. The layering is described in the
`app-common` skill's `references/backend/index.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-router-repo-import] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
