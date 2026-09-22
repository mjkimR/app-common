# app-prebuilt-auth Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-auth"
```

## Configuration (`AuthSettings`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | Key used to sign JWTs (`openssl rand -hex 64`) |
| `FIRST_USER_EMAIL` | **Yes** | — | Initial bootstrap superuser email |
| `FIRST_USER_PASSWORD` | **Yes** | — | Initial bootstrap superuser password |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `10` | Access token lifespan in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `14` | Refresh token lifespan; each refresh issues a new one (sliding session) |
| `FIRST_USER_SYNC_PASSWORD` | No | `false` | Keep the first superuser's password equal to `FIRST_USER_PASSWORD` on every startup |
| `LOGIN_MAX_FAILURES` | No | `5` | Failed logins within the window that lock a caller out |
| `LOGIN_FAILURE_WINDOW_SECONDS` | No | `60` | Window in which failed logins are counted |
| `LOGIN_LOCKOUT_SECONDS` | No | `300` | How long a locked-out caller is refused (HTTP 429) |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_ISSUER` | No | `app-base` | JWT issuer (`iss`) claim |
| `JWT_AUDIENCE` | No | `app-base` | JWT audience (`aud`) claim |
| `JWT_LEEWAY_SECONDS` | No | `10` | Allowed clock-skew tolerance |
