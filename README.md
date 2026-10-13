# app-common

Independent Python foundation packages, adapters, prebuilt services, a Svelte UI
library, and developer tools. Python packages share a `uv` workspace; the UI and
frontend development tooling have their own npm lifecycle.

## Packages

Each package README covers its installation, public API, and usage.

| Category | Package | Purpose |
| --- | --- | --- |
| Base | [app-layer-base](packages/base/app-layer-base/README.md) | CRUD hooks, command/transaction contracts, database and FastAPI infrastructure. |
| Base | [app-testing-base](packages/base/app-testing-base/README.md) | Pytest plugins, DB/HTTP fixtures, and contract assertions. |
| Adapter | [app-file-storage](packages/adapters/app-file-storage/README.md) | Local and S3 object storage. |
| Adapter | [app-document-store](packages/adapters/app-document-store/README.md) | Async Firestore documents with version-checked writes. |
| Adapter | [app-vector-store](packages/adapters/app-vector-store/README.md) | Qdrant storage and filtering with caller-supplied embeddings. |
| Adapter | [app-http-client](packages/adapters/app-http-client/README.md) | Async HTTP clients based on httpx. |
| Adapter | [app-ai-catalog](packages/adapters/app-ai-catalog/README.md) | Embedding/LLM factories and LiteLLM/LangChain clients. |
| Prebuilt | [app-prebuilt-auth](packages/prebuilt/app-prebuilt-auth/README.md) | User and Google login, sessions, approval, administrators, and machine API keys. |
| Prebuilt | [app-prebuilt-outbox](packages/prebuilt/app-prebuilt-outbox/README.md) | Transactional event capture and delivery. |
| Prebuilt | [app-prebuilt-search](packages/prebuilt/app-prebuilt-search/README.md) | Semantic search and explicit incremental indexing. |
| Transport | [app-mcp](packages/transports/app-mcp/README.md) | MCP tool registry, authorization, and error translation. |
| UI | [app-ui-base](packages/ui/app-ui-base/README.md) | Svelte 5 components, state, and Tailwind tokens. |
| Tooling | [app-tools](tools/app-tools/README.md) | The `devkit app` commands (guides, updates, scaffolding, local linking) and the `app-common` devkit bundle (skill, architecture rules, onboarding playbook). |
| Tooling | [@app-common/eslint-config](tools/app-tools/src/app_tools/bundle/skills/app-common/references/ui/structure.md) | Shared frontend size policy, distributed by the root npm package. |
| Tooling | [@app-common/api-codegen](packages/ui/app-ui-api-codegen/README.md) | Tag-based OpenAPI declarations, shared schema types and contract freshness checks. |

## Installation

