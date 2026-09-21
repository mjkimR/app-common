# Svelte UI

Use Svelte 5 runes, SvelteKit, Tailwind v4, shadcn-svelte, and openapi-fetch.
Follow the consumer's existing layout, dependency versions, and commands.

## Working rules

- Use generated OpenAPI types and the typed client in `$lib/api`; do not invent
  backend DTOs or endpoints or replace the client with raw `fetch`. Regenerate the
  schema with the project's API-generation command when its contract changes.
- Keep domain state and async operations in feature-owned `*.svelte.ts` classes.
  Components handle presentation and interaction; routes remain thin wrappers.
- Use existing UI primitives and shared components, `@lucide/svelte` icons, and
  semantic Tailwind tokens. Do not introduce bespoke styled buttons/inputs or
  hardcoded hex colors.
- Run the project's Svelte type check and lint; resolve errors before completion.
  Size failures require a meaningful split or a reasoned, bounded exception, not
  suppression or automatic ceiling increases.

## Read only the relevant reference

| Task | Reference |
| --- | --- |
| Initialize or change project configuration | [Setup](setup.md) |
| Write reactive state or derived values | [Runes](runes.md) |
| Choose components, snippets, icons, or tokens | [Components](components.md) |
| Change API types, client, or schema generation | [API binding](api.md) |
| Configure size checks or resolve an overage | [File-size policy](structure.md) |
| Verify a UI change | [Checklist](checklist.md) |
| Change app-common from a consumer | [Local development](../local-dev/index.md) |

For a new feature, use `app-tools create-code web-feature --name Project`.
It generates a feature state class, view, dialog, and index under `src/lib/features/`.
Keep reusable UI in `src/lib/components/`, cross-feature state in `src/lib/stores/`,
and API bindings in `src/lib/api/`; follow existing consumer paths when they differ.
