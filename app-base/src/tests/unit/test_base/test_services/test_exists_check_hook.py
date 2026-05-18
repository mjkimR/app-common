"""Unit tests for ExistsCheckHooksMixin."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app_base.base.exceptions.basic import NotFoundException
from app_base.base.services.base import BaseContextKwargs
from app_base.base.services.exists_check_hook import ExistsCheckHooksMixin

# =============================================================================
# Concrete service for testing
# =============================================================================


class ConcreteExistsCheckService(ExistsCheckHooksMixin):
    def __init__(self, repo):
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


# =============================================================================
# Tests for _context_update
# =============================================================================


class TestExistsCheckUpdate:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteExistsCheckService(mock_repo)

    async def test_context_update_passes_when_obj_exists(self, service, mock_async_session, sample_uuid, base_context):
        service.repo.get_by_pk = AsyncMock(return_value=MagicMock())

        async with service._context_update(mock_async_session, sample_uuid, MagicMock(), base_context):
            pass  # No exception expected

    async def test_context_update_raises_not_found_when_obj_missing(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        service.repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            async with service._context_update(mock_async_session, sample_uuid, MagicMock(), base_context):
                pass


# =============================================================================
# Tests for _context_delete
# =============================================================================


class TestExistsCheckDelete:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteExistsCheckService(mock_repo)

    async def test_context_delete_passes_when_obj_exists(self, service, mock_async_session, sample_uuid, base_context):
        service.repo.get_by_pk = AsyncMock(return_value=MagicMock())

        async with service._context_delete(mock_async_session, sample_uuid, base_context):
            pass  # No exception expected

    async def test_context_delete_raises_not_found_when_obj_missing(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        service.repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            async with service._context_delete(mock_async_session, sample_uuid, base_context):
                pass


# =============================================================================
# Tests for _context_delete_multi
# =============================================================================


class TestExistsCheckDeleteMulti:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteExistsCheckService(mock_repo)

    async def test_context_delete_multi_passes_when_all_exist(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        existing_obj = MagicMock()
        # primary_keys[0].key must match what the repo mock exposes
        pk_col = service.repo.primary_keys[0]
        setattr(existing_obj, pk_col.key, sample_uuid)

        service.repo.get_all = AsyncMock(return_value=[existing_obj])

        async with service._context_delete_multi(mock_async_session, [sample_uuid], base_context):
            pass  # No exception expected

    async def test_context_delete_multi_raises_not_found_when_missing(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        # Return empty list → all PKs are missing
        service.repo.get_all = AsyncMock(return_value=[])

        with pytest.raises(NotFoundException):
            async with service._context_delete_multi(mock_async_session, [sample_uuid], base_context):
                pass

    async def test_context_delete_multi_skips_check_for_empty_list(self, service, mock_async_session, base_context):
        async with service._context_delete_multi(mock_async_session, [], base_context):
            pass  # Empty list should not raise