Install Python packages directly from Git, pinned to one pushed commit:

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/base/app-layer-base"
uv add --dev "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=tools/app-tools"
```

Errors and agent advisories come from [devkit](https://github.com/mjkimR/devkit)'s
`devkit-advisory` package (`devkit.advisory`, standard library only), the runtime
dependency of the packages; `devkit` itself is development tooling that app-tools brings.
Pin every app-common package the project declares to one commit. uv resolves what those
packages depend on (other app-common packages, and `devkit` and `devkit-advisory` at the
revision this repository's root `pyproject.toml` pins) from app-common's own sources at
that commit, so two different commits are a conflicting-URL error. Still copy the `devkit`
and `devkit-advisory` entries of that root `[tool.uv.sources]` into the project's, with the
same revision, and list both as dependencies (a dev dependency is enough; a package that
imports `devkit.advisory` lists `devkit-advisory` in `project.dependencies`, never
`devkit`): a project's source applies only to its direct dependencies, and a declared
`devkit` that nothing brings from Git resolves from PyPI, where an unrelated project owns
the name. `uv run devkit app update` keeps all of this in step afterwards.

## Use in a project

app-tools registers the `app-common` devkit bundle, deployed automatically by
`uv run devkit sync`: the `app-common` skill for Claude Code, Codex and Antigravity, the
architecture rules run by `uv run devkit rules check`, a line in the root `AGENTS.md`, and
the onboarding playbook (`/devkit-playbook app-common onboarding`). A fresh checkout,
cloud agent, or CI environment runs `uv sync` and `uv run devkit sync` to deploy the
assets from installed packages. Run `uv run devkit sync` again after changing
dependencies or the selection. Projects that raise app-common
errors also select devkit's advisory library guide once: `uv run devkit add advisory:python`.

| Command | Purpose |
| --- | --- |
| `uv run devkit app guide list` / `guide show <topic>` | Guides for the packages the project uses, offline |
| `uv run devkit app update [--ref <ref>]` | Pin every app-common package and devkit to one app-common commit, lock, sync and redeploy |
| `uv run devkit app create-code feature\|web-feature --name <Name>` | Scaffold a backend or Svelte feature |
| `uv run devkit app dev link\|unlink\|status` | Use a local app-common checkout without editing manifests |
| `uv run devkit app doctor` / `env-spec --type <type>` | Check the setup; list settings variables |

## Migrating a project from APM and app-error

The app-tools a project installed before the devkit migration cannot make this move:
its `update` reads only requirement URLs and GitHub releases, and the skill APM installed
does not describe devkit. Move once by hand; `uv run devkit app update` takes over after.

1. **Pins.** Set every app-common reference (`[tool.uv.sources]` `rev`, or the `@<ref>` of
   a requirement URL) to the new app-common commit. Copy the `devkit` and
   `devkit-advisory` entries of this repository's root `[tool.uv.sources]` at that commit
   into the project's, and add both to the `dev` dependency group (`devkit-advisory` to
   `project.dependencies` of every package that imports `devkit.advisory`). Drop `app-error` from dependencies and sources.
2. **APM.** Remove the app-common entry from `apm.yml` (`apm.yml`, `apm.lock.yaml` and
   `apm_modules/` too when it was the only one) and delete `.agents/skills/app-common` and
   `.claude/skills/app-common`.
3. **Environment and agents.** `uv lock`, `uv sync`, `uv run devkit sync`,
   `uv run devkit add advisory:python` to deploy the development assets.
4. **Code.** `from app_error import AppError, Actor, Retry` becomes
   `from devkit.advisory import AdvisoryError, Actor, Retry`, and `AppError` becomes
   `AdvisoryError`; `render_mcp()` is `render()`, `ToolResult.from_app_error` is
   `from_advisory_error`, `to_dict(include_advisory=...)` takes a keyword, `target_files`
   is a tuple and exit codes are devkit's `0/1/2`. An error whose mode is `AUTO` (actor
   `TOOL`, retry not `UNSAFE`) must carry a `fix`, or its constructor raises `ValueError`.
5. **Tooling.** `app-tools run <task>` becomes the tool itself (`uv run ruff ...`,
   `uv run pyright ...`, `npm --prefix <dir> run <script>`), wrapped as
   `uv run devkit run -- <command>` when an agent reads the output. `app-tools check-arch`
   becomes `uv run devkit rules check`; delete `[tool.app-tools] check-arch` (the
   `architecture` tables stay) and rename `# arch: ignore[ARCH_X]` to the rule ID
   (`RULE-app-x`, listed in [app-tools](tools/app-tools/README.md#architecture-rules)).
   Every other `app-tools <command>` is `uv run devkit app <command>`, with
   `get-env-spec` renamed `env-spec` and `guide` split into `guide list` and `guide show`.
6. **Verify.** `uv run devkit app doctor` and `uv run devkit rules check`.

## Architecture

The CRUD stack follows `Router → UseCase → Service → Repository`: usecases own
transactions, and services compose ordered hook objects. Non-CRUD applications can
use typed commands and caller-owned transactions without adopting the CRUD stack.
Each package owns its settings; the application composes the settings it needs.
See [backend guides](tools/app-tools/src/app_tools/bundle/skills/app-common/references/backend/index.md).

## Development

Install `just` with `scripts/install-just.sh` (macOS/Linux) or
`scripts/install-just.bat` (Windows). [justfile](justfile) defines available commands
and arguments; start with `just init` or `just init-dev` for optional dependencies. Both
sync the whole workspace into the shared `.venv` (there is no per-package init: a partial
sync would remove the other members and the bundles they ship) and run
`devkit sync`, which generates the ignored local receipts and projected agent assets
from the installed bundles; devkit supports macOS and Linux only. After editing a bundle
source, run `just sync-agents` to redeploy it before running checks.

```bash
just lint
just check
just test            # SQLite; no Docker required
just init-ui
just check-ui
just build-ui
```

`just test-pg` verifies PostgreSQL locking; `just test-docker` runs container-backed
contracts. Both need Docker. `just test-eslint` verifies the shared frontend preset.
`just init-api-codegen` installs the API generator; `just test-api-codegen` runs
its lint, type checks and generation/CLI tests.
SQLite package suites run in separate processes, up to four at a time. Use
`TEST_JOBS=1 just test` for serial execution; PostgreSQL, Docker, and coverage runs
remain serial. All selected packages finish before a failing exit status is returned.
`uv run devkit run -- just test` prints a bounded view and keeps the complete output in
a log file. Contribution rules and test selection are in [AGENTS.md](AGENTS.md).

## Releases

Packages are Git dependencies, not PyPI releases. Use one repository version across
all package `pyproject.toml` files, root/UI/tooling npm manifests and locks, the guide
catalog and both bundle manifests (`bundle.toml`). After updating versions, run
`just sync-agents`, tag and push `vX.Y.Z`; CI creates the GitHub Release only after lint,
type checks, and all three Python test legs pass. Consumers pin a commit rather than
`main`. Moving the devkit pins (`devkit` and `devkit-advisory`, always one devkit
commit) is a release note: consumers receive them through
`devkit app update`.

## Agent guidance

The consumer bundle's sources live in
[tools/app-tools/src/app_tools/bundle](tools/app-tools/src/app_tools/bundle/bundle.toml); the
contributor skill is the repository-only bundle in
[tools/app-common-dev](tools/app-common-dev/pyproject.toml). The
[onboarding playbook](tools/app-tools/src/app_tools/bundle/playbooks/onboard.md) covers a
new FastAPI project.

## Test tiers and source layout

Each package owns `tests/unit/` and `tests/integration/`, mirroring its `src/<package>/`
paths where the owner has subpackages. Flat source modules keep flat tests.
Unit uses doubles at persistence, process, HTTP and vector-store boundaries;
integration uses real implementations, including in-memory SQLite/Qdrant and
in-process API clients. `tests/e2e/` is reserved for actual process-level user
journeys; currently no package has an e2e suite. Shared builders belong in local
`tests/support/`; never import another package's tests or add workspace test paths.

`just test-unit [module]` selects unit; `just test-integration [module]` selects
local integration. `just test` retains all local tests. Empty tiers are reported
explicitly per package. `TEST_TIER` cannot be combined with explicit paths.
Run unit plus relevant integration while iterating, and all tests before completion.
Docker and PostgreSQL remain separate backend dimensions: `just test-docker` and
`just test-pg` retain their real service/locking coverage. A local integration pass
does not substitute for those contracts. `TEST_TIER=integration just test-pg` is
available when testing only PostgreSQL integration.

The shared ESLint policy follows the same tiers: `npm run test:unit` checks option
validation; `npm run test:integration` runs actual ESLint and Svelte/TypeScript
parsers. `just test-eslint` retains both.
