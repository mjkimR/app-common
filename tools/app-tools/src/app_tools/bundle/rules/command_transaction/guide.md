# [RULE-app-command-transaction] Commands Leave the Transaction to Their Caller

## 1. Overview

A command runs in the execution scope its caller supplies (`ctx.tx`); opening, committing or rolling back a
transaction inside it breaks the caller's unit of work.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: every `commands.py` inside a configured commands `source`, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Every call of an attribute
  named `commit`, `rollback`, `begin`, `begin_nested`, `transaction` or `tx`, in private helpers too, is reported.

## 2. Cause of Violation

- A command module controls a transaction: `Command module calls <name>(); its caller owns the execution scope.`

## 3. Remediation

Use the supplied `ctx.tx`. A short, explicit transaction belongs in a usecase with an application policy. See
the `app-common` skill's `references/backend/commands.md`.

## 4. Configuration

Command conventions are opt-in per project, in the nearest `pyproject.toml` above the file:

```toml
[[tool.app-tools.architecture.commands]]
source = "consumer.features"   # dotted module prefix; every commands.py below it is a command module
```

Without the table the rule checks nothing. A malformed table is reported as `RULE-app-architecture-config`.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-command-transaction] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
