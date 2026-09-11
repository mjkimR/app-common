---
name: app-prebuilt-services
description: Guide for mounting and customizing production-ready prebuilt features in app-common (app-prebuilt-user, app-prebuilt-outbox). Covers user authentication and JWT login flows, role-based dependencies, transactional outbox pattern event capture via OutboxHook, row locking, and transport-agnostic relay workers.
---

# app-prebuilt-services

This skill provides integration recipes for prebuilt domain components: authentication/user management (`app-prebuilt-user`) and reliable event delivery (`app-prebuilt-outbox`).

---

## 1. User Management & Authentication (`app-prebuilt-user`)

Provides the complete `User` model, layered service/usecase stack, OAuth2 password flow with JWT tokens, and admin management endpoints.

### Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/prebuilt/app-prebuilt-user"
# OAuth2 password form login requires python-multipart in the host app:
uv add python-multipart
```

### Configuration (`AuthSettings`)
| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | Secret for signing JWTs (`openssl rand -hex 64`) |
| `FIRST_USER_EMAIL` | **Yes** | — | Email of bootstrap superuser |
| `FIRST_USER_PASSWORD` | **Yes** | — | Initial password of bootstrap superuser |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `10` | Access token lifespan |

### Mounting Routers
```python
from fastapi import FastAPI
from app_prebuilt_user.api import v1_users_router

app = FastAPI()
# Mounts /users/login, /users/me, /users/register, and admin CRUD
app.include_router(v1_users_router, prefix="/api/v1")
```

### Protecting Application Endpoints
Inject authenticated user dependencies into custom domain routers:

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app_prebuilt_user.deps import get_current_user, on_superuser
from app_prebuilt_user.models import User

router = APIRouter()

CurrentUser = Annotated[User, Depends(get_current_user)]
SuperUser = Annotated[User, Depends(on_superuser)]

@router.get("/profile")
async def get_my_profile(user: CurrentUser):
    return {"id": str(user.id), "email": user.email}

@router.delete("/system/purge")
async def admin_purge(admin: SuperUser):
    return {"status": "purged"}
```

---

## 2. Transactional Outbox Pattern (`app-prebuilt-outbox`)

Guarantees atomic message delivery: domain events are saved in the **exact same database transaction** as business data writes, then a background relay publishes them to any broker (FastStream, RabbitMQ, Kafka, Webhook, etc.).

### Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/prebuilt/app-prebuilt-outbox"
```

### Architecture & Lifecycle
1. **Capture**: Attach an `OutboxHook` to your domain service's `hooks` tuple. Whenever a record is created, updated, or deleted, an outbox entry is written in the same transaction.
2. **Relay**: The `scheduler_lifespan` runs background worker jobs using `SELECT ... FOR UPDATE SKIP LOCKED` so multiple replicas never process the same event concurrently.
3. **Recovery**: An automated zombie-resolver cleans stuck events or marks exhausted ones as dead-letter records.

### Step 1: Attach `OutboxHook` to a Service

```python
from app_prebuilt_outbox.hooks import OutboxHook, OutboxHookEventTypeDict
from app_prebuilt_outbox.repo import OutboxRepository
from app_prebuilt_outbox.models import Outbox
from app_layer_base.base.services.base import BaseService

BOOK_EVENTS: OutboxHookEventTypeDict = {
    "CREATE": "BOOK_CREATED",
    "UPDATE": "BOOK_UPDATED",
    "DELETE": "BOOK_DELETED",
}

class BookOutboxHook(OutboxHook[Book]):
    def payload(self, op: str, obj: Book, identity: str) -> dict:
        return {
            "book_id": str(obj.id),
            "title": obj.title,
            "operation": op,
        }

class BookService(BaseService[Book, BookCreate, BookUpdate]):
    # Attach hook: outbox repository is passed to the constructor
    hooks = (
        BookOutboxHook(
            repo=OutboxRepository(Outbox),
            event_types=BOOK_EVENTS,
            aggregate_type="Book",
        ),
    )
```

### Step 2: Configure the Background Relay

Inject your transport callable into `scheduler_lifespan`:

```python
from functools import partial
from fastapi import FastAPI
from app_prebuilt_outbox.scheduler import scheduler_lifespan, make_faststream_publisher

# With FastStream broker:
publisher = make_faststream_publisher(broker)

# Or a custom publisher:
# async def publisher(event_type: str, event: DomainEvent) -> None:
#     await my_queue.send(event_type, event.payload)

app = FastAPI(lifespan=partial(scheduler_lifespan, publisher=publisher))
```
