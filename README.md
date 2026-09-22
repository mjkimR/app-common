# app-common

Independent Python foundation packages, adapters, prebuilt services, a Svelte UI
library, and developer tools. Python packages share a `uv` workspace; the UI and
ESLint tooling have their own npm lifecycle.

## Packages

Each package README covers its installation, public API, and usage.

| Category | Package | Purpose |
| --- | --- | --- |
| Base | [app-error](packages/base/app-error/README.md) | Dependency-free errors and agent advisories. |
| Base | [app-layer-base](packages/base/app-layer-base/README.md) | CRUD hooks, command/transaction contracts, database and FastAPI infrastructure. |
| Base | [app-testing-base](packages/base/app-testing-base/README.md) | Pytest plugins, DB/HTTP fixtures, and contract assertions. |
| Adapter | [app-file-storage](packages/adapters/app-file-storage/README.md) | Local and S3 object storage. |
| Adapter | [app-vector-store](packages/adapters/app-vector-store/README.md) | Qdrant storage and filtering with caller-supplied embeddings. |
| Adapter | [app-http-client](packages/adapters/app-http-client/README.md) | Async HTTP clients based on httpx. |
| Adapter | [app-ai-catalog](packages/adapters/app-ai-catalog/README.md) | Embedding/LLM factories and LiteLLM/LangChain clients. |
| Prebuilt | [app-prebuilt-auth](packages/prebuilt/app-prebuilt-auth/README.md) | User and Google login, sessions, approval, administrators, and machine API keys. |
| Prebuilt | [app-prebuilt-outbox](packages/prebuilt/app-prebuilt-outbox/README.md) | Transactional event capture and delivery. |
| Prebuilt | [app-prebuilt-search](packages/prebuilt/app-prebuilt-search/README.md) | Semantic search and explicit incremental indexing. |
| Transport | [app-mcp](packages/transports/app-mcp/README.md) | MCP tool registry, authorization, and error translation. |
| UI | [app-ui-base](packages/ui/app-ui-base/README.md) | Svelte 5 components, state, and Tailwind tokens. |
| Tooling | [app-tools](tools/app-tools/README.md) | Check runner, scaffolding, local linking, updates, and guides. |
| Tooling | [@app-common/eslint-config](agents/skills/app-common/references/ui/structure.md) | Shared frontend size policy, distributed by the root npm package. |

## Installation

Install Python packages directly from Git, pinned to a release tag or pushed commit:

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<ref>#subdirectory=packages/base/app-layer-base"
uv add --dev "git+https://github.com/mjkimR/app-common.git@<ref>#subdirectory=tools/app-tools"
```

## Architecture

The CRUD stack follows `Router → UseCase → Service → Repository`: usecases own
transactions, and services compose ordered hook objects. Non-CRUD applications can
use typed commands and caller-owned transactions without adopting the CRUD stack.
Each package owns its settings; the application composes the settings it needs.
See [backend guides](agents/skills/app-common/references/backend/index.md).

## Development

Install `just` with `scripts/install-just.sh` (macOS/Linux) or
`scripts/install-just.bat` (Windows). [justfile](justfile) defines available commands
and arguments; start with `just init` or `just init-dev` for optional dependencies.

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
SQLite package suites run in separate processes, up to four at a time. Use
`TEST_JOBS=1 just test` for serial execution; PostgreSQL, Docker, and coverage runs
remain serial. All selected packages finish before a failing exit status is returned.
Check output includes a `log:` path with complete diagnostics. Contribution rules
and test selection are in [AGENTS.md](AGENTS.md).

## Releases

Packages are Git dependencies, not PyPI releases. Use one repository version across
all package `pyproject.toml` files, root/UI npm manifests and locks, and the guide
catalog/APM manifest. After updating versions, tag and push `vX.Y.Z`; CI creates the
GitHub Release only after lint, type checks, and all three Python test legs pass.
Consumers should pin a tag or commit rather than `main`.

## Agent guidance

[agents/README.md](agents/README.md) covers APM installation and canonical guide
sources. Consumers use the `app-common` skill; contributors additionally read
`app-common-contributor`. `app-tools guide` recommends topics for the current project;
`app-tools guide show <topic>` opens one. The [onboarding guide](agents/onboard/SKILL.md)
covers a new FastAPI project.

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
