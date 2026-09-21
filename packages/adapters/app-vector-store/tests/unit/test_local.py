"""Embedded storage must neither block the loop nor outlive cancellation cleanup."""

import asyncio
import threading

import pytest
from app_vector_store import QdrantSettings, open_qdrant
from app_vector_store import client as client_module
from qdrant_client import models
from qdrant_client.local.async_qdrant_local import AsyncQdrantLocal


@pytest.mark.parametrize("stage", ["construct", "query", "close"])
async def test_local_lifecycle_runs_on_one_worker_thread(tmp_path, monkeypatch, stage):
    entered, release = threading.Event(), threading.Event()
    owner_threads = []
    factory = client_module.create_qdrant_client
    native_query, native_close = AsyncQdrantLocal.get_collections, AsyncQdrantLocal.close

    def track(current):
        owner_threads.append(threading.get_ident())
        if stage == current:
            entered.set()
            assert release.wait(5), "event loop could not release embedded storage"

    def construct(settings):
        track("construct")
        return factory(settings)

    async def query(self, **kwargs):
        track("query")
        return await native_query(self, **kwargs)

    async def close(self, **kwargs):
        track("close")
        await native_close(self, **kwargs)

    monkeypatch.setattr(client_module, "create_qdrant_client", construct)
    monkeypatch.setattr(AsyncQdrantLocal, "get_collections", query)
    monkeypatch.setattr(AsyncQdrantLocal, "close", close)

    async def lifecycle():
        async with open_qdrant(QdrantSettings(mode="local", path=tmp_path)) as client:
            await client.get_collections()

    task = asyncio.create_task(lifecycle())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        assert not task.done()
    finally:
        release.set()
        await task
    assert len(owner_threads) == 3 and len(set(owner_threads)) == 1
    assert owner_threads[0] != threading.get_ident()


@pytest.mark.parametrize("stage", ["construct", "query"])
async def test_cancelled_local_work_drains_and_releases_storage_lock(tmp_path, monkeypatch, stage):
    entered, release = threading.Event(), threading.Event()
    settings = QdrantSettings(mode="local", path=tmp_path)
    factory = client_module.create_qdrant_client

    def construct(settings):
        client = factory(settings)
        if stage == "construct":
            entered.set()
            assert release.wait(5)
        return client

    async def failing_query(self, **kwargs):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("storage failed after cancellation")

    async def lifecycle():
        async with open_qdrant(settings) as client:
            await client.get_collections()

    with monkeypatch.context() as patch:
        patch.setattr(client_module, "create_qdrant_client", construct)
        patch.setattr(AsyncQdrantLocal, "get_collections", failing_query)
        task = asyncio.create_task(lifecycle())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            release.set()
            results = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError)
    async with open_qdrant(settings) as client:
        assert (await client.get_collections()).collections == []


async def test_persistent_local_vectors_survive_reopen(tmp_path):
    settings = QdrantSettings(mode="local", path=tmp_path)
    async with open_qdrant(settings) as client:
        await client.create_collection(
            "docs", vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE)
        )
        await client.upsert("docs", [models.PointStruct(id=1, vector=[1.0, 0.0], payload={"source_id": "doc"})])
    async with open_qdrant(settings) as client:
        result = await client.query_points("docs", query=[1.0, 0.0], with_payload=True)
        assert result.points[0].payload == {"source_id": "doc"}
