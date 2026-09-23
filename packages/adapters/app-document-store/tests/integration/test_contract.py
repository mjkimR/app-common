import asyncio

import pytest
from app_document_store import DocumentAlreadyExists, InvalidDocument, VersionConflict

pytestmark = pytest.mark.docker


async def test_roundtrip_replace_and_namespace_isolation(stores):
    store, other = stores
    assert await store.get("report") is None
    first = await store.create("report", {"body": "한글", "nested": {"a": 1}, "old": True})
    doc = await store.get("report")
    assert doc.version == first
    assert doc.data == {"body": "한글", "nested": {"a": 1}, "old": True}
    assert await other.get("report") is None
    await other.put("report", {"body": "other app"})
    second = await store.put("report", {"nested": {"b": 2}}, expected_version=first)
    assert (await store.get("report")).data == {"nested": {"b": 2}}
    with pytest.raises(VersionConflict):
        await store.put("report", {}, expected_version=first)
    await store.put("report", {}, expected_version=second)
    assert (await store.get("report")).data == {}
    assert (await other.get("report")).data == {"body": "other app"}


async def test_create_only_and_ordered_batched_reads(stores):
    store, _ = stores
    for key in ("a", "b", "c"):
        await store.create(key, {"key": key})
    with pytest.raises(DocumentAlreadyExists):
        await store.create("a", {"overwritten": True})
    values = await store.get_many(["c", "missing", "a", "b", "a"])
    assert [doc.key if doc else None for doc in values] == ["c", None, "a", "b", "a"]
    assert values[2].data == {"key": "a"}
    assert await store.get_many([]) == []


async def test_concurrent_compare_and_swap_has_exactly_one_winner(stores):
    store, _ = stores
    version = await store.create("race", {"value": "initial"})
    results = await asyncio.gather(
        store.put("race", {"value": "one"}, expected_version=version),
        store.put("race", {"value": "two"}, expected_version=version),
        return_exceptions=True,
    )
    assert sum(isinstance(result, str) for result in results) == 1
    assert sum(isinstance(result, VersionConflict) for result in results) == 1
    doc = await store.get("race")
    assert doc.version in results
    assert doc.data["value"] in ("one", "two")


async def test_conditional_delete_and_missing_preconditions(stores):
    store, _ = stores
    first = await store.create("key", {"value": 1})
    second = await store.put("key", {"value": 2})
    with pytest.raises(VersionConflict):
        await store.delete("key", expected_version=first)
    assert (await store.get("key")).version == second
    await store.delete("key", expected_version=second)
    assert await store.get("key") is None
    await store.delete("key")
    with pytest.raises(VersionConflict):
        await store.delete("key", expected_version=second)
    with pytest.raises(VersionConflict):
        await store.put("key", {}, expected_version=second)


async def test_reserved_envelope_and_literal_payload_keys(stores):
    store, _ = stores
    await store.put("literal", {"a.b": {"data": "body"}, "array": [1, False, None]})
    assert (await store.get("literal")).data == {"a.b": {"data": "body"}, "array": [1, False, None]}
    await store._reference("foreign").set({"body": "written outside the adapter"})
    with pytest.raises(InvalidDocument):
        await store.get("foreign")
