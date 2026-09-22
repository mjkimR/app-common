from unittest.mock import AsyncMock, Mock

import pytest
from app_vector_store import CollectionMismatchError, QdrantSettings, QdrantVectorStore, VectorPoint, open_qdrant
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse


def make_store(client, **overrides):
    return QdrantVectorStore(client, "docs", **{"dimension": 2, "embedding_id": "model-v1", **overrides})


def project_filter(project):
    return models.Filter(must=[models.FieldCondition(key="project", match=models.MatchValue(value=project))])


@pytest.fixture
async def client():
    async with open_qdrant(QdrantSettings(mode="memory")) as client:
        yield client


async def test_filtered_lifecycle_and_payload_refresh(client):
    store = make_store(client)
    await store.ensure_payload_indexes({"project": models.PayloadSchemaType.KEYWORD})
    await store.upsert(
        [
            VectorPoint(1, [1.0, 0.0], {"project": "a", "kind": "doc", "price": 10, "legacy": True}),
            VectorPoint(2, [0.0, 1.0], {"project": "a", "kind": "note", "price": 30}),
            VectorPoint(3, [1.0, 0.0], {"project": "b", "kind": "doc", "price": 10}),
        ],
        batch_size=1,
    )
    combined = models.Filter(
        must=[project_filter("a"), models.FieldCondition(key="price", range=models.Range(lte=20))],
        should=[models.FieldCondition(key="kind", match=models.MatchAny(any=["doc", "note"]))],
        must_not=[models.FieldCondition(key="kind", match=models.MatchValue(value="excluded"))],
    )
    hits = await store.search([1.0, 0.0], query_filter=combined, limit=1, score_threshold=0.9)
    assert [hit.id for hit in hits] == [1]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].vector is None
    assert [h.id for h in await store.search([1.0, 0.0], query_filter=project_filter("a"), score_threshold=0.9)] == [1]
    records = [r async for r in store.scroll(query_filter=project_filter("a"), batch_size=1)]
    assert {r.id for r in records} == {1, 2}
    assert all(r.vector is None for r in records)

    before = await client.retrieve("docs", [1], with_vectors=True)
    await store.overwrite_payload({"project": "a", "kind": "updated"}, models.PointIdsList(points=[1]))
    after = await client.retrieve("docs", [1], with_vectors=True)
    assert after[0].vector == before[0].vector
    assert after[0].payload == {"project": "a", "kind": "updated"}
    await store.overwrite_payload({"project": "b", "updated": True}, models.FilterSelector(filter=project_filter("b")))
    assert (await client.retrieve("docs", [3]))[0].payload == {"project": "b", "updated": True}
    await store.delete(models.PointIdsList(points=[2]))
    await store.delete(models.FilterSelector(filter=project_filter("a")))
    assert [r.id async for r in store.scroll()] == [3]


async def test_idempotent_upsert_replaces_payload(client):
    store = make_store(client)
    await store.upsert([VectorPoint(1, [1.0, 0.0], {"old": True})])
    await store.upsert([VectorPoint(1, [0.0, 1.0], {"new": True})])
    assert (await client.count("docs")).count == 1
    hits = await store.search([0.0, 1.0])
    assert hits[0].payload == {"new": True}
    assert hits[0].score == pytest.approx(1.0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"dimension": 3},
        {"embedding_id": "same-dimension-other-model"},
        {"distance": models.Distance.DOT},
    ],
)
async def test_existing_schema_mismatch_preserves_data(client, overrides):
    await make_store(client).upsert([VectorPoint(1, [1.0, 0.0])])
    with pytest.raises(CollectionMismatchError):
        await make_store(client, **overrides).ensure_collection()
    assert (await client.count("docs")).count == 1
    assert (await make_store(client).search([1.0, 0.0]))[0].id == 1


