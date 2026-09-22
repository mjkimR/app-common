from dataclasses import replace

import pytest
from app_prebuilt_search import BooleanFilter, NumericRange
from app_vector_store import QdrantSettings, open_qdrant

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def endpoint():
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.wait_strategies import HttpWaitStrategy

    container = DockerContainer("qdrant/qdrant:v1.16.2").with_exposed_ports(6333)
    container.waiting_for(HttpWaitStrategy(6333, "/readyz").with_startup_timeout(60))
    with container as server:
        yield f"http://{server.get_container_host_ip()}:{server.get_exposed_port(6333)}"


async def test_real_remote_indexes_filters_and_incremental_payloads(harness, endpoint):
    h = harness
    async with open_qdrant(QdrantSettings(mode="remote", url=endpoint)) as client:
        search = h.make(
            vector_client=client,
            index=replace(h.service.index, filters={**h.service.index.filters, "archived": BooleanFilter()}),
        )
        assert not (await search.search(scope="a", query="q")).index_ready
        await h.put("doc", filters={"kind": "note", "price": 10, "tags": ["public"]})
        await h.put("doc", scope="b", filters={"kind": "note", "price": 10, "tags": ["public"]})
        await search.sync(scope="a")
        await search.sync(scope="b")
        assert (await search.sync(scope="a")).skipped == 1
        result = await search.search(
            scope="a", query="q", filters={"price": NumericRange(gte=5, lt=20), "tags": "public"}
        )
        assert result.total == 1
        await h.put("doc", filters={"kind": "changed", "price": 30, "tags": ["private"], "archived": False})
        assert (await search.sync(scope="a")).refreshed == 1
        assert (await search.search(scope="a", query="q", filters={"price": 30, "tags": "private"})).total == 1
        assert (await search.search(scope="a", query="q", filters={"tags": "public"})).total == 0
        assert (await search.search(scope="b", query="q", filters={"tags": "public"})).total == 1
        assert (await search.search(scope="a", query="q", filters={"archived": False})).total == 1
        assert (await search.search(scope="a", query="q", filters={"archived": True})).total == 0
        await h.put("doc", scope="branch", filters={"tags": ["public"], "archived": False})
        result = await search.search(
            scope="a", source_scope="branch", query="q", filters={"tags": "public", "archived": False}
        )
        assert result.total == 1
        assert len(h.embedder.documents) == 2
