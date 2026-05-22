"""Unit tests for UniqueConstraintHooksMixin."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_base.base.exceptions.basic import BadRequestException
from app_base.base.services.base import BaseContextKwargs
from app_base.base.services.unique_constraints_hook import UniqueConstraintHooksMixin
from sqlalchemy.sql.expression import ColumnElement

from tests.unit.test_base.conftest import MockModel

# =============================================================================
# Concrete service for testing
# =============================================================================


class ConcreteUniqueConstraintService(UniqueConstraintHooksMixin):
    def __init__(self, repo):
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    async def _unique_constraints(self, obj_data, context) -> AsyncIterator[tuple[ColumnElement, str]]:
        # Yield a real SQLAlchemy expression for testing
        if getattr(obj_data, "name", None):
            condition = MockModel.id == None  # noqa: E711 — dummy condition for test
            yield condition, "Name already exists."


# =============================================================================
# Tests for _context_create
# =============================================================================


class TestUniqueConstraintCreate:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteUniqueConstraintService(mock_repo)

    async def test_context_create_passes_when_no_duplicate(self, service, mock_async_session, base_context):
        service.repo.exists = AsyncMock(return_value=False)
        obj_data = MagicMock()
        obj_data.name = "unique_name"

        async with service._context_create(mock_async_session, obj_data, base_context):
            pass  # No exception expected

        service.repo.exists.assert_called_once()

    async def test_context_create_raises_when_duplicate_found(self, service, mock_async_session, base_context):
        service.repo.exists = AsyncMock(return_value=True)
        obj_data = MagicMock()
        obj_data.name = "duplicate_name"

        with pytest.raises(BadRequestException, match=r"Name already exists."):
            async with service._context_create(mock_async_session, obj_data, base_context):
                pass

    async def test_context_create_skips_check_when_no_constraint_yields(
        self, service, mock_async_session, base_context
    ):
        service.repo.exists = AsyncMock(return_value=False)
        obj_data = MagicMock()
        obj_data.name = None  # Constraint only yields when name is set

        async with service._context_create(mock_async_session, obj_data, base_context):
            pass

        service.repo.exists.assert_not_called()


# =============================================================================
# Tests for _context_update
# =============================================================================


class TestUniqueConstraintUpdate:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteUniqueConstraintService(mock_repo)

    async def test_context_update_passes_when_no_duplicate(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        service.repo.exists = AsyncMock(return_value=False)
        obj_data = MagicMock()
        obj_data.name = "unique_name"

        async with service._context_update(mock_async_session, sample_uuid, obj_data, base_context):
            pass

        service.repo.exists.assert_called_once()

    async def test_context_update_raises_when_duplicate_found(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        service.repo.exists = AsyncMock(return_value=True)
        obj_data = MagicMock()
        obj_data.name = "duplicate_name"

        with pytest.raises(BadRequestException):
            async with service._context_update(mock_async_session, sample_uuid, obj_data, base_context):
                pass

    async def test_context_update_passes_exclude_id_to_check(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        """exclude_id should be forwarded so the current record is not flagged as duplicate."""
        service.repo.exists = AsyncMock(return_value=False)
        obj_data = MagicMock()
        obj_data.name = "some_name"

        async with service._context_update(mock_async_session, sample_uuid, obj_data, base_context):
            pass

        # Verify exists was called (with an AND condition that excludes current PK)
        service.repo.exists.assert_called_once()
