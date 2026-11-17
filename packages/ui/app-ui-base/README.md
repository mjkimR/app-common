# @app-common/ui-base

Agent-First foundational UI library for Svelte 5 and SvelteKit applications.

---

## Features

- **Svelte 5 Runes**: Built entirely with `$state`, `$derived`, and reactive classes.
- **Layout Shell**: Responsive `AppShell` with desktop/mobile navigation drawers.
- **Feedback Primitives**: `EmptyState`, `StatusBadge`, `LoadingSpinner`.
- **Global Reactive Stores**: `sessionStore` (auth session token management) and `themeStore` (dark/light theme).
- **Core UI Primitives**: Accessible, customizable `Button`, `Card`, and `Input` components.
- **Design Tokens**: Semantic color tokens, status roles included, in `tokens.css`, with
  an optional Tailwind v4 mapping in `theme.css`.

---

## Installation & Consumption

In your downstream SvelteKit project (e.g., `web/`):

```bash
# Add as local workspace or git dependency
pnpm add @app-common/ui-base
```

### 1. Import Design Tokens (`src/routes/layout.css`)
```css
@import 'tailwindcss';
@import '@app-common/ui-base/styles'; /* token values (CSS custom properties) */
@import '@app-common/ui-base/theme';  /* Tailwind v4 @theme inline mapping */
@source '../../node_modules/@app-common/ui-base/dist';
@custom-variant dark (&:where(.dark, .dark *)); /* themeStore toggles .dark */
```

Components use only Tailwind utilities on semantic tokens (`bg-primary`,
`text-success`, ...); none of them reads a token through `hsl(var(--x))`. `@source`
lets Tailwind generate the classes used inside the package.

### Token contract

- Each color token (`--background`, `--primary`, `--success`, ...) holds a complete
  CSS color. Defaults are `hsl()` values in `@layer base`; override any subset with
  unlayered `:root` / `.dark` rules in any color format (`oklch()`, hex, ...).
- `theme.css` maps each token to Tailwind as `--color-<name>: var(--<name>)` and
  derives `--radius-sm`..`--radius-xl` from `--radius`. Skip it to keep your own
  `@theme inline` block, or redefine single entries in a later `@theme inline`. Your
  mapping must include every color the components use, status roles included.
- Status roles: `success`, `warning`, `info` and `destructive` describe an outcome;
  `attention` means the person must act or decide. Each has a `-foreground` pair for
  fills. A role is also used as text color on its own 15% tint, so keep overrides at
  WCAG AA contrast for both uses.

### Status and loading primitives

- `StatusBadge` takes `variant` (`default`, `outline`, `info`, `success`, `warning`,
  `attention`, `destructive`) and a visible `label`. Status variants add an
  `aria-hidden` icon with a distinct shape per role; pass `icon={false}` to hide it.
  Color never carries the status alone.
- `LoadingSpinner` takes a `label` for its `role="status"` announcement (default
  `Loading...`); pass a localized string. Under `prefers-reduced-motion: reduce` the
  ring stops rotating.
- `Button` spaces icon and label with `gap-2` (`gap-1.5` for `sm`). Icons without
  their own `size-*` class are sized to the button (`size-4`, `size-3.5` for `sm`).

### Changes since commit 120f7a5

- Token values changed from bare HSL triplets (`0 0% 100%`) to complete colors
  (`hsl(0 0% 100%)`). A mapping written as `hsl(var(--x))` must become `var(--x)`.
- New tokens: `--success`, `--warning`, `--info`, `--attention` and their
  `-foreground` pairs, plus the `@app-common/ui-base/theme` export.
- `--destructive` defaults are darker in light mode and lighter in dark mode (with a
  dark `--destructive-foreground`) to reach AA contrast as text and as a fill.
- `StatusBadge` uses the status tokens instead of the raw Tailwind palette, gains the
  `info` and `attention` variants and the `icon` prop, and shows an icon by default.
- `LoadingSpinner` gains `label` and stops rotating under reduced motion.
- `Button` adds icon gap and sizing; the `default` variant uses `shadow-sm` like the
  other variants instead of Tailwind v4's deprecated bare `shadow`.

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

## Async refresh and polling

Import `LatestRequest` and `startPolling` from `@app-common/ui-base/async`. A
`LatestRequest` cancels the previous read and suppresses late results; `run(read,
signal?)` returns `undefined` when cancelled. Non-cancellation errors propagate.
`startPolling(read, interval)` starts immediately, waits for each read before
scheduling the next, and returns a cleanup function that aborts the pending read
and clears its timer. Poll callbacks own error reporting and must handle failures.
These helpers have no Svelte lifecycle dependency; call cleanup from the owning
effect's teardown.

## Development & Building

From the repository root:

```bash
just init-ui      # Install root ESLint tooling and UI dependencies
just check-ui     # File-size lint and svelte-check
just build-ui     # Package into dist/ with @sveltejs/package
just test-eslint  # Verify the shared size policy
```

The UI uses the shared [file-size policy](../../../tools/app-tools/src/app_tools/bundle/skills/app-common/references/ui/structure.md).
Authored components are checked; oversized files need a meaningful split or a
documented per-file ceiling. Run `npm run lint` inside this package for size checks alone.
