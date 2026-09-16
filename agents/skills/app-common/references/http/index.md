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
