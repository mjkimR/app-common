"""Unit tests for DetailDeleteResponseHookMixin."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.services.base import BaseContextKwargs
from app_layer_base.base.services.detail_delete_response_hook import DetailDeleteResponseHookMixin

# =============================================================================
# Concrete service for testing
# =============================================================================


class ConcreteDetailDeleteService(DetailDeleteResponseHookMixin):
    def __init__(self, repo):
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    def _parse_delete_represent_text(self, obj) -> str:
        return f"Item({obj.name})"


# =============================================================================
# Tests
# =============================================================================


class TestDetailDeleteResponseHook:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteDetailDeleteService(mock_repo)

    async def test_context_delete_sets_represent_text_when_obj_exists(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        mock_obj = MagicMock()
        mock_obj.name = "Test Item"
        service.repo.get_by_pk = AsyncMock(return_value=mock_obj)

        async with service._context_delete(mock_async_session, sample_uuid, base_context):
            pass

        assert service._delete_represent_text == "Item(Test Item)"

    async def test_context_delete_does_not_set_represent_text_when_obj_not_found(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        service.repo.get_by_pk = AsyncMock(return_value=None)

        async with service._context_delete(mock_async_session, sample_uuid, base_context):
            pass

        assert service._delete_represent_text is None

    async def test_post_delete_sets_representation_on_result(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        service._delete_represent_text = "Item(Test Item)"
        result = DeleteResponse(success=True)

        updated = await service._post_delete(mock_async_session, sample_uuid, result, base_context)

        assert updated.representation == "Item(Test Item)"

    async def test_post_delete_skips_representation_when_not_set(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        result = DeleteResponse(success=True)

        updated = await service._post_delete(mock_async_session, sample_uuid, result, base_context)

        assert updated.representation is None
