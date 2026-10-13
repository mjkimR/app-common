# app-prebuilt-auth

The user module of the unified authentication prebuilt, built on `app-layer-base`. All capabilities and tables are included by default. Provides the `User` model, layered service/usecase stack, auth dependencies, and FastAPI routers.

> For package installation and `AuthSettings` environment variables, see [setup.md](./setup.md).

## Router Mounting

```python
from fastapi import FastAPI
from app_prebuilt_auth import install_auth

app = FastAPI()
# Mounts password login, current-user/profile reads, and administrator management
install_auth(app)
```

## Protecting Endpoints

Inject auth dependencies into your application routers:

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app_prebuilt_auth.user.deps import get_current_user, on_superuser
from app_prebuilt_auth.user.models import User

router = APIRouter()

CurrentUser = Annotated[User, Depends(get_current_user)]
SuperUser = Annotated[User, Depends(on_superuser)]


@router.get("/me")
async def read_current_user(user: CurrentUser):
    return {"id": str(user.id), "email": user.email}


@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin: SuperUser):
    return {"status": "deleted"}
```

## Sessions, First User, and Lockout

- `POST /users/login/` returns `access_token`, `refresh_token`, and `expires_in`. Exchange the refresh token at
  `POST /users/login/refresh` for a new pair before expiry or on a 401; every exchange extends the session. A refresh
  token dies when its user is deactivated or its password changes.
- An invalid or expired token answers **401** (`INVALID_CREDENTIALS`); **403** means the user may not do that.
- Nothing creates users by itself: call `UserService.ensure_first_user(session)` once at startup. Set
  `FIRST_USER_SYNC_PASSWORD=true` when a secret store is the source of truth for that password.
- Passwords are hashed with Argon2id; bcrypt hashes from earlier versions verify and are upgraded at login.
- Failed logins lock a caller out (429). Override `get_login_caller` behind a proxy so the caller is the address the
  platform wrote, not one the client chose, and `get_login_lockout_listener` to tell an operator.

```python
from app_prebuilt_auth.user.deps import get_login_caller


def cloud_run_caller(request: Request) -> str:
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    return forwarded[-1] if forwarded else (request.client.host if request.client else "unknown")


app.dependency_overrides[get_login_caller] = cloud_run_caller
```


## External login and approval

Use [Google login](google-auth.md) to add optional Google OIDC beside local login.
External registrations require manual approval by default. Set `REGISTRATION_REQUIRE_APPROVAL=false`
only when immediate admission is intentional. Existing/local administrator-created users remain
approved; there is no public password signup route or built-in whitelist.

The host owns migrations and its admin UI. Add `approval_status` and `auth_version` to users, plus
`UserAccessEvent` metadata, before adopting this package revision. Protect business endpoints with
`get_current_user`; it rejects pending, rejected, suspended and version-revoked sessions.
Superadmins manage access through `POST /users/admin/{user_id}/access` with
`{action, expected_version, reason?}` and inspect `/access-events`. Avoid direct DB flag updates for revocation.
