# app-prebuilt-user Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-user"
# OAuth2 password form login requires python-multipart in the host app:
uv add python-multipart
```

## Configuration (`AuthSettings`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | Key used to sign JWTs (`openssl rand -hex 64`) |
| `FIRST_USER_EMAIL` | **Yes** | — | Initial bootstrap superuser email |
| `FIRST_USER_PASSWORD` | **Yes** | — | Initial bootstrap superuser password |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `10` | Access token lifespan in minutes |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_ISSUER` | No | `app-base` | JWT issuer (`iss`) claim |
| `JWT_AUDIENCE` | No | `app-base` | JWT audience (`aud`) claim |
| `JWT_LEEWAY_SECONDS` | No | `10` | Allowed clock-skew tolerance |
