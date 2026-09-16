# Svelte 5 Runes Pattern Guide

Svelte 5 replaces legacy store subscriptions (`$store`, `writable`) and `let` reactivity with explicit **Runes**.

---

## 1. Core Runes Reference

| Rune | Purpose | Example |
|---|---|---|
| `$state(val)` | Declare deep reactive state | `let count = $state(0);` |
| `$derived(expr)` | Pure computed value | `let doubled = $derived(count * 2);` |
| `$derived.by(() => ...)` | Complex computed value | `let filtered = $derived.by(() => list.filter(...));` |
| `$props()` | Component inputs & events | `let { title, onclick }: Props = $props();` |
| `$effect(() => ...)` | Side effects after render (logging, DOM sync) | Run DOM listeners, timers, etc. |

---

## 2. The Class-Based State Store Pattern (`*.svelte.ts`)

**Rule**: Put all domain business logic, API requests, and mutating operations inside class instances in `.svelte.ts` files, NEVER embedded inside `.svelte` components.

### Example: Domain State Class
```typescript
// src/lib/features/project/project.svelte.ts
import { apiClient } from '$lib/api/client';
import type { components } from '$lib/api/schema';
import { toast } from 'svelte-sonner';

type Project = components['schemas']['ProjectResponse'];
type ProjectCreate = components['schemas']['ProjectCreate'];

export class ProjectState {
  // Reactive fields
  items = $state<Project[]>([]);
  selectedId = $state<string | null>(null);
  loading = $state(false);
  filter = $state('');

  // Derived state
  filtered = $derived(
    this.filter.trim() === ''
      ? this.items
      : this.items.filter((p) =>
          p.name.toLowerCase().includes(this.filter.toLowerCase())
        )
  );

  selected = $derived(this.items.find((p) => p.id === this.selectedId));

  // Async Actions
  async load() {
    this.loading = true;
    try {
      const { data, error } = await apiClient.GET('/api/v1/projects');
      if (error) {
        toast.error('Failed to load projects');
        return;
      }
      if (data) this.items = data;
    } finally {
      this.loading = false;
    }
  }

  async create(body: ProjectCreate) {
    const { data, error } = await apiClient.POST('/api/v1/projects', {
      body,
    });
    if (error) {
      toast.error('Failed to create project');
      return null;
    }
    if (data) {
      this.items = [data, ...this.items];
      toast.success(`Project "${data.name}" created`);
      return data;
    }
  }
}
```

---

## 3. Critical Anti-Patterns for AI Agents

### ❌ Anti-Pattern 1: Destructuring Props Reactivity
```svelte
<!-- WRONG: Loses reactivity on prop change -->
<script lang="ts">
  let { count } = $props<{ count: number }>();
  let doubled = count * 2; // NOT reactive!
</script>

<!-- CORRECT: Use $derived -->
<script lang="ts">
  let { count } = $props<{ count: number }>();
  let doubled = $derived(count * 2);
</script>
```

### ❌ Anti-Pattern 2: Overusing `$effect` for Computed State
Never use `$effect` to synchronize state values. That causes layout thrashing and infinite loops.
```svelte
<!-- WRONG: Don't set state in $effect for calculations -->
<script lang="ts">
  let total = $state(0);
  $effect(() => {
    total = price * quantity; // ❌ BAD!
  });
</script>

<!-- CORRECT: Always use $derived -->
<script lang="ts">
  let total = $derived(price * quantity); // ⭕ GOOD!
</script>
```

### ❌ Anti-Pattern 3: Legacy `$:` Labels or Writable Stores
Do **NOT** use `$: reactive_declaration` or `writable()` from `svelte/store`. All code in this repository uses Svelte 5 runes.
