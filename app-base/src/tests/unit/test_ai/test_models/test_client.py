from unittest.mock import MagicMock

import pytest
from app_base.ai.models.client import AIClient, LiteLLMEmbeddingsAdapter


@pytest.fixture
def raw_config():
    return {
        "router": {
            "routing_strategy": "simple-shuffle",
            "num_retries": 2,
            "fallbacks": [{"chat-fast": ["gpt-4o-mini"]}],
            "context_window_fallbacks": [{"chat-fast": ["gpt-4o-mini"]}],
        },
        "models": [
            {
                "name": "gpt-4o-mini",
                "type": "llm",
                "litellm_params": {"model": "openai/gpt-4o-mini", "api_key": "key"},
            },
            {
                "name": "embedding-small",
                "type": "text-embedding",
                "litellm_params": {"model": "openai/text-embedding-3-small", "api_key": "key"},
                "model_info": {"dimension": 1536},
            },
            {
                "name": "dall-e-3",
                "type": "image-generation",
                "litellm_params": {"model": "openai/dall-e-3", "api_key": "key"},
            },
        ],
        "routes": [
            {
                "name": "chat-fast",
                "type": "llm",
                "deployments": [
                    {"litellm_params": {"model": "openai/gpt-4o-mini", "api_key": "key", "weight": 8}},
                    {
                        "litellm_params": {
                            "model": "anthropic/claude-3-5-haiku-latest",
                            "api_key": "key",
                            "weight": 2,
                        }
                    },
                ],
            }
        ],
        "aliases": [
            {"name": "default-llm", "type": "llm", "target": "chat-fast"},
            {"name": "default-embedding", "type": "text-embedding", "target": "embedding-small"},
        ],
        "collections": [],
    }


@pytest.fixture
def mock_router(mocker):
    mock_router_cls = mocker.MagicMock()
    router = mock_router_cls.return_value
    mock_litellm_router = mocker.MagicMock(Router=mock_router_cls)
    mocker.patch.dict("sys.modules", {"litellm.router": mock_litellm_router})
    return mock_router_cls, router


class TestAIClient:
    def test_initializes_litellm_router(self, mocker, raw_config, mock_router, tmp_path):
        mock_load = mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        mock_router_cls, _ = mock_router

        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        assert client.registry.resolve_name("default-llm") == "chat-fast"
        mock_load.assert_called_once_with(str(tmp_path / "catalog.yml"))
        mock_router_cls.assert_called_once()
        kwargs = mock_router_cls.call_args.kwargs
        assert kwargs["routing_strategy"] == "simple-shuffle"
        assert kwargs["num_retries"] == 2
        assert kwargs["fallbacks"] == [{"chat-fast": ["gpt-4o-mini"]}]
        assert kwargs["context_window_fallbacks"] == [{"chat-fast": ["gpt-4o-mini"]}]
        assert [item["model_name"] for item in kwargs["model_list"]] == [
            "gpt-4o-mini",
            "embedding-small",
            "dall-e-3",
            "chat-fast",
            "chat-fast",
        ]

    def test_completion_delegates_to_router_with_resolved_name(self, mocker, raw_config, mock_router, tmp_path):
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        router.completion.return_value = {"choices": []}
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        result = client.completion("default-llm", [{"role": "user", "content": "hi"}], temperature=0.2)

        assert result == {"choices": []}
        router.completion.assert_called_once_with(
            model="chat-fast",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.2,
        )

    def test_embedding_adapter_extracts_vectors(self, mocker, raw_config, mock_router, tmp_path):
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        router.embedding.return_value = {
            "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}],
        }
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        adapter = client.get_embedding("default-embedding")

        assert isinstance(adapter, LiteLLMEmbeddingsAdapter)
        assert adapter.embed_documents(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]
        router.embedding.assert_called_once_with(model="embedding-small", input=["a", "b"])

    def test_get_embedding_dimension_uses_metadata_before_dynamic_call(self, mocker, raw_config, mock_router, tmp_path):
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        assert client.get_embedding_dimension("default-embedding") == 1536
        router.embedding.assert_not_called()

    def test_dynamic_embedding_dimension(self, mocker, raw_config, mock_router, tmp_path):
        raw_config["models"][1].pop("model_info")
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        router.embedding.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        assert client.get_embedding_dimension("default-embedding") == 3
        assert client.get_embedding_dimension("default-embedding") == 3
        router.embedding.assert_called_once_with(model="embedding-small", input="test")

    async def test_dynamic_embedding_dimension_async(self, mocker, raw_config, mock_router, tmp_path):
        raw_config["models"][1].pop("model_info")
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        router.aembedding = mocker.AsyncMock(return_value={"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        assert await client.aget_embedding_dimension("default-embedding") == 3
        assert await client.aget_embedding_dimension("default-embedding") == 3
        router.aembedding.assert_awaited_once_with(model="embedding-small", input="test")

    async def test_embedding_adapter_extracts_vectors_async(self, mocker, raw_config, mock_router, tmp_path):
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        router.aembedding = mocker.AsyncMock(
            return_value={
                "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}],
            }
        )
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        adapter = client.get_embedding("default-embedding")

        assert await adapter.aembed_documents(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]
        router.aembedding.assert_awaited_once_with(model="embedding-small", input=["a", "b"])

    def test_clients_can_use_independent_config_paths(self, mocker, raw_config, mock_router, tmp_path):
        mock_load = mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        first_path = str(tmp_path / "catalog.yml")
        second_path = str(tmp_path / "other-catalog.yml")

        first = AIClient(config_path=first_path)
        second = AIClient(config_path=second_path)

        assert first is not second
        assert [call.args[0] for call in mock_load.call_args_list] == [first_path, second_path]

    def test_reload_reloads_same_config_path(self, mocker, raw_config, mock_router, tmp_path):
        mock_load = mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        mock_router_cls, _ = mock_router
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        client.reload()

        assert mock_load.call_count == 2
        mock_load.assert_called_with(str(tmp_path / "catalog.yml"))
        assert mock_router_cls.call_count == 2

    def test_image_generation_delegates_to_router(self, mocker, raw_config, mock_router, tmp_path):
        mocker.patch("app_base.ai.models.client.ConfigLoader.load_yaml_with_env", return_value=raw_config)
        _, router = mock_router
        router.image_generation.return_value = MagicMock()
        client = AIClient(config_path=str(tmp_path / "catalog.yml"))

        client.image_generation("dall-e-3", "a city")

        router.image_generation.assert_called_once_with(model="dall-e-3", prompt="a city")
