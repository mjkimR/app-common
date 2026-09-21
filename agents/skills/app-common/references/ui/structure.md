# Frontend file-size policy

Use `@app-common/eslint-config/structure` for authored Svelte and TypeScript source.
The limits are errors: resolve an overage in the change that introduces it instead
of leaving recurring warnings for future runs.

| Source | Maximum counted lines |
| --- | ---: |
| `.svelte` components | 500 |
| `.ts`, including `.svelte.ts` state modules | 400 |
| `src/routes/**/*.{ts,svelte}` | 200 |

The count uses ESLint's core `max-lines` rule: blank lines and JS/TS comment-only
lines are excluded. Markup and styles, including HTML/CSS comments, count toward
the limit; the Svelte parser does not expose those comments to this core rule.
Test/spec files and `.d.ts` declarations are excluded by default. Explicitly exclude
generated/vendor UI and mock fixtures using the consumer's actual paths; do not
exclude authored UI just because it lives in a directory named `ui`.

## Resolving an overage

1. Prefer splitting at a meaningful boundary: cohesive child components, state
   modules, or pure helpers. Keep routes thin. Do not compress formatting or create
   arbitrary fragments merely to reduce the count.
2. If keeping the file together is justified, record an exception with its exact
   `src/` path, a concrete reason, and a finite maximum close to its reviewed size.
   For example, a cohesive 540-line form may have a 550-line ceiling. It passes
   quietly until it exceeds 550, at which point the check fails again.
3. Do not disable `max-lines`, add the authored file to ignores, or use bulk
   suppression as a size exception. Do not automatically raise an exception's
   ceiling to make checks pass. A new or increased ceiling requires an explicit
   rationale in the change, reviewed alongside the code.
4. When editing an excepted file, remove its exception if it now fits the default;
   reduce excessive headroom if it has substantially shrunk. ESLint enforces the
   configured ceiling; it does not automatically remove or lower exceptions.

Line count is a size constraint, not proof of good design. Changes that increase
complexity without increasing lines still need ordinary code review.

## Install and configure

The repository-root npm manifest packages only the shared ESLint implementation;
the UI runtime library is not required. After the implementation is pushed, pin a
full commit containing it (or an immutable release tag), never a sibling checkout
path. Run in the consumer's web directory:

```bash
npm install --save-dev '@app-common/eslint-config@git+https://github.com/mjkimR/app-common.git#<pushed-ref>'
```

Keep ESLint, Svelte, and TypeScript installed in the consumer as peer dependencies.
Commit the manifest and lockfile. Add the preset to the existing flat ESLint config
alongside its correctness and formatting rules:

```javascript
import { structure } from '@app-common/eslint-config/structure';

export default [
  // Existing project configs go here.
  ...structure({
    // Only if these paths contain generated UI and mock fixtures in this project:
    ignores: ['src/lib/components/ui/**', 'src/lib/mocks/**'],
    exceptions: [
      // Example only; omit this entry unless this file needs a reviewed exception.
      {
        file: 'src/lib/features/settings/components/SettingsForm.svelte',
        max: 550,
        reason: 'One cohesive form; keeping the related fields together aids review.'
      }
    ]
  })
];
```

The preset supplies parsers for an untyped size check. Keep any existing Svelte
parser options needed by the project's other rules. Paths are relative to the
consumer's ESLint config directory; put the config in the web project root.
SvelteKit paths such as `src/routes/(app)/projects/[id]/+page.svelte` are supported
as literal exception paths, not globs.

The normal `npm run lint` must execute ESLint and is the enforcement path used by
`app-tools run lint`. For a separate fast check, export the same `structure(...)`
configuration from `eslint.structure.config.js` and import it into the normal
config too; do not duplicate exceptions across two files. No new app-tools command
is needed.
