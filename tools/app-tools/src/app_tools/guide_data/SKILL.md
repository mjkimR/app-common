---
name: app-common
description: Build applications with app-common packages (app-layer-base, app-error, app-testing-base, adapters, app-mcp, prebuilt user/outbox, and Svelte UI); use app-tools for scaffolding, local linking, and dependency updates. Applies when using or introducing app-common, not generic FastAPI or Svelte work.
---

# app-common

Read only the guide relevant to the task. Package availability narrows the default recommendations; it does not prevent reading setup guidance for a new package. Apply backend architecture rules only when using `app-layer-base`, not when using standalone `app-error` or adapters.

## Find guidance

When app-tools is already installed, run `app-tools guide` in the target project, then `app-tools guide show <topic>`. Use `app-tools guide --project <path>` for another project and `app-tools guide list --all` to discover all topics. The report distinguishes declared dependencies, lock entries, and packages installed in the project's `.venv`; none is interchangeable with the others. It never installs dependencies or fetches documentation.

In an offline environment, invoke the existing executable directly (for example `.venv/bin/app-tools`); `uv run --no-sync --offline app-tools guide` is another option when that environment is provisioned. If the CLI is absent, read the relative references below directly. Do not install app-tools just to read a guide.

Check the reported document version/source against the project's dependency refs. An unresolved Git ref or mismatched version is not proof of compatibility. For local package development, select the matching checkout with `app-tools guide --source <app-common-checkout>` or read its references directly. Do not fetch a newer guide automatically.

| Task | Reference / CLI topic |
|---|---|
| Layered backend, feature scaffolding, hooks | [backend](references/backend/index.md); [backend/hooks](references/backend/hooks.md) |
| Standalone structured errors and advisories | [backend/errors](references/backend/errors.md) |
| Database and backend installation | [backend/setup](references/backend/setup.md) |
| Tests, fixtures, deterministic seeders | [testing](references/testing/index.md) |
| Object storage | [storage](references/storage/index.md); [storage/setup](references/storage/setup.md) |
| Vector search | [vector](references/vector/index.md); [vector/setup](references/vector/setup.md) |
| Pooled HTTP client | [http](references/http/index.md); [http/setup](references/http/setup.md) |
| AI model catalog | [ai](references/ai/index.md); [ai/setup](references/ai/setup.md) |
| MCP tool boundaries | [mcp](references/mcp/index.md) |
| User authentication | [user](references/user/index.md); [user/setup](references/user/setup.md) |
| Transactional outbox | [outbox](references/outbox/index.md); [outbox/setup](references/outbox/setup.md) |
| Svelte UI and API binding | [ui](references/ui/index.md); follow its task-specific references |
| Modify packages from a consumer project | [local-dev](references/local-dev/index.md) |
| Update released dependencies | [update](references/update/index.md) |

User instructions take precedence over this guidance. For changes to app-common itself, also read the repository's `AGENTS.md` and its local `app-common-contributor` skill when available. Package installation, release lookup, updates, and external-service tests have their own network requirements; offline guide access does not make those operations offline.
