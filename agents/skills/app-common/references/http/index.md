# app-http-client

Shared, connection-pooled `httpx` client singleton for async and sync calls, preventing socket exhaustion and connection leaks.

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
    client = get_http_client()  # shared httpx.AsyncClient
    resp = await client.get("https://api.example.com/data")
    return resp.json()


# Sync request (for background threads or non-async contexts)
def call_api_sync():
    client = get_http_sync_client()  # shared httpx.Client
    resp = client.get("https://api.example.com/data")
    return resp.json()
```

## Ownership and lint

Use this guide when changing outbound HTTP behavior in a project that uses
app-http-client. Merely having the package installed does not require loading it.

The returned clients are shared. Do not use `with`/`async with` around them or close
them in request code; lifespan owns shutdown. A dedicated client for separate auth,
transport, or lifecycle requirements can be appropriate and needs its own cleanup.

`ARCH_HTTP_CLIENT_CONSTRUCTION` advises using the shared getters instead of directly
constructing httpx clients. `ARCH_SHARED_CLIENT_CLOSE` detects direct or locally assigned
shared-client closure and context-manager use. Both are warnings, support reasoned
inline `arch: ignore[...]` exceptions, and leave transport-specific decisions to you.
