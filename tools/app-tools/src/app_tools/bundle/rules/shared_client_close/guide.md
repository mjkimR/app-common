# [RULE-app-shared-client-close] Do Not Close the Shared HTTP Client

## 1. Overview

The shared clients of `app-http-client` are closed by its lifespan. Closing one in application code breaks
every other user of it in the process.

- **Phase and severity**: `linter`, `warning`: reported by `devkit rules check` without failing it.
- **What is checked**: packages that declare `app-http-client`, except `app-http-client` itself, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). The client
  returned by `get_http_client()` or `get_http_sync_client()` (directly or through a variable) is followed;
  calling `aclose()` or `close()` on it, or using it as a `with`/`async with` context manager, is reported.

## 2. Cause of Violation

- `Application code closes a shared HTTP client.`
- `A context manager will close the shared HTTP client.`

## 3. Remediation

Use the shared client directly, without closing it, and let the `app-http-client` lifespan shut it down. See
the `app-common` skill's `references/http/index.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-shared-client-close] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
