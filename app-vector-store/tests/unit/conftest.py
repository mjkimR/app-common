import pytest
from app_vector_store.config import QdrantSettings, VectorDBSettings
from pydantic import SecretStr


@pytest.fixture
def mock_qdrant_settings():
    return VectorDBSettings(
        VECTOR_DB_PROVIDER="qdrant",
        config=QdrantSettings(url="http://localhost:6333", api_key=SecretStr("test_api_key")),
    )
