# app-prebuilt-user

A drop-in user-management and JWT authentication feature built on [`app-layer-base`](../app-layer-base/README.md). Provides the `User` model, layered service/usecase stack, auth dependencies, and ready-to-mount routers for signup, login and admin management.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-prebuilt-user"
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

`v1_users_router` mounts login (`POST /users/login/`), user (`GET/PUT /users/{user_id}`) and admin routes.

## Public API

- `v1_users_router` (from `app_prebuilt_user.api`) — the composed router
- `get_current_user`, `get_current_superuser`, `on_superuser` (from `app_prebuilt_user.deps`)
- `User`, `UserService`, `UserRepository`, and the schema/usecase classes from their submodules
