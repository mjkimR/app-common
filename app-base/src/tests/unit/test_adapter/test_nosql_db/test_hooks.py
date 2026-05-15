"""Tests for nosql_db hooks (base, exists_check, event, user_aware, unique_constraints, nested_resource)."""

from typing import Any

import pytest
from app_base.adapter.nosql_db.hooks.base import (
    BaseNoSQLContextKwargs,
    BaseNoSQLCreateServiceMixin,
    BaseNoSQLDeleteServiceMixin,
    BaseNoSQLGetMultiServiceMixin,
    BaseNoSQLGetServiceMixin,
    BaseNoSQLUpdateServiceMixin,
)
from app_base.adapter.nosql_db.hooks.event import NoSQLDomainEventHooksMixin
from app_base.adapter.nosql_db.hooks.exists_check import NoSQLExistsCheckHooksMixin
from app_base.adapter.nosql_db.hooks.nested_resource import (
    NoSQLNestedResourceContextKwargs,
    NoSQLNestedResourceHooksMixin,
)
from app_base.adapter.nosql_db.hooks.user_aware import NoSQLUserAwareHooksMixin, NoSQLUserContextKwargs
from app_base.adapter.nosql_db.repository import NoSQLRepository
from app_base.base.exceptions.basic import NotFoundException
from pydantic import BaseModel

# ----------------------------------------------------------------
# Common test models
# ----------------------------------------------------------------


class ItemModel(BaseModel):
    id: str
    name: str
    owner_id: str | None = None


class ItemCreate(BaseModel):
    id: str
    name: str


class ItemPut(BaseModel):
    name: str


class ItemPatch(BaseModel):
    name: str | None = None


class ItemRepo(NoSQLRepository):
    collection_name = "items"
    model = ItemModel


# ----------------------------------------------------------------
# Concrete service for basic mixin tests
# ----------------------------------------------------------------


class ItemService(
    BaseNoSQLCreateServiceMixin,
    BaseNoSQLUpdateServiceMixin,
    BaseNoSQLDeleteServiceMixin,
    BaseNoSQLGetServiceMixin,
    BaseNoSQLGetMultiServiceMixin,
):
    @property
    def repo(self) -> ItemRepo:
        return ItemRepo()

    @property
    def context_model(self) -> type[BaseNoSQLContextKwargs]:
        return BaseNoSQLContextKwargs


@pytest.fixture
def item_service():
    class ConcreteItemService(ItemService):
        pass

    return ConcreteItemService()


# ================================================================
# BaseNoSQL Mixin Tests
# ================================================================


@pytest.mark.asyncio
async def test_create_mixin(item_service, mock_provider):
    obj = await item_service.create(mock_provider, "i1", ItemCreate(id="i1", name="Widget"))
    assert obj.id == "i1"
    assert obj.name == "Widget"


@pytest.mark.asyncio
async def test_get_mixin(item_service, mock_provider):
    await item_service.create(mock_provider, "i2", ItemCreate(id="i2", name="Gadget"))
    obj = await item_service.get(mock_provider, "i2")
    assert obj is not None
    assert obj.name == "Gadget"


@pytest.mark.asyncio
async def test_get_mixin_not_found(item_service, mock_provider):
    obj = await item_service.get(mock_provider, "nonexistent")
    assert obj is None


@pytest.mark.asyncio
async def test_put_mixin(item_service, mock_provider):
    await item_service.create(mock_provider, "i3", ItemCreate(id="i3", name="Original"))
    updated = await item_service.put(mock_provider, "i3", ItemPut(name="Replaced"))
    assert updated is not None
    assert updated.name == "Replaced"


@pytest.mark.asyncio
async def test_patch_mixin(item_service, mock_provider):
    await item_service.create(mock_provider, "i4", ItemCreate(id="i4", name="Original"))
    patched = await item_service.patch(mock_provider, "i4", ItemPatch(name="Patched"))
    assert patched is not None
    assert patched.name == "Patched"


@pytest.mark.asyncio
async def test_delete_mixin(item_service, mock_provider):
    await item_service.create(mock_provider, "i5", ItemCreate(id="i5", name="ToDelete"))
    result = await item_service.delete(mock_provider, "i5")
    assert result.success is True
    assert result.identity == "i5"


