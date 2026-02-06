from unittest.mock import MagicMock, patch

import pytest
from app_base.ai.models.factory_embedding import EmbeddingFactory
from app_base.ai.models.schemas import AIModelItem


class TestEmbeddingFactory:
    @pytest.fixture
    def embedding_factory(self):
        return EmbeddingFactory()

    @pytest.fixture
    def mock_model_item(self):
        item = MagicMock(spec=AIModelItem)
        item.name = "test-embedding-model"
        item.args = {}
        item.dimension = None  # Default for testing dynamic calculation
        return item

    @pytest.fixture(autouse=True)
    def mock_langchain_embedding_imports(self, mocker):
        # Create mock for langchain_openai and langchain_google_genai modules
        mock_langchain_openai = mocker.MagicMock()
        mock_langchain_google_genai = mocker.MagicMock()

        # Patch sys.modules to return our mock modules when imported
        mocker.patch.dict(
            "sys.modules",
            {
                "langchain_openai": mock_langchain_openai,
                "langchain_google_genai": mock_langchain_google_genai,
            },
        )
        return mock_langchain_openai, mock_langchain_google_genai

    def test_create_model_openai(self, embedding_factory, mock_model_item, mock_langchain_embedding_imports):
        mock_langchain_openai, _ = mock_langchain_embedding_imports
        mock_model_item.provider = "openai"
        mock_model_item.args = {"model": "text-embedding-ada-002"}

        embedding = embedding_factory.create_model(mock_model_item)

        mock_langchain_openai.OpenAIEmbeddings.assert_called_once_with(model="text-embedding-ada-002")
        assert embedding == mock_langchain_openai.OpenAIEmbeddings.return_value

    def test_create_model_openai_compatible(self, embedding_factory, mock_model_item, mock_langchain_embedding_imports):
        mock_langchain_openai, _ = mock_langchain_embedding_imports
        mock_model_item.provider = "openai-compatible"
        mock_model_item.args = {"base_url": "http://localhost:8000"}

        embedding = embedding_factory.create_model(mock_model_item)

        mock_langchain_openai.OpenAIEmbeddings.assert_called_once_with(base_url="http://localhost:8000")
        assert embedding == mock_langchain_openai.OpenAIEmbeddings.return_value

    def test_create_model_google(self, embedding_factory, mock_model_item, mock_langchain_embedding_imports):
        _, mock_langchain_google_genai = mock_langchain_embedding_imports
        mock_model_item.provider = "google"
        mock_model_item.args = {"api_key": "test_key", "model": "embedding-001"}

        embedding = embedding_factory.create_model(mock_model_item)

        mock_langchain_google_genai.GoogleGenerativeAIEmbeddings.assert_called_once_with(
            google_api_key="test_key", model="embedding-001"
        )
        assert embedding == mock_langchain_google_genai.GoogleGenerativeAIEmbeddings.return_value

    def test_create_model_google_no_api_key_mapping(
        self, embedding_factory, mock_model_item, mock_langchain_embedding_imports
    ):
        _, mock_langchain_google_genai = mock_langchain_embedding_imports
        mock_model_item.provider = "google"
        mock_model_item.args = {"model": "embedding-001"}

        embedding = embedding_factory.create_model(mock_model_item)

        mock_langchain_google_genai.GoogleGenerativeAIEmbeddings.assert_called_once_with(model="embedding-001")
        assert embedding == mock_langchain_google_genai.GoogleGenerativeAIEmbeddings.return_value

    def test_create_model_unsupported_provider(self, embedding_factory, mock_model_item):
        mock_model_item.provider = "unsupported"
        mock_model_item.args = {}

        with pytest.raises(ValueError, match="Unsupported Embedding provider: unsupported"):
            embedding_factory.create_model(mock_model_item)

    def test_create_model_import_error(self, embedding_factory, mock_model_item, mock_langchain_embedding_imports):
        mock_langchain_openai, _ = mock_langchain_embedding_imports
        mock_langchain_openai.OpenAIEmbeddings.side_effect = ImportError("Simulated ImportError")

        mock_model_item.provider = "openai"
        mock_model_item.args = {}

        with pytest.raises(ImportError, match="Failed to import dependencies for provider 'openai'"):
            embedding_factory.create_model(mock_model_item)
        mock_langchain_openai.OpenAIEmbeddings.assert_called_once()

    def test_get_dimension_from_config(self, embedding_factory, mock_model_item):
        mock_model_item.dimension = 1536
        dimension = embedding_factory.get_dimension(mock_model_item)
        assert dimension == 1536

    @patch.object(EmbeddingFactory, "create_model")
    def test_get_dimension_dynamically(self, mock_create_model, embedding_factory, mock_model_item):
        mock_model_item.dimension = None
        mock_model_item.provider = "openai"
        mock_model_item.args = {"model": "test-model"}

        # Mock the behavior of the created model
        mock_embedding_instance = MagicMock()
        mock_embedding_instance.embed_query.return_value = [0.1] * 128
        mock_create_model.return_value = mock_embedding_instance

        dimension = embedding_factory.get_dimension(mock_model_item)

        assert dimension == 128
        assert mock_model_item.dimension == 128  # Check if cached
        mock_create_model.assert_called_once_with(mock_model_item)
        mock_embedding_instance.embed_query.assert_called_once_with("test")

    @patch.object(EmbeddingFactory, "create_model")
    def test_get_dimension_dynamically_failure(self, mock_create_model, embedding_factory, mock_model_item):
        mock_model_item.dimension = None
        mock_model_item.provider = "openai"
        mock_model_item.args = {"model": "test-model"}

        mock_create_model.side_effect = Exception("Failed to create model")

        with pytest.raises(
            RuntimeError,
            match="Failed to determine embedding dimension for 'test-embedding-model': Failed to create model",
        ):
            embedding_factory.get_dimension(mock_model_item)
