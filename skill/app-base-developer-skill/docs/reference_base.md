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
Provides the business logic layer with a powerful Hook system to manage operations like validations, external API calls, or event publishing cleanly during CRUD.

### `base.py`
- **Classes**: `BaseServiceMixinInterface`, `BaseCreateHooks`, `BaseUpdateHooks`, `BaseDeleteHooks`.
- **Usage**: Services should inherit from hook mixins and implement specific logic using context managers (`_context_create`, etc.).

### Pre-built Hooks
- **`ExistsCheckHooksMixin`**: Checks if an entity exists before `update` or `delete`. Raises `NotFoundException` if it fails.
- **`UniqueConstraintHooksMixin`**: Provides an async generator `_unique_constraints` to check DB uniqueness before `create` or `update` to prevent duplicate data conflicts (Raises `ConflictException`).
- **`DomainEventHooksMixin`**: Publishes domain events (e.g. `Model.created`) after successful CUD operations. Implement the abstract `publish_event(topic, payload)` to wire it to your transport — it is transport-agnostic and has no message-broker dependency.
- **`UserAwareHooksMixin`**: Automatically injects a `user_id` context into operations (e.g. tracking `created_by` / `updated_by`).
- **`NestedResourceHooksMixin`**: Ensures parent-child relationships are strictly validated.
- **`DetailDeleteResponseHookMixin`**: Enriches the delete response with detail about the removed object(s).
- **Usage**:
  ```python
  from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHooksMixin
  
  class UserService(UniqueConstraintHooksMixin, ...):
      async def _unique_constraints(self, obj_data, context):
          yield self.repo.model.email == obj_data.email, "Email already exists."
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