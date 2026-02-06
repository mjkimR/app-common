import os
from unittest.mock import MagicMock, patch

import pytest
import yaml
from app_base.ai.models.factory import AIModelFactory, ConfigLoader
from app_base.ai.models.schemas import AIModelType


# Mock logger to prevent actual logging during tests
@pytest.fixture(autouse=True)
def mock_logger():
    with patch("app_base.ai.models.factory.logger") as mock_log:
        yield mock_log


@pytest.fixture(autouse=True)
def cleanup_singleton():
    """Ensure a clean AIModelFactory singleton instance for each test."""
    AIModelFactory._instance = None
    yield
    AIModelFactory._instance = None


class TestConfigLoader:
    def test_load_yaml_with_env_success(self, tmp_path):
        config_content = """
        key: value
        db_url: ${TEST_DB_URL}
        api_key: ${NON_EXISTENT_VAR:-default_api_key}
        """
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)

        os.environ["TEST_DB_URL"] = "sqlite:///test.db"

        loaded_config = ConfigLoader.load_yaml_with_env(str(config_file))

        assert loaded_config == {
            "key": "value",
            "db_url": "sqlite:///test.db",
            "api_key": "default_api_key",
        }
        del os.environ["TEST_DB_URL"]

    def test_load_yaml_with_env_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            ConfigLoader.load_yaml_with_env(str(tmp_path / "non_existent.yml"))

    @patch("app_base.ai.models.factory.logger")
    def test_load_yaml_with_env_missing_env_var_no_default(self, mock_log, tmp_path):
        config_content = """
        key: ${MISSING_VAR}
        """
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)

        loaded_config = ConfigLoader.load_yaml_with_env(str(config_file))
        assert loaded_config == {"key": ""}
        mock_log.warning.assert_called_once_with(
            "Environment variable 'MISSING_VAR' is not set but required in config."
        )


