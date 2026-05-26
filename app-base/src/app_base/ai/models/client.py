import os
from threading import RLock
from typing import Any

from langchain_core.embeddings import Embeddings

from app_base.ai.models.config import ConfigLoader
from app_base.ai.models.registry import AIModelRegistry
from app_base.ai.models.schemas import AICatalogItem, AICollectionItem, AIModelType
from app_base.config import get_project_root
from app_base.core.log import logger


class AIClient:
    DEFAULT_PATH = os.path.join(get_project_root(), "catalog.yml")

    def __init__(self, config_path: str = DEFAULT_PATH):
        self._state_lock = RLock()
        self._initialize(config_path)

    def _initialize(self, config_path: str) -> None:
        logger.info(f"[System] Loading AI catalog from {config_path}...")
        raw_config = ConfigLoader.load_yaml_with_env(config_path)
        registry = AIModelRegistry(raw_config)
        router = self._create_router(registry)
        with self._state_lock:
            self.registry = registry
            self.router = router
            self._config_path = config_path

    def _create_router(self, registry: AIModelRegistry):
        try:
            from litellm.router import Router
        except ImportError as e:
            raise ImportError("Failed to import LiteLLM. Please install the 'ai' extra for app-base.") from e

        return Router(
            model_list=registry.get_router_model_list(),
            **registry.router_settings.to_router_kwargs(),
        )

    def _snapshot(self) -> tuple[AIModelRegistry, Any]:
        with self._state_lock:
            return self.registry, self.router

    def resolve_name(self, name: str, expected_type: AIModelType | str | None = None) -> str:
        registry, _ = self._snapshot()
        return registry.resolve_name(name, expected_type)

    def completion(self, name: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        registry, router = self._snapshot()
        model_name = registry.resolve_name(name, AIModelType.LLM)
        return router.completion(model=model_name, messages=messages, **kwargs)

    async def acompletion(self, name: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        registry, router = self._snapshot()
        model_name = registry.resolve_name(name, AIModelType.LLM)
        return await router.acompletion(model=model_name, messages=messages, **kwargs)  # type: ignore[reportCallIssue]

    def embedding(self, name: str, input: str | list[str], **kwargs: Any) -> Any:
        registry, router = self._snapshot()
        model_name = registry.resolve_name(name, AIModelType.EMBEDDING)
        return router.embedding(model=model_name, input=input, **kwargs)

    async def aembedding(self, name: str, input: str | list[str], **kwargs: Any) -> Any:
        registry, router = self._snapshot()
        model_name = registry.resolve_name(name, AIModelType.EMBEDDING)
        return await router.aembedding(model=model_name, input=input, **kwargs)

    def image_generation(self, name: str, prompt: str, **kwargs: Any) -> Any:
        registry, router = self._snapshot()
        model_name = registry.resolve_name(name, AIModelType.IMAGE_GEN)
        return router.image_generation(model=model_name, prompt=prompt, **kwargs)

    async def aimage_generation(self, name: str, prompt: str, **kwargs: Any) -> Any:
        registry, router = self._snapshot()
        model_name = registry.resolve_name(name, AIModelType.IMAGE_GEN)
        return await router.aimage_generation(model=model_name, prompt=prompt, **kwargs)

    def get_embedding(self, name: str) -> "LiteLLMEmbeddingsAdapter":
        self.resolve_name(name, AIModelType.EMBEDDING)
        return LiteLLMEmbeddingsAdapter(self, name)

    def get_embedding_dimension(self, name: str) -> int:
        registry, router = self._snapshot()
        dimension = registry.get_dimension(name)
        if dimension is not None:
            return dimension

        model_name = registry.resolve_name(name, AIModelType.EMBEDDING)
        response = router.embedding(model=model_name, input="test")
        vector = LiteLLMEmbeddingsAdapter.get_embedding_from_response(response)
        dimension = len(vector)
        registry.cache_dimension(name, dimension)
        return dimension

    async def aget_embedding_dimension(self, name: str) -> int:
        registry, router = self._snapshot()
        dimension = registry.get_dimension(name)
        if dimension is not None:
            return dimension

        model_name = registry.resolve_name(name, AIModelType.EMBEDDING)
        response = await router.aembedding(model=model_name, input="test")
        vector = LiteLLMEmbeddingsAdapter.get_embedding_from_response(response)
        dimension = len(vector)
        registry.cache_dimension(name, dimension)
        return dimension

    def get_catalog(self, model_type: AIModelType | str) -> list[AICatalogItem]:
        registry, _ = self._snapshot()
        return registry.get_catalog(model_type)

    def get_collection(self, name: str) -> AICollectionItem:
        registry, _ = self._snapshot()
        return registry.get_collection(name)

    def get_collections(self, model_type: AIModelType | str | None = None) -> list[AICollectionItem]:
        registry, _ = self._snapshot()
        return registry.get_collections(model_type)

    def reload(self) -> None:
        logger.info("[System] Reloading AI catalog...")
        self._initialize(self._config_path)


class LiteLLMEmbeddingsAdapter(Embeddings):
    def __init__(self, client: AIClient, model_name: str):
        self.client = client
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embedding(self.model_name, texts)
        return [self._get_embedding(item) for item in self._get_data(response)]

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embedding(self.model_name, text)
        return self._get_embedding(self._get_data(response)[0])

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.aembedding(self.model_name, texts)
        return [self._get_embedding(item) for item in self._get_data(response)]

    async def aembed_query(self, text: str) -> list[float]:
        response = await self.client.aembedding(self.model_name, text)
        return self._get_embedding(self._get_data(response)[0])

    @classmethod
    def get_embedding_from_response(cls, response: Any) -> list[float]:
        return cls._get_embedding(cls._get_data(response)[0])

    @staticmethod
    def _get_data(response: Any) -> list[Any]:
        return response["data"] if isinstance(response, dict) else response.data

    @staticmethod
    def _get_embedding(item: Any) -> list[float]:
        return item["embedding"] if isinstance(item, dict) else item.embedding
