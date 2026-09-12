# @app-common/ui-base

Agent-First foundational UI library for Svelte 5 and SvelteKit applications.

---

## Features

- **Svelte 5 Runes**: Built entirely with `$state`, `$derived`, and reactive classes.
- **Layout Shell**: Responsive `AppShell` with desktop/mobile navigation drawers.
- **Feedback Primitives**: `EmptyState`, `StatusBadge`, `LoadingSpinner`.
- **Global Reactive Stores**: `sessionStore` (auth session token management) and `themeStore` (dark/light theme).
- **Core UI Primitives**: Accessible, customizable `Button`, `Card`, and `Input` components.
- **Design Tokens**: Standard Tailwind CSS variables in `tokens.css`.

---

## Installation & Consumption

In your downstream SvelteKit project (e.g., `web/`):

```bash
# Add as local workspace or git dependency
pnpm add @app-common/ui-base
```

### 1. Import Design Tokens (`src/routes/layout.css`)
```css
@import '@app-common/ui-base/styles';
```

### 2. Use in Svelte Components
```svelte
<script lang="ts">
  import { AppShell, PageHeader, EmptyState, Button, ThemeToggle } from '@app-common/ui-base';
  import { sessionStore } from '@app-common/ui-base';
</script>

<AppShell appName="My App">
  {#snippet headerActions()}
    <ThemeToggle />
  {/snippet}

  <PageHeader title="Dashboard" description="Overview of metrics">
    {#snippet actions()}
      <Button onclick={() => console.log('clicked')}>Action</Button>
    {/snippet}
  </PageHeader>

  <EmptyState
    title="No items found"
    description="Get started by creating your first item."
  />
</AppShell>
```

---

## Development & Building

Inside `packages/ui/app-ui-base`:

```bash
npm install     # Install dependencies
npm run check   # Type check with svelte-check
npm run build   # Package into dist/ with @sveltejs/package
```
