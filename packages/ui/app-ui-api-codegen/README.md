# @app-common/api-codegen

Development tooling for frontend API contracts, independent of Svelte and the UI
runtime. Generates `openapi-typescript` declarations by OpenAPI operation tag.
The backend application remains responsible for exporting its OpenAPI document.

## Installation

Build an npm artifact from a **pushed app-common commit** and install the artifact
as a development dependency, using the same artifact distribution workflow as
`@app-common/ui-base`. Record the source commit alongside the artifact; commit the
consumer lockfile to pin npm integrity. npm Git dependencies install the repository
root package, not this nested package.

From a checkout of the chosen published commit:

```sh
npm ci --prefix packages/ui/app-ui-api-codegen
npm pack ./packages/ui/app-ui-api-codegen --pack-destination /path/to/consumer/web/vendor
```

In the consumer's frontend directory:

```sh
npm install --save-dev ./vendor/app-common-api-codegen-0.1.0.tgz
```

## CLI

```sh
npx --no-install app-common-gen-api --input openapi.json --output src/lib/api/generated
npx --no-install app-common-gen-api --input openapi.json --output src/lib/api/generated --check
```

`--input` accepts a local JSON file or HTTP(S) OpenAPI endpoint. HTTP errors fail
generation and requests have a 30-second timeout. Local export is preferable for
CI because it does not require starting the backend. Retain the project's existing
export script, environment and temporary-file cleanup.

Output consists of `<tag>.d.ts`, `common.d.ts` and `index.d.ts`. Shared schema
dependencies (including recursive references) and unused schemas live in `common`;
domain files contain their routes, operations and schema types. `index` exports
aggregate `paths`, `components` and `operations` for a single `openapi-fetch` client. Tags are
discovered from operations; no domain list or schema ownership table is maintained.

`--check` fails for missing, changed or stale generated declarations and does not
write files. CRLF is accepted. Generation removes stale declarations carrying the
generator's header, preserves unrelated files and refuses to overwrite authored
files or symlinks at generated filenames. Use a dedicated generated directory.

When migrating a client previously generated with openapi-typescript's default
settings, pass `--default-non-nullable` (JS API: `{ defaultNonNullable: true }`) to
retain required properties with defaults. The package defaults to `false`, as in
resource-indexer. Keep this policy explicit in the consumer's generation/check
commands so file splitting does not change its existing type contract.

## Backend contract

- Every HTTP operation declares exactly one lowercase kebab-case domain tag.
- All methods on a path share the same tag. `common`, `index` and Windows device
  names are reserved filenames.
- Every operation has a globally unique `operationId`.
- References use local `#/components/schemas/...` targets. External references,
  referenced paths, webhooks and `$defs` are rejected. Inline parameters, request
  bodies and responses are supported. This targets exported FastAPI schemas.

## JavaScript API

```js
import { generateContract, writeContract } from '@app-common/api-codegen';

const files = await generateContract(document);
writeContract(files, targetDir, { check: process.argv.includes('--check') });
```

`generateContract` returns a `Map<filename, declaration>` without file or network
side effects. `writeContract` owns output synchronization and freshness checking.
Project-specific Python/uv execution does not belong in this package.

Keep existing imports working with an authored compatibility entry point outside
the generated directory:

```ts
// src/lib/api/schema.d.ts
export type { paths, components, operations } from './generated';
```

New domain code can import `components` directly from `./generated/<tag>`. Do not
hand-edit generated declarations or fabricate backend DTOs.

## Development

From app-common: `just init-api-codegen` then `just test-api-codegen`. Tests cover
shared/recursive types, domain validation, TypeScript compilation and real CLI
generation/check/cleanup. `npm pack` builds the public JS and declaration artifacts.
