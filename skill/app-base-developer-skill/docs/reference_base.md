# `app_base/base` Module Guide

This document explains the core `base` components in the `app-base` package. It provides the essential classes for Repositories, Services, UseCases, Models, Schemas, Dependencies, and Exceptions.

---

## 1. Models (`app_base.base.models`)

### Summary
Provides standard SQLAlchemy declarative mixins to ensure consistency across database models.

### `mixin.py`
- **Classes**: `UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`, `TaggableMixin`.
- **Usage**: Inherit from `Base` and the necessary mixins.
  ```python
  from app_base.base.models.mixin import Base, UUIDMixin, TimestampMixin
  class User(Base, UUIDMixin, TimestampMixin):
      __tablename__ = "users"
  ```
- **Precautions**: `SoftDeleteMixin` adds an `is_deleted` flag and `deleted_at` timestamp. Ensure repositories or queries correctly filter by `is_deleted == False` when fetching active records.

---

## 2. Repositories (`app_base.base.repos`)

### Summary
Provides generic classes to handle standard database operations (CRUD).

### `base.py`
- **Classes**: `BaseRepository[ModelType, CreateSchemaType, PutSchemaType, PatchSchemaType]`
- **Usage**: Handles `get`, `create`, `update`, `delete`, `exists`, and paginated list queries.
- **Precautions**: For soft deletes, configure `is_deleted_column` properly. The repository automatically manages primary keys through generic typing.

---

## 3. Services and Hooks (`app_base.base.services`)

### Summary
Provides the business logic layer with a powerful Hook system to manage operations like validations, external API calls, or event publishing cleanly during CRUD.

### `base.py`
- **Classes**: `BaseServiceMixinInterface`, `BaseCreateHooks`, `BaseUpdateHooks`, `BaseDeleteHooks`.
- **Usage**: Services should inherit from hook mixins and implement specific logic using context managers (`_context_create`, etc.).

### Pre-built Hooks
- **`ExistsCheckHooksMixin`**: Checks if an entity exists before `update` or `delete`. Raises `NotFoundException` if it fails.
- **`UniqueConstraintHooksMixin`**: Provides an async generator `_unique_constraints` to check DB uniqueness before `create` or `update` to prevent duplicate data conflicts (Raises `BadRequestException(status_code=409)`).
- **`EventDomainHooksMixin`**: Publishes messages to an event broker after successful CUD operations.
- **`UserAwareHooksMixin`**: Automatically injects a `user_id` context into operations (e.g. tracking `created_by` / `updated_by`).
- **`NestedResourceHooksMixin`**: Ensures parent-child relationships are strictly validated.
- **Usage**:
  ```python
  class UserService(UniqueConstraintHooksMixin, ...):
      async def _unique_constraints(self, obj_data, context):
          yield self.repo.model.email == obj_data.email, "Email exists."
  ```
- **Precautions**: Hooks rely heavily on `context_model` validation. Ensure contexts are properly constructed to avoid type mismatches.

---

## 4. UseCases (`app_base.base.usecases`)

### Summary
Encapsulates single units of application logic.

### `base.py` & `crud.py`
- **Classes**: `BaseUseCase`, `CreateUseCase`, `GetUseCase`, `UpdateUseCase`, `DeleteUseCase`.
- **Usage**: Inherit from `BaseUseCase` and implement the `execute` method.
- **Precautions**: Ensure SRP (Single Responsibility Principle) is maintained. A use case should generally only perform one distinct action.

---

## 5. Dependencies and Filters (`app_base.base.deps`)

### Summary
FastAPI dependencies used for filtering and ordering dynamically via HTTP Query parameters.

### `filters/base.py` & Prebuilt Filters
- **Classes**: `SqlFilterCriteriaBase`, `SimpleFilterCriteriaBase`.
- **Usage**: Binds query parameters (e.g., `?email=test@test.com`) directly to SQLAlchemy expressions.
- **Precautions**: Properly map `alias` and `bound_type`. Unhandled filters can lead to SQL syntax errors if not tested properly.

---

## 6. Exceptions (`app_base.base.exceptions`)

### Summary
Centralized application exceptions to ensure consistent error handling.

### `basic.py`, `db.py`, `handler.py`
- **Classes**: `AppException`, `NotFoundException`, `BadRequestException`, `ForbiddenException`, `ConflictException`.
- **Usage**: Throw these directly in Services or Repositories. FastAPI exception handlers (`handler.py`) catch these and translate them to proper JSON HTTP responses.
- **Precautions**: Always provide a meaningful `log_message` for internal tracking, while `message` is exposed to the client.