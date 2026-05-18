"""Unit tests for DomainEventHooksMixin."""

import uuid
from unittest.mock import MagicMock

import pytest
from app_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_base.base.services.base import BaseContextKwargs
from app_base.base.services.event_hook import DomainEventHooksMixin

# =============================================================================
# Concrete service for testing
# =============================================================================


class ConcreteEventHookService(DomainEventHooksMixin):
    def __init__(self, repo):
        self._repo = repo
        self.published_events: list[tuple[str, dict]] = []

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    async def publish_event(self, topic: str, payload: dict) -> None:
        self.published_events.append((topic, payload))


# =============================================================================
# Tests
# =============================================================================


class TestDomainEventHookPost:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteEventHookService(mock_repo)

    async def test_post_create_publishes_created_event(self, service, mock_async_session, base_context):
        obj = MagicMock()
        pk_col = service.repo.primary_keys[0]
        obj_id = uuid.uuid4()
        setattr(obj, pk_col.key, obj_id)

        await service._post_create(mock_async_session, obj, base_context)

        assert len(service.published_events) == 1
        topic, payload = service.published_events[0]
        assert topic == "MockModel.created"
        assert payload["event_type"] == "created"
        assert payload["resource_type"] == "MockModel"
        assert payload["resource_id"] == str(obj_id)

    async def test_post_create_multi_publishes_created_multi_event(self, service, mock_async_session, base_context):
        pk_col = service.repo.primary_keys[0]
        objs = []
        for _ in range(3):
            obj = MagicMock()
            setattr(obj, pk_col.key, uuid.uuid4())
            objs.append(obj)

        await service._post_create_multi(mock_async_session, objs, base_context)

        topics = [e[0] for e in service.published_events]
        assert "MockModel.created_multi" in topics
        _, payload = next(e for e in service.published_events if e[0] == "MockModel.created_multi")
        assert payload["event_type"] == "created_multi"
        assert len(payload["resource_ids"]) == 3

    async def test_post_create_multi_does_not_publish_for_empty_list(self, service, mock_async_session, base_context):
        await service._post_create_multi(mock_async_session, [], base_context)

        assert not any(e[0] == "MockModel.created_multi" for e in service.published_events)

    async def test_post_update_publishes_updated_event(self, service, mock_async_session, base_context):
        obj = MagicMock()
        pk_col = service.repo.primary_keys[0]
        obj_id = uuid.uuid4()
        setattr(obj, pk_col.key, obj_id)

        await service._post_update(mock_async_session, obj, base_context)

        assert len(service.published_events) == 1
        topic, payload = service.published_events[0]
        assert topic == "MockModel.updated"
        assert payload["event_type"] == "updated"

    async def test_post_delete_publishes_deleted_event_on_success(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        result = DeleteResponse(success=True)

        await service._post_delete(mock_async_session, sample_uuid, result, base_context)

        assert len(service.published_events) == 1
        topic, payload = service.published_events[0]
        assert topic == "MockModel.deleted"
        assert payload["event_type"] == "deleted"

    async def test_post_delete_does_not_publish_on_failure(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        result = DeleteResponse(success=False)

        await service._post_delete(mock_async_session, sample_uuid, result, base_context)

        assert len(service.published_events) == 0

    async def test_post_delete_multi_publishes_event_when_deleted(
        self, service, mock_async_session, sample_uuid, base_context
    ):
        result = MultipleDeleteResponse(deleted_count=2)
        pks = [uuid.uuid4(), uuid.uuid4()]

        await service._post_delete_multi(mock_async_session, pks, result, base_context)

        assert len(service.published_events) == 1
        topic, payload = service.published_events[0]
        assert topic == "MockModel.deleted_multi"
        assert len(payload["resource_ids"]) == 2

    async def test_post_delete_multi_does_not_publish_when_deleted_count_zero(
        self, service, mock_async_session, base_context
    ):
        result = MultipleDeleteResponse(deleted_count=0)

        await service._post_delete_multi(mock_async_session, [], result, base_context)

        assert not any(e[0] == "MockModel.deleted_multi" for e in service.published_events)
