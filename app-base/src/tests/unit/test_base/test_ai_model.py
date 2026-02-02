import os
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Modules to test
from app_base.ai.models.factory import AIModelFactory, ConfigLoader
from app_base.ai.models.schemas import AIModelItem

# Mock external dependencies
mock_openai = MagicMock()
mock_google = MagicMock()


@pytest.fixture(autouse=True)
def mock_langchain_imports():
    """Mocks the langchain provider modules for the duration of a test."""
    with patch.dict(
        "sys.modules",
        {
            "langchain_openai": mock_openai,
            "langchain_google_genai": mock_google,
        },
    ):
        yield
        mock_openai.reset_mock()
        mock_google.reset_mock()


@pytest.fixture(autouse=True)
def mock_schemas():
    """
    Mocks the Pydantic schema classes that are not available in the test context.
    This fixture patches the factory module where these schemas are imported.
    """

    class MockAIModelType(str, Enum):
        LLM = "llm"
        EMBEDDING = "text-embedding"
        STT = "stt"
        TTS = "tts"
        IMAGE_GEN = "image-generation"

    class MockBaseItem:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]
            self.type = MockAIModelType(kwargs["type"])
            self.help = kwargs.get("help")
            # Emulate Pydantic's behavior
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self, exclude_unset=False):
            # Simple version for testing
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    class MockAIModelItem(MockBaseItem):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.provider = kwargs.get("provider")
            self.args = kwargs.get("args", {})
            self.fallbacks = kwargs.get("fallbacks", [])

        def to_catalog_item(self):
            return MagicMock(kind="model", name=self.name, provider=self.provider)

    class MockAIModelAliasItem(MockBaseItem):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.target = kwargs["target"]
            self.fallbacks = kwargs.get("fallbacks", [])

        def to_catalog_item(self):
            return MagicMock(kind="alias", name=self.name, provider=None)  # Aliases don't have a provider

    with patch.dict(
        "sys.modules",
        {
            "app_base.base.models.schemas": MagicMock(
                AIModelType=MockAIModelType,
                AIModelItem=MockAIModelItem,
                AIModelAliasItem=MockAIModelAliasItem,
                AICatalogItem=MagicMock,
            )
        },
    ):
        yield


@pytest.fixture
def temp_config_file(tmp_path):
    """A pytest fixture to create a temporary YAML config file for testing."""

    def _create_config(data):
        config_path = tmp_path / "catalog.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)
        return str(config_path)

    return _create_config


def test_config_loader_with_env_vars(tmp_path):
    os.environ["TEST_API_KEY"] = "my-secret-key"
    config_content = "key: ${TEST_API_KEY}\nanother_key: value"
    config_path = tmp_path / "config.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_content)
    loaded_config = ConfigLoader.load_yaml_with_env(str(config_path))
    assert loaded_config["key"] == "my-secret-key"
    del os.environ["TEST_API_KEY"]


