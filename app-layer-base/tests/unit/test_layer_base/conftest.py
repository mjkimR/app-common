"""
Conftest for base module unit app_tests.
Provides mock models, repositories, and services for testing.
"""

import datetime
import uuid
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from test_layer_base.mock_models import (
    MockCreateSchema,
    MockModel,
    MockRepository,
    MockSoftDeleteRepository,
    MockUpdateSchema,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_model():
    """Create a mock model instance."""
    model = MockModel(
        id=uuid.uuid4(),
        name="Test Item",
        description="Test Description",
        created_at=datetime.datetime.now(UTC),
        updated_at=datetime.datetime.now(UTC),
    )
    return model


@pytest.fixture
def mock_repository():
    """Create a MockRepository instance."""
    return MockRepository()


@pytest.fixture
def mock_soft_delete_repository():
    """Create a MockSoftDeleteRepository instance."""
    return MockSoftDeleteRepository()


@pytest.fixture
def mock_async_session():
    """Create a fully mocked async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def sample_uuid():
    """Provide a consistent UUID for testing."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_create_schema():
    """Create a sample create schema."""
    return MockCreateSchema(name="New Item", description="New Description")


@pytest.fixture
def mock_update_schema():
    """Create a sample update schema."""
    return MockUpdateSchema(name="Updated Item")