class TestAIModelFactory:
    @pytest.fixture
    def mock_catalog_file(self, tmp_path):
        catalog_content = {
            "models": [
                {"name": "llm-model-1", "type": "llm", "provider": "openai", "args": {"temperature": 0.7}},
                {"name": "llm-model-2", "type": "llm", "provider": "google"},
                {"name": "embedding-model-1", "type": "text-embedding", "provider": "openai"},
            ],
            "aliases": [
                {"name": "default-llm", "type": "llm", "target": "llm-model-1"},
                {"name": "alias-to-alias", "type": "llm", "target": "default-llm"},
            ],
            "groups": [
                {
                    "name": "llm-group",
                    "type": "llm",
                    "members": ["llm-model-1", "default-llm"],
                    "default": "default-llm",
                }
            ],
        }
        file_path = tmp_path / "catalog.yml"
        with open(file_path, "w") as f:
            yaml.dump(catalog_content, f)
        return str(file_path)

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")  # Mock project root
    def test_singleton_pattern(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, tmp_path
    ):
        mock_load_yaml.return_value = {"models": [], "aliases": [], "groups": []}
        factory1 = AIModelFactory(config_path=str(tmp_path / "catalog.yml"))
        factory2 = AIModelFactory(
            config_path=str(tmp_path / "another_catalog.yml")
        )  # Should ignore this path after first init

        assert factory1 is factory2
        mock_load_yaml.assert_called_once()  # Only loaded once

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_initialization_success(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        mock_load_yaml.return_value = {
            "models": [
                {"name": "m1", "type": "llm", "provider": "p1"},
            ],
            "aliases": [],
            "groups": [],
        }
        factory = AIModelFactory(config_path=mock_catalog_file)

        assert "m1" in factory.models
        MockLLMFactory.assert_called_once()
        MockEmbeddingFactory.assert_called_once()
        mock_load_yaml.assert_called_once_with(mock_catalog_file)
        assert factory._initialized is True
        assert factory._config_path == mock_catalog_file

    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_initialization_model_validation_error(self, mock_get_project_root, mock_load_yaml, tmp_path):
        mock_load_yaml.return_value = {
            "models": [
                {"name": "m1"},  # Missing type and provider
            ],
            "aliases": [],
            "groups": [],
        }
        with pytest.raises(ValueError, match="Error in models item 'm1'"):
            AIModelFactory(config_path=str(tmp_path / "catalog.yml"))

    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_initialization_alias_validation_error(self, mock_get_project_root, mock_load_yaml, tmp_path):
        mock_load_yaml.return_value = {
            "models": [],
            "aliases": [
                {"name": "a1", "type": "llm", "target": "non-existent"},
            ],
            "groups": [],
        }
        with pytest.raises(
            ValueError, match="Configuration Error: Alias 'a1' refers to non-existent target 'non-existent'"
        ):
            AIModelFactory(config_path=str(tmp_path / "catalog.yml"))

    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_initialization_group_validation_error(self, mock_get_project_root, mock_load_yaml, tmp_path):
        mock_load_yaml.return_value = {
            "models": [
                {"name": "m1", "type": "llm", "provider": "p1"},
            ],
            "aliases": [],
            "groups": [
                {"name": "g1", "type": "llm", "members": ["non-existent"]},
            ],
        }
        with pytest.raises(ValueError, match="Model group 'g1' has unknown member 'non-existent'"):
            AIModelFactory(config_path=str(tmp_path / "catalog.yml"))

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_get_llm(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        mock_llm_instance = MagicMock()
        mock_llm_instance.bind.return_value = mock_llm_instance
        MockLLMFactory.return_value.create_model.return_value = mock_llm_instance

        # Setup raw_config for _initial_dictionaries to populate models and aliases
        mock_load_yaml.return_value = {
            "models": [
                {"name": "llm-model-1", "type": "llm", "provider": "openai", "args": {"temperature": 0.7}},
                {"name": "embedding-model-1", "type": "text-embedding", "provider": "openai"},
            ],
            "aliases": [
                {"name": "default-llm", "type": "llm", "target": "llm-model-1"},
            ],
            "groups": [],
        }

        factory = AIModelFactory(config_path=mock_catalog_file)

        # Test direct model access
        llm = factory.get_llm("llm-model-1")
        MockLLMFactory.return_value.create_model.assert_called_once()
        assert llm == mock_llm_instance
        MockLLMFactory.return_value.create_model.reset_mock()  # Reset mock for next call

        # Test alias access
        llm_alias = factory.get_llm("default-llm", top_p=0.9)
        MockLLMFactory.return_value.create_model.assert_called_once()
        mock_llm_instance.bind.assert_called_once_with(top_p=0.9)
        assert llm_alias == mock_llm_instance
        MockLLMFactory.return_value.create_model.reset_mock()
        mock_llm_instance.bind.reset_mock()

        # Test type mismatch
        with pytest.raises(
            ValueError,
            match="Type mismatch: Requested model 'embedding-model-1' is 'text-embedding', but operation expects 'llm'",
        ):
            factory.get_llm("embedding-model-1")

        # Test model not found
        with pytest.raises(ValueError, match="Model 'non-existent' not found in models."):
            factory.get_llm("non-existent")

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_get_fallback_llms(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        # Configure create_model to return different mocks for different configs
        # Configure create_model to return a new MagicMock each time
        MockLLMFactory.return_value.create_model.return_value = MagicMock()

        mock_load_yaml.return_value = {
            "models": [
                {
                    "name": "llm-main",
                    "type": "llm",
                    "provider": "p1",
                    "fallbacks": ["llm-fallback-1", "llm-fallback-2"],
                },
                {"name": "llm-fallback-1", "type": "llm", "provider": "p2"},
                {"name": "llm-fallback-2", "type": "llm", "provider": "p3"},
                {"name": "embedding-main", "type": "text-embedding", "provider": "p4"},
            ],
            "aliases": [
                {"name": "alias-with-fallback", "type": "llm", "target": "llm-main", "fallbacks": ["llm-fallback-1"]},
            ],
            "groups": [],
        }

        factory = AIModelFactory(config_path=mock_catalog_file)

        # Reset mock before first set of calls to count calls accurately
        MockLLMFactory.return_value.create_model.reset_mock()

        fallbacks = factory.get_fallback_llms("llm-main")
        assert len(fallbacks) == 2
        # Assert that create_model was called twice
        assert MockLLMFactory.return_value.create_model.call_count == 2
        MockLLMFactory.return_value.create_model.reset_mock()

        # Test alias with fallbacks
        alias_fallbacks = factory.get_fallback_llms("alias-with-fallback")
        assert len(alias_fallbacks) == 1
        assert MockLLMFactory.return_value.create_model.call_count == 0  # Should be 0 due to cache

        # Test errors
        with pytest.raises(
            ValueError,
            match="Type mismatch: Model 'embedding-main' is type 'text-embedding', but LLM fallbacks were requested.",
        ):
            factory.get_fallback_llms("embedding-main")

        with pytest.raises(ValueError, match="Model or Alias 'non-existent' not found in models or aliases."):
            factory.get_fallback_llms("non-existent")

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_get_embedding(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        mock_embedding_instance = MagicMock()
        MockEmbeddingFactory.return_value.create_model.return_value = mock_embedding_instance

        mock_load_yaml.return_value = {
            "models": [
                {"name": "embedding-model-1", "type": "text-embedding", "provider": "openai"},
                {"name": "llm-model-1", "type": "llm", "provider": "openai"},
            ],
            "aliases": [
                {"name": "default-embedding", "type": "text-embedding", "target": "embedding-model-1"},
            ],
            "groups": [],
        }

        factory = AIModelFactory(config_path=mock_catalog_file)

        # Test direct model access
        embedding = factory.get_embedding("embedding-model-1")
        MockEmbeddingFactory.return_value.create_model.assert_called_once()
        assert embedding == mock_embedding_instance
        MockEmbeddingFactory.return_value.create_model.reset_mock()

        # Test alias access
        embedding_alias = factory.get_embedding("default-embedding")
        MockEmbeddingFactory.return_value.create_model.assert_called_once()
        assert embedding_alias == mock_embedding_instance

        # Test type mismatch
        with pytest.raises(
            ValueError,
            match="Type mismatch: Requested model 'llm-model-1' is 'llm', but operation expects 'text-embedding'",
        ):
            factory.get_embedding("llm-model-1")

        # Test model not found
        with pytest.raises(ValueError, match="Model 'non-existent' not found in models."):
            factory.get_embedding("non-existent")

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_get_embedding_dimension(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        mock_load_yaml.return_value = {
            "models": [
                {"name": "embedding-dim-1", "type": "text-embedding", "provider": "p1", "dimension": 100},
                {"name": "embedding-dim-2", "type": "text-embedding", "provider": "p2"},  # No dimension in config
                {"name": "llm-model", "type": "llm", "provider": "p3"},
            ],
            "aliases": [
                {"name": "alias-embedding-dim-1", "type": "text-embedding", "target": "embedding-dim-1"},
            ],
            "groups": [],
        }
        factory = AIModelFactory(config_path=mock_catalog_file)

        # Test dimension from config
        dim = factory.get_embedding_dimension("embedding-dim-1")
        assert dim == 100
        MockEmbeddingFactory.return_value.get_dimension.assert_not_called()

        # Test dimension from alias (which points to a model with dimension in config)
        dim_alias = factory.get_embedding_dimension("alias-embedding-dim-1")
        assert dim_alias == 100
        MockEmbeddingFactory.return_value.get_dimension.assert_not_called()

        # Test dimension dynamically calculated
        MockEmbeddingFactory.return_value.get_dimension.return_value = 200
        dim_dynamic = factory.get_embedding_dimension("embedding-dim-2")
        assert dim_dynamic == 200
        MockEmbeddingFactory.return_value.get_dimension.assert_called_once()
        MockEmbeddingFactory.return_value.get_dimension.reset_mock()

        # Test type mismatch
        with pytest.raises(
            ValueError,
            match="Type mismatch: Requested model 'llm-model' is 'llm', but operation expects 'text-embedding'",
        ):
            factory.get_embedding_dimension("llm-model")

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_get_catalog(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        mock_load_yaml.return_value = {
            "models": [
                {"name": "llm-model-1", "type": "llm", "provider": "openai"},
                {"name": "embedding-model-1", "type": "text-embedding", "provider": "google"},
                {"name": "llm-model-2", "type": "llm", "provider": "anthropic"},
            ],
            "aliases": [
                {"name": "default-llm", "type": "llm", "target": "llm-model-1"},
                {"name": "default-embedding", "type": "text-embedding", "target": "embedding-model-1"},
            ],
            "groups": [],
        }

        factory = AIModelFactory(config_path=mock_catalog_file)

        llm_catalog = factory.get_catalog(AIModelType.LLM)
        assert len(llm_catalog) == 3
        # Ensure sorting: alias comes last if provider same, then by name
        assert [item.name for item in llm_catalog] == ["llm-model-2", "llm-model-1", "default-llm"]

        embedding_catalog = factory.get_catalog("text-embedding")
        assert len(embedding_catalog) == 2
        assert [item.name for item in embedding_catalog] == ["embedding-model-1", "default-embedding"]

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    def test_get_group(
        self, mock_get_project_root, mock_load_yaml, MockEmbeddingFactory, MockLLMFactory, mock_catalog_file
    ):
        mock_load_yaml.return_value = {
            "models": [
                {"name": "llm-model-A", "type": "llm", "provider": "p1"},
                {"name": "llm-model-B", "type": "llm", "provider": "p2"},
            ],
            "aliases": [],
            "groups": [
                {
                    "name": "group-llm",
                    "type": "llm",
                    "members": ["llm-model-A", "llm-model-B"],
                    "default": "llm-model-A",
                },
            ],
        }

        factory = AIModelFactory(config_path=mock_catalog_file)

        group = factory.get_group("group-llm")
        assert group.name == "group-llm"
        assert group.type == AIModelType.LLM
        assert len(group.members) == 2
        assert group.default == "llm-model-A"

        with pytest.raises(ValueError, match="Model group 'non-existent-group' not found."):
            factory.get_group("non-existent-group")

    @patch("app_base.ai.models.factory.LLMFactory")
    @patch("app_base.ai.models.factory.EmbeddingFactory")
    @patch("app_base.ai.models.factory.ConfigLoader.load_yaml_with_env")
    @patch("app_base.ai.models.factory.get_project_root", return_value="/tmp")
    @patch.object(AIModelFactory, "_get_llm")  # Patch the actual method
    @patch.object(AIModelFactory, "_get_embedding")  # Patch the actual method
    def test_reload(
        self,
        mock_get_embedding,
        mock_get_llm,
        mock_get_project_root,
        mock_load_yaml,
        MockEmbeddingFactory,
        MockLLMFactory,
        mock_catalog_file,
    ):
        # Initial load
        mock_load_yaml.return_value = {
            "models": [{"name": "initial-model", "type": "llm", "provider": "test"}],
            "aliases": [],
            "groups": [],
        }
        factory = AIModelFactory(config_path=mock_catalog_file)
        assert "initial-model" in factory.models
        mock_load_yaml.assert_called_once()

        # Ensure cache_clear is a mock function on the patched methods
        mock_get_llm.cache_clear = MagicMock()
        mock_get_embedding.cache_clear = MagicMock()

        # Modify config content and reload
        mock_load_yaml.return_value = {
            "models": [{"name": "reloaded-model", "type": "llm", "provider": "test"}],
            "aliases": [],
            "groups": [],
        }
        factory.reload()

        assert "initial-model" not in factory.models
        assert "reloaded-model" in factory.models
        assert mock_load_yaml.call_count == 2
        mock_get_llm.cache_clear.assert_called_once()
        mock_get_embedding.cache_clear.assert_called_once()
