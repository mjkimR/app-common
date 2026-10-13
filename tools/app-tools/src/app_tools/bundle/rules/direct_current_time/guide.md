# [RULE-app-direct-current-time] Read the Clock Through the UTC Utilities

## 1. Overview

`app-layer-base` reads the current time in one place, as timezone-aware UTC, so stored instants compare
correctly and tests can control the clock. `datetime.now()` and friends return naive or local values.

- **Phase and severity**: `linter`, `warning`: reported by `devkit rules check` without failing it.
- **What is checked**: packages that declare `app-layer-base`, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Calls of `datetime.datetime.now`, `utcnow`,
  `today` and `datetime.date.today` are reported, through aliases too; `app-layer-base`'s own
  `utils/time_util.py` is exempt, and other `datetime` functions (`timedelta`, `fromisoformat`) are not checked.

## 2. Cause of Violation

- `<function> bypasses the shared clock utility.`

## 3. Remediation

Use `app_layer_base.utils.time_util.get_current_utc_time()` for an instant or `get_current_utc_date()` for a
UTC date. Keep explicit local-time semantics where they are intended (a user's calendar day) instead of
replacing them blindly, and record that with a suppression comment. See the `app-common` skill's
`references/backend/time.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-direct-current-time] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
