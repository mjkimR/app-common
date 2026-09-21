# Setup & Project Configuration

Guide for initializing and configuring a standard SvelteKit UI project within the `app-common` ecosystem.

---

## 1. Core Dependencies

Every web project should pin standard dependencies:

```json
{
  "name": "web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch",
    "lint": "prettier --check . && eslint .",
    "format": "prettier --write .",
    "gen-api": "bash ./scripts/gen-api.sh"
  },
  "dependencies": {
    "openapi-fetch": "^0.13.0"
  },
  "devDependencies": {
    "@lucide/svelte": "^0.474.0",
    "@sveltejs/adapter-static": "^3.0.8",
    "@sveltejs/kit": "^2.16.0",
    "@sveltejs/vite-plugin-svelte": "^5.0.3",
    "@tailwindcss/vite": "^4.0.0",
    "bits-ui": "^1.0.0",
    "clsx": "^2.1.1",
    "mode-watcher": "^0.5.1",
    "openapi-typescript": "^7.6.1",
    "prettier": "^3.4.2",
    "prettier-plugin-svelte": "^3.3.3",
    "prettier-plugin-tailwindcss": "^0.6.11",
    "shadcn-svelte": "^1.0.0",
    "svelte": "^5.19.0",
    "svelte-check": "^4.1.4",
    "svelte-sonner": "^0.3.28",
    "tailwind-merge": "^3.0.1",
    "tailwind-variants": "^0.3.1",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.3",
    "vite": "^6.0.7"
  }
}
```

---

## 2. Configuration Files

### ESLint file-size checks

Install and compose the shared `@app-common/eslint-config/structure` preset as
described in [structure.md](./structure.md). Keep `npm run lint` in local checks and
CI. Overages fail the check; use a meaningful split or a documented per-file ceiling
instead of persistent warnings or disabling the rule.

### `components.json` (shadcn-svelte)
```json
{
  "$schema": "https://shadcn-svelte.com/schema.json",
  "tailwind": {
    "css": "src/routes/layout.css",
    "baseColor": "neutral"
  },
  "aliases": {
    "components": "$lib/components",
    "utils": "$lib/utils",
    "ui": "$lib/components/ui",
    "hooks": "$lib/hooks",
    "lib": "$lib"
  },
  "typescript": true,
  "registry": "https://shadcn-svelte.com/registry",
  "style": "nova",
  "iconLibrary": "lucide"
}
```

### `svelte.config.js`
```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      fallback: 'index.html',
    }),
    alias: {
      $lib: './src/lib',
    },
  },
};

export default config;
```

### `vite.config.ts`
```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.API_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 3. Utility Function (`src/lib/utils.ts`)

Standard classnames helper for shadcn-svelte:

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```
