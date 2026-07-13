# `app-layer-base` Base Module Guide

This document explains the core `base` components in the `app-layer-base` foundational workspace package. It provides the essential classes for database models, repositories, services, service hooks, usecases, and exceptions.

---

## 1. Models (`app_layer_base.base.models`)

### Summary
Provides standard SQLAlchemy declarative mixins to ensure consistency across database models.

### `mixin.py`
- **Import**: `from app_layer_base.base.models.mixin import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin`
- **Classes**: `UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`, `TaggableMixin`.
- **Usage**: Inherit from `Base` and the necessary mixins.
  ```python
  from app_layer_base.base.models.mixin import Base, UUIDMixin, TimestampMixin
  
  class User(Base, UUIDMixin, TimestampMixin):
      __tablename__ = "users"
  ```
- **Precautions**: `SoftDeleteMixin` adds an `is_deleted` flag and `deleted_at` timestamp. Our repository queries automatically filter by `is_deleted == False` when fetching active records.

---

## 2. Repositories (`app_layer_base.base.repos`)

### Summary
Provides generic classes to handle standard database CRUD operations using SQLAlchemy async sessions.

### `base.py`
- **Import**: `from app_layer_base.base.repos.base import BaseRepository`
- **Classes**: `BaseRepository[ModelType, CreateSchemaType, PutSchemaType, PatchSchemaType]`
- **Usage**: Automatically handles `get`, `create`, `update`, `delete`, `exists`, and paginated list queries.
- **Precautions**: Configure `is_deleted_column` properly for models that support soft deletion.

---

## 3. Services and Hooks (`app_layer_base.base.services`)

### Summary
Provides the business logic layer with a Hook system to manage operations like validations, external API calls, or event publishing cleanly during CRUD. Hooks are **standalone objects**, not mixins on the service: a service declares one ordered `hooks` tuple, and the service executor runs them.

### `base.py`
- **Classes**: `BaseServiceMixinInterface`, `BaseCreateServiceMixin`, `BaseUpdateServiceMixin`, `BaseDeleteServiceMixin`, `BaseGetServiceMixin`, `BaseGetMultiServiceMixin`.
- **Usage**: A service inherits the operation mixins it needs and declares `hooks = (...)`. For each operation the executor picks the hooks that implement that operation's protocol, enters every hook's context in declaration order, runs the repository call, then unwinds in reverse — so `*_post` methods run in reverse declaration order.
- **Precautions**: A hook never calls `super()` and never calls the next hook; the executor owns the chain. Adding, reordering, or removing a hook therefore cannot silently disable another one.

### `hooks.py`
- **Import**: `from app_layer_base.base.services.hooks import Operation, CreateHook, UpdateHook, DeleteHook, GetHook, GetMultiHook, BaseContextKwargs`
- **Classes**: one protocol per operation — implement only the ones your hook cares about.

  | Protocol | Methods |
  |---|---|
  | `CreateHook` | `create_context`, `create_prepare_fields`, `create_post`, `create_context_multi`, `create_post_multi` |
  | `UpdateHook` | `update_context`, `update_prepare_fields`, `update_post` |
  | `DeleteHook` | `delete_context`, `delete_post`, `delete_context_multi`, `delete_post_multi` |
  | `GetHook` | `get_context`, `get_post` |
  | `GetMultiHook` | `get_multi_context`, `get_multi_prepare_filters`, `get_multi_post` |

- **`Operation`**: every hook method takes one as its first argument. It carries `session`, `context`, `repo` and `state` — a scratch dict scoped to a single service call.
- **Precautions**: Per-operation state belongs on `op.state`, **never** on the hook instance. Hooks are shared across items and across calls, so `self._something = ...` leaks between them.
- **Bulk methods** (`*_multi`): overriding one replaces only *that hook's* per-item behaviour with a single bulk query (e.g. one parent lookup instead of N). It does not affect the other hooks — the executor asks each hook separately, and a hook that has not overridden the bulk method still gets its single-item hook applied to every item.

### Pre-built Hooks
- **`ExistsCheckHook`**: Checks if an entity exists before `update` or `delete`. Raises `NotFoundException` if it fails. Stateless and dependency-free.
- **`UniqueConstraintHook`**: Implement the async generator `constraints(op, data)` to check DB uniqueness before `create` or `update` and prevent duplicates (raises `ConflictException`, HTTP 409).
- **`DomainEventHook`**: Publishes domain events (e.g. `Model.created`) after successful CUD operations. Implement the abstract `publish_event(topic, payload)` to wire it to your transport — it is transport-agnostic and has no message-broker dependency. Override `payload(op, event_type, pk, obj=None)` to enrich the event body.
- **`UserAwareHook`**: Stamps `created_by` / `updated_by` from `context["user_id"]` (use `UserContextKwargs`).
- **`NestedResourceHook(parent_repo, fk_name="parent_id")`**: Scopes every operation to `context["parent_id"]` (use `NestedResourceContextKwargs`) — injects the FK on create, filters lists by parent, and refuses to read/update/delete a child through the wrong parent. `fk_name` accepts a sequence for a composite key.
- **`DetailDeleteResponseHook`**: Puts a human-readable representation of the deleted row on `DeleteResponse.representation`. Implement `represent(obj) -> str`. Applies to `delete` only; it opts out of `delete_multi`, since `MultipleDeleteResponse` has no per-item representation field.
- **Usage**:
  ```python
  from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
  from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHook

  class UserUniqueHook(UniqueConstraintHook[User, BaseContextKwargs]):
      async def constraints(self, op, data):
          yield op.repo.model.email == data.email, "Email already exists."

  class UserService(BaseCreateServiceMixin[...], BaseUpdateServiceMixin[...]):
      hooks = (UserUniqueHook(), ExistsCheckHook())
  ```
  Hooks that need dependencies (a repository, a client) take them as constructor arguments, so build the tuple in `__init__` instead:
  ```python
  def __init__(self, repo: Annotated[ChapterRepository, Depends()], book_repo: Annotated[BookRepository, Depends()]):
      self._repo = repo
      self.hooks = (ChapterUniqueHook(), NestedResourceHook(book_repo, fk_name="book_id"))
  ```

---

## 4. UseCases (`app_layer_base.base.usecases`)

### Summary
Encapsulates single units of application logic.

### `base.py` & `crud.py`
- **Classes**: `BaseGetUseCase`, `BaseGetMultiUseCase`, `BaseCreateUseCase`, `BasePutUseCase`, `BasePatchUseCase`, `BaseDeleteUseCase` (`Put` = full replace, `Patch` = partial update; there is no single "Update" use case).
- **Usage**: Inherit from the matching base and inject the service via `Annotated[Service, Depends()]`; the base `execute` coordinates the transaction.

---

## 5. Dependencies and Filters (`app_layer_base.base.deps`)

### Summary
FastAPI dependencies used for filtering and ordering dynamically via HTTP Query parameters.

### `filters/base.py` & Prebuilt Filters
- **Classes**: `SqlFilterCriteriaBase`, `SimpleFilterCriteriaBase`.
- **Usage**: Binds query parameters (e.g., `?email=test@test.com`) directly to SQLAlchemy expressions.

---

## 6. Exceptions (`app_layer_base.base.exceptions`)

### Summary
Centralized application exceptions to ensure consistent error handling.

### `basic.py`, `db.py`
- **Classes**: `AppException`, `NotFoundException`, `BadRequestException`, `ForbiddenException`, `ConflictException`.
- **Usage**: Throw these directly in Services or Repositories. FastAPI exception handlers catch these and translate them to proper JSON HTTP responses.