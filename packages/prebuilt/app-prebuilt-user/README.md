# app-prebuilt-user

A drop-in user-management and JWT authentication feature built on [`app-layer-base`](../../base/app-layer-base/README.md). Provides the `User` model, layered service/usecase stack, auth dependencies, and ready-to-mount routers for signup, login and admin management.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-user"
```

> The host application provides `fastapi`; the login route uses OAuth2 form login, so also install `python-multipart` in the host app.

## Configuration

`AuthSettings` (read from the environment):

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — (required) | Key used to sign JWTs (`openssl rand -hex 64`) |
| `FIRST_USER_EMAIL` | — (required) | Email of the bootstrap superuser |
| `FIRST_USER_PASSWORD` | — (required) | Password of the bootstrap superuser |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ISSUER` | `app-base` | `iss` claim |
| `JWT_AUDIENCE` | `app-base` | `aud` claim |
| `JWT_LEEWAY_SECONDS` | `10` | Clock-skew tolerance |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10` | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Refresh-token lifetime; every refresh issues a new one, so this is how long an unused session survives |
| `FIRST_USER_SYNC_PASSWORD` | `false` | Keep the first superuser's password equal to `FIRST_USER_PASSWORD` on every startup |
| `LOGIN_MAX_FAILURES` | `5` | Failed logins within the window that lock a caller out |
| `LOGIN_FAILURE_WINDOW_SECONDS` | `60` | Window in which failed logins are counted |
| `LOGIN_LOCKOUT_SECONDS` | `300` | How long a locked-out caller is refused (HTTP 429) |

## Usage

Mount the router and reuse the auth dependencies to protect your own endpoints:

```python
from typing import Annotated
from fastapi import FastAPI, Depends
from app_prebuilt_user.api import v1_users_router
from app_prebuilt_user.deps import get_current_user, on_superuser
from app_prebuilt_user.models import User

app = FastAPI()
app.include_router(v1_users_router, prefix="/api/v1")


@app.get("/api/v1/me")
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return {"id": str(current_user.id), "email": current_user.email}


@app.get("/api/v1/admin/ping", dependencies=[Depends(on_superuser)])
async def admin_only():
    return {"ok": True}
```

`v1_users_router` mounts login (`POST /users/login/`, `POST /users/login/refresh`), user
(`GET/PUT /users/{user_id}`) and admin routes.

### Sessions

`POST /users/login/` returns a short-lived access token and a refresh token. A client sends the access token as
`Authorization: Bearer ...` and exchanges the refresh token at `POST /users/login/refresh` for a new pair before
the access token expires (`expires_in` seconds) or when a request answers 401. Each exchange extends the session,
so it ends only after `REFRESH_TOKEN_EXPIRE_DAYS` without use. A refresh token stops working when its user is
deactivated or its password changes. An invalid or expired token answers **401**; 403 is kept for a request the
user is not allowed to make.
Deactivation also rejects existing access tokens on protected endpoints immediately.

### Passwords

New hashes are Argon2id. A bcrypt hash written by an earlier version still verifies and is replaced by an Argon2id
hash the next time its user logs in. The login use case commits this change before issuing the token pair,
so the refresh token refers to the persisted password hash.

### The first superuser

Nothing creates users by itself. Call `UserService.ensure_first_user(session)` once at startup to create the
superuser from `FIRST_USER_EMAIL` / `FIRST_USER_PASSWORD` when it is missing. With `FIRST_USER_SYNC_PASSWORD=true`
the account's password also follows the setting on every startup, for deployments whose secret store is the source
of truth: change the secret, restart, and the old password and its sessions stop working.

### Failed-login lockout

After `LOGIN_MAX_FAILURES` failed logins within the window a caller is refused with 429 for
`LOGIN_LOCKOUT_SECONDS`, right password or not. Counters live in the process. Two dependencies adapt it to a
deployment through `app.dependency_overrides`:

- `get_login_caller`: who is logging in. The default is the peer address; behind a proxy return the address the
  platform itself wrote (for example the last entry of `X-Forwarded-For` on Cloud Run), never a client-chosen one.
- `get_login_lockout_listener`: an async callable invoked once when a caller is locked out, to tell an operator.

## Public API

- `v1_users_router` (from `app_prebuilt_user.api`) — the composed router
- `get_current_user`, `get_current_superuser`, `on_superuser`, `get_login_caller`, `get_login_lockout_listener` (from `app_prebuilt_user.deps`)
- `User`, `UserService`, `UserRepository`, and the schema/usecase classes from their submodules

## See also

- [App Prebuilt User Skill](../../../agents/skills/app-common/references/user/index.md) — user auth, JWT login flow, and admin CRUD.
- [App Backend Core Skill](../../../agents/skills/app-common/references/backend/index.md) — layered architecture and dependencies.

### Application-owned transactions

Override `get_user_transaction` from `app_prebuilt_user.database` with a dependency
returning `partial(AsyncTransaction, your_session_maker)` to bind every user usecase
to the host's DB. Also override `app_layer_base.core.database.deps.get_session`
for token refresh and current-user lookup. Close authentication reads before
starting a separate SQLite write transaction; hosts can override `get_current_user`
with a short-lived lookup that delegates validation to the original function.
