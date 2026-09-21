"""Real REST behavior, including payload index schema round trips."""

import pytest
from app_vector_store import (
    CollectionMismatchError,
    PayloadUpdate,
    QdrantSettings,
    QdrantVectorStore,
    VectorPoint,
    open_qdrant,
)
from qdrant_client import models

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def endpoint():
    import docker
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.wait_strategies import HttpWaitStrategy

    try:
        docker.from_env().ping()
    except docker.errors.DockerException as exc:
        pytest.skip(f"Docker is not available: {exc}")
    container = DockerContainer("qdrant/qdrant:v1.16.2").with_exposed_ports(6333)
    container.waiting_for(HttpWaitStrategy(6333, "/readyz").with_startup_timeout(60))
    with container as server:
        yield f"http://{server.get_container_host_ip()}:{server.get_exposed_port(6333)}"


async def test_remote_collection_indexes_filters_and_payloads(endpoint):
    async with open_qdrant(QdrantSettings(mode="remote", url=endpoint)) as client:
        store = QdrantVectorStore(client, "contract", dimension=2, embedding_id="model-v1")
        indexes = {
            "project": models.KeywordIndexParams(type="keyword", is_tenant=True),
            "kind": models.PayloadSchemaType.KEYWORD,
        }
        await store.ensure_payload_indexes(indexes)
        await store.ensure_payload_indexes(indexes)
        with pytest.raises(CollectionMismatchError, match="Payload index"):
            await store.ensure_payload_indexes({"project": models.PayloadSchemaType.INTEGER})
        await store.upsert(
            [
                VectorPoint(1, [1.0, 0.0], {"project": "a", "kind": "doc"}),
                VectorPoint(2, [1.0, 0.0], {"project": "b", "kind": "doc"}),
            ]
        )
        scope = models.Filter(must=[models.FieldCondition(key="project", match=models.MatchValue(value="a"))])
        assert [hit.id for hit in await store.search([1.0, 0.0], query_filter=scope)] == [1]
        assert [r.id async for r in store.scroll(query_filter=scope, batch_size=1)] == [1]
        await store.overwrite_payload({"project": "a", "kind": "updated"}, models.FilterSelector(filter=scope))
        assert (await store.search([1.0, 0.0], query_filter=scope))[0].payload["kind"] == "updated"
        await store.overwrite_payloads(
            [PayloadUpdate(1, {"project": "a", "kind": "batched"}), PayloadUpdate(2, {"project": "b"})],
            batch_size=1,
        )
        records = await client.retrieve("contract", [1, 2], with_vectors=True)
        assert [r.payload for r in records] == [{"project": "a", "kind": "batched"}, {"project": "b"}]
        assert all(r.vector == {"model-v1": [1.0, 0.0]} for r in records)
        await store.delete(models.FilterSelector(filter=scope))
        assert [r.id async for r in store.scroll()] == [2]
        wrong = QdrantVectorStore(client, "contract", dimension=2, embedding_id="different-model")
        with pytest.raises(CollectionMismatchError):
            await wrong.search([1.0, 0.0])
