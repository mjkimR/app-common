# Test patterns

Read the [testing guide](index.md) first to select HTTP-only or DB-aware fixtures.
Names, schemas, and routes below are examples; use the consumer's actual contract.

## HTTP-only app

In top-level `tests/conftest.py`:

```python
import pytest
from my_app.server import create_app

pytest_plugins = ["app_testing_base.http_plugin"]


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client_headers():
    return {"X-API-Key": "test-key"}
```

```python
def test_health(http_client):
    assert http_client.get("/health").status_code == 200
```

## DB integration

With `app_testing_base.plugin` loaded in top-level `tests/conftest.py`:

```python
from app_testing_base import IntegrationTest
from app.features.items.models import Item
from app.features.items.schemas import ItemCreate
from app.features.items.usecases.create_item import CreateItemUseCase


class TestCreateItem(IntegrationTest):
    async def test_create_item(self):
        result = await self.resolve(CreateItemUseCase).execute(
            ItemCreate(name="New Item", category="electronics")
        )
        saved = await self.refresh(Item, result.id)
        assert saved is not None
        assert saved.name == "New Item"
```

## DB-backed API and seeding

Use the same DB plugin. `E2ETest` supplies the E2E/real-commit markers and fixtures.
Keep a seeder local to the test file unless multiple suites need it.

```python
from app_testing_base import E2ETest, assert_json_contains, assert_status_code, random_string
from app.features.items.models import Item
from app.features.items.repos import ItemRepository
from app.features.items.schemas import ItemCreate
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_item(session: AsyncSession, **overrides) -> Item:
    defaults = {"name": f"item-{random_string(4)}", "category": "general"}
    return await ItemRepository().create(session, ItemCreate(**(defaults | overrides)))


class TestItemsAPI(E2ETest):
    base_url = "/api/v1/items"

    async def test_get_item(self):
        item = await seed_item(self.session, name="Specific Item")
        response = await self.client.get(self.url(f"/{item.id}"))
        assert_status_code(response, 200)
        assert_json_contains(response, {"id": str(item.id), "name": "Specific Item"})

    async def test_create_item(self):
        response = await self.client.post(
            self.url(), json={"name": "Created Item", "category": "books"}
        )
        assert_status_code(response, 201)
        saved = await self.refresh(Item, response.json()["id"])
        assert saved is not None
        assert saved.name == "Created Item"
```
