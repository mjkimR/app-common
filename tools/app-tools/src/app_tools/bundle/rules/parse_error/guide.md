# [RULE-app-parse-error] Python Sources Can Be Inspected

## 1. Overview

The architecture rules read Python files as syntax trees. A file that does not parse, or is not valid UTF-8,
cannot be checked at all, so it is reported instead of passing silently.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`).

## 2. Cause of Violation

- A file cannot be parsed or tokenized: `Cannot inspect Python source: <error>`.

## 3. Remediation

Fix the syntax error or the encoding. A file that is deliberately not Python (a template, a broken fixture)
belongs under a `tests` directory or in `[rules] exclude`.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-parse-error] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.

A suppression comment cannot apply: a file that does not parse has no comments to read.
