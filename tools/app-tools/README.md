# App Tools

Personal app development helper tools and utilities.

## Installation

To add this tool to your project, install it via `uv` from the GitHub repository:

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=tools/app-tools" --dev
```

## Usage

Run the `app-tools` command to access various utilities.

```bash
app-tools [COMMAND]
```

### Features

#### Compact Command Runner (`run`)

Run existing project checks without an additional configuration file:

```bash
app-tools run lint
app-tools run lint --fix
app-tools run check
app-tools run test
app-tools run test --path packages/base/app-error
app-tools run check --path web
```

`--path` selects a directory tree (default: the current directory). Discovery stays
inside that tree: invoking from a package does not expand to the entire repository.
Run from the repository root to select all projects. Python projects are identified
by `[project]` in `pyproject.toml`; uv workspace member/exclusion patterns are respected
when selecting descendants. Node projects are identified by `package.json`. Generated
and hidden directories, tests/fixtures/templates, symlink directories, and nested Git
repositories are not traversed. Selecting a directory explicitly permits running its
own project even when a parent workspace excludes it.

| Task | Python | Node |
| --- | --- | --- |
| `lint` | `ruff format --check .`, then `ruff check .` | `npm run lint` |
| `lint --fix` | `ruff format .`, then `ruff check --fix .` | `npm run lint:fix` |
| `check` | Pyright when an existing Pyright configuration is found | `npm run check` |
| `test` | pytest when a tests directory or pytest configuration exists | `npm run test` |

Each Python command runs in its package directory through `uv run --no-sync`; existing
pytest options, test paths, and plugins remain authoritative. Shared ancestor Pyright
configuration is used with the selected package's `src` (or package directory) as the
target. A package's own Pyright configuration controls its own scope. Unsupported tasks
are reported as `SKIP`; an invocation with no runnable targets fails. Test collection
failures, including pytest exit code 5, are not converted to success.

Node scripts retain their project-defined behavior, including preparatory commands and
E2E tests. Define `lint` as a read-only check and `lint:fix` as the project's explicit fix
command. If a project has `lint` but no `lint:fix`, `lint --fix` fails during planning
before any commands run. The runner does not append guessed flags to compound scripts.

Use individual tools for native arguments, or the generic wrapper for repository scripts:

```bash
app-tools run pytest -- tests/unit -k user -n 0
app-tools run pytest --path packages/base/app-layer-base -- --db-type postgres
app-tools run ruff -- check src tests
app-tools run vitest --path web -- run
app-tools run npm --path web -- run build
app-tools run -- bash scripts/check.sh py fast
app-tools run --raw -- python -c 'print("complete output")'
```

Put wrapper options before `--`; everything after it is passed verbatim. Native relative
paths are relative to `--path`, not the original calling directory. The generic wrapper
executes an argument array without shell expansion; explicitly use `bash -c` for shell
syntax. Individual Python tools are `pytest`, `ruff`, and `pyright`. Node tools are
`vite`, `vitest`, `svelte-check`, `svelte-package`, `eslint`, `prettier`, `tsc`, and
`playwright`; they resolve installed `node_modules/.bin` executables in the selected
directory or its ancestors. `npm` and `uv` can also be invoked directly.

Install dependencies and activate the appropriate Node version before running commands.
The runner does not install dependencies or source nvm. Existing repository recipes can
continue to perform that setup before calling `app-tools run`. There are no profiles,
target aliases, DB defaults, Docker exclusions, or worker defaults added by app-tools;
keep those policies in the project's existing configuration or scripts. In particular,
`run test` does not inherit app-common's `just test` Docker deselection policy.

Output is collected until each command exits. Success produces one line; failure prints
up to 16 KB of output (head and tail when truncated). Complete combined stdout/stderr is
saved in a private OS temporary directory, and every result includes its log path.
Successful architecture warnings are also shown in compact output. Other tools' successful
warnings are retained in the log; the generic renderer does not interpret their formats. `--raw` prints all collected output, including
successful output, after each command finishes. These commands are intended for finite
checks, not interactive shells or watch servers. Logs remain until removed or cleaned by
the OS; they are not written into the repository.

Independent steps continue after a failure. A single command preserves its exit status;
a multi-step task returns 1 if any step failed and reports totals. Ctrl-C stops execution
and terminates the command process group on POSIX systems.

#### Create Code (`create-code`)

Generate boilerplate code for new application features.

**1. Backend Feature (FastAPI Layered Architecture):**
```bash
app-tools create-code feature --name <FeatureName> [--plural <plural_name>] [--prefix <prefix>]
```
- `--name`: Name of the feature in CamelCase (e.g., `Article`, `User`).
- `--plural`: (Optional) Plural name in snake_case (e.g., `articles`). If omitted, it will be auto-generated.
- `--prefix`: (Optional) Directory prefix (defaults to `app/features`).

*Example:*
```bash
app-tools create-code feature --name Article
```

**2. Web Feature (Svelte 5 Runes & shadcn UI):**
```bash
app-tools create-code web-feature --name <FeatureName> [--plural <plural_name>] [--prefix <prefix>]
```
- Generates Svelte 5 state store (`*.svelte.ts`), main view (`*View.svelte`), dialog (`*Dialog.svelte`), and index exports.
- `--prefix`: (Optional) Directory prefix (auto-detects `src/lib/features` or `web/src/lib/features`).

*Example:*
```bash
app-tools create-code web-feature --name Project
```

#### Local Development Linking (`dev`)

Link installed `app-common` packages in downstream projects to a local clone of `app-common` without modifying `pyproject.toml` or `package.json`.

- **Link packages**:
  ```bash
  app-tools dev link
  # Or specify custom path
  app-tools dev link --target-path ../app-common
  ```
- **Check status**:
  ```bash
  app-tools dev status
  ```
- **Unlink & restore original packages**:
  ```bash
  app-tools dev unlink
  ```

#### Update Installed Packages (`update`)

Update every `app-common` Git dependency in the current consumer project's `pyproject.toml` to the latest published release, regenerate `uv.lock`, and synchronize `.venv`:

```bash
app-tools update
```

Preview the latest upgrade first if desired:

```bash
app-tools update --dry-run
```

`--no-sync` skips `.venv` installation. Skills are managed separately through APM; update the skill ref in `apm.yml` and follow the [APM installation workflow](../../../agents/README.md). Package updates do not download, install, or change skills.

---
*More commands will be added as the project evolves.*

## Documentation

For a complete list of commands, usage examples, and details on how code generation and local linking work, please refer to the developer guides:

- **[Local Development Guide](../../../agents/skills/app-common/references/local-dev/index.md)**: Details on local symlinking (`app-tools dev`), backup mechanics, and options.
- **[Package Update Guide](../../../agents/skills/app-common/references/update/index.md)**: Updates downstream projects to a released `app-common` version.
- **[Backend Guide](../../../agents/skills/app-common/references/backend/index.md)**: FastAPI feature code scaffolding (`app-tools create-code feature`).
- **[Svelte UI Guide](../../../agents/skills/app-common/references/ui/index.md)**: Svelte 5 web feature scaffolding (`app-tools create-code web-feature`).

## Offline package guidance

`app-tools guide` lists relevant topics for the current project. Use
`app-tools guide show backend/hooks` to read a document or
`app-tools guide list --all` to discover setup guides for uninstalled packages.
`--project <directory>` selects another project; `--source <app-common-checkout>`
selects local-development documentation. These options precede `list` or `show`.

All documents ship inside app-tools. The command reads manifests and distribution
metadata without importing optional packages, spawning subprocesses, syncing an
environment, or contacting the network. It distinguishes declarations, lock
entries, and installed packages and reports known version mismatches.

In a pre-provisioned offline environment, call `.venv/bin/app-tools guide` directly
or use `uv run --no-sync --offline app-tools guide`. With no CLI installed, the
copied `app-common` skill contains the same references and works by file reads.

## Duration hygiene

Every `run` command warns once with `RUN_SLOW_COMMAND` if an individual subprocess
is still running after 60 seconds. This is wall time per command (including fixtures
and child processes), not per test function or the accumulated task duration. The
warning appears while the command is running, even in compact mode. It never cancels
a command or changes its exit status. Tool-generated warnings retain their own behavior.

```bash
app-tools run test --warn-after 120
app-tools run lint --no-warn
```

`--warn-after` accepts finite nonnegative seconds; `0` disables this warning.
`--no-warn` overrides `--warn-after` and only silences the runner's duration warning.
Put both options before `--` when forwarding native tool arguments.

## Architecture lint

`app-tools check-arch [PATH ...]` emits rule codes, source locations, explanations,
and suggested fixes; `--json` exposes the same diagnostics for agents. Errors
exit with status 1; package-aware advisories are warnings. Enable it after Ruff in `app-tools run lint` (including `--fix`):

```toml
[tool.app-tools]
check-arch = true
```

The nearest explicit ancestor setting wins, stopping at the Git repository boundary.
A package can opt out with `false`. This repository enables it and also runs the check
in `just lint` / `just lint-check`, so CI enforces it. Architecture fixes are manual.

| Code | Check |
| --- | --- |
| `ARCH_ROUTER_REPO_IMPORT` | Router/API imports repository modules, including nested and relative forms |
| `ARCH_SERVICE_COMMIT` | Service invokes `commit()` or `rollback()` |
| `ARCH_HOOK_SUPER_CALL` | Hook methods except `__init__` chain through `super()` |
| `ARCH_ERROR_DEPENDENCY` | `src/app_error` imports a non-standard-library dependency |
| `ARCH_ADAPTER_DEPENDENCY` | An adapter imports a sibling adapter in the source checkout |
| `ARCH_PARSE_ERROR` | A Python source file cannot be parsed or decoded |

Exceptions require the exact code and a reason on the diagnostic's physical line:

```python
session.commit()  # arch: ignore[ARCH_SERVICE_COMMIT] -- Legacy transaction boundary
```

Multiple codes are comma-separated inside brackets. Bare `noqa`, string contents,
and comments without a reason do not suppress architecture diagnostics. For multiline
imports, put the comment on the opening import line. This syntax is independent of
Ruff's suppression syntax. `app_layer_base.base.repos.query_options` is a permitted
router value-object import. The existing Qdrant catalog coupling has an explicit
compatibility exception; removing that dependency needs a separate API change.

These are static, convention-based checks, not a proof of architecture: dynamic
imports, aliases of transaction methods, transitive dependencies, and transitive dependency
manifest relationships are not analyzed. Direct app-common imports are checked against declarations. Tests and migrations are excluded. Package
isolation checks require the source layout; design rationale remains in the guides.

### Package-aware advisories

Architecture errors still fail the command. These advisories have severity `warning`
and keep exit status 0 when no errors exist:

| Code | Guidance |
| --- | --- |
| `ARCH_HTTP_CLIENT_CONSTRUCTION` | Use shared HTTP getters when app-http-client is declared |
| `ARCH_SHARED_CLIENT_CLOSE` | Shared client shutdown belongs to lifespan |
| `ARCH_DIRECT_CURRENT_TIME` | Use UTC time/date utilities when app-layer-base is declared |
| `ARCH_DB_FACTORY_IN_LAYER` | Inject configured sessions into routers/services |
| `ARCH_UNDECLARED_DEPENDENCY` | Declare directly imported app-common packages |
| `ARCH_INVALID_SUPPRESSION` | Remove unused exceptions or correct unknown codes |

JSON includes severity, guide topic, and separate error/warning counts. `run lint`
shows architecture warnings even when the check succeeds in compact mode. The output
is bounded with a full-log pointer. `--no-warn` only disables duration warnings.

The nearest project manifest owns each file. Required and optional dependency
names (including extras and markers) establish applicability; optional groups are
considered declared without evaluating the current environment's selected extras.
Lockfiles and the shared virtualenv do not activate rules. Tests/migrations remain
excluded. Implementation code in app-http-client may create/close clients and the
canonical time utility may read the clock directly.

Import aliases and simple local assignments are resolved conservatively; runtime
rebinding, interprocedural data flow, and dynamic imports are outside this check.
No recommendation rewrites timezone semantics or resource ownership automatically.
The env-spec command's optional integrations are declared in `app-tools[env-spec]`.

Ruff additionally enables `DTZ` timezone checks and `FAST002` for Annotated FastAPI
dependencies; these general rules retain Ruff diagnostics and suppression syntax.
