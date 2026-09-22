import asyncio

import pytest
from app_layer_base.base.models.mixin import Base
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def concurrent_maker(harness, is_postgres, tmp_path):
    if is_postgres:
        yield harness.maker
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'concurrency.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            yield async_sessionmaker(engine, expire_on_commit=False)
        finally:
            await engine.dispose()


async def test_database_lock_serializes_independent_services_before_snapshot(harness, concurrent_maker):
    h = harness
    async with concurrent_maker.begin() as session:
        session.add(h.row(scope="a", source_id="doc", item_id="overview", text="body", filters={}))
    entered, release = asyncio.Event(), asyncio.Event()
    original = h.embedder.embed_documents

    async def slow(texts):
        entered.set()
        await release.wait()
        return await original(texts)

    h.embedder.embed_documents = slow
    first, second = h.make(session_maker=concurrent_maker), h.make(session_maker=concurrent_maker)
    a = asyncio.create_task(first.sync(scope="a"))
    await asyncio.wait_for(entered.wait(), 5)
    b = asyncio.create_task(second.sync(scope="a"))
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(b), 0.1)
        assert h.source.enumerations == 1
    finally:
        release.set()
        results = await asyncio.gather(a, b)
    assert [r.embedded for r in results] == [1, 0]
    assert results[1].skipped == 1


async def test_cancellation_drains_sync_before_releasing_lock(harness):
    h = harness
    await h.put("doc")
    entered, release = asyncio.Event(), asyncio.Event()
    original = h.embedder.embed_documents

    async def slow(texts):
        entered.set()
        await release.wait()
        return await original(texts)

    h.embedder.embed_documents = slow
    task = asyncio.create_task(h.service.sync(scope="a"))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await h.service.status(scope="a")).index_ready
    assert (await h.service.sync(scope="a")).skipped == 1
