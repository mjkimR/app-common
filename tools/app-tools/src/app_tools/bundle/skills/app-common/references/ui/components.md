# Components & Styling Guidelines

App-owned primitives, composite layouts, semantic token roles and contrast.

---

## 1. Atomic Primitives (`$lib/components/ui/`)

Primitives follow the shadcn-svelte model: their source is copied into the app (the
shadcn-svelte CLI or by hand, on `bits-ui` where it fits) and owned there. No shared
package supplies them; edit the copy instead of wrapping it. **Never create bespoke
styled `<button>` or `<input>` tags**; extend the app's primitive.

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

Use the paths the project already has. Copied primitives count as authored code for
the [file-size policy](structure.md) unless the project deliberately keeps them as
unmodified generator output and says so in its ignores.

---

## 2. Iconography: Lucide Svelte

**Rule**: All icons must be imported from `@lucide/svelte`.

```svelte
<script lang="ts">
  import Plus from '@lucide/svelte/icons/plus';
  import Loader2 from '@lucide/svelte/icons/loader-2';
</script>

<!-- Always set explicit dimensions with Tailwind classes -->
<Plus class="size-4" />
<Loader2 class="size-4 animate-spin text-muted-foreground" />
```

Decorative icons next to a visible label get `aria-hidden="true"`; an icon-only
control needs an accessible name (`aria-label` or visually hidden text).

### Composites (`$lib/components/`)

Keep app-wide composites (page header, empty state, status badge, loading indicator)
in the app. Build them from primitives and tokens; give each one required visible
text where it conveys state, for example:

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

<div class="flex min-h-80 flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
  <div class="flex size-12 items-center justify-center rounded-full bg-muted">
    <Inbox class="size-6 text-muted-foreground" aria-hidden="true" />
  </div>
  <h3 class="mt-4 text-base font-semibold text-foreground">{title}</h3>
  <p class="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
  {#if action}
    <div class="mt-4">{@render action()}</div>
  {/if}
</div>
```

---

## 3. Semantic Color Tokens

Components use **roles**, never colors. Define each role as a CSS custom property in
the app stylesheet for light (`:root`) and dark (`.dark`) themes:

| Role | Use |
|---|---|
| `background` / `foreground` | Page surface and body text |
| `card`, `popover` (+ `-foreground`) | Raised surfaces and their text |
| `muted` / `muted-foreground` | Subdued surfaces; secondary text |
| `accent` / `accent-foreground` | Hover and selected surfaces |
| `primary`, `secondary` (+ `-foreground`) | Main and secondary actions |
| `destructive` / `destructive-foreground` | Irreversible or failed outcomes |
| `success`, `warning`, `info` (+ `-foreground`) | Outcome status |
| `attention` / `attention-foreground` | The person must act or decide |
| `border`, `input`, `ring` | Separators, field outlines, focus ring |

Each token holds a complete CSS color in any format (`oklch()`, `hsl()`, hex,
`color-mix()`). Map roles to Tailwind v4 with `var()` inside `@theme inline`, never as
`hsl(var(--x))` channel fragments:

```css
@import 'tailwindcss';

:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.21 0 0);
  --success: oklch(0.45 0.11 155);
  --success-foreground: oklch(0.98 0 0);
  /* ...every role above, then the same set under .dark */
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-success: var(--success);
  --color-success-foreground: var(--success-foreground);
  /* ...one --color-<role> entry per role */
}
```

Rules:

- **No raw palette for meaning**: no hex/arbitrary values (`text-[#333]`) and no
  Tailwind palette classes (`text-emerald-700`, `bg-red-50`) to express state or
  hierarchy. Add or adjust a role instead.
- **Status pairs**: use a status role as a fill with its `-foreground` text
  (`bg-success text-success-foreground`), or as text and icon on its own tint
  (`border-success/30 bg-success/15 text-success`). Pick role values that pass the
  contrast floors in both uses and both themes.
- **Status is never color-only**: pair it with a visible label, and preferably a
  distinct icon shape per status, so it survives color-vision deficiency, grayscale
  and forced-colors modes.
- The mapping covers every role the components use; a missing role silently falls
  back to nothing.

---

## 4. Contrast

Floors (WCAG 2.2 AA), in light and dark themes:

- **4.5:1** for text, including muted text and status text on its tint.
- **3:1** for UI component boundaries and states that identify a control (input
  borders, focus ring, toggles, icon-only buttons) and for meaningful graphics.

Add an automated contrast test that resolves each foreground/background token pair
(including `success` on its 15% tint over `background`, and every `-foreground` on
its fill) from the stylesheet and fails below the floor. Run it with the other web
checks, so a palette change cannot silently regress readability. Large text may use
the 3:1 large-text threshold only where the design actually renders it large.
