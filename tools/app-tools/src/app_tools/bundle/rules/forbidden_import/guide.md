# [RULE-app-forbidden-import] Declared Import Boundaries

## 1. Overview

A project declares which modules a part of its code must not import (the application layer must not import
the server, a domain package must not import SQLAlchemy), and the rule enforces it without relying on file
or package naming conventions.

- **Phase and severity**: `linter`, `error`: fails `devkit rules check` (exit 1) and the commit gates that run it.
- **What is checked**: the modules inside a declared boundary's `source`, among the targeted `.py` files, except those under a `tests`, `alembic` or `migrations` directory. Files whose
  project has an invalid `tool.app-tools.architecture` table are skipped until it is fixed
  (`RULE-app-architecture-config`). Absolute, relative, star and
  function-level imports all count: `import a.b`, `from a import b`, `from .. import b`.

## 2. Cause of Violation

- A module inside a boundary imports a forbidden module:
  `Boundary '<name>': '<module>' imports forbidden module '<forbidden>'.`

## 3. Remediation

Move the dependency behind the boundary: depend on an interface or a command the outer layer provides, and
keep the forbidden module in the layer that owns it. Command boundaries are described in the `app-common`
skill's `references/backend/commands.md`.

## 4. Configuration

Boundaries live in the nearest `pyproject.toml` above the file (the search stops at the workspace root or a
Git repository boundary):

```toml
[[tool.app-tools.architecture.boundaries]]
name = "application"                              # nonempty, unique
source = "consumer.features"                      # dotted module prefix the boundary governs
forbidden_imports = ["consumer.server", "sqlalchemy"]  # nonempty list of dotted module prefixes
```

The module name is the file's path below that manifest, without a leading `src/`. A malformed table is reported as
`RULE-app-architecture-config`.

## 5. Exceptions

Record a justified exception on the reported line as an inline comment naming the exact rule and a reason:
`# arch: ignore[RULE-app-forbidden-import] -- <reason>`. A comment without the reason, inside a string or naming another rule suppresses nothing, and
`RULE-app-invalid-suppression` reports one that no longer matches a finding. Leave whole paths out with
`exclude` under `[rules]` in `.devkit/config.toml`; `[rules.severity_overrides]` changes the severity for the
whole project.
