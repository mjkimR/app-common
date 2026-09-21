# UI project setup

Treat the consumer's `package.json`, lockfile, config files, and command runner as
sources of truth. Preserve existing versions and package-manager conventions;
installation examples are not instructions to upgrade or downgrade dependencies.

## Required integration points

| Concern | Configuration |
| --- | --- |
| SvelteKit | Use `vitePreprocess()` and the project's deployment adapter. For a static SPA, use `adapter-static` with an `index.html` fallback. |
| Vite | Register `sveltekit()` and `@tailwindcss/vite`. Preserve project ports, proxy routes, and backend URL configuration. |
| Tailwind v4 | Keep CSS-first semantic tokens in the project's main stylesheet, commonly `src/routes/layout.css`. |
| shadcn-svelte | Match `components.json` aliases and stylesheet path to the project; use `@lucide/svelte` icons and existing primitives. |
| API | Use `openapi-fetch` with generated `openapi-typescript` schemas; see [API binding](api.md). |
| ESLint | Compose the shared [file-size preset](structure.md) with existing correctness and formatting rules. |

Keep these scripts, or their existing project equivalents, connected to local
verification and CI:

- `check`: `svelte-kit sync && svelte-check --tsconfig ./tsconfig.json`
- `lint`: `prettier --check . && eslint .`
- `format`: `prettier --write .`
- API generation: the project's script that produces `src/lib/api/schema.d.ts`

Reuse the existing `cn` helper. If absent, define it with `clsx` and
`tailwind-merge` rather than manually combining conflicting Tailwind classes:

```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
```
