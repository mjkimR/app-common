# app-http-client

Shared, connection-pooled `httpx2` client singleton for async and sync calls, preventing socket exhaustion and connection leaks.

> For package installation and environment variables, see [setup.md](./setup.md).

## Lifespan Wiring

Register the lifespan so the connection pool is initialized at startup and closed on shutdown:

```python
from fastapi import FastAPI
from app_http_client import lifespan_http_client

app = FastAPI(lifespan=lifespan_http_client)
```

## Usage

```python
from app_http_client import get_http_client, get_http_sync_client


# Async request (preferred in FastAPI endpoints and services)
async def call_api():
    client = get_http_client()  # shared httpx2.AsyncClient
    resp = await client.get("https://api.example.com/data")
    return resp.json()


# Sync request (for background threads or non-async contexts)
def call_api_sync():
    client = get_http_sync_client()  # shared httpx2.Client
    resp = client.get("https://api.example.com/data")
    return resp.json()
```

## httpx2 and legacy httpx

The shared clients are `httpx2` objects, and `httpx2` classes are distinct from `httpx` ones:
`except httpx.HTTPError` does not catch an error raised through `get_http_client()`. Import
request, response, transport and exception types from `httpx2` in code that uses these clients.
Third-party libraries that still depend on `httpx` may stay in the environment; catch their own
exception types around their calls, and never pass a shared client where a library expects an
`httpx` client.

## Ownership and lint

Use this guide when changing outbound HTTP behavior in a project that uses
app-http-client. Merely having the package installed does not require loading it.

The returned clients are shared. Do not use `with`/`async with` around them or close
them in request code; lifespan owns shutdown. A dedicated client for separate auth,
transport, or lifecycle requirements can be appropriate and needs its own cleanup.

`RULE-app-http-client-construction` advises using the shared getters instead of directly
constructing httpx2 clients. `RULE-app-shared-client-close` detects direct or locally assigned
shared-client closure and context-manager use. Both are warnings, support reasoned
inline `arch: ignore[...]` exceptions, and leave transport-specific decisions to you.
