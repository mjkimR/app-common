# [RULE-app-command-signature] Command Function Shape

## 1. Overview

A command module's public functions are its commands: callers and tests rely on each being an async function
of a typed context and a typed input that returns a typed output, with orchestration kept elsewhere.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: every `commands.py` inside a configured commands `source`, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Each public top-level
  function or class (a name without a leading `_`) must be an undecorated `async def` with exactly two
  positional parameters, no defaults, `*args`, `**kwargs` or keyword-only parameters, and concrete annotations
  on both parameters and the return (not `Any`, `object`, `dict`, `list` or `BaseModel`).

## 2. Cause of Violation

- A public function or class does not have the command shape: `Public command '<name>' must be an undecorated
  async function with typed context, input and output.`

## 3. Remediation

Write `async def operation(ctx: Context, inp: Input) -> Output`. Prefix helpers with `_`, and move usecases or
orchestration to another module. See the `app-common` skill's `references/backend/commands.md`.

## 4. Configuration

Command conventions are opt-in per project, in the nearest `pyproject.toml` above the file:

```toml
[[tool.app-tools.architecture.commands]]
source = "consumer.features"   # dotted module prefix; every commands.py below it is a command module
```

Without the table the rule checks nothing. A malformed table is reported as `RULE-app-architecture-config`.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-command-signature] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
