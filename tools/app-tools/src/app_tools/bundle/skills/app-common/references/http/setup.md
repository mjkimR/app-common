# app-http-client Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-http-client"
```

## Configuration

Settings are read from environment variables (defaults match standard `httpx` settings):

| Variable | Default | Description |
|---|---|---|
| `HTTP_TIMEOUT` | `5.0` | Default request timeout (seconds) |
| `HTTP_MAX_CONNECTIONS` | `100` | Max pooled connections |
| `HTTP_MAX_KEEPALIVE_CONNECTIONS` | `20` | Max idle keep-alive connections |
| `HTTP_KEEPALIVE_EXPIRY` | `5.0` | Keep-alive expiration (seconds) |
