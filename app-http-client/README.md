# app-http-client

A lightweight adapter that manages a single, shared `httpx` client (async and sync) behind a global singleton, so an application reuses one connection pool instead of creating clients ad hoc.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-http-client"
```

## Configuration

All settings are optional and read from environment variables (defaults match httpx):

| Variable | Default | Description |
|---|---|---|
| `HTTP_TIMEOUT` | `5.0` | Default request timeout (seconds) |
| `HTTP_MAX_CONNECTIONS` | `100` | Max concurrent connections in the pool |
| `HTTP_MAX_KEEPALIVE_CONNECTIONS` | `20` | Max idle keep-alive connections |
| `HTTP_KEEPALIVE_EXPIRY` | `5.0` | Seconds before an idle keep-alive connection is closed |

## Usage

Wire the lifespan into your FastAPI app so the pool is opened at startup and closed on shutdown, then resolve the shared client where you need it:

```python
from fastapi import FastAPI
from app_http_client import get_http_client, get_http_sync_client, lifespan_http_client

app = FastAPI(lifespan=lifespan_http_client)


async def call_upstream():
    client = get_http_client()  # shared httpx.AsyncClient
    resp = await client.get("https://example.com")
    return resp.json()


def call_upstream_sync():
    client = get_http_sync_client()  # shared httpx.Client
    return client.get("https://example.com").text
```

Getters lazily initialize the client on first use, so `get_http_client()` also works outside the FastAPI lifespan (e.g. in workers or scripts).

## Public API

- `get_http_client()` — shared `httpx.AsyncClient`
- `get_http_sync_client()` — shared `httpx.Client`
- `lifespan_http_client` — FastAPI lifespan that initializes and closes both clients

## See also

- [Adapter Module Reference](../skill/app-base-developer-skill/docs/reference_adapter.md) — shared adapter conventions and index.
- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_base_guide.md) — how adapters fit the layered app.
