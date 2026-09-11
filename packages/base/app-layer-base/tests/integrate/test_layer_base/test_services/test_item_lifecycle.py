"""
Integration tests for base Repository and Service with real DB.
"""

import uuid

import pytest
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from app_layer_base.base.repos.base import BaseRepository
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.services.base import (
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.user_aware_hook import UserAwareHook, UserContextKwargs
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

# =============================================================================
# Test Models & Schemas
# =============================================================================


class IntegrationItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_items"
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# =============================================================================
# Repository & Service
# =============================================================================


class ItemRepository(BaseRepository[IntegrationItem, ItemCreate, ItemUpdate, ItemUpdate]):
    model = IntegrationItem


class ItemService(
    BaseCreateServiceMixin,
    BaseUpdateServiceMixin,
    BaseGetServiceMixin,
    BaseGetMultiServiceMixin,
    BaseDeleteServiceMixin,
):
    def __init__(self, repo: ItemRepository):
        self._repo = repo
        # Existence is checked first, so a missing row fails before anything else runs.
        self.hooks = (ExistsCheckHook(), UserAwareHook())

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return UserContextKwargs


# =============================================================================
# Tests
# =============================================================================


async def test_item_crud_lifecycle(session):
    repo = ItemRepository()
    service = ItemService(repo)
    user_id = uuid.uuid4()
    context = {"user_id": user_id}

    # 1. Create
    create_data = ItemCreate(name="Integrate Test", description="Test Description")
    item = await service.create(session, create_data, context=context)

    assert item.id is not None
    assert item.name == "Integrate Test"
    assert item.created_by == user_id
    assert item.updated_by == user_id

    # 2. Get
    fetched = await service.get(session, item.id, context=context)
    assert fetched is not None
    assert fetched.id == item.id

    # 3. Update (Patch)
    patch_data = ItemUpdate(name="Updated Name")
    updated = await service.patch(session, item.id, patch_data, context=context)
    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.description == "Test Description"
    assert updated.updated_by == user_id

    # 4. Get Multi
    items_list = await service.get_multi(session, query_options=ListQueryOptions(limit=10), context=context)
    assert items_list.total_count == 1
    assert items_list.items[0].id == item.id

    # 5. Delete
    delete_resp = await service.delete(session, item.id, context=context)
    assert delete_resp.success is True

    # 6. Verify Deleted
    not_found = await service.get(session, item.id, context=context)
    assert not_found is None


async def test_exists_check_hook_integration(session):
    repo = ItemRepository()
    service = ItemService(repo)
    non_existent_id = uuid.uuid4()

    with pytest.raises(NotFoundException):
        await service.patch(session, non_existent_id, ItemUpdate(name="Fail"), context={"user_id": uuid.uuid4()})
