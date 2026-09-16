# Components & Styling Guidelines

Standard atomic components, composite layouts, and styling tokens.

---

## 1. Atomic Primitives (`$lib/components/ui/`)

All base interactive elements must come from shadcn-svelte (`bits-ui`). **Never create bespoke `<button>` or `<input>` tags.**

| Component | Import Path | Common Usage |
|---|---|---|
| **Button** | `$lib/components/ui/button` | `<Button variant="default\|outline\|ghost\|destructive" size="sm\|default\|lg">` |
| **Card** | `$lib/components/ui/card` | `<Card>`, `<CardHeader>`, `<CardTitle>`, `<CardDescription>`, `<CardContent>`, `<CardFooter>` |
| **Dialog** | `$lib/components/ui/dialog` | Modal dialogs for creation, confirmation, and detail views |
| **Input** | `$lib/components/ui/input` | Standard text/number inputs |
| **Table** | `$lib/components/ui/table` | Data tables with `<TableHeader>`, `<TableRow>`, `<TableHead>`, `<TableCell>` |
| **Tabs** | `$lib/components/ui/tabs` | Tabbed navigation (`<Tabs>`, `<TabsList>`, `<TabsTrigger>`, `<TabsContent>`) |
| **Badge** | `$lib/components/ui/badge` | Tag and status displays (`variant="default\|secondary\|outline\|destructive"`) |
| **ScrollArea** | `$lib/components/ui/scroll-area` | Constrained scroll containers |
| **Sonner** | `$lib/components/ui/sonner` | Toast notification provider (mount in `+layout.svelte`) |

---

## 2. Iconography: Lucide Svelte

**Rule**: All icons must be imported from `@lucide/svelte`.

```svelte
<script lang="ts">
  import Plus from '@lucide/svelte/icons/plus';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import Loader2 from '@lucide/svelte/icons/loader-2';
  import CheckCircle from '@lucide/svelte/icons/check-circle-2';
</script>

<!-- Always set explicit dimensions with Tailwind classes -->
<Plus class="h-4 w-4" />
<Loader2 class="h-4 w-4 animate-spin text-muted-foreground" />
```

---

## 3. Standard Composite Components (`$lib/components/shared/`)

### (1) `PageHeader.svelte`
Standard header section with page title, description, and action button slots.
```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    description?: string;
    actions?: Snippet;
  }

  let { title, description, actions }: Props = $props();
</script>

<div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b pb-5">
  <div>
    <h1 class="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
    {#if description}
      <p class="text-sm text-muted-foreground">{description}</p>
    {/if}
  </div>
  {#if actions}
    <div class="flex items-center gap-2">
      {@render actions()}
    </div>
  {/if}
</div>
```

### (2) `EmptyState.svelte`
Centered placeholder when no data exists.
```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import Inbox from '@lucide/svelte/icons/inbox';

  interface Props {
    title: string;
    description: string;
    action?: Snippet;
  }

  let { title, description, action }: Props = $props();
</script>

<div class="flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center animate-in fade-in-50">
  <div class="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
    <Inbox class="h-6 w-6 text-muted-foreground" />
  </div>
  <h3 class="mt-4 text-base font-semibold text-foreground">{title}</h3>
  <p class="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
  {#if action}
    <div class="mt-4">
      {@render action()}
    </div>
  {/if}
</div>
```

---

## 4. Semantic Color Tokens (Strict Rule)

**NEVER use hardcoded hex values** (e.g. `text-[#333]`, `bg-[#f8f9fa]`).
Always use Tailwind semantic variables defined in `layout.css`:

- Backgrounds: `bg-background`, `bg-card`, `bg-muted`, `bg-accent`
- Text: `text-foreground`, `text-card-foreground`, `text-muted-foreground`
- Borders: `border-border`, `border-input`
- Primary/Destructive: `bg-primary text-primary-foreground`, `bg-destructive text-destructive-foreground`