class TestAIModelFactory:
    @pytest.fixture(autouse=True)
    def clear_singleton(self):
        if AIModelFactory._instance:
            AIModelFactory._instance = None
        yield
        if AIModelFactory._instance:
            AIModelFactory._instance = None

    @pytest.fixture
    def valid_config(self):
        return {
            "models": [
                {
                    "name": "gpt-4",
                    "type": "llm",
                    "provider": "openai",
                    "args": {"model": "gpt-4"},
                },
                {
                    "name": "gemini-pro",
                    "type": "llm",
                    "provider": "google",
                    "args": {"model": "gemini-pro"},
                },
                {
                    "name": "fallback-gpt",
                    "type": "llm",
                    "provider": "openai",
                    "args": {"model": "gpt-3.5-turbo"},
                },
                {
                    "name": "text-embedding-ada",
                    "type": "text-embedding",
                    "provider": "openai",
                    "args": {"model": "text-embedding-ada-002"},
                },
            ],
            "aliases": [
                {
                    "name": "main-llm",
                    "type": "llm",
                    "target": "gpt-4",
                    "fallbacks": ["fallback-gpt"],
                },
                {
                    "name": "main-embedding",
                    "type": "text-embedding",
                    "target": "text-embedding-ada",
                },
            ],
            "groups": [
                {
                    "name": "default-group",
                    "type": "llm",
                    "members": ["main-llm", "gemini-pro"],
                    "default": "main-llm",
                }
            ],
        }

    def test_initialization_with_valid_config(self, temp_config_file, valid_config):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)
        assert "gpt-4" in factory.models
        assert "main-llm" in factory.aliases
        assert hasattr(factory.models["gpt-4"], "provider")  # Check it's an object
        assert factory._initialized

    def test_get_llm(self, temp_config_file, valid_config):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)
        factory.llm_factory.create_model = MagicMock(return_value="mock_llm")

        llm = factory.get_llm("gpt-4")
        assert llm == "mock_llm"
        # Assert that a dictionary representation is passed
        factory.llm_factory.create_model.assert_called_once_with(AIModelItem.model_validate(valid_config["models"][0]))

    def test_get_embedding(self, temp_config_file, valid_config):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)
        factory.embedding_factory.create_model = MagicMock(return_value="mock_embedding")

        embedding = factory.get_embedding("text-embedding-ada")
        assert embedding == "mock_embedding"
        factory.embedding_factory.create_model.assert_called_once_with(
            AIModelItem.model_validate(valid_config["models"][3])
        )

    def test_get_fallback_llms(self, temp_config_file, valid_config):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)
        mock_fallback_llm = MagicMock()

        with patch.object(factory, "get_llm", return_value=mock_fallback_llm) as mock_get_llm:
            fallbacks = factory.get_fallback_llms("main-llm")
            assert fallbacks == [mock_fallback_llm]
            mock_get_llm.assert_called_once_with("fallback-gpt")

    def test_get_catalog(self, temp_config_file, valid_config, mock_schemas):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)
        llm_catalog = factory.get_catalog("llm")

        # The mock `to_catalog_item` returns a MagicMock with attributes
        # The final sorting is by (is_alias, provider, name)
        # Providers: google, openai, openai | alias (None)
        # Expected order:
        # 1. gemini-pro (model, google)
        # 2. fallback-gpt (model, openai)
        # 3. gpt-4 (model, openai)
        # 4. main-llm (alias, None)
        names = [item.name for item in llm_catalog]
        kinds = [item.kind for item in llm_catalog]

        assert len(names) == 4
        assert names == ["gemini-pro", "fallback-gpt", "gpt-4", "main-llm"]
        assert kinds == ["model", "model", "model", "alias"]

    def test_get_group(self, temp_config_file, valid_config):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)

        group = factory.get_group("default-group")
        assert group.name == "default-group"
        assert group.type == factory.models["gpt-4"].type  # llm
        assert group.default == "main-llm"
        assert set(member.name for member in group.members) == {
            "main-llm",
            "gemini-pro",
        }

    def test_reload(self, temp_config_file, valid_config):
        config_path = temp_config_file(valid_config)
        factory = AIModelFactory(config_path)
        assert "gpt-4" in factory.models

        # Modify the config file to add a new model
        new_config = valid_config.copy()
        new_config["models"].append(
            {
                "name": "new-model",
                "type": "llm",
                "provider": "openai",
                "args": {"model": "gpt-5"},
            }
        )
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(new_config, f)

        factory.reload()
        assert "new-model" in factory.models


