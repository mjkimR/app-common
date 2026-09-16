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
Success warnings are retained in that log; this initial generic renderer does not extract
warnings or tool-specific diagnostics. `--raw` prints all collected output, including
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
