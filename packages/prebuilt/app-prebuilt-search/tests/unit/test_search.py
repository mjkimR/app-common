from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from app_prebuilt_search import NumericRange, SearchIndexState, SearchInputError, SearchItem, SearchSourceError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError


async def test_sync_incremental_changes_and_isolated_deletion(harness):
    h = harness
    await h.put("doc", filters={"kind": "note", "price": 10, "tags": ["a", "b"]})
    await h.put("doc", scope="b")
    first = await h.service.sync(scope="a")
    assert (first.scanned, first.embedded) == (1, 1)
    assert (await h.service.sync(scope="a")).skipped == 1
    await h.service.sync(scope="b")
    assert len(h.embedder.documents) == 2
    await h.put("doc", filters={"kind": "changed"})
    assert (await h.service.sync(scope="a")).refreshed == 1
    assert len(h.embedder.documents) == 2
    await h.put("doc", text="changed body", filters={"kind": "changed"})
    assert (await h.service.sync(scope="a")).embedded == 1
    hits = await h.service.search(scope="a", query="query", filters={"kind": "changed"})
    assert [r.text for r in hits.items] == ["changed body"]
    async with h.maker.begin() as session:
        await session.execute(delete(h.row).where(h.row.scope == "a"))
    assert (await h.service.sync(scope="a")).deleted == 1
    assert (await h.service.search(scope="a", query="query")).total == 0
    assert (await h.service.search(scope="b", query="query")).total == 1
    status = await h.service.status(scope="a")
    assert status.index_ready and status.last_synced_at and status.last_result.deleted == 1
    assert all(
        ["text" not in r.payload async for r in h.service.store.scroll(query_filter=h.service.policy.query("a", {}))]
    )


async def test_unsynced_search_is_read_only_and_scope_specific(harness):
    h = harness
    assert not (await h.service.search(scope="a", query="hello")).index_ready
    assert not await h.service.store.collection_exists()
    assert h.embedder.queries == []
    async with h.maker() as session:
        assert (await session.scalars(select(SearchIndexState))).all() == []
    await h.service.sync(scope="b")
    assert not (await h.service.search(scope="a", query="hello")).index_ready
    assert (await h.service.status(scope="a")).collection_exists
    assert (await h.service.search(scope="b", query="hello")).index_ready


async def test_search_hydrates_current_text_filters_and_permissions(harness):
    h = harness
    for name in ["fresh", "changed", "gone", "denied"]:
        await h.put(name, filters={"kind": "note", "price": 10, "tags": ["tag"]})
    await h.service.sync(scope="a")
    h.source.denied = {"denied"}
    await h.put("fresh", text="current body", filters={"kind": "note", "price": 12, "tags": ["tag"]})
    await h.put("changed", filters={"kind": "different", "price": 10, "tags": ["tag"]})
    async with h.maker.begin() as session:
        await session.execute(delete(h.row).where(h.row.source_id == "gone"))
    result = await h.service.search(
        scope="a", query="q", filters={"kind": "note", "price": NumericRange(gte=5, lt=20), "tags": "tag"}
    )
    assert [(r.source_id, r.text) for r in result.items] == [("fresh", "current body")]
    assert h.source.enumerations == 1 and len(h.embedder.documents) == 4


async def test_paging_grouping_budget_and_ranking(harness):
    h = harness
    for i in range(8):
        await h.put(f"doc-{i}")
    await h.put("doc-0", item_id="detail")
    await h.service.sync(scope="a")
    ranked = await h.service.store.search([1.0, 0.0], limit=20)
    ordered = list(dict.fromkeys(p.payload["source_id"] for p in ranked))
    h.source.denied = set(ordered[:3])
    result = await h.service.search(scope="a", query="q", limit=3, group_by_source=True)
    assert [r.source_id for r in result.items] == ordered[3:6]
    limited = h.make(index=replace(h.service.index, candidate_budget=2))
    result = await limited.search(scope="a", query="q", limit=3)
    assert result.candidate_limit_reached and not result.items


async def test_model_and_recipe_changes_select_new_collections(harness):
    h = harness
    await h.put("doc")
    await h.service.sync(scope="a")
    revised = h.make(index=replace(h.service.index, recipe_version="v2"))
    assert revised.collection_name != h.service.collection_name
    assert not (await revised.search(scope="a", query="q")).index_ready
    await revised.sync(scope="a")
    assert len(h.embedder.documents) == 2 and await h.service.store.collection_exists()
    embedder = type(h.embedder)()
    embedder.embedding_id = "same-dimension-new-model"
    other = h.make(embedder=embedder)
    assert other.collection_name != revised.collection_name
    assert (await other.sync(scope="a")).embedded == 1


