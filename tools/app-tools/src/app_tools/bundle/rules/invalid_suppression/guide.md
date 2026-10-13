# [RULE-app-invalid-suppression] Suppressions Match a Finding

## 1. Overview

An exception recorded as `# arch: ignore[...]` must keep matching a real finding. One that matches nothing
hides the next violation on that line without anyone deciding it, and one with a mistyped rule never worked.

- **Phase and severity**: `linter`, `warning`: reported by `devkit rules check` without failing it.
- **What is checked**: every `# arch: ignore[<rule>, ...] -- <reason>` comment in the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Each rule it names must be an
  app-common architecture rule that reports a finding on that same line.

## 2. Cause of Violation

- `Unused suppression of <rule>.`: the rule reports nothing on that line (the code was fixed or moved).
- `Unknown suppression of <rule>.`: the name is not an app-common architecture rule.

## 3. Remediation

Remove the stale comment, or move it to the line the finding is reported on and use the exact rule ID. A
comment without `-- <reason>` is not a suppression and is not reported here: the finding it meant to hide is.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-invalid-suppression] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.

This rule cannot be suppressed by a comment; use `[rules] exclude` for generated code.
