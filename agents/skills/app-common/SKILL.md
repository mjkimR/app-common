---
name: app-common
description: Use or integrate app-common packages and app-tools. Routes to task-specific backend, testing, adapter, and UI guidance; does not apply to unrelated Python, HTTP, or datetime work.
---

# app-common

Read a guide when the current change touches its concern, not merely because its
package is installed. HTTP calls → `http`; DB session/transaction work →
`backend/session`; current-time or date work → `backend/time`. Unrelated tasks need
none of these. The backend guide distinguishes CRUD conventions from non-CRUD import boundaries.
The testing guide offers an HTTP-only plugin for application-owned stores.
Apply backend architecture guidance when working with app-layer-base,
not when using standalone app-error or adapters. Read before editing; lint is a safety
net for omissions and cannot decide design intent.

If the topic is known, open its reference below or run `app-tools guide show <topic>`
directly. Otherwise use `app-tools guide` to discover candidates; do not read every
recommendation. The target package's declared dependencies indicate applicability;
lock entries and installed packages alone do not establish task relevance.

Use the existing executable (`.venv/bin/app-tools` or `uv run --no-sync --offline
app-tools`); do not install tools or fetch guides just to read instructions. For another
project use `guide --project <path>`. Match guide versions to dependency refs; for local
development use `guide --source <checkout>`. The relative references work without CLI.

| Task | Reference / CLI topic |
|---|---|
| Layered backend, feature scaffolding, hooks | [backend](references/backend/index.md); [backend/hooks](references/backend/hooks.md) |
| Non-CRUD command features, execution scopes and conventions | [backend/commands](references/backend/commands.md) |
| Standalone structured errors and advisories | [backend/errors](references/backend/errors.md) |
| DB sessions and transaction ownership | [backend/session](references/backend/session.md) |
| Current UTC time and calendar dates | [backend/time](references/backend/time.md) |
| Database and backend installation | [backend/setup](references/backend/setup.md) |
| Tests, fixtures, deterministic seeders | [testing](references/testing/index.md) |
| Object storage | [storage](references/storage/index.md); [storage/setup](references/storage/setup.md) |
| Vector search | [vector](references/vector/index.md); [vector/setup](references/vector/setup.md) |
| Pooled HTTP client | [http](references/http/index.md); [http/setup](references/http/setup.md) |
| DB-backed semantic search | [search](references/search/index.md) |
| AI model catalog | [ai](references/ai/index.md); [ai/setup](references/ai/setup.md) |
| MCP tool boundaries | [mcp](references/mcp/index.md) |
| User authentication | [user](references/user/index.md); [user/setup](references/user/setup.md) |
| Transactional outbox | [outbox](references/outbox/index.md); [outbox/setup](references/outbox/setup.md) |
| Svelte UI and API binding | [ui](references/ui/index.md); file-size limits and bounded exceptions: [ui/structure](references/ui/structure.md) |
| Modify packages from a consumer project | [local-dev](references/local-dev/index.md) |
| Update released dependencies | [update](references/update/index.md) |

User instructions take precedence over this guidance. For changes to app-common itself, also read the repository's `AGENTS.md` and its local `app-common-contributor` skill when available. Package installation, release lookup, updates, and external-service tests have their own network requirements; offline guide access does not make those operations offline.
