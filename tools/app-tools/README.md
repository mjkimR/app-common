# app-tools

The app-common development tooling, built on [devkit](https://github.com/mjkimR/devkit):

- the **`devkit app`** command group (entry point `devkit.commands`), and
- the **`app-common` devkit bundle** (entry point `devkit.bundles`, `src/app_tools/bundle/`),
  deployed automatically by `devkit sync`: the `app-common` skill, the architecture rules,
  the onboarding playbook and a guidance line in the root `AGENTS.md`.

## Installation

A development dependency of the consumer project, pinned to the app-common commit its
other app-common packages use, next to `devkit-agt` and `devkit-advisory` at the revision app-common pins:

```bash
uv add --dev "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=tools/app-tools"
uv run devkit sync
```

List both as dependencies too (a dev dependency is enough), at the same revision as app-common's pins (uv rejects two URLs for one package): a project's source applies only to its direct dependencies, and a declared `devkit-agt` that nothing brings from Git does not resolve: no package index hosts it. `devkit app update` adds them when missing. A fresh clone and CI run `uv run devkit sync --locked`, which restores the managed copies from the committed receipt without rewriting committed files.

Run every command from the project environment (`uv run devkit ...`): a separately
installed devkit does not see the project's packages.

## Commands

All commands follow devkit's agent-first output contract: one `[KIND: ...]` fact per
stdout line, or one JSON object with `--format json`; advisories (`APP_*` codes) on stderr;
exit `0` success, `1` a negative result, `2` could not run.

| Command | What it does |
| --- | --- |
| `devkit app guide list [--all] [--project P] [--source CHECKOUT]` | Guide topics for the packages the project declares or installs, with the declared, locked and installed state. Offline: no network, subprocess or package import. |
| `devkit app guide show <topic>` | One guide; setup guides of packages that are not installed are readable too. |
| `devkit app update [--ref REF] [--dry-run] [--no-sync]` | Resolve `REF` (default `main`) to a commit; pin every app-common dependency to it (requirement URLs and `[tool.uv.sources]`, workspace members included) and `devkit-agt` and `devkit-advisory` to the revision app-common pins there; then `uv lock`, `uv sync` and `devkit sync`. A failed lock restores the manifests. |
| `devkit app dev link\|unlink\|status [--target-path P] [--dry-run]` | Replace installed app-common packages with symlinks into a local checkout (backups as `.bak`), restore them, or report their state. |
| `devkit app doctor [--project P]` | Declared app-common packages, whether the bundle is deployed, APM leftovers and the database URL. |
| `devkit app create-code feature\|web-feature --name Name [--plural p] [--prefix dir] [--dry-run]` | Scaffold a backend CRUD feature (and register its router) or a Svelte 5 web feature; existing directories are refused. |
| `devkit app env-spec --type app\|auth\|file_storage\|file_storage_local\|file_storage_s3\|vector_db` | The environment variables of an app-common settings class, with types and defaults (secrets hidden). Needs the package installed; `app-tools[env-spec]` installs all of them. |

Long-running checks are not app-specific: wrap them with `devkit run -- <command>` for a
bounded view and a complete log.

## Architecture rules

`devkit rules check [paths]` runs one rule per convention; `devkit rules explain <id>` prints
its guide and `devkit rules test [id]` runs its tests. Tests, `migrations/` and `alembic/`
are not checked.

| Rule | Severity | Check |
| --- | --- | --- |
| `RULE-app-router-repo-import` | error | A router/API module imports a repository module |
| `RULE-app-service-commit` | error | A service calls `commit()` or `rollback()` |
| `RULE-app-hook-super-call` | error | A hook method other than `__init__` chains through `super()` |
| `RULE-app-adapter-dependency` | error | An adapter imports a sibling adapter (app-common source checkout) |
| `RULE-app-forbidden-import` | error | An import crosses a boundary declared in `[[tool.app-tools.architecture.boundaries]]` |
| `RULE-app-command-signature` | error | A public command in an opted-in `commands.py` is not `async def op(ctx: C, inp: I) -> O` |
| `RULE-app-command-transaction` | error | A command module controls transactions |
| `RULE-app-architecture-config` | error | `tool.app-tools.architecture` is malformed |
| `RULE-app-parse-error` | error | A Python file cannot be parsed |
| `RULE-app-http-client-construction` | warning | A package declaring app-http-client constructs httpx clients |
| `RULE-app-shared-client-close` | warning | Application code closes the shared HTTP client |
| `RULE-app-direct-current-time` | warning | A package declaring app-layer-base reads the clock directly |
| `RULE-app-db-factory-in-layer` | warning | A router or service builds a DB engine or session factory |
| `RULE-app-undeclared-dependency` | warning | An app-common package is imported but not declared |
| `RULE-app-invalid-suppression` | warning | An `# arch: ignore[...]` names no finding on its line |

A justified exception names the rule and a reason on the reported line:

```python
session.commit()  # arch: ignore[RULE-app-service-commit] -- Legacy transaction boundary
```

Several rules are comma-separated inside the brackets; a comment without a reason, bare
`noqa` and text inside strings suppress nothing. Put the comment on the opening line of a
multi-line import. A project turns a rule off, changes its severity or excludes paths in
`[rules]` of `.devkit/config.toml`.

The checks are static and convention-based: dynamic imports, aliases of transaction
methods and transitive dependencies are not analyzed. The nearest `pyproject.toml` owns
each file; its declared dependencies (extras and groups included) enable the
package-aware warnings, while lock files and the shared environment do not.
`app_layer_base.base.repos.query_options` is a permitted router import.

## Development

Each rule is one plugin package of the bundle, `src/app_tools/bundle/rules/<slug>/`, in
devkit's rule layout: `rule.py` subclasses `ArchitectureRule` with the rule's ID, `guide.md`
is the guide `devkit rules explain` prints (overview, cause, remediation, configuration,
exceptions), and `tests/test_rule.py` loads the folder with `devkit.rules.testing.load_rule`
and checks it on files it writes. The checks themselves live in `app_tools.architecture`
(`scan_files` and the rule catalog `RULES`): one AST pass serves every rule, because a
suppression comment and `RULE-app-invalid-suppression` need all findings of a line. A new
rule adds a catalog entry, its finding in the scanner, a package and a `[[assets]]` entry in
`bundle.toml`; `tests/unit/architecture/test_rules.py` checks that they stay in step.

The rule tests run with the package's tests (`just test app-tools`, which collects `src/`
too) and, against the deployed copies, with `just rules-test`. After changing anything
under `src/app_tools/bundle/`, run `just sync-agents` in the repository root and commit the
updated receipt and projections with the change.