async def test_rejects_unnamed_collection(client):
    await client.create_collection("docs", vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
    with pytest.raises(CollectionMismatchError):
        await make_store(client).ensure_collection()


async def test_invalid_dimension_does_not_partially_write(client):
    store = make_store(client)
    with pytest.raises(ValueError, match="dimension"):
        await store.upsert([VectorPoint(1, [1.0, 0.0]), VectorPoint(2, [1.0])], batch_size=1)
    assert not await client.collection_exists("docs")
    with pytest.raises(ValueError, match="dimension"):
        await store.search([1.0])


async def test_empty_and_invalid_limits(client):
    store = make_store(client)
    assert await store.upsert([]) == 0
    assert not await client.collection_exists("docs")
    with pytest.raises(ValueError, match="batch_size"):
        await store.upsert([], batch_size=0)
    with pytest.raises(ValueError, match="limit"):
        await store.search([1.0, 0.0], limit=0)
    with pytest.raises(ValueError, match="batch_size"):
        _ = [r async for r in store.scroll(batch_size=0)]
    assert await store.search([1.0, 0.0]) == []
    assert [r async for r in store.scroll()] == []


async def test_concurrent_first_use(client):
    import asyncio

    store = make_store(client)
    await asyncio.gather(*(store.upsert([VectorPoint(i, [1.0, 0.0])]) for i in range(10)))
    assert (await client.count("docs")).count == 10


async def test_persistence_and_independent_locations(tmp_path):
    a = QdrantSettings(mode="local", path=tmp_path / "a")
    b = QdrantSettings(mode="local", path=tmp_path / "b")
    async with open_qdrant(a) as client_a, open_qdrant(b) as client_b:
        await make_store(client_a).upsert([VectorPoint(1, [1.0, 0.0])])
        assert await make_store(client_b).search([1.0, 0.0]) == []
    async with open_qdrant(a) as reopened:
        assert (await make_store(reopened).search([1.0, 0.0]))[0].id == 1


async def remote_mock(client):
    await make_store(client).ensure_collection()
    info = await client.get_collection("docs")
    remote = Mock(spec=AsyncQdrantClient)
    remote._client = object()
    remote.collection_exists = AsyncMock(return_value=True)
    remote.get_collection = AsyncMock(return_value=info)
    remote.create_payload_index = AsyncMock()
    return remote, info


async def test_remote_indexes_and_mismatch(client):
    remote, info = await remote_mock(client)
    store = make_store(remote)
    tenant = models.KeywordIndexParams(type="keyword", is_tenant=True)
    await store.ensure_payload_indexes({"project": tenant})
    remote.create_payload_index.assert_awaited_once_with("docs", "project", field_schema=tenant, wait=True)
    info.payload_schema = {"project": models.PayloadIndexInfo(data_type="keyword", params=tenant, points=0)}
    await store.ensure_payload_indexes({"project": tenant})
    assert remote.create_payload_index.await_count == 1
    with pytest.raises(CollectionMismatchError, match="Payload index"):
        await store.ensure_payload_indexes({"project": models.PayloadSchemaType.INTEGER})
    with pytest.raises(CollectionMismatchError, match="Payload index"):
        await store.ensure_payload_indexes({"project": models.KeywordIndexParams(type="keyword", is_tenant=False)})


@pytest.mark.parametrize("status", [409, 403, 500])
async def test_remote_creation_race_only_recovers_conflicts(client, status):
    remote, _ = await remote_mock(client)
    remote.collection_exists.return_value = False
    remote.create_collection = AsyncMock(side_effect=UnexpectedResponse(status, "error", b"error", {}))
    if status == 409:
        await make_store(remote).ensure_collection()
    else:
        with pytest.raises(UnexpectedResponse):
            await make_store(remote).ensure_collection()


async def test_creation_race_still_checks_embedding_identity(client):
    remote, _ = await remote_mock(client)
    remote.collection_exists.return_value = False
    remote.create_collection = AsyncMock(side_effect=UnexpectedResponse(409, "conflict", b"exists", {}))
    with pytest.raises(CollectionMismatchError):
        await make_store(remote, embedding_id="other").ensure_collection()


async def test_reads_and_cleanup_never_create_collections(client):
    store = make_store(client)
    assert not await store.validate_collection()
    assert await store.search([1.0, 0.0], offset=1) == []
    assert [r async for r in store.scroll()] == []
    await store.delete(models.PointIdsList(points=[1]))
    await store.overwrite_payload({}, models.PointIdsList(points=[1]))
    assert not await store.collection_exists()


async def test_search_pagination_and_recreate_after_external_deletion(client):
    store = make_store(client)
    await store.upsert([VectorPoint(i, [1.0, 0.0]) for i in range(5)])
    all_hits = await store.search([1.0, 0.0], limit=5)
    assert [h.id for h in await store.search([1.0, 0.0], limit=2, offset=2)] == [h.id for h in all_hits[2:4]]
    with pytest.raises(ValueError, match="offset"):
        await store.search([1.0, 0.0], offset=-1)
    await client.delete_collection("docs")
    await store.ensure_collection()
    assert await store.collection_exists()


async def test_batch_payload_replacement_preserves_vectors_and_scope(client, monkeypatch):
    from app_vector_store import PayloadUpdate

    store = make_store(client)
    await store.upsert([VectorPoint(i, [1.0, 0.0], {"legacy": True}) for i in range(6)])
    batch = AsyncMock(wraps=client.batch_update_points)
    monkeypatch.setattr(client, "batch_update_points", batch)
    assert await store.overwrite_payloads([PayloadUpdate(i, {"current": i}) for i in range(5)], batch_size=2) == 5
    assert batch.await_count == 3
    records = await client.retrieve("docs", list(range(6)), with_vectors=True)
    assert all(r.vector == {"model-v1": [1.0, 0.0]} for r in records)
    assert [r.payload for r in records] == [{"current": i} for i in range(5)] + [{"legacy": True}]
    assert await store.overwrite_payloads([]) == 0
    with pytest.raises(ValueError, match="batch_size"):
        await store.overwrite_payloads([], batch_size=0)
    await client.delete_collection("docs")
    assert await store.overwrite_payloads([PayloadUpdate(1, {})]) == 0
    assert not await store.collection_exists()
