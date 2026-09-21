# Frontend file-size policy

`@app-common/eslint-config/structure` enforces these limits as errors:

| Source | Counted lines |
| --- | ---: |
| `.svelte` | 500 |
| `.ts`, including `.svelte.ts` | 400 |
| `src/routes/**/*.{ts,svelte}` | 200 |

ESLint `max-lines` excludes blank and JS/TS comment-only lines. Markup and styles,
including HTML/CSS comments, count. Tests/specs and `.d.ts` files are excluded;
explicitly exclude actual generated/vendor UI and mock paths, not authored UI.

## Resolve an overage

- Split by responsibility: cohesive child components, state modules, or helpers.
  Do not compress formatting or create arbitrary fragments to meet the limit.
- If keeping a file together is justified, record its exact `src/` path, reason,
  and finite ceiling close to the reviewed size. A 540-line form with a 550-line
  exception passes quietly; at 551 lines it fails again.
- Do not disable the rule, ignore authored files, bulk-suppress it, or automatically
  raise ceilings to pass. New or increased exceptions need a rationale in the change.
- When editing an excepted file, remove its exception if it fits the default and
  reduce excessive headroom after substantial shrinkage. This cleanup is manual.

Size checks do not detect complexity changes that leave the line count unchanged.

## Configure

From the consumer's web directory, install a pushed commit or immutable release tag:

```bash
npm install --save-dev '@app-common/eslint-config@git+https://github.com/mjkimR/app-common.git#<pushed-ref>'
```

The root npm package contains the preset, not the UI library. Keep ESLint, Svelte,
and TypeScript installed as peers and commit the manifest and lockfile. Compose
with existing flat configs; retain parser options needed by other Svelte rules:

```javascript
import { structure } from '@app-common/eslint-config/structure';

export default [
  // Existing configs go here. Paths and exception below are examples.
  ...structure({
    ignores: ['src/lib/components/ui/**', 'src/lib/mocks/**'], // Only if generated/mocks.
    exceptions: [{
      file: 'src/lib/SettingsForm.svelte', max: 550,
      reason: 'Related fields share one validation flow.'
    }]
  })
];
```

Paths are relative to the web-root ESLint config. Exception paths are literal,
including SvelteKit `[id]` and `(group)` segments. Normal `npm run lint` must run
ESLint; `app-tools run lint` uses that script. If adding a separate structure check,
share its config with normal lint rather than duplicating exceptions.
