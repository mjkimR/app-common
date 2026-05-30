from typing import Any

from app_ai_catalog.models import get_ai_client
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_vector_store.interface import VectorStoreProvider, import_error_handler


class QdrantSettings(BaseSettings):
    url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    api_key: SecretStr = Field(description="API key for Qdrant authentication")
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_QDRANT_")


class QdrantProvider(VectorStoreProvider):
    @classmethod
    def from_env(cls) -> VectorStoreProvider:
        with import_error_handler("qdrant"):
            from qdrant_client import QdrantClient
        config = QdrantSettings()  # type: ignore
        client = QdrantClient(url=config.url, api_key=config.api_key.get_secret_value())
        return QdrantProvider(client)

    def close(self) -> None:
        if self.client:
            self.client.close()

    async def create_vector_store(self, collection_name: str, model_name: str) -> Any:
        with import_error_handler("qdrant"):
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client.http import models as conf
            from qdrant_client.http.exceptions import ApiException

        ai_client = get_ai_client()
        embeddings = ai_client.get_embedding(model_name)

        if not self.client.collection_exists(collection_name=collection_name):
            dimension = await ai_client.aget_embedding_dimension(model_name)
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
