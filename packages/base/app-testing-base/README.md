# app-testing-base

Standard testing foundation for `app-common` packages and downstream FastAPI services.

## Overview

`app-testing-base` provides the unified test infrastructure required for building robust, reliable tests in FastAPI + SQLAlchemy applications:

- **Database Fixtures**: Transaction savepoint/rollback isolation for PostgreSQL, in-memory SQLite for fast testing, and `@pytest.mark.real_commit` for outbox/background worker tests.
- **FastAPI DI Resolver**: `resolve_dependency` to recursively construct `Annotated[T, Depends()]` dependency trees for UseCases and Services without manual mock chains.
- **Test Client**: `AsyncClientWithJson` and `client` fixture with automatic session dependency override and safe serialization for Enums, UUIDs, and Datetimes.
- **Assertion Helpers**: High-clarity assertion functions (`assert_status_code`, `assert_json_contains`, `assert_paginated_response`, `assert_error_response`, `assert_model_fields`).
- **Deterministic Seeding Primitives**: Lightweight collision-avoidance utilities (`random_string`, `random_email`, `random_uuid`, `utc_now`) for explicit seeder patterns without heavy factory magic.

## Installation

```toml
[dependency-groups]
dev = [
    "app-testing-base",
]
```

## Quick Start

In your project's top-level `tests/conftest.py`:

```python
pytest_plugins = ["app_testing_base.plugin"]


# If using the `client` fixture for E2E tests, expose your FastAPI app instance:
@pytest.fixture
def app():
    from app.main import create_app

    return create_app()
```

### Integration Test Example (UseCase / Service)

```python
import pytest
from app_testing_base import resolve_dependency
from app.features.items.usecases import CreateItemUseCase


@pytest.mark.integrate
class TestCreateItem:
    async def test_create_item_success(self, session):
        use_case = resolve_dependency(CreateItemUseCase, state={"db": session})
        result = await use_case.execute({"name": "Test Item"})
        assert result.name == "Test Item"
```

### E2E Test Example (Router / API)

```python
import pytest
from app_testing_base import assert_status_code, assert_json_contains


@pytest.mark.e2e
@pytest.mark.real_commit
class TestItemAPI:
    async def test_get_item(self, client):
        response = await client.get("/api/v1/items")
        assert_status_code(response, 200)
```
