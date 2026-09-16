# app-prebuilt-user

Drop-in user authentication and management module built on `app-layer-base`. Provides the `User` model, layered service/usecase stack, auth dependencies, and FastAPI routers.

> For package installation and `AuthSettings` environment variables, see [setup.md](./setup.md).

## Router Mounting

```python
from fastapi import FastAPI
from app_prebuilt_user.api import v1_users_router

app = FastAPI()
# Mounts /users/login, /users/register, /users/me, and admin management CRUD
app.include_router(v1_users_router, prefix="/api/v1")
```

## Protecting Endpoints

Inject auth dependencies into your application routers:

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app_prebuilt_user.deps import get_current_user, on_superuser
from app_prebuilt_user.models import User

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
