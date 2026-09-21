# Agent Self-Verification Checklist

Before presenting your solution to the user, run through this verification checklist.

---

## 1. Type & Syntax Self-Healing Loop (Mandatory)

Execute the project type-checker:

```bash
pnpm check
# or
npm run check
```

- [ ] `svelte-check` reported **0 errors**.
- [ ] No `any` casting used to suppress type checking errors.
- [ ] No missing imports or unused reactive variables.

---

## 2. Formatting & Linting

```bash
pnpm lint
# or
npm run lint
```

- [ ] Prettier formatting applied cleanly.
- [ ] Tailwind class names merged properly with `cn()`.
- [ ] [File-size checks](./structure.md) pass: Svelte 500, TypeScript 400, routes 200 counted lines.
- [ ] Any size exception has an exact path, reason, and finite ceiling; no blanket
  suppression or automatic ceiling increase was used. Remove obsolete exceptions
  from files touched by this change.

---

## 3. Visual & UX Standards

- [ ] **Empty States**: If a table or list can be empty, is `<EmptyState>` rendered?
- [ ] **Loading Indicators**: Is there a loading spinner or skeleton while data is fetching?
- [ ] **Toasts & Feedback**: Are success and error toasts triggered via `toast.success()` / `toast.error()`?
- [ ] **No Raw Buttons**: Are all buttons using `<Button>` from `$lib/components/ui/button`?
- [ ] **Semantic Tokens**: Are all colors using Tailwind semantic tokens (`bg-card`, `text-muted-foreground`) instead of arbitrary hex codes?
- [ ] **Responsive Design**: Does the layout adapt gracefully from mobile (`flex-col`) to desktop (`md:flex-row`)?
