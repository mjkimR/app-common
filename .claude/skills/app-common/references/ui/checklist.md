# UI verification

Use the project's command runner or package scripts before completing a UI change.

- Run Svelte type checking and formatting/lint checks; resolve errors without `any`
  casts or suppressions that hide the problem. Check imports and reactive variables.
- Confirm the [file-size policy](structure.md) passes. Exceptions need an exact
  path, reason, and finite ceiling; remove obsolete exceptions in touched files.
- Preserve loading, empty, and error states and action feedback using existing
  shared components and `svelte-sonner` where the project uses them.
- Use shared buttons/inputs, semantic color tokens, and `cn()` for class merging.
  Check responsive layout at the affected sizes.
