from unittest.mock import MagicMock

import pytest
from app_base.ai.models.factory_llm import LLMFactory
from app_base.ai.models.schemas import AIModelItem


class TestLLMFactory:
    @pytest.fixture
    def llm_factory(self):
        return LLMFactory()

    @pytest.fixture
    def mock_model_item(self):
        # A basic AIModelItem for testing
        item = MagicMock(spec=AIModelItem)
        item.get_mapped_args.return_value = {}
        return item

    @pytest.fixture(autouse=True)
    def mock_langchain_llm_imports(self, mocker):
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

    def test_create_model_openai(self, llm_factory, mock_model_item, mock_langchain_llm_imports):
        mock_langchain_openai, _ = mock_langchain_llm_imports
        mock_model_item.provider = "openai"
        mock_model_item.get_mapped_args.return_value = {"temperature": 0.7}

        llm = llm_factory.create_model(mock_model_item)

        mock_langchain_openai.ChatOpenAI.assert_called_once_with(temperature=0.7)
        assert llm == mock_langchain_openai.ChatOpenAI.return_value

    def test_create_model_openai_compatible(self, llm_factory, mock_model_item, mock_langchain_llm_imports):
        mock_langchain_openai, _ = mock_langchain_llm_imports
        mock_model_item.provider = "openai-compatible"
        mock_model_item.get_mapped_args.return_value = {"base_url": "http://localhost"}

        llm = llm_factory.create_model(mock_model_item)

        mock_langchain_openai.ChatOpenAI.assert_called_once_with(base_url="http://localhost")
        assert llm == mock_langchain_openai.ChatOpenAI.return_value

    def test_create_model_google(self, llm_factory, mock_model_item, mock_langchain_llm_imports):
        _, mock_langchain_google_genai = mock_langchain_llm_imports
        mock_model_item.provider = "google"
        mock_model_item.get_mapped_args.return_value = {"api_key": "test_key", "model": "gemini-pro"}

        llm = llm_factory.create_model(mock_model_item)

        mock_langchain_google_genai.ChatGoogleGenerativeAI.assert_called_once_with(
            google_api_key="test_key", model="gemini-pro"
        )
        assert llm == mock_langchain_google_genai.ChatGoogleGenerativeAI.return_value

    def test_create_model_google_no_api_key_mapping(self, llm_factory, mock_model_item, mock_langchain_llm_imports):
        _, mock_langchain_google_genai = mock_langchain_llm_imports
        mock_model_item.provider = "google"
        mock_model_item.get_mapped_args.return_value = {"model": "gemini-pro"}

        llm = llm_factory.create_model(mock_model_item)

        mock_langchain_google_genai.ChatGoogleGenerativeAI.assert_called_once_with(model="gemini-pro")
        assert llm == mock_langchain_google_genai.ChatGoogleGenerativeAI.return_value

    def test_create_model_unsupported_provider(self, llm_factory, mock_model_item):
        mock_model_item.provider = "unsupported"
        mock_model_item.get_mapped_args.return_value = {}

        with pytest.raises(ValueError, match="Unsupported LLM provider: unsupported"):
            llm_factory.create_model(mock_model_item)

    def test_create_model_import_error(self, llm_factory, mock_model_item, mock_langchain_llm_imports):
        # We need to simulate ImportError when ChatOpenAI is accessed.
        # This means the mock_langchain_openai.ChatOpenAI should raise ImportError.
        mock_langchain_openai, _ = mock_langchain_llm_imports
        mock_langchain_openai.ChatOpenAI.side_effect = ImportError("Simulated ImportError")

        mock_model_item.provider = "openai"
        mock_model_item.get_mapped_args.return_value = {}

        with pytest.raises(ImportError, match="Failed to import dependencies for provider 'openai'"):
            llm_factory.create_model(mock_model_item)

        mock_langchain_openai.ChatOpenAI.assert_called_once()
