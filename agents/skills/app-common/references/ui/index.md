# app-svelte-ui

Agent-First & Friendly UI development guidelines for **Svelte 5 (Runes)**, **SvelteKit**, **Tailwind CSS**, **shadcn-svelte (bits-ui)**, and **openapi-fetch**.

> **References & Guides**:
> - [setup.md](./setup.md): Project initialization, standard dependencies, and config files.
> - [runes.md](./runes.md): Svelte 5 Runes standard patterns (`$state`, `$derived`, Class State).
> - [components.md](./components.md): shadcn-svelte atomic components, Lucide icons, and layout tokens.
> - [api.md](./api.md): Schema-first API binding with `openapi-fetch` and `gen-api.sh`.
> - [checklist.md](./checklist.md): Agent self-verification checklist before finishing tasks.

---

## 5 Critical Rules for AI Agents

When generating or editing UI code, you MUST follow these 5 rules without exception:

1. **Schema-First API Binding (No Hallucinated Types)**:
   - Never write manual TypeScript interfaces for backend DTOs.
   - Never use raw `fetch()` or guess API endpoints.
   - Always run/use `scripts/gen-api.sh` and consume `src/lib/api/schema.d.ts` via `src/lib/api/client.ts`.
2. **Svelte 5 Runes Class Pattern**:
   - Encapsulate domain reactive states and async operations inside dedicated classes (`*.svelte.ts`).
   - Keep `.svelte` markup files clean and focused on layout and interaction.
3. **Strict Use of Atomic UI Components**:
   - Never write raw `<button>` or `<input>` with custom styling.
   - Use `$lib/components/ui/button`, `$lib/components/ui/card`, `$lib/components/ui/dialog`, etc.
   - Only import icons from `@lucide/svelte`.
   - Never use arbitrary hex colors (e.g. `bg-[#1e293b]`). Use semantic Tailwind tokens (`bg-card`, `text-muted-foreground`).
4. **Thin Routing Layer**:
   - `src/routes/**/+page.svelte` must remain thin wrappers that import and render domain views from `$lib/features/` or `$lib/components/views/`.
5. **Self-Healing Verification Loop**:
   - Always run `pnpm check` (or `npm run check`) after editing code to verify type correctness with `svelte-check`.
   - Fix all type and syntax errors before presenting the solution.

---

## Standard Directory Structure

```text
src/
├── app.d.ts
├── app.html
├── routes/                     # [Thin Routing Layer]
│   ├── +layout.svelte          # AppShell, Sonner (toaster), Global Dialogs
│   ├── layout.css              # Tailwind & design tokens
│   ├── +page.svelte            # Mounts feature views
│   └── [domain]/
│       └── +page.svelte
└── lib/                        # [Domain & UI Logic]
    ├── api/                    # 1. Type-Safe API Client
    │   ├── schema.d.ts         # Generated OpenAPI schema (Do NOT edit manually)
    │   ├── client.ts           # openapi-fetch client instance
    │   └── index.ts
    ├── stores/                 # 2. Global State (Svelte 5 Runes)
    │   ├── session.svelte.ts   # Auth & user session
    │   └── theme.svelte.ts     # Dark/Light theme state
    ├── components/
    │   ├── ui/                 # 3. Atomic Components (shadcn-svelte)
    │   │   ├── button/
    │   │   ├── card/
    │   │   ├── dialog/
    │   │   ├── input/
    │   │   ├── table/
    │   │   └── sonner/
    │   └── shared/             # 4. Composite UI Components
    │       ├── AppShell.svelte
    │       ├── PageHeader.svelte
    │       ├── EmptyState.svelte
    │       └── StatusBadge.svelte
    ├── features/               # 5. Domain Features & Views
    │   └── [feature]/
    │       ├── [feature].svelte.ts  # State store class
    │       ├── components/          # Feature-specific subcomponents
    │       ├── [Feature]View.svelte # Main feature view
    │       └── index.ts
    └── utils/                  # 6. Utilities (cn, formatters)
        └── utils.ts
```

---

## Quick Reference Patterns

### 1. Svelte 5 Reactive Class Store
```typescript
// src/lib/features/task/task.svelte.ts
import { apiClient } from '$lib/api/client';
import type { components } from '$lib/api/schema';
import { toast } from 'svelte-sonner';

type Task = components['schemas']['TaskResponse'];

export class TaskState {
  items = $state<Task[]>([]);
  selectedId = $state<string | null>(null);
  loading = $state(false);

  selected = $derived(this.items.find((t) => t.id === this.selectedId));

  async load() {
    this.loading = true;
    try {
      const { data, error } = await apiClient.GET('/api/v1/tasks');
      if (error) {
        toast.error('Failed to load tasks');
        return;
      }
      if (data) this.items = data;
    } finally {
      this.loading = false;
    }
  }

  async remove(id: string) {
    const { error } = await apiClient.DELETE('/api/v1/tasks/{id}', {
      params: { path: { id } },
    });
    if (error) {
      toast.error('Failed to delete task');
      return;
    }
    this.items = this.items.filter((t) => t.id !== id);
    toast.success('Task deleted');
  }
}
```

### 2. Feature View Component
```svelte
<!-- src/lib/features/task/TaskView.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { TaskState } from './task.svelte';
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import EmptyState from '$lib/components/shared/EmptyState.svelte';
  import { Button } from '$lib/components/ui/button';
  import Plus from '@lucide/svelte/icons/plus';

  const state = new TaskState();

  onMount(() => {
    state.load();
  });
</script>

<div class="space-y-6">
  <PageHeader title="Tasks" description="Manage your team tasks">
    {#snippet actions()}
      <Button onclick={() => { /* open modal */ }}>
        <Plus class="mr-2 h-4 w-4" />
        New Task
      </Button>
    {/snippet}
  </PageHeader>

  {#if state.loading}
    <div class="p-8 text-center text-muted-foreground">Loading...</div>
  {:else if state.items.length === 0}
    <EmptyState
      title="No tasks found"
      description="Create your first task to get started."
    />
  {:else}
    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {#each state.items as task (task.id)}
        <div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
          <h3 class="font-semibold">{task.title}</h3>
          <p class="text-sm text-muted-foreground">{task.description}</p>
        </div>
      {/each}
    </div>
  {/if}
</div>
```

---

## Scaffolding New Features

Generate scaffolding using `app-tools`:
```bash
uv run app-tools create-code web-feature --name Project
```
This generates:
- `src/lib/features/project/project.svelte.ts`
- `src/lib/features/project/ProjectView.svelte`
- `src/lib/features/project/components/ProjectDialog.svelte`
- `src/lib/features/project/index.ts`

---

## Modifying UI Base Packages Locally (`app-tools dev`)

When developing frontend features that require changes to `@app-common/ui-base`:
1. Use `uv run app-tools dev link` to temporarily symlink `node_modules/@app-common/ui-base` to the local `app-common` repository without editing `package.json`.
2. After finishing and pushing changes, **always run `uv run app-tools dev unlink`** to restore original packages.
3. For core contribution details, see the `agents/dev-skills/app-common-contributor/SKILL.md` in the local app-common checkout (when available).
