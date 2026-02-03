from typing import Any

from app_base.config import VectorDBSettings
from app_base.config.vector_db import QdrantSettings

from app_base.adapter.vector_store.interface import VectorStoreProvider, import_error_handler
from app_base.adapter.vector_store.registry import register_vector_store
from app_base.ai.models import AIModelFactory


@register_vector_store("qdrant")
class QdrantProvider(VectorStoreProvider):
    @classmethod
    def from_config(cls, settings: VectorDBSettings[QdrantSettings]) -> VectorStoreProvider:
        with import_error_handler("qdrant"):
            from qdrant_client import QdrantClient
        config: QdrantSettings = settings.config
        client = QdrantClient(url=config.url, api_key=config.api_key.get_secret_value() if config.api_key else None)
        return QdrantProvider(client)

    def close(self) -> None:
        if self.client:
            self.client.close()

    def create_vector_store(self, collection_name: str, model_name: str) -> Any:
        with import_error_handler("qdrant"):
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client.http import models as conf
            from qdrant_client.http.exceptions import ApiException

        model_factory = AIModelFactory()
        # AIModelFactory internally caches embeddings
        embeddings = model_factory.get_embedding(model_name)

        if not self.client.collection_exists(collection_name=collection_name):
            dimension = model_factory.get_embedding_dimension(model_name)
            try:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=conf.VectorParams(size=dimension, distance=conf.Distance.COSINE),
                )
            except ApiException as e:
                if "exists" in str(e):
                    pass
                else:
                    raise e

        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=embeddings,
        )
