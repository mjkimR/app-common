import pytest
from app_vector_store.config import VectorDBProviderType, VectorDBSettings


@pytest.fixture
def mock_qdrant_settings():
    return VectorDBSettings(
        VECTOR_DB_PROVIDER=VectorDBProviderType.QDRANT,
    )
