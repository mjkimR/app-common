from unittest.mock import AsyncMock, Mock

import pytest
from app_document_store import FirestoreDocumentStore, InvalidDocument, VersionConflict
from app_document_store.firestore import _option, _version
from google.api_core import exceptions
from google.api_core.datetime_helpers import DatetimeWithNanoseconds


@pytest.fixture
def store_and_ref():
    client = Mock()
    ref = Mock(get=AsyncMock(), update=AsyncMock(), set=AsyncMock(), delete=AsyncMock(), create=AsyncMock())
    client.collection.return_value.document.return_value = ref
    return FirestoreDocumentStore(client, "reports", namespace="autohub"), ref


def test_version_preserves_nanoseconds():
    value = "2026-09-23T01:02:03.123456789Z"
    stamp = DatetimeWithNanoseconds.from_rfc3339(value)
    assert _version(stamp) == value
    assert _option(value)._last_update_time.nanosecond == 123456789


@pytest.mark.parametrize("operation", ["get", "create", "put", "delete"])
@pytest.mark.parametrize(
    "error", [exceptions.PermissionDenied, exceptions.ServiceUnavailable, exceptions.DeadlineExceeded]
)
async def test_operational_errors_are_never_reported_as_missing_or_success(store_and_ref, operation, error):
    store, ref = store_and_ref
    method = "set" if operation == "put" else operation
    getattr(ref, method).side_effect = error("backend failure")
    with pytest.raises(error):
        args = ("key", {}) if operation in ("create", "put") else ("key",)
        await getattr(store, operation)(*args)


async def test_conditional_write_maps_conflict_but_not_permission_failure(store_and_ref):
    store, ref = store_and_ref
    version = "2026-09-23T01:02:03.123456789Z"
    ref.update.side_effect = exceptions.FailedPrecondition("stale")
    with pytest.raises(VersionConflict):
        await store.put("key", {}, expected_version=version)
    ref.update.side_effect = exceptions.PermissionDenied("denied")
    with pytest.raises(exceptions.PermissionDenied):
        await store.put("key", {}, expected_version=version)


async def test_invalid_version_fails_before_write(store_and_ref):
    store, ref = store_and_ref
    with pytest.raises(ValueError):
        await store.put("key", {}, expected_version="invalid")
    ref.update.assert_not_called()
    ref.set.assert_not_called()


async def test_malformed_document_is_not_absence(store_and_ref):
    store, ref = store_and_ref
    ref.get.return_value = Mock(exists=True, to_dict=lambda: {"foreign": "schema"})
    with pytest.raises(InvalidDocument):
        await store.get("key")


async def test_batch_validates_all_keys_before_network(store_and_ref):
    store, _ = store_and_ref
    with pytest.raises(ValueError):
        await store.get_many(["valid", "invalid/key"])
    store._client.get_all.assert_not_called()
    assert await store.get_many([]) == []


@pytest.mark.parametrize("error", [exceptions.Aborted, exceptions.Conflict])
async def test_create_does_not_misclassify_operational_conflicts(store_and_ref, error):
    store, ref = store_and_ref
    ref.create.side_effect = error("operation failed without confirming an existing document")
    with pytest.raises(error):
        await store.create("key", {})


@pytest.mark.parametrize("operation", ["put", "delete"])
async def test_missing_database_is_not_a_document_version_conflict(store_and_ref, operation):
    store, ref = store_and_ref
    method = ref.update if operation == "put" else ref.delete
    method.side_effect = exceptions.NotFound("The database does not exist")
    args = ("key", {}) if operation == "put" else ("key",)
    with pytest.raises(exceptions.NotFound):
        await getattr(store, operation)(*args, expected_version="2026-09-23T01:02:03Z")
