# [RULE-app-http-client-construction] Use the Shared HTTP Clients

## 1. Overview

`app-http-client` owns one pooled client per process, with the configured timeouts, limits and lifecycle. A
client built with `httpx2` (or legacy `httpx`) directly ignores that configuration and is never closed by the lifespan.

- **Phase and severity**: `linter`, `warning`: reported by `devkit rules check` without failing it.
- **What is checked**: packages that declare `app-http-client` (in `project.dependencies` or an optional dependency of the nearest
  `pyproject.toml` with a `[project]` table), except `app-http-client` itself, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). A call of
  `httpx2.Client` or `httpx2.AsyncClient` (and the legacy `httpx` equivalents) is reported, through aliases
  (`import httpx2 as hx`, `from httpx2 import Client as C`, `factory = httpx2.AsyncClient`) too; names shadowed
  by a parameter or assignment are not.

## 2. Cause of Violation

- A client is constructed directly: `httpx2.AsyncClient bypasses shared client settings and lifecycle.`

## 3. Remediation

Use `app_http_client.get_http_client()` (async) or `get_http_sync_client()`. A client that must stay
isolated (dedicated credentials, a different proxy) keeps its own construction with a suppression comment
giving the reason. See the `app-common` skill's `references/http/index.md`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:

```python
client = httpx2.Client()  # arch: ignore[RULE-app-http-client-construction] -- dedicated credentials
```

A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
