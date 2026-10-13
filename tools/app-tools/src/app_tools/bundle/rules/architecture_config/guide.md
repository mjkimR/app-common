# [RULE-app-architecture-config] Architecture Configuration Is Well Formed

## 1. Overview

`RULE-app-forbidden-import`, `RULE-app-command-signature` and `RULE-app-command-transaction` read
`[tool.app-tools.architecture]` from the nearest `pyproject.toml`. A table they cannot read would silently
check nothing, so it is reported, and every file it governs is skipped until it is fixed.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: the nearest `pyproject.toml` above each targeted `.py` file (the search stops at the workspace root or a Git
  repository boundary). Each manifest is reported once, on line 1, even when no Python file is otherwise checked.

## 2. Cause of Violation

- `Invalid architecture configuration: <reason>`, where the reason is one of: the TOML does not parse;
  `architecture` is not a table holding only `boundaries` and `commands`; `boundaries` or `commands` is not an
  array of tables; a boundary does not have exactly `name`, `source` and `forbidden_imports`; a boundary name
  is empty or repeated; a `source` or forbidden entry is not a dotted module name; `forbidden_imports` is
  empty; a commands entry does not have exactly `source`; a commands `source` is repeated.

## 3. Remediation

Fix the table as the message says; the formats are in the guides of `RULE-app-forbidden-import` and
`RULE-app-command-signature`. Until then the architecture rules skip the files of that project.

## 4. Configuration

No settings.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-architecture-config] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.

A suppression comment cannot apply: the finding is on the manifest, not on Python source.
