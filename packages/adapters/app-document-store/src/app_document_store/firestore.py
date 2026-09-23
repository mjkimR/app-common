import math
from collections.abc import Sequence
from typing import Any

from google.api_core import exceptions
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
from google.cloud.firestore_v1 import AsyncClient, LastUpdateOption
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.protobuf.timestamp_pb2 import Timestamp

from app_document_store.config import validate_segment
from app_document_store.types import Document, DocumentAlreadyExists, InvalidDocument, VersionConflict


def _version(value: DatetimeWithNanoseconds | Timestamp) -> str:
    # isoformat() loses nanoseconds, which would make a valid precondition fail.
    if isinstance(value, Timestamp):
        return value.ToJsonString()
    return value.rfc3339()


def _option(version: str | None) -> LastUpdateOption | None:
    if version is None:
        return None
    try:
        stamp = DatetimeWithNanoseconds.from_rfc3339(version)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected_version must be an unchanged version returned by this store") from exc
    return LastUpdateOption(stamp)


def _document(snapshot: DocumentSnapshot) -> Document | None:
    if not snapshot.exists:
        return None
    envelope = snapshot.to_dict()
    if not isinstance(envelope, dict) or set(envelope) != {"data"} or not isinstance(envelope["data"], dict):
        raise InvalidDocument("Stored document must contain exactly one 'data' map")
    if snapshot.update_time is None:
        raise InvalidDocument("Stored document has no version")
    return Document(key=snapshot.id, data=envelope["data"], version=_version(snapshot.update_time))


class FirestoreDocumentStore:
    """DocumentStore over namespaces/{namespace}/{collection}/{key}.

    Client ownership stays with the application. The data envelope makes a
    conditional put replace the entire application payload in one atomic RPC.
    Versions belong to the original document; they are not source revisions or
    idempotency keys. Namespaces isolate paths, not IAM access.
    """

    def __init__(
        self,
        client: AsyncClient,
        collection: str,
        *,
        namespace: str,
        timeout: float = 10,
        batch_size: int = 100,
    ) -> None:
        validate_segment(namespace)
        validate_segment(collection)
        if not math.isfinite(timeout) or timeout <= 0 or batch_size <= 0:
            raise ValueError("timeout must be finite and positive; batch_size must be positive")
        self._collection = client.collection("namespaces", namespace, collection)
        self._client = client
        self._timeout = timeout
        self._batch_size = batch_size

    def _reference(self, key: str):
        return self._collection.document(validate_segment(key))

    @staticmethod
    def _envelope(data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise TypeError("Document data must be a dict")
        return {"data": data}

    async def get(self, key: str) -> Document | None:
        snapshot = await self._reference(key).get(retry=None, timeout=self._timeout)
        return _document(snapshot)

    async def get_many(self, keys: Sequence[str]) -> list[Document | None]:
        """Input-ordered results, including duplicate keys and missing documents.

        Validate every key before I/O. Batches do not share a read snapshot.
        """
        refs = {key: self._reference(key) for key in keys}
        unique = list(refs.values())
        found: dict[str, Document | None] = {}
        for start in range(0, len(unique), self._batch_size):
            async for snapshot in self._client.get_all(
                unique[start : start + self._batch_size], retry=None, timeout=self._timeout
            ):
                found[snapshot.id] = _document(snapshot)
        return [found[key] for key in keys]

    async def create(self, key: str, data: dict[str, Any]) -> str:
        try:
            result = await self._reference(key).create(self._envelope(data), retry=None, timeout=self._timeout)
        except exceptions.AlreadyExists as exc:
            # Conflict also includes Aborted; those failures are not duplicate creates.
            raise DocumentAlreadyExists("Document already exists") from exc
        return _version(result.update_time)

    async def put(self, key: str, data: dict[str, Any], *, expected_version: str | None = None) -> str:
        ref = self._reference(key)
        envelope = self._envelope(data)
        option = _option(expected_version)
        if option is None:
            result = await ref.set(envelope, retry=None, timeout=self._timeout)
        else:
            try:
                result = await ref.update(envelope, option=option, retry=None, timeout=self._timeout)
            except exceptions.FailedPrecondition as exc:
                # A missing last-update-time target fails its precondition. NotFound
                # can instead mean the database is missing and must propagate.
                raise VersionConflict("Document version changed or document is missing") from exc
        return _version(result.update_time)

    async def delete(self, key: str, *, expected_version: str | None = None) -> None:
        ref = self._reference(key)
        option = _option(expected_version)
        try:
            await ref.delete(option=option, retry=None, timeout=self._timeout)
        except exceptions.FailedPrecondition as exc:
            if option is None:
                raise  # An operational failure is not an absent document.
            raise VersionConflict("Document version changed or document is missing") from exc