class TestAIModelFactoryValidation:
    """Test suite for configuration validation in AIModelFactory."""

    @pytest.fixture(autouse=True)
    def clear_singleton(self):
        if AIModelFactory._instance:
            AIModelFactory._instance = None
        yield
        if AIModelFactory._instance:
            AIModelFactory._instance = None

    def test_init_error_on_bad_field(self, temp_config_file):
        """Tests that Pydantic validation errors are caught on init."""
        config = {"models": [{"name": "gpt-4"}]}  # Missing 'type'
        config_path = temp_config_file(config)
        with pytest.raises(ValueError, match="Error in models item 'gpt-4'"):
            AIModelFactory(config_path)

    def test_alias_target_not_exist(self, temp_config_file):
        config = {
            "models": [{"name": "gpt-4", "type": "llm", "provider": "openai"}],
            "aliases": [{"name": "my-alias", "type": "llm", "target": "non-existent"}],
        }
        config_path = temp_config_file(config)
        with pytest.raises(ValueError, match="refers to non-existent target 'non-existent'"):
            AIModelFactory(config_path)

    def test_alias_target_type_mismatch(self, temp_config_file):
        config = {
            "models": [{"name": "my-model", "type": "text-embedding", "provider": "openai"}],
            "aliases": [{"name": "my-alias", "type": "llm", "target": "my-model"}],
        }
        config_path = temp_config_file(config)
        with pytest.raises(
            ValueError,
            match=r"does not match final target 'my-model' type \(text-embedding\)",
        ):
            AIModelFactory(config_path)

    def test_fallback_type_mismatch(self, temp_config_file):
        """Tests that a fallback's type mismatch with the alias's type raises an error."""
        config = {
            "models": [
                {"name": "gpt-4", "type": "llm", "provider": "openai"},
                {
                    "name": "my-embedding",
                    "type": "text-embedding",
                    "provider": "openai",
                },
            ],
            "aliases": [
                {
                    "name": "my-alias",
                    "type": "llm",
                    "target": "gpt-4",
                    "fallbacks": ["my-embedding"],
                }
            ],
        }
        config_path = temp_config_file(config)
        with pytest.raises(
            ValueError,
            match=r"fallback 'my-embedding' type \(text-embedding\) does not match alias type \(llm\)",
        ):
            AIModelFactory(config_path)

    def test_name_conflict(self, temp_config_file):
        """Tests that a name conflict between models and aliases raises an error."""
        config = {
            "models": [
                {"name": "conflict-name", "type": "llm", "provider": "openai"},
                {"name": "gpt-4", "type": "llm", "provider": "openai"},
            ],
            "aliases": [{"name": "conflict-name", "type": "llm", "target": "gpt-4"}],
        }
        config_path = temp_config_file(config)
        with pytest.raises(
            ValueError,
            match="Model names must be unique. Conflicts found: {'conflict-name'}",
        ):
            AIModelFactory(config_path)

    def test_self_referential_fallback(self, temp_config_file):
        """Tests the new check for self-referential fallbacks."""
        config = {
            "models": [{"name": "gpt-4", "type": "llm", "provider": "openai"}],
            "aliases": [
                {
                    "name": "my-alias",
                    "type": "llm",
                    "target": "gpt-4",
                    "fallbacks": ["my-alias"],
                }
            ],
        }
        config_path = temp_config_file(config)
        with pytest.raises(ValueError, match="Alias 'my-alias' cannot have itself as a fallback"):
            AIModelFactory(config_path)

    def test_circular_alias_target(self, temp_config_file):
        """Tests the new check for circular alias dependencies."""
        config = {
            "models": [{"name": "gpt-4", "type": "llm", "provider": "openai"}],
            "aliases": [
                {"name": "alias-a", "type": "llm", "target": "alias-b"},
                {"name": "alias-b", "type": "llm", "target": "alias-a"},
            ],
        }
        config_path = temp_config_file(config)
        with pytest.raises(
            ValueError,
            match="Circular reference detected in alias target chain: alias-a -> alias-b",
        ):
            AIModelFactory(config_path)

    def test_group_member_not_exist(self, temp_config_file):
        config = {
            "models": [{"name": "gpt-4", "type": "llm", "provider": "openai"}],
            "groups": [{"name": "test-group", "type": "llm", "members": ["gpt-4", "non-existent"], "default": "gpt-4"}],
        }
        config_path = temp_config_file(config)
        with pytest.raises(ValueError, match="Model group 'test-group' has unknown member 'non-existent'"):
            AIModelFactory(config_path)

    def test_group_member_type_mismatch(self, temp_config_file):
        config = {
            "models": [
                {"name": "gpt-4", "type": "llm", "provider": "openai"},
                {"name": "embedding", "type": "text-embedding", "provider": "openai"},
            ],
            "groups": [{"name": "test-group", "type": "llm", "members": ["gpt-4", "embedding"], "default": "gpt-4"}],
        }
        config_path = temp_config_file(config)
        with pytest.raises(
            ValueError,
            match=r"Model group 'test-group' has member 'embedding' with type \(text-embedding\) that does not match group type \(llm\)",
        ):
            AIModelFactory(config_path)

    def test_group_default_not_member(self, temp_config_file):
        config = {
            "models": [{"name": "gpt-4", "type": "llm", "provider": "openai"}],
            "groups": [{"name": "test-group", "type": "llm", "members": ["gpt-4"], "default": "non-member"}],
        }
        config_path = temp_config_file(config)
        with pytest.raises(
            ValueError, match="Model group 'test-group' has default 'non-member' which is not in its members list"
        ):
            AIModelFactory(config_path)
