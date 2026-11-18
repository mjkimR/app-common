# UI project setup

Treat the consumer's `package.json`, lockfile, config files, and command runner as
sources of truth. Preserve existing versions and package-manager conventions;
installation examples are not instructions to upgrade or downgrade dependencies.

## Required integration points

| Concern | Configuration |
| --- | --- |
| SvelteKit | Use `vitePreprocess()` and the project's deployment adapter. For a static SPA, use `adapter-static` with an `index.html` fallback. |
| Vite | Register `sveltekit()` and `@tailwindcss/vite`. Preserve project ports, proxy routes, and backend URL configuration. |
| Tailwind v4 | Define the semantic token roles and their `@theme inline` mapping in the project's main stylesheet, commonly `src/routes/layout.css`; see [Components](components.md#3-semantic-color-tokens). |
| Primitives | Copy shadcn-svelte-style primitives into `src/lib/components/ui/` (shadcn-svelte CLI or by hand) and own them; match `components.json` aliases and the stylesheet path. Use `@lucide/svelte` icons. |
| API | Use `openapi-fetch` with tag-based types from the copied API codegen; see [API binding](api.md). |
| ESLint | Compose the shared [file-size preset](structure.md) with existing correctness and formatting rules. |

## Initial setup steps

1. Create the SvelteKit app and configure Vite and Tailwind v4 as above.
2. Write the token roles for light and dark themes and map them with `@theme inline`;
   add a [contrast test](components.md#4-contrast) over the token pairs.
3. Copy the primitives the app needs into `src/lib/components/ui/`. They are authored
   code from then on; app-common distributes none.
4. Copy the API codegen template from a pushed app-common commit into
   `web/scripts/api-codegen/`, mark the copied files with the provenance header, add
   `openapi-typescript` and `typescript` as dev dependencies and wire `gen:api`; see
   [API binding](api.md#1-tag-based-openapi-generator-copied-template).
5. Install `@app-common/eslint-config` at the same commit and compose its preset.

Keep these scripts, or their existing project equivalents, connected to local
verification and CI:

- `check`: `svelte-kit sync && svelte-check --tsconfig ./tsconfig.json`
- `lint`: `prettier --check . && eslint .`
- `format`: `prettier --write .`
- `gen:api`: the project's schema export plus the copied generator, producing
  `src/lib/api/generated/`; keep `schema.d.ts` as a type re-export when existing
  imports need it. Connect its `--check` mode to verification/CI.
- The copied generator's own tests and the contrast test.

Reuse the existing `cn` helper. If absent, define it with `clsx` and
`tailwind-merge` rather than manually combining conflicting Tailwind classes:

```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
```
