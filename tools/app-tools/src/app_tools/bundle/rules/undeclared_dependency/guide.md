# [RULE-app-undeclared-dependency] Imported app-common Packages Are Declared

## 1. Overview

A package that imports an app-common package, or devkit, only because another dependency happens to bring it
breaks when that dependency changes. Every package declares what it imports.

- **Phase and severity**: `linter`, `warning`: reported by `devkit rules check` without failing it.
- **What is checked**: every module of a package (the nearest `pyproject.toml` with a `[project]` table), among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). The
  checked imports are app-common's public packages (`app_layer_base`, `app_http_client`, `app_mcp`, ...,
  `app_tools`) and devkit: `devkit.advisory` (also `from devkit import advisory`) needs `devkit-advisory`, or
  `devkit-agt`, which depends on it; any other `devkit` module needs `devkit-agt`. Declarations are read from
  `project.dependencies` and every optional dependency, with names normalized.

## 2. Cause of Violation

- `<distribution> is imported but not declared by <package>.`

## 3. Remediation

Declare the distribution in the package's `project.dependencies` (or the optional dependency that uses it).
Library and service code declares `devkit-advisory`, never `devkit-agt`, which is development tooling. app-common
and devkit are not on a package index: declare them with the Git source and revision app-common pins in
`[tool.uv.sources]`. See the `app-common` skill's `references/local-dev/index.md` and
`references/backend/setup.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-undeclared-dependency] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
