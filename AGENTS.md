# app-common: agent guide

See [README](README.md) for packages and installation. Read
[app-common-contributor](agents/dev-skills/app-common-contributor/SKILL.md) when
contributing here; use the consumer `app-common` skill for package integration.

## Boundaries and architecture

- Python sources live in `packages/<category>/<package>/src/` or `tools/<tool>/src/`;
  tests belong in each package's `tests/`, never under `src/`.
- app-error has no third-party dependencies. Adapters must not depend on sibling
  adapters. Each package owns its settings; applications compose them explicitly.
- CRUD flow is `Router → UseCase → Service → Repository`. Business hooks are
  standalone objects in an ordered `hooks` tuple: enter in order, unwind in reverse.
  Hooks never call one another or chain hook methods with `super()`.
- Non-CRUD features use typed `Command`, `execute_command`, and `TransactionScope`
  with caller-owned transactions. Read the `backend/commands` guide and enforce
  the opt-in architecture and registry/scope contracts.
- Use `Annotated[T, Depends(...)]` for FastAPI dependencies.
- Keep justfile recipes thin; shared shell logic belongs in `scripts/`.
- Make only requested changes. Do not commit `.env`, log secrets/PII, or commit/push
  without explicit instructions. No emojis in commits, comments, or documentation.

## Verification

Read [justfile](justfile) for exact targets and defaults. Run lint, type checks,
and relevant tests before finishing code changes; add behavior tests when needed.

| Change | Checks |
| --- | --- |
| Python package | `just lint <module>`, `just check <module>`, package tests |
| PostgreSQL locking/outbox | `just test-pg` (Docker required; SQLite does not verify row locking) |
| External storage contracts | `just test-docker` (Docker required) |
| UI library | `just check-ui`, `just build-ui` after `just init-ui` |
| Shared ESLint policy | `just test-eslint` |

`just test` runs SQLite tests without Docker. For a focused package, use
`uv run pytest packages/base/app-layer-base/tests`. Each package owns its pytest
configuration; there is no workspace-wide `pythonpath`. Load shared fixtures with
`pytest_plugins = ["app_testing_base.plugin"]` in the top-level conftest; never copy
DB fixtures or share a `tests/` directory through `sys.path`.

Mark container-dependent tests `docker` or gate PostgreSQL-only tests with
`--db-type postgres`; do not silently skip required backend coverage. CI runs all
three Python test legs. `just test-cov` includes container tests and emits HTML in
`htmlcov/`; coverage is diagnostic, not a CI threshold.

For frontend size failures, follow the `ui/structure` guide: split by responsibility
or declare an exact-file, reasoned, finite ceiling. Do not disable the rule or
raise ceilings automatically. Generated primitives are excluded, authored UI is not.

## Shared guides and consumer development

Canonical consumer documents live in `agents/skills/app-common/`; app-tools'
`guide_data` points there. Edit only the canonical files. [Agent setup](agents/README.md)
covers APM packaging and offline provisioning; contributors read `agents/dev-skills/`
directly. Standalone app-error use does not imply the backend architecture rules.

When testing local packages in a consumer, run `app-tools dev link` there. Never
put local dependency paths in its manifests. Finish with `app-tools dev unlink`
and `app-tools dev status` to verify restored installations. Follow the
[release checklist](README.md#releases) when updating repository versions.

## Documentation language

Use English for README/AGENTS files and technical, operational, or agent instructions.
Korean is for documents under `docs/` intended for the user's review, including
analysis, research, and their review indexes. Preserve localized examples, literal
UI labels, and the configured language of planning artifacts.