async def test_failed_enumeration_never_prunes_or_marks_success(harness):
    h = harness
    await h.put("old")
    await h.service.sync(scope="a")
    before = await h.service.status(scope="a")
    async with h.maker.begin() as session:
        await session.execute(delete(h.row))
    await h.put("new")
    h.source.fail_iteration = True
    with pytest.raises(RuntimeError, match="incomplete"):
        await h.service.sync(scope="a")
    assert (await h.service.status(scope="a")).last_synced_at == before.last_synced_at
    assert [
        r.payload["source_id"] async for r in h.service.store.scroll(query_filter=h.service.policy.query("a", {}))
    ] == ["old"]
    h.source.fail_iteration = False
    result = await h.service.sync(scope="a")
    assert (result.embedded, result.deleted) == (1, 1)


async def test_external_failure_and_retry(harness):
    h = harness
    await h.put("doc")
    h.embedder.failure = True
    with pytest.raises(RuntimeError, match="embedding failed"):
        await h.service.sync(scope="a")
    status = await h.service.status(scope="a")
    assert status.collection_exists and not status.index_ready and status.last_synced_at is None
    h.embedder.failure = False
    assert (await h.service.sync(scope="a")).embedded == 1
    await h.client.delete_collection(h.service.collection_name)
    assert not (await h.service.search(scope="a", query="q")).index_ready
    assert (await h.service.sync(scope="a")).embedded == 1


async def test_hydration_cannot_write_and_connection_is_restored(harness):
    h = harness
    await h.put("doc")
    await h.service.sync(scope="a")

    async def bad_hydrate(session, scope, hits, filters):
        await session.execute(update(h.row).values(text="forbidden"))
        return []

    h.source.hydrate = bad_hydrate
    with pytest.raises(DBAPIError):
        await h.service.search(scope="a", query="q")
    await h.put("doc", text="allowed after read-only reset")
    async with h.maker() as session:
        assert (await session.scalar(select(h.row.text))) == "allowed after read-only reset"


async def test_unrequested_hydration_is_rejected(harness):
    h = harness
    await h.put("doc")
    await h.service.sync(scope="a")
    h.source.hydrate = AsyncMock(return_value=[SearchItem(source_id="other", item_id="other", text="leak")])
    with pytest.raises(SearchSourceError):
        await h.service.search(scope="a", query="q")


@pytest.mark.parametrize(
    "options",
    [{"scope": ""}, {"query": " "}, {"limit": 0}, {"score_threshold": float("nan")}, {"filters": {"scope_id": "b"}}],
)
async def test_invalid_queries(harness, options):
    with pytest.raises(SearchInputError):
        await harness.service.search(**{"scope": "a", "query": "q", **options})


@pytest.mark.parametrize("vectors", [[], [[1.0]], [[float("nan"), 0.0]]])
async def test_bad_embeddings_do_not_publish_success(harness, vectors):
    await harness.put("doc")
    harness.embedder.embed_documents = AsyncMock(return_value=vectors)
    with pytest.raises(SearchSourceError):
        await harness.service.sync(scope="a")
    assert not (await harness.service.status(scope="a")).index_ready


async def test_empty_scope_can_rebuild_lost_collection(harness):
    h = harness
    await h.service.sync(scope="a")
    await h.client.delete_collection(h.service.collection_name)
    await h.service.sync(scope="a")
    assert (await h.service.status(scope="a")).index_ready


async def test_duplicate_source_identity_rejected_before_vector_writes(harness):
    async def duplicates(session, scope):
        for _ in range(2):
            yield SearchItem(source_id="doc", item_id="overview", text="body")

    harness.source.iter_items = duplicates
    with pytest.raises(SearchSourceError, match="Duplicate"):
        await harness.service.sync(scope="a")
    assert not await harness.service.store.collection_exists()