@pytest.mark.asyncio
async def test_get_multi_mixin(item_service, mock_provider):
    for i in range(3):
        await item_service.create(mock_provider, f"l{i}", ItemCreate(id=f"l{i}", name=f"Item{i}"))
    result = await item_service.get_multi(mock_provider)
    assert result.total_count == 3


# ================================================================
# ExistsCheck Hook Tests
# ================================================================


class ExistsCheckService(
    NoSQLExistsCheckHooksMixin,
    BaseNoSQLUpdateServiceMixin,
    BaseNoSQLDeleteServiceMixin,
):
    @property
    def repo(self) -> ItemRepo:
        return ItemRepo()

    @property
    def context_model(self):
        return BaseNoSQLContextKwargs


@pytest.fixture
def exists_check_service():
    return ExistsCheckService()


@pytest.mark.asyncio
async def test_exists_check_put_raises_if_not_found(exists_check_service, mock_provider):
    with pytest.raises(NotFoundException):
        await exists_check_service.put(mock_provider, "missing", ItemPut(name="X"))


@pytest.mark.asyncio
async def test_exists_check_patch_raises_if_not_found(exists_check_service, mock_provider):
    with pytest.raises(NotFoundException):
        await exists_check_service.patch(mock_provider, "missing", ItemPatch(name="X"))


@pytest.mark.asyncio
async def test_exists_check_delete_raises_if_not_found(exists_check_service, mock_provider):
    with pytest.raises(NotFoundException):
        await exists_check_service.delete(mock_provider, "missing")


@pytest.mark.asyncio
async def test_exists_check_put_succeeds_if_found(exists_check_service, mock_provider):
    repo = exists_check_service.repo
    await repo.create(mock_provider, "e1", ItemCreate(id="e1", name="Exists"))
    updated = await exists_check_service.put(mock_provider, "e1", ItemPut(name="Updated"))
    assert updated is not None


# ================================================================
# UserAware Hook Tests
# ================================================================


class UserAwareService(
    NoSQLUserAwareHooksMixin,
    BaseNoSQLCreateServiceMixin,
    BaseNoSQLUpdateServiceMixin,
):
    @property
    def repo(self) -> ItemRepo:
        return ItemRepo()

    @property
    def context_model(self):
        return NoSQLUserContextKwargs


@pytest.fixture
def user_aware_service():
    return UserAwareService()


@pytest.mark.asyncio
async def test_user_aware_create_injects_user_id(user_aware_service, mock_provider):
    context: NoSQLUserContextKwargs = {"user_id": "user_abc"}
    await user_aware_service.create(mock_provider, "ua1", ItemCreate(id="ua1", name="Item"), context=context)
    raw = await mock_provider.get_document("items", "ua1")
    assert raw is not None
    assert raw.get("created_by") == "user_abc"
    assert raw.get("updated_by") == "user_abc"


@pytest.mark.asyncio
async def test_user_aware_patch_injects_updated_by(user_aware_service, mock_provider):
    repo = user_aware_service.repo
    await repo.create(mock_provider, "ua2", ItemCreate(id="ua2", name="Item"))
    context: NoSQLUserContextKwargs = {"user_id": "user_xyz"}
    await user_aware_service.patch(mock_provider, "ua2", ItemPatch(name="Changed"), context=context)
    raw = await mock_provider.get_document("items", "ua2")
    assert raw is not None
    assert raw.get("updated_by") == "user_xyz"


# ================================================================
# Domain Event Hook Tests
# ================================================================


class EventService(
    NoSQLDomainEventHooksMixin,
    BaseNoSQLCreateServiceMixin,
    BaseNoSQLUpdateServiceMixin,
    BaseNoSQLDeleteServiceMixin,
):
    def __init__(self):
        self.published_events: list[tuple[str, dict]] = []

    @property
    def repo(self) -> ItemRepo:
        return ItemRepo()

    @property
    def context_model(self):
        return BaseNoSQLContextKwargs

    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        self.published_events.append((topic, payload))


@pytest.fixture
def event_service():
    return EventService()


@pytest.mark.asyncio
async def test_event_hook_create_publishes(event_service, mock_provider):
    await event_service.create(mock_provider, "ev1", ItemCreate(id="ev1", name="Item"))
    topics = [t for t, _ in event_service.published_events]
    assert "ItemModel.created" in topics


