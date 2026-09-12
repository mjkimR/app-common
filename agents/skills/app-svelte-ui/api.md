# Type-Safe API Client (`openapi-fetch`)

This architecture enforces **zero type hallucination**. Frontend types are directly compiled from backend OpenAPI specifications.

---

## 1. OpenAPI Generator (`scripts/gen-api.sh`)

Every project must have a script to fetch or compile the FastAPI schema:

```bash
#!/usr/bin/env bash
set -e

# Target backend OpenAPI endpoint
API_URL="${API_URL:-http://localhost:8000/openapi.json}"
OUT_FILE="src/lib/api/schema.d.ts"

echo "Generating TypeScript schema from ${API_URL}..."
npx openapi-typescript "${API_URL}" -o "${OUT_FILE}"

echo "Schema successfully generated at ${OUT_FILE}."
```

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