async def test_query_embedding_runs_without_an_open_db_transaction(harness):
    from sqlalchemy import event

    h = harness
    await h.put("doc")
    await h.service.sync(scope="a")
    active = set()
    engine = h.maker.kw["bind"].sync_engine

    def begin(connection):
        active.add(connection)

    def end(connection):
        active.discard(connection)

    event.listen(engine, "begin", begin)
    event.listen(engine, "commit", end)
    event.listen(engine, "rollback", end)
    original = h.embedder.embed_query

    async def embed(text):
        assert not active
        return await original(text)

    h.embedder.embed_query = embed
    try:
        assert (await h.service.search(scope="a", query="query")).total == 1
        assert not active
    finally:
        event.remove(engine, "begin", begin)
        event.remove(engine, "commit", end)
        event.remove(engine, "rollback", end)


async def test_partial_vector_failure_is_repaired_before_stale_deletion(harness):
    h = harness
    await h.put("old")
    await h.service.sync(scope="a")
    before = await h.service.status(scope="a")
    async with h.maker.begin() as session:
        await session.execute(delete(h.row))
    for i in range(5):
        await h.put(f"new-{i}")
    original, count = h.client.upsert, 0

    async def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("remote unavailable")
        return await original(*args, **kwargs)

    h.client.upsert = fail_second
    with pytest.raises(RuntimeError, match="remote unavailable"):
        await h.service.sync(scope="a")
    assert (await h.service.status(scope="a")).last_synced_at == before.last_synced_at
    assert (
        len([r async for r in h.service.store.scroll(query_filter=h.service.policy.query("a", {}))]) == 3
    )  # two new + old, not pruned
    h.client.upsert = original
    retried = await h.service.sync(scope="a")
    assert (retried.embedded, retried.skipped, retried.deleted) == (3, 2, 1)
    result = await h.service.search(scope="a", query="q")
    assert result.model_dump()["total"] == 5


async def test_sqlalchemy_facade_can_hydrate_an_alternate_authorized_scope(harness):
    h = harness
    await h.put("doc", filters={"kind": "old"})
    await h.put("doc", scope="branch", text="branch body", filters={"kind": "new"})
    await h.service.sync(scope="a")
    result = await h.service.search(scope="a", source_scope="branch", query="q", filters={"kind": "new"})
    assert [(i.source_id, i.text) for i in result.items] == [("doc", "branch body")]
    assert not (await h.service.status(scope="branch")).index_ready
    assert h.source.enumerations == 1


async def test_custom_runtime_joins_caller_transaction_without_committing(harness):
    import asyncio
    from contextlib import asynccontextmanager

    from app_prebuilt_search import SearchEngine, SQLAlchemySearchRuntime

    h = harness
    await h.put("doc", text="committed source")
    owner = asyncio.current_task()

    class BoundSource:
        def __init__(self, session, state, repo):
            self.session, self.state, self.repo = session, state, repo

        async def iter_items(self):
            assert asyncio.current_task() is owner
            async for item in h.source.iter_items(self.session, "a"):
                yield item

        async def record_success(self, result):
            assert asyncio.current_task() is owner
            self.repo.record_success(self.state, result)

    class JoinedRuntime(SQLAlchemySearchRuntime):
        @asynccontextmanager
        async def sync(self, key):
            assert asyncio.current_task() is owner
            state = await self.repo.lock(caller_session, key.index_name, key.scope, key.profile_id)
            await caller_session.execute(update(h.row).where(h.row.scope == "a").values(text="uncommitted source"))
            yield BoundSource(caller_session, state, self.repo)
            # Joining must not close or commit the caller's transaction.
            assert caller_session.in_transaction()

    runtime = JoinedRuntime(h.maker, h.source)
    engine = SearchEngine(runtime=runtime, vector_client=h.client, embedder=h.embedder, index=h.service.index)
    with pytest.raises(RuntimeError, match="caller rollback"):
        async with h.maker.begin() as caller_session:
            assert (await engine.sync(scope="a")).embedded == 1
            assert caller_session.in_transaction()
            assert (await caller_session.scalars(select(SearchIndexState))).one().last_synced_at is not None
            raise RuntimeError("caller rollback")
    async with h.maker() as session:
        assert (await session.scalar(select(h.row.text))) == "committed source"
        assert (await session.scalars(select(SearchIndexState))).all() == []
    # External vectors are not part of the rollback; a normal sync repairs them.
    assert not (await h.service.status(scope="a")).index_ready
    assert (await h.service.sync(scope="a")).embedded == 1
    assert (await h.service.search(scope="a", query="q")).items[0].text == "committed source"
