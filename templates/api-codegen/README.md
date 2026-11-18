# API codegen template

A copy-and-own generator for frontend API contracts: it splits `openapi-typescript`
declarations by OpenAPI operation tag. It is not an npm package. A project copies the
files once at initial setup, then owns, edits and tests them like its own code; app-common
does not publish, pack or vendor it. The backend application still exports its OpenAPI
document.

The template lives in `templates/` rather than `packages/` because nothing installs it:
`packages/` holds what consumers pin and upgrade, a template is a starting point that
diverges per project. app-common keeps it tested so every copy starts from working code.

## Layout

| Path | Copied | Purpose |
| --- | --- | --- |
| `src/*.ts` | yes | Generator (`generate.ts`, `domains.ts`, `ast.ts`), output sync (`output.ts`), entry (`index.ts`) and CLI (`cli.ts`). |
| `tests/unit`, `tests/integration` | yes | `node:test` suites for partitioning, type compilation and CLI generation/check/cleanup. |
| `tsconfig.json` | yes | Type check for the copied sources (no emit). |
| `package.json`, `package-lock.json`, `eslint.config.js` | no | app-common's own verification harness. |

The sources run directly under Node's TypeScript type stripping (Node 22.18 or later):
imports use `.ts` extensions and only erasable syntax, so there is no build step and no
`dist/`. `tsc --noEmit` with `erasableSyntaxOnly` keeps them that way.

## Copy into a project

1. Choose a pushed app-common commit and copy from a checkout at that commit, keeping
   the `src/` and `tests/` split so relative imports hold:

   ```sh
   mkdir -p web/scripts/api-codegen
   cp -R <app-common>/templates/api-codegen/{src,tests,tsconfig.json} web/scripts/api-codegen/
   ```

2. Replace `<commit>` in the header comment of every copied file with that commit:

   ```ts
   // Copied from app-common <commit> templates/api-codegen; owned and customized by this project.
   ```

   The header records provenance only. The project owns the files from then on: edit
   them freely and do not re-copy over local changes. To take a later fix, compare with
   the template at a newer commit and port it by hand, updating the header.

3. Add the development dependencies to the frontend manifest (keep the project's
   existing versions when present) and commit the lockfile:

   ```sh
   npm install --save-dev openapi-typescript typescript @types/node
   ```

   The frontend manifest must keep `"type": "module"` (the SvelteKit default), and the
   project's Node must be 22.18 or later.

4. Wire the scripts in `web/package.json`, keeping the project's own schema export step:

   ```json
   {
     "scripts": {
       "gen:api": "<export openapi.json> && node scripts/api-codegen/src/cli.ts --input openapi.json --output src/lib/api/generated",
       "check:api": "<export openapi.json> && node scripts/api-codegen/src/cli.ts --input openapi.json --output src/lib/api/generated --check",
       "test:api-codegen": "tsc --noEmit -p scripts/api-codegen/tsconfig.json && node --test scripts/api-codegen/tests/*/*.test.js"
     }
   }
   ```

   Connect the `--check` command and the copied tests to local verification and CI.
   The copied files are authored code: keep them inside the project's
   [file-size policy](../../tools/app-tools/src/app_tools/bundle/skills/app-common/references/ui/structure.md)
   rather than ignoring them as generated.

An exporter script that already runs the backend (Python/uv, temporary directories,
cleanup) can import the API instead of calling the CLI:

```js
import { generateContract, writeContract } from './api-codegen/src/index.ts';

const files = await generateContract(document);
writeContract(files, targetDir, { check: process.argv.includes('--check') });
```

## Behavior

`--input` accepts a local JSON file or an HTTP(S) OpenAPI endpoint. HTTP errors fail
generation and requests time out after 30 seconds. A local export keeps CI independent
of a running backend.

Output consists of `<tag>.d.ts`, `common.d.ts` and `index.d.ts`. Shared schema
dependencies (including recursive references) and unused schemas live in `common`;
domain files contain their routes, operations and schema types. `index` exports
aggregate `paths`, `components` and `operations` for one `openapi-fetch` client. Tags are
discovered from operations; no domain list or schema ownership table is maintained.

`--check` fails for missing, changed or stale declarations and writes nothing. CRLF is
accepted. Generation removes stale declarations carrying the generator's header,
preserves unrelated files and refuses to overwrite authored files or symlinks at
generated filenames. Use a dedicated generated directory.

`generateContract` returns a `Map<filename, declaration>` without file or network side
effects; `writeContract` owns output synchronization and freshness checking.

When migrating a client generated with openapi-typescript's default settings, pass
`--default-non-nullable` (JS: `{ defaultNonNullable: true }`) to keep required properties
with defaults. The template defaults to `false`; keep the choice explicit in the
project's generation and check commands.

For existing `$lib/api/schema` imports, keep an authored re-export outside the generated
directory:

```ts
// src/lib/api/schema.d.ts
export type { paths, components, operations } from './generated';
```

New domain code can import `components` from `./generated/<tag>`. Do not hand-edit
generated declarations or fabricate backend DTOs.

## Backend contract

- Every HTTP operation declares exactly one lowercase kebab-case domain tag.
- All methods on a path share the same tag. `common`, `index` and Windows device names
  are reserved filenames.
- Every operation has a globally unique `operationId`.
- References use local `#/components/schemas/...` targets. External references,
  referenced paths, webhooks and `$defs` are rejected. Inline parameters, request bodies
  and responses are supported. This targets exported FastAPI schemas.

## Development in app-common

`just init-api-codegen` installs the harness dependencies; `just test-api-codegen` runs
ESLint (file-size policy), `tsc --noEmit` and the test suites against the template.
Change the template here only for fixes or improvements every new copy should start
from; existing copies are unaffected until their owners port the change.
