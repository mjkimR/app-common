# app-testing

Testing guidance and conventions for FastAPI + SQLAlchemy applications using `app-testing-base`.
Optimized for AI Agents to produce deterministic, high-ROI tests without flaky failures.

---

## 1. Test Strategy & The Test Trophy

| Scope | Directory | Target | When to Use | Key Tooling |
|---|---|---|---|---|
| **Integration** (Primary) | `tests/integrate/` | `UseCase`, `Service`, `Repository` | Core business logic, DB queries, service hooks. **Default choice for most tests.** | `resolve_dependency`, `session` |
| **E2E** (Secondary) | `tests/e2e/` | API Routers, HTTP Endpoints | Verify routing, status codes, query/body serialization, authentication. | `client`, `session.expire_all()` |
| **Unit** (Minimal) | `tests/unit/` | Pure functions, algorithms | Complex calculations or data parsers with no DB or HTTP dependency. | Standard pytest |

---

## 2. Test Data Seeding Rules

**Never use random data generators for database entities.** Random strings cause flaky tests by violating field constraints (email regex, cron syntax, max length, unique keys).

### Rule 1: Explicit Seeder Function (`_seed_<entity>`)
When a test file needs one or more entities in the database, define a lightweight seeder function using the `defaults | overrides` pattern:

```python
from app_testing_base import random_string
from app.features.items.schemas import ItemCreate
from app.features.items.repos import ItemRepository
from app.features.items.models import Item
from sqlalchemy.ext.asyncio import AsyncSession


def make_item_payload(**overrides) -> ItemCreate:
    """Deterministic, valid default schema for testing."""
    defaults = {
        "name": f"item-{random_string(4)}",
        "category": "general",
        "is_active": True,
    }
    return ItemCreate(**(defaults | overrides))


async def seed_item(session: AsyncSession, **overrides) -> Item:
    """Create and persist an entity directly using its repository."""
    payload = make_item_payload(**overrides)
    repo = ItemRepository()
    return await repo.create(session, payload)
```

### Rule 2: Inline Pydantic for Validation / Negative Tests
When testing bad input or edge cases, create the schema or dictionary inline directly:

```python
payload = {"name": "", "category": "invalid"}  # Direct dict for testing 422
response = await client.post("/api/v1/items", json=payload)
assert_status_code(response, 422)
```

### Rule 3: Batch Seeding via List Comprehension
When testing pagination or list endpoints:

```python
items = [await seed_item(session, name=f"item-{i}") for i in range(5)]
```

---

## 3. Golden Rules for AI Agents

1. **NO `@pytest.mark.asyncio` decorator**:
   Async mode is configured globally (`asyncio_mode = "auto"` in `pyproject.toml`). Adding `@pytest.mark.asyncio` is redundant.
2. **USE `resolve_dependency` for Integration tests**:
   Never manually instantiate nested services or repositories.
   ```python
   use_case = resolve_dependency(CreateItemUseCase, state={"db": session})
   ```
3. **MARK E2E tests with `@pytest.mark.real_commit`**:
   The HTTP client runs against an app that commits transactions.
   ```python
   @pytest.mark.e2e
   @pytest.mark.real_commit
   class TestItemAPI: ...
   ```
4. **USE `refresh_get` before querying DB after API calls**:
   SQLAlchemy holds an in-memory Identity Map cache. After an API commits changes or a worker updates a row, using `await refresh_get(session, Model, id)` automatically clears stale cache and fetches fresh data:
   ```python
   response = await client.delete(f"/api/v1/items/{item.id}")
   assert_status_code(response, 200)

   db_item = await refresh_get(session, Item, item.id)
   assert db_item is None
   ```
5. **PREFER `app_testing_base` assertion helpers**:
   - `assert_status_code(response, 200)`
   - `assert_json_contains(response, {"name": "target"})`
   - `assert_paginated_response(response, min_items=3)`
   - `assert_error_response(response, 404, error_type="NotFound")`
6. **USE `mocker` from `pytest-mock` for Unit test isolation**:
   For external third-party services or network calls in unit tests, request the `mocker` fixture instead of manually managing `unittest.mock.patch`.

---

## 4. Canonical Test Templates

### Template 1: Integration Test (`tests/integrate/test_<op>_<entity>.py`)

Inheriting from `IntegrationTest` automatically sets `@pytest.mark.integrate`, binds `self.session`, and provides `self.resolve(UseCase)` and `self.refresh(Model, id)`.

```python
from app_testing_base import IntegrationTest
from app.features.items.models import Item
from app.features.items.schemas import ItemCreate
from app.features.items.usecases.create_item import CreateItemUseCase


class TestCreateItem(IntegrationTest):
    async def test_create_item_success(self):
        # 1. Setup - self.resolve automatically binds the test session
        use_case = self.resolve(CreateItemUseCase)
        payload = ItemCreate(name="New Item", category="electronics")

        # 2. Execute
        result = await use_case.execute(payload)

        # 3. Verify - self.refresh reloads fresh state from DB
        assert result.name == "New Item"
        saved = await self.refresh(Item, result.id)
        assert saved is not None
        assert saved.name == "New Item"
```

### Template 2: E2E API Test (`tests/e2e/test_<entity>_api.py`)

Inheriting from `E2ETest` automatically sets `@pytest.mark.e2e` and `@pytest.mark.real_commit`, binds `self.client` and `self.session`, and provides `self.url(...)` and `self.refresh(...)`.

```python
from app_testing_base import (
    E2ETest,
    assert_json_contains,
    assert_paginated_response,
    assert_status_code,
    random_string,
)
from app.features.items.models import Item
from app.features.items.repos import ItemRepository
from app.features.items.schemas import ItemCreate
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_item(session: AsyncSession, **overrides) -> Item:
    defaults = {"name": f"item-{random_string(4)}", "category": "general"}
    return await ItemRepository().create(session, ItemCreate(**(defaults | overrides)))


class TestItemsAPI(E2ETest):
    base_url = "/api/v1/items"

    async def test_get_item_by_id(self):
        item = await seed_item(self.session, name="Specific Item")

        response = await self.client.get(self.url(f"/{item.id}"))

        assert_status_code(response, 200)
        assert_json_contains(response, {"id": str(item.id), "name": "Specific Item"})

    async def test_create_item(self):
        payload = {"name": "Created Item", "category": "books"}

        response = await self.client.post(self.url(), json=payload)

        assert_status_code(response, 201)
        item_id = response.json()["id"]

        saved = await self.refresh(Item, item_id)
        assert saved is not None
        assert saved.name == "Created Item"
```

---

## 5. Self-Correction & Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| `AssertionError: Expected 200, got 422` | Request body failed Pydantic validation. | Check required fields, regex patterns, or enums in schemas. Pass explicit valid values. |
| `IntegrityError: duplicate key value` | Collided unique field (email, slug, name). | Use `random_string(4)` or `random_email()` in `_seed_*` defaults. |
| DB assertion failed after API call | Stale SQLAlchemy Identity Map cache. | Use `await refresh_get(session, Model, id)` or call `session.expire_all()` before `session.get(...)`. |
| `DependencyResolutionError` | Parameter has no default and is not marked with Depends(). | Add `Annotated[T, Depends()]` in constructor or pass mock instance via `overrides={T: mock}`. |
| `NotImplementedError: No FastAPI 'app' could be auto-discovered` | App fixture was not found in `app.main`. | Define `@pytest.fixture def app(): return create_app()` in your root `tests/conftest.py`. |
