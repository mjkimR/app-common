import asyncio
import importlib
from typing import Any

from app_prebuilt_search.errors import SearchConfigurationError


class FastEmbedProvider:
    """Optional lazy local embedding provider. Caller supplies a versioned identity.

    Install app-prebuilt-search[fastembed]. No model is imported/downloaded until
    the first embedding call. Construction is independent of DB/vector locations.
    """

    def __init__(self, *, model_name: str, dimension: int, embedding_id: str, cache_dir: str | None = None) -> None:
        if not model_name.strip() or not embedding_id.strip() or dimension <= 0:
            raise SearchConfigurationError("model_name, embedding_id and positive dimension are required")
        self.model_name = model_name
        self.dimension = dimension
        self.embedding_id = embedding_id
        self.cache_dir = cache_dir
        self._model: Any = None
        self._lock = asyncio.Lock()

    def _embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        if self._model is None:
            try:
                module = importlib.import_module("fastembed")
            except ImportError as exc:
                raise SearchConfigurationError(
                    "Install app-prebuilt-search[fastembed] to use FastEmbedProvider"
                ) from exc
            self._model = module.TextEmbedding(model_name=self.model_name, cache_dir=self.cache_dir)
        vectors = self._model.query_embed(texts) if query else self._model.passage_embed(texts)
        return [vector.tolist() for vector in vectors]

    async def _run(self, texts: list[str], *, query: bool) -> list[list[float]]:
        async with self._lock:
            task = asyncio.create_task(asyncio.to_thread(self._embed, texts, query=query))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                finally:
                    raise

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._run(texts, query=False) if texts else []

    async def embed_query(self, text: str) -> list[float]:
        return (await self._run([text], query=True))[0]
