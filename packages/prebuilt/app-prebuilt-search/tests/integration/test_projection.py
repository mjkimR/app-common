"""Snapshot publication and cancellation preserve the existing projection."""

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from app_prebuilt_search import ProjectionItem, sync_snapshot
from app_vector_store import QdrantSettings, QdrantVectorStore, open_qdrant


class Embedder:
    def __init__(self):
        self.calls = 0
        self.failure = None

    async def embed_documents(self, texts):
        self.calls += 1
        if self.failure is not None and self.calls == 2:
            raise self.failure
        return [[1.0, 0.0] for _ in texts]


def item(number, fingerprint="old"):
    return ProjectionItem(
        str(UUID(int=number)), f"text {number}", {"fingerprint": fingerprint, "nested": {"kept": True}}
    )


@pytest.mark.parametrize("failure", ["inference", "publication", "cancel"])
async def test_failed_preparation_never_changes_existing_points(failure):
    async with open_qdrant(QdrantSettings(mode="memory")) as client:
        store = QdrantVectorStore(client, "test", dimension=2, embedding_id="fixed")
        await sync_snapshot(store, Embedder(), [item(1), item(2)], {})
        existing = {str(p.id): p.payload async for p in store.scroll()}
        embedder = Embedder()
        if failure != "publication":
            embedder.failure = asyncio.CancelledError() if failure == "cancel" else RuntimeError("inference")
        entered = False

        @asynccontextmanager
        async def publication():
            nonlocal entered
            entered = True
            raise RuntimeError("source changed")
            yield  # pragma: no cover

        with pytest.raises(asyncio.CancelledError if failure == "cancel" else RuntimeError):
            await sync_snapshot(
                store,
                embedder,
                [item(1, "new"), item(3, "new")],
                existing,
                batch_size=1,
                publication=publication,
            )
        assert entered == (failure == "publication")
        assert {str(p.id): p.payload async for p in store.scroll()} == existing


async def test_publication_scope_surrounds_writes_and_payloads_are_detached():
    async with open_qdrant(QdrantSettings(mode="memory")) as client:
        store = QdrantVectorStore(client, "test", dimension=2, embedding_id="fixed")
        source = item(1)
        owner = asyncio.current_task()
        phases = []

        class MutatingEmbedder:
            async def embed_documents(self, texts):
                phases.append("inference")
                source.payload["nested"]["kept"] = False
                return [[1.0, 0.0]]

        @asynccontextmanager
        async def publication():
            assert asyncio.current_task() is owner
            assert not await store.collection_exists()
            phases.append("validate")
            yield
            phases.append("published")
            assert await store.collection_exists()

        report = await sync_snapshot(store, MutatingEmbedder(), [source], {}, publication=publication)
        assert report.embedded == 1
        assert phases == ["inference", "validate", "published"]
        points = [p async for p in store.scroll()]
        assert points[0].payload["nested"]["kept"] is True
