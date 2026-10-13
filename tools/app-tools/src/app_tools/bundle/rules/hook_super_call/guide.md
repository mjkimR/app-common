# [RULE-app-hook-super-call] Hooks Do Not Chain Through super()

## 1. Overview

Hooks are independent protocol units: the service executor calls each registered hook in order. A hook that
calls `super()` runs a parent's step a second time, or out of order.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: classes whose name ends in `Hook` or that derive from a class named `*Hook`, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Every
  `super().<method>(...)` call in a method other than `__init__` is reported.

## 2. Cause of Violation

- A hook method calls `super()`: `Hook '<Class>.<method>' calls super().<method>().`

## 3. Remediation

Remove the `super()` call. To combine behaviour, register both hooks with the service; the executor chains
them. See the `app-common` skill's `references/backend/hooks.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-hook-super-call] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
