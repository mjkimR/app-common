# [RULE-app-service-commit] Services Do Not Commit

## 1. Overview

A service runs inside the unit of work its caller opened; committing or rolling back there ends that unit
early, so a later failure can no longer undo the earlier writes.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: service modules (a path component `services`, or a file named `service.py` or `services.py`) among
  the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Every call of an attribute named `commit` or `rollback` is reported.

## 2. Cause of Violation

- A service calls `commit()` or `rollback()`: `Service directly invokes 'commit()' on session.`

## 3. Remediation

Remove the call and let the usecase or the session context commit or roll back (`get_session`). The session
lifecycle is in the `app-common` skill's `references/backend/session.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-service-commit] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
