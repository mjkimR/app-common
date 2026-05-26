import pytest
from app_base.ai.models.registry import AIModelRegistry
from app_base.ai.models.schemas import AIModelType


def catalog_config():
    return {
        "router": {"routing_strategy": "simple-shuffle", "num_retries": 2},
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
        "collections": [
            {
                "name": "local-models",
                "type": "llm",
                "members": ["gpt-4o-mini", "default-llm"],
                "default": "default-llm",
            }
        ],
    }


class TestAIModelRegistry:
    def test_resolves_aliases_and_builds_router_model_list(self):
        registry = AIModelRegistry(catalog_config())

        assert registry.resolve_name("default-llm", AIModelType.LLM) == "chat-fast"
        assert registry.resolve_name("gpt-4o-mini", "llm") == "gpt-4o-mini"
        assert registry.get_dimension("default-embedding") == 1536
        assert registry.router_settings.routing_strategy == "simple-shuffle"
        assert registry.router_settings.num_retries == 2

        model_list = registry.get_router_model_list()
        assert [item["model_name"] for item in model_list] == [
            "gpt-4o-mini",
            "embedding-small",
            "chat-fast",
            "chat-fast",
        ]
        assert model_list[2]["litellm_params"]["weight"] == 8

    def test_router_model_list_skips_exact_duplicate_specs(self):
        config = catalog_config()
        config["routes"][0]["deployments"].append(
            {"litellm_params": {"model": "openai/gpt-4o-mini", "api_key": "key", "weight": 8}}
        )
        registry = AIModelRegistry(config)

        model_list = registry.get_router_model_list()

        assert [item["model_name"] for item in model_list] == [
            "gpt-4o-mini",
            "embedding-small",
            "chat-fast",
            "chat-fast",
        ]

    def test_catalog_and_collections_are_separate(self):
        registry = AIModelRegistry(catalog_config())

        catalog = registry.get_catalog(AIModelType.LLM)
        assert [item.name for item in catalog] == ["default-llm", "gpt-4o-mini", "chat-fast"]

        collections = registry.get_collections(AIModelType.LLM)
        assert len(collections) == 1
        assert collections[0].name == "local-models"
        assert registry.get_collection("local-models").members == ["gpt-4o-mini", "default-llm"]

    def test_type_mismatch_is_rejected(self):
        registry = AIModelRegistry(catalog_config())

        with pytest.raises(ValueError, match="operation expects 'text-embedding'"):
            registry.resolve_name("default-llm", AIModelType.EMBEDDING)

    def test_alias_target_must_exist(self):
        config = catalog_config()
        config["aliases"] = [{"name": "missing", "type": "llm", "target": "nope"}]

        with pytest.raises(ValueError, match="Model, route, or alias 'nope' not found"):
            AIModelRegistry(config)

    def test_collection_member_types_must_match(self):
        config = catalog_config()
        config["collections"] = [
            {"name": "bad", "type": "llm", "members": ["embedding-small"]},
        ]

        with pytest.raises(ValueError, match="Collection 'bad' member 'embedding-small' type"):
            AIModelRegistry(config)

    def test_circular_alias_is_rejected(self):
        config = catalog_config()
        config["aliases"] = [
            {"name": "a", "type": "llm", "target": "b"},
            {"name": "b", "type": "llm", "target": "a"},
        ]

        with pytest.raises(ValueError, match="Circular reference detected"):
            AIModelRegistry(config)

    def test_cache_dimension_stores_dynamic_embedding_dimension(self):
        config = catalog_config()
        config["models"][1].pop("model_info")
        registry = AIModelRegistry(config)

        registry.cache_dimension("default-embedding", 3)

        assert registry.get_dimension("embedding-small") == 3
        assert registry.models["embedding-small"].model_info == {}
