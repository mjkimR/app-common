"""Unit tests for NestedResourceHooksMixin."""

import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_base.base.exceptions.basic import NotFoundException
from app_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from app_base.base.repos.base import BaseRepository
from app_base.base.services.nested_resource_hook import (
    NestedResourceContextKwargs,
    NestedResourceHooksMixin,
)
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tests.unit.test_base.conftest import MockModel, MockRepository

# =============================================================================
# Nested-aware test models
# =============================================================================


class MockChildModel(Base, UUIDMixin, TimestampMixin):
    """Child model that has a parent_id FK for testing nested hooks."""

    __tablename__ = "mock_child_items"

    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)


class MockChildRepository(BaseRepository[MockChildModel, BaseModel, BaseModel, BaseModel]):
    model = MockChildModel


# =============================================================================
# Concrete service for testing
# =============================================================================


class ConcreteNestedService(NestedResourceHooksMixin):
    def __init__(self, repo, parent_repo):
        self._repo = repo
        self._parent_repo = parent_repo

    @property
    def repo(self):
        return self._repo

    @property
    def parent_repo(self):
        return self._parent_repo

    @property
    def context_model(self):
        return NestedResourceContextKwargs

    @property
    def fk_name(self):
        return "parent_id"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def parent_repo_mock():
    repo = AsyncMock(spec=MockRepository)
    repo.primary_keys = MockRepository().primary_keys
    repo.model = MockModel
    repo.model_name = MockRepository.model_name
    repo.model_repr = MockRepository().model_repr
    repo.normalize_pk = MockRepository().normalize_pk
    repo.normalize_pk_as_str = MockRepository().normalize_pk_as_str
    return repo


@pytest.fixture
def child_repo_mock():
    """Child repo backed by MockChildModel (which has a parent_id column)."""
    repo = AsyncMock(spec=MockChildRepository)
    repo.primary_keys = MockChildRepository().primary_keys
    repo.model = MockChildModel
    repo.model_name = MockChildRepository.model_name
    repo.model_repr = MockChildRepository().model_repr
    repo.normalize_pk = MockChildRepository().normalize_pk
    repo.normalize_pk_as_str = MockChildRepository().normalize_pk_as_str
    return repo


@pytest.fixture
def service(child_repo_mock, parent_repo_mock):
    return ConcreteNestedService(child_repo_mock, parent_repo_mock)


@pytest.fixture
def parent_id():
    return uuid.uuid4()


@pytest.fixture
def nested_context(parent_id) -> NestedResourceContextKwargs:
    return {"parent_id": parent_id}


# =============================================================================
# Tests for _check_parent_exists
# =============================================================================


class TestCheckParentExists:
    @pytest.mark.asyncio
    async def test_passes_when_parent_exists(self, service, mock_async_session, parent_id):
        service.parent_repo.get_by_pk = AsyncMock(return_value=MagicMock())

        await service._check_parent_exists(mock_async_session, parent_id)  # No exception

    @pytest.mark.asyncio
    async def test_raises_not_found_when_parent_missing(self, service, mock_async_session, parent_id):
        service.parent_repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service._check_parent_exists(mock_async_session, parent_id)


# =============================================================================
# Tests for _ensure_ownership
# =============================================================================


class TestEnsureOwnership:
    @pytest.mark.asyncio
    async def test_passes_when_obj_belongs_to_parent(self, service, mock_async_session, sample_uuid, parent_id):
        mock_obj = MagicMock()
        mock_obj.parent_id = parent_id
        service.repo.get_by_pk = AsyncMock(return_value=mock_obj)

        await service._ensure_ownership(mock_async_session, sample_uuid, parent_id)  # No exception

    @pytest.mark.asyncio
    async def test_raises_when_obj_belongs_to_different_parent(
        self, service, mock_async_session, sample_uuid, parent_id
    ):
        other_parent_id = uuid.uuid4()
        mock_obj = MagicMock()
        mock_obj.parent_id = other_parent_id
        service.repo.get_by_pk = AsyncMock(return_value=mock_obj)

        with pytest.raises(NotFoundException):
            await service._ensure_ownership(mock_async_session, sample_uuid, parent_id)

    @pytest.mark.asyncio
    async def test_passes_when_obj_not_found(self, service, mock_async_session, sample_uuid, parent_id):
        service.repo.get_by_pk = AsyncMock(return_value=None)

        await service._ensure_ownership(mock_async_session, sample_uuid, parent_id)  # Should not raise


# =============================================================================
# Tests for _prepare_create_fields
# =============================================================================


class TestPrepareCreateFields:
    def test_injects_parent_id_into_fields(self, service, parent_id, nested_context):
        result = service._prepare_create_fields(obj_data=None, context=nested_context)

        assert result["parent_id"] == parent_id

    def test_merges_extra_fields(self, service, parent_id, nested_context):
        result = service._prepare_create_fields(obj_data=None, context=nested_context, extra="value")

        assert result["parent_id"] == parent_id
        assert result["extra"] == "value"


# =============================================================================
# Tests for _prepare_get_multi_filters
# =============================================================================


class TestPrepareGetMultiFilters:
    def test_adds_parent_id_filter(self, service, nested_context):
        filters = service._prepare_get_multi_filters(nested_context)

        assert len(filters) == 1


# =============================================================================
# Tests for context hooks
# =============================================================================


class TestNestedContextHooks:
    @pytest.mark.asyncio
    async def test_context_create_checks_parent_exists(self, service, mock_async_session, nested_context):
        service.parent_repo.get_by_pk = AsyncMock(return_value=MagicMock())

        async with service._context_create(mock_async_session, MagicMock(), nested_context):
            pass

        service.parent_repo.get_by_pk.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_create_raises_when_parent_missing(self, service, mock_async_session, nested_context):
        service.parent_repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            async with service._context_create(mock_async_session, MagicMock(), nested_context):
                pass

    @pytest.mark.asyncio
    async def test_context_get_multi_checks_parent_exists(self, service, mock_async_session, nested_context):
        service.parent_repo.get_by_pk = AsyncMock(return_value=MagicMock())

        async with service._context_get_multi(mock_async_session, nested_context):
            pass

        service.parent_repo.get_by_pk.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_update_raises_when_wrong_parent(
        self, service, mock_async_session, sample_uuid, nested_context, parent_id
    ):
        mock_obj = MagicMock()
        mock_obj.parent_id = uuid.uuid4()  # Different parent
        service.repo.get_by_pk = AsyncMock(return_value=mock_obj)

        with pytest.raises(NotFoundException):
            async with service._context_update(mock_async_session, sample_uuid, MagicMock(), nested_context):
                pass

    @pytest.mark.asyncio
    async def test_context_delete_raises_when_wrong_parent(
        self, service, mock_async_session, sample_uuid, nested_context
    ):
        mock_obj = MagicMock()
        mock_obj.parent_id = uuid.uuid4()  # Different parent
        service.repo.get_by_pk = AsyncMock(return_value=mock_obj)

        with pytest.raises(NotFoundException):
            async with service._context_delete(mock_async_session, sample_uuid, nested_context):
                pass