@pytest.mark.asyncio
async def test_event_hook_put_publishes(event_service, mock_provider):
    repo = event_service.repo
    await repo.create(mock_provider, "ev2", ItemCreate(id="ev2", name="Item"))
    event_service.published_events.clear()
    await event_service.put(mock_provider, "ev2", ItemPut(name="Updated"))
    topics = [t for t, _ in event_service.published_events]
    assert "ItemModel.updated" in topics


@pytest.mark.asyncio
async def test_event_hook_patch_publishes(event_service, mock_provider):
    repo = event_service.repo
    await repo.create(mock_provider, "ev3", ItemCreate(id="ev3", name="Item"))
    event_service.published_events.clear()
    await event_service.patch(mock_provider, "ev3", ItemPatch(name="Patched"))
    topics = [t for t, _ in event_service.published_events]
    assert "ItemModel.updated" in topics


@pytest.mark.asyncio
async def test_event_hook_delete_publishes(event_service, mock_provider):
    repo = event_service.repo
    await repo.create(mock_provider, "ev4", ItemCreate(id="ev4", name="Item"))
    event_service.published_events.clear()
    await event_service.delete(mock_provider, "ev4")
    topics = [t for t, _ in event_service.published_events]
    assert "ItemModel.deleted" in topics


# ================================================================
# NestedResource Hook Tests
# ================================================================


class ChildModel(BaseModel):
    id: str
    name: str
    parent_id: str | None = None


class ChildCreate(BaseModel):
    id: str
    name: str


class ChildPatch(BaseModel):
    name: str | None = None


class ChildRepo(NoSQLRepository):
    collection_name = "children"
    model = ChildModel


class ParentModel(BaseModel):
    id: str
    name: str


class ParentRepo(NoSQLRepository):
    collection_name = "parents"
    model = ParentModel


class NestedChildService(
    NoSQLNestedResourceHooksMixin,
    BaseNoSQLCreateServiceMixin,
    BaseNoSQLUpdateServiceMixin,
    BaseNoSQLGetServiceMixin,
    BaseNoSQLGetMultiServiceMixin,
    BaseNoSQLDeleteServiceMixin,
):
    _child_repo = ChildRepo()
    _parent_repo = ParentRepo()

    @property
    def repo(self) -> ChildRepo:
        return self._child_repo

    @property
    def parent_repo(self) -> ParentRepo:
        return self._parent_repo

    @property
    def context_model(self):
        return NoSQLNestedResourceContextKwargs


@pytest.fixture
def nested_service():
    return NestedChildService()


@pytest.mark.asyncio
async def test_nested_create_injects_parent_id(nested_service, mock_provider):
    # Insert parent document directly via provider
    await mock_provider.create_document("parents", "p1", {"id": "p1", "name": "Parent"})

    context: NoSQLNestedResourceContextKwargs = {"parent_id": "p1"}
    child = await nested_service.create(mock_provider, "c1", ChildCreate(id="c1", name="Child"), context=context)
    assert child.parent_id == "p1"


@pytest.mark.asyncio
async def test_nested_create_raises_if_parent_not_found(nested_service, mock_provider):
    context: NoSQLNestedResourceContextKwargs = {"parent_id": "no_parent"}
    with pytest.raises(NotFoundException):
        await nested_service.create(mock_provider, "c2", ChildCreate(id="c2", name="Orphan"), context=context)


@pytest.mark.asyncio
async def test_nested_patch_raises_if_wrong_parent(nested_service, mock_provider):
    await mock_provider.create_document("parents", "p2", {"id": "p2", "name": "Parent2"})
    await mock_provider.create_document("children", "c3", {"id": "c3", "name": "Child", "parent_id": "p2"})

    context: NoSQLNestedResourceContextKwargs = {"parent_id": "different_parent"}
    with pytest.raises(NotFoundException):
        await nested_service.patch(mock_provider, "c3", ChildPatch(name="Wrong"), context=context)


@pytest.mark.asyncio
async def test_nested_get_multi_filters_by_parent(nested_service, mock_provider):
    await mock_provider.create_document("parents", "p3", {"id": "p3", "name": "Parent3"})
    await mock_provider.create_document("children", "c4", {"id": "c4", "name": "Child4", "parent_id": "p3"})
    await mock_provider.create_document("children", "c5", {"id": "c5", "name": "Child5", "parent_id": "other_parent"})

    context: NoSQLNestedResourceContextKwargs = {"parent_id": "p3"}
    result = await nested_service.get_multi(mock_provider, context=context)
    assert result.total_count == 1
    assert result.items[0].id == "c4"
