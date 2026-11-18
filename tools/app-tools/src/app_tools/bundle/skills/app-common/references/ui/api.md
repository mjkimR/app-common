# Type-Safe API Client (`openapi-fetch`)

This architecture enforces **zero type hallucination**. Frontend types are directly compiled from backend OpenAPI specifications.

---

## 1. Tag-based OpenAPI generator (copied template)

The generator is a copy-and-own template, not a package: app-common keeps it tested at
`templates/api-codegen/` and a project copies it once at initial setup. It builds
`openapi-typescript` declarations by operation tag, extracts shared schema references
into `common.d.ts`, and exports aggregate `paths`, `components` and `operations` from
`generated/index.d.ts`. Keep schema export in the consumer project: its script knows
how to compose the FastAPI application without starting a server.

Setup, from a checkout of a pushed app-common commit (the template README has details):

1. Copy `templates/api-codegen/src/`, `tests/` and `tsconfig.json` into
   `web/scripts/api-codegen/`, keeping the `src/` and `tests/` split.
2. Replace `<commit>` in each copied file's header with that commit:
   `// Copied from app-common <commit> templates/api-codegen; owned and customized by this project.`
3. Add `openapi-typescript`, `typescript` and `@types/node` as dev dependencies and
   commit the lockfile. The sources run under Node 22.18+ type stripping; no build step.
4. Wire `gen:api` (and a `--check` variant) plus the copied tests into the project's
   scripts and CI.

The project owns the copy: customize it in place, never install, vendor or link it,
and never point manifests at a sibling checkout. To adopt a later template fix, port
it by hand and update the header's commit.

```sh
node scripts/api-codegen/src/cli.ts --input /path/to/openapi.json --output src/lib/api/generated
node scripts/api-codegen/src/cli.ts --input /path/to/openapi.json --output src/lib/api/generated --check
```

An HTTP(S) OpenAPI URL is also supported, but local export makes CI independent of
server availability. `--check` compares without writing and reports missing,
changed or stale declarations. Generation removes only stale files carrying the
generator's header; authored files are preserved. Use a dedicated output directory.

The backend contract is explicit: each operation needs one lowercase kebab-case
tag and a unique `operationId`; every method on the same path must share the tag.
`common`, `index` and Windows device names are reserved. References must target
local `#/components/schemas/...`; external/component response or parameter refs,
referenced paths, webhooks and `$defs` are rejected. Missing tags/references fail
rather than silently producing incomplete types.

For existing `$lib/api/schema` imports, replace the old monolithic generated file
with an authored re-export outside the generated directory:

```typescript
// src/lib/api/schema.d.ts
export type { paths, components, operations } from './generated';
```

Use the aggregate for one typed client. Feature code can import `components` from
`$lib/api/generated/<tag>` to use domain types. Tags determine the file inventory;
do not maintain a manual domain or schema ownership mapping.

Existing project exporters can retain Python/uv invocation, temporary directories
and cleanup, replacing only the generation/check stage:

```javascript
import { generateContract, writeContract } from './api-codegen/src/index.ts';

const files = await generateContract(document);
writeContract(files, targetDir, { check: process.argv.includes('--check') });
```

When migrating the default openapi-typescript policy, pass
`--default-non-nullable` (JS: `{ defaultNonNullable: true }`) to retain required
default-valued fields. The template otherwise defaults to `false`.

---

## 2. API Client Instance (`src/lib/api/client.ts`)

Create a singleton client initialized with the generated `paths` schema:

```typescript
import createClient from 'openapi-fetch';
import type { paths } from './schema';

export const apiClient = createClient<paths>({
  baseUrl: '', // Uses current origin or Vite proxy
});

// Optional: Global request/response middleware
apiClient.use({
  async onRequest({ request }) {
    // Add auth headers if token is present
    const token = localStorage.getItem('access_token');
    if (token) {
      request.headers.set('Authorization', `Bearer ${token}`);
    }
    return request;
  },
  async onResponse({ response }) {
    if (response.status === 401) {
      // Handle session expiry
      console.warn('Session expired. Redirecting to login...');
    }
    return response;
  },
});
```

---

## 3. Type-Safe Query & Mutation Patterns

### GET Requests
TypeScript enforces exact route strings and parameter names:

```typescript
// Query with path params and query params
const { data, error, response } = await apiClient.GET('/api/v1/projects/{id}', {
  params: {
    path: { id: 'proj-123' },
    query: { include_details: true },
  },
});

if (error) {
  // `error` is strongly typed to the FastAPI HTTP error response!
  toast.error(error.detail || 'Failed to fetch project');
  return;
}

// `data` is automatically typed as ProjectResponse
console.log(data.name);
```

### POST Requests
```typescript
const { data, error } = await apiClient.POST('/api/v1/projects', {
  body: {
    name: 'New Project',
    description: 'Managed by AI agent',
  },
});
```

### DELETE Requests
```typescript
const { error } = await apiClient.DELETE('/api/v1/projects/{id}', {
  params: {
    path: { id: projectId },
  },
});
```

### Refresh cancellation and polling

Keep small async helpers in the app (for example `src/lib/async.ts`); app-common does
not supply them. A refresh helper aborts the previous request and discards late
results; cancellation resolves to `undefined` and other errors propagate. A polling
helper waits for a read to complete before scheduling the next one and returns
cleanup that aborts the pending request. Handle errors in the poll callback, return
the cleanup from the owning `$effect`, and keep UI state in the feature class, not
in the helpers.
