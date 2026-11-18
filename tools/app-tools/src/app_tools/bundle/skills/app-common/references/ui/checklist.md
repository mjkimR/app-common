# UI verification

Use the project's command runner or package scripts before completing a UI change.

- Run Svelte type checking and formatting/lint checks; resolve errors without `any`
  casts or suppressions that hide the problem. Check imports and reactive variables.
- Confirm the [file-size policy](structure.md) passes. Exceptions need an exact
  path, reason, and finite ceiling; remove obsolete exceptions in touched files.
- Preserve loading, empty, and error states and action feedback using the app's
  shared components and `svelte-sonner` where the project uses them.
- Use the app's primitives, semantic token roles (no raw palette or hex for meaning),
  and `cn()` for class merging. Check responsive layout at the affected sizes.
- Status carries a label or icon, not color alone. Token or palette changes keep
  4.5:1 text and 3:1 UI contrast in both themes; run the contrast test.
- After a backend contract change, run `gen:api` and its `--check` mode.
