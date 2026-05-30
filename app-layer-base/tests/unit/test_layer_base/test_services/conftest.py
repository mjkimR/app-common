"""
Shared fixtures for services hook unit tests.
Reuses mock models/repos from the parent conftest (test_base/conftest.py).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.base import BaseContextKwargs
from test_layer_base.mock_models import MockModel, MockRepository

# =============================================================================
# Common Service Builder Helper
# =============================================================================


def make_repo_mock() -> AsyncMock:
    """Create a repository-like AsyncMock with common attributes set."""
    repo = AsyncMock(spec=MockRepository)
    repo.primary_keys = MockRepository().primary_keys
    repo.model = MockModel
    repo.model_name = MockRepository.model_name
    repo.model_repr = MockRepository().model_repr
    repo.normalize_pk = MockRepository().normalize_pk
    repo.normalize_pk_as_str = MockRepository().normalize_pk_as_str
    return repo


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repo():
    return make_repo_mock()


@pytest.fixture
def sample_uuid():
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_delete_response():
    return DeleteResponse(success=True)


@pytest.fixture
def mock_failed_delete_response():
    return DeleteResponse(success=False)


@pytest.fixture
def mock_multiple_delete_response():
    return MultipleDeleteResponse(deleted_count=2)


@pytest.fixture
def mock_async_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def base_context() -> BaseContextKwargs:
    return {}


@pytest.fixture
def user_context():
    return {"user_id": uuid.uuid4()}
