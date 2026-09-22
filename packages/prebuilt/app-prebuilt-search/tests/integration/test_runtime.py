"""A non-SQL source exercises the public integration contract, without planroot imports."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from app_prebuilt_search import (
    BooleanFilter,
    KeywordArrayFilter,
    KeywordFilter,
    SearchEngine,
    SearchIndex,
    SearchInputError,
    SearchItem,
    SearchSourceError,
    SyncState,
)
from app_vector_store import QdrantSettings, open_qdrant


class SnapshotSession:
    def __init__(self, runtime, key):
        self.runtime, self.key = runtime, key
        self.owner = asyncio.current_task()

    async def iter_items(self):
        assert asyncio.current_task() is self.owner
        self.runtime.enumerations += 1
        for item in self.runtime.sources[self.key.scope]:
            yield item
            if self.runtime.partial:
                raise RuntimeError("partial snapshot")

    async def record_success(self, result):
        assert asyncio.current_task() is self.owner
        assert self.runtime.lock.locked()
        if self.runtime.fail_record:
            raise RuntimeError("state persistence failed")
        self.runtime.states[self.key] = SyncState(last_synced_at=datetime.now(UTC), last_result=result)


class SnapshotRuntime:
    def __init__(self):
        self.sources = {"main": [], "branch": []}
        self.states = {}
        self.lock = asyncio.Lock()
        self.enumerations = 0
        self.partial = self.fail_record = False
        self.hydrated = []
        self.denied = set()

    @asynccontextmanager
    async def sync(self, key):
        # Application policy: only the canonical snapshot can publish vectors.
        if key.scope != "main":
            raise ValueError("snapshot is not an index writer")
        async with self.lock:
            yield SnapshotSession(self, key)

    async def read_state(self, key):
        return self.states.get(key, SyncState())

    async def hydrate(self, request, hits):
        assert request.index_scope == "main"
        assert request.source_scope in self.sources
        self.hydrated.append((request, hits))
        current = {(i.source_id, i.item_id): i for i in self.sources[request.source_scope]}
        items = []
        for hit in reversed(hits):  # Engine must preserve candidate order, not hydration order.
            item = current.get((hit.source_id, hit.item_id))
            if item is None or item.source_id in self.denied:
                continue
            stale = hit.index_metadata.get("source_hash") != item.index_metadata.get("source_hash")
            # Application owns excerpt policy and stale-result annotations.
            items.append(item.model_copy(update={"metadata": {**item.metadata, "stale": stale}}))
        return items


class Embedder:
    embedding_id = "test-v1"
    dimension = 2

    def __init__(self):
        self.documents = []

    async def embed_documents(self, texts):
        self.documents.extend(texts)
        return [[1.0, 0.0] if text.startswith("best") else [0.8, 0.6] for text in texts]

    async def embed_query(self, text):
        return [1.0, 0.0]


def chunk(doc="doc", target="unit", number=0, *, archived=False, text="body", revision="old"):
    return SearchItem(
        source_id=doc,
        item_id=f"{target}:{number}",
        text=text,
        title="display title",
        filters={"archived": archived, "kind": "note", "ancestors": [doc, "parent"]},
        metadata={"target": target, "private_display": "not indexed"},
        index_metadata={"source_hash": revision, "start": number * 10, "end": number * 10 + 10},
    )


@pytest.fixture
async def engine():
    runtime, embedder = SnapshotRuntime(), Embedder()
    async with open_qdrant(QdrantSettings(mode="memory")) as client:
        yield SearchEngine(
            runtime=runtime,
            vector_client=client,
            embedder=embedder,
            index=SearchIndex(
                name="snapshots",
                recipe_version="chunks-v1",
                batch_size=2,
                candidate_batch_size=1,
                candidate_budget=20,
                filters={"archived": BooleanFilter(), "kind": KeywordFilter(), "ancestors": KeywordArrayFilter()},
            ),
        )


async def test_alternate_snapshot_uses_main_vectors_and_current_source_filters(engine):
    r = engine.runtime
    r.sources["main"] = [
        chunk(number=0, archived=True, text="best old", revision="old"),
        chunk(number=1, archived=True),
        chunk(doc="gone"),
        chunk(doc="denied"),
    ]
    await engine.sync(scope="main")
    r.sources["branch"] = [
        chunk(number=0, text="current excerpt", revision="new"),
        chunk(number=1, text="current other excerpt", revision="new"),
        chunk(doc="denied"),
        chunk(doc="branch-only"),
    ]
    r.denied.add("denied")
    result = await engine.search(
        scope="main",
        source_scope="branch",
        query="needle",
        filters={"archived": False, "ancestors": "parent"},
        group_by=lambda item: (item.source_id, item.metadata["target"]),
    )
    assert result.index_ready and result.total == 1
    assert result.items[0].text == "current excerpt"
    assert result.items[0].metadata["stale"] is True
    assert result.items[0].score == pytest.approx(1)
    request, hits = r.hydrated[0]
    assert request.query == "needle" and dict(request.candidate_filters) == {}
    assert request.filters["archived"] is False
    assert hits[0].index_metadata == {"source_hash": "old", "start": 0, "end": 10}
    assert result.items[0].index_metadata["source_hash"] == "new"
    assert r.enumerations == 1
    with pytest.raises(ValueError, match="not an index writer"):
        await engine.sync(scope="branch")
    assert not (await engine.status(scope="branch")).index_ready


async def test_relaxed_candidates_still_apply_final_filters_and_group_after_hydration(engine):
    r = engine.runtime
    r.sources["main"] = [chunk(text="best body", archived=True), chunk(doc="other")]
    await engine.sync(scope="main")
    result = await engine.search(scope="main", query="q", filters={"archived": False}, candidate_filters={}, limit=1)
    assert [i.source_id for i in result.items] == ["other"]
    assert len(r.hydrated) == 2  # Refill after the top candidate fails current filters.
    r.sources["main"][0] = chunk(text="best body", archived=False)
    assert (await engine.search(scope="main", query="q", filters={"archived": False})).total == 1
    assert (await engine.search(scope="main", query="q", filters={"archived": False}, candidate_filters={})).total == 2


async def test_metadata_refresh_and_shrinking_chunks_preserve_vectors(engine, monkeypatch):
    r = engine.runtime
    r.sources["main"] = [chunk(number=i) for i in range(5)]
    await engine.sync(scope="main")
    ids = [point.id async for point in engine.store.scroll(query_filter=engine.policy.query("main", {}))]
    before = await engine.store.client.retrieve(engine.collection_name, ids, with_vectors=True)
    for item in r.sources["main"]:
        item.index_metadata["source_hash"] = "changed metadata only"
        item.metadata["private_display"] = "new display"
    from unittest.mock import AsyncMock

    batch = AsyncMock(wraps=engine.store.client.batch_update_points)
    monkeypatch.setattr(engine.store.client, "batch_update_points", batch)
    result = await engine.sync(scope="main")
    assert result.refreshed == 5 and result.embedded == 0
    assert batch.await_count == 3
    assert len(engine.embedder.documents) == 5
    after = await engine.store.client.retrieve(engine.collection_name, ids, with_vectors=True)
    assert [p.vector for p in before] == [p.vector for p in after]
    assert all("metadata" not in p.payload and "title" not in p.payload for p in after)
    r.sources["main"] = r.sources["main"][:1]
    assert (await engine.sync(scope="main")).deleted == 4
    result = await engine.search(scope="main", query="q")
    assert result.total == 1 and not result.items[0].metadata["stale"]


async def test_sync_context_stays_in_caller_task_and_drains_repeated_cancellation(engine):
    r = engine.runtime
    r.sources["main"] = [chunk()]
    entered, release = asyncio.Event(), asyncio.Event()
    original = engine.embedder.embed_documents

    async def slow(texts):
        assert r.lock.locked()
        entered.set()
        await release.wait()
        assert r.lock.locked()
        return await original(texts)

    engine.embedder.embed_documents = slow
    first = asyncio.create_task(engine.sync(scope="main"))
    await asyncio.wait_for(entered.wait(), 5)
    second = asyncio.create_task(engine.sync(scope="main"))
    try:
        first.cancel()
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.sleep(0)
        assert not first.done() and r.lock.locked()
        assert r.enumerations == 1
    finally:
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
    assert isinstance(results[0], asyncio.CancelledError)
    assert results[1].skipped == 1
    assert (await engine.status(scope="main")).index_ready


async def test_partial_snapshot_and_state_failure_are_reconcilable(engine):
    r = engine.runtime
    r.sources["main"] = [chunk()]
    await engine.sync(scope="main")
    before = await engine.status(scope="main")
    r.sources["main"] = [chunk(doc="new")]
    r.partial = True
    with pytest.raises(RuntimeError, match="partial"):
        await engine.sync(scope="main")
    assert [
        p.payload["source_id"] async for p in engine.store.scroll(query_filter=engine.policy.query("main", {}))
    ] == ["doc"]
    r.partial, r.fail_record = False, True
    with pytest.raises(RuntimeError, match="persistence"):
        await engine.sync(scope="main")
    after = await engine.status(scope="main")
    assert after.last_synced_at == before.last_synced_at
    assert not after.index_ready
    r.fail_record = False
    assert (await engine.sync(scope="main")).skipped == 1
    assert (await engine.search(scope="main", query="q")).items[0].source_id == "new"


async def test_grouping_paging_and_candidate_budget(engine):
    r = engine.runtime
    r.sources["main"] = [chunk(number=0, text="best first"), chunk(number=1), chunk(target="other")]
    await engine.sync(scope="main")
    grouped = await engine.search(scope="main", query="q", group_by=lambda i: i.metadata["target"])
    assert grouped.total == 2 and grouped.items[0].item_id == "unit:0"
    assert (await engine.search(scope="main", query="q", group_by_source=True)).total == 1
    small = SearchEngine(
        runtime=r,
        vector_client=engine.store.client,
        embedder=engine.embedder,
        index=replace(engine.index, candidate_budget=1),
    )
    limited = await small.search(scope="main", query="q", limit=2)
    assert limited.total == 1 and limited.candidate_limit_reached


@pytest.mark.parametrize(
    "options",
    [
        {"source_scope": ""},
        {"candidate_filters": {"scope_id": "other"}},
        {"candidate_filters": {"archived": "false"}},
        {"filters": {"archived": 0}},
        {"group_by_source": True, "group_by": lambda i: i.source_id},
    ],
)
async def test_invalid_new_options_rejected_before_index_lookup(engine, options):
    with pytest.raises(SearchInputError):
        await engine.search(scope="main", query="q", **options)
    assert not await engine.store.collection_exists()


async def test_boolean_payload_is_strict_and_no_vector_write_on_invalid_snapshot(engine):
    item = chunk()
    item.filters["archived"] = 0
    engine.runtime.sources["main"] = [item]
    with pytest.raises(SearchSourceError):
        await engine.sync(scope="main")
    assert not await engine.store.collection_exists()


async def test_scope_marker_detects_collection_recreation_and_repairs_empty_scope(engine):
    r = engine.runtime
    await engine.sync(scope="main")
    assert (await engine.status(scope="main")).index_ready
    # A different application's runtime can publish another scope in the same collection.
    other = SearchEngine(
        runtime=SnapshotRuntime(), vector_client=engine.store.client, embedder=engine.embedder, index=engine.index
    )
    r.sources["main"] = [chunk()]
    await engine.sync(scope="main")
    await engine.store.client.delete_collection(engine.collection_name)
    await engine.store.ensure_collection()
    status = await engine.status(scope="main")
    assert status.collection_exists and not status.index_ready
    assert not (await engine.search(scope="main", query="q")).index_ready
    # Even an old successful timestamp must not authorize a recreated collection.
    old = r.states[engine._key("main")]
    old.last_result.generation = None
    assert not (await engine.status(scope="main")).index_ready
    await engine.sync(scope="main")
    assert (await engine.status(scope="main")).index_ready
    assert not (await other.status(scope="main")).index_ready
