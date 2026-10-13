# Document storage and Firestore

Use `app-document-store` for independently addressable documents such as completed
reports or derived observation snapshots. The adapter owns Firestore I/O; the
application owns domain DTOs, collection/key mapping, authorization, retention, and
coordination with SQL. There is no dependency on app-layer-base or other adapters.

## Setup

Install `packages/adapters/app-document-store` at the same pushed app-common ref as
the consumer's other packages. Configure `DOCUMENT_STORE_PROJECT_ID`,
`DOCUMENT_STORE_NAMESPACE`, optionally `DOCUMENT_STORE_DATABASE_ID` and
`DOCUMENT_STORE_TIMEOUT`. Provision Firestore explicitly, preferably in the same
region as the backend. Cloud Run uses attached-service-account ADC and IAM.

Enter `open_firestore(FirestoreSettings())` in the application lifespan. Construct
`FirestoreDocumentStore(client, "reports", namespace=settings.namespace,
timeout=settings.timeout)` there and inject it into application repositories.
Reuse the client in its event loop; stores borrow it and must not close it.

The structural `DocumentStore` protocol provides `get`, `get_many`, `create`,
`put`, and `delete`. Keep domain models and SDK-independent repository interfaces
in the application; no generic SQL-to-Firestore query conversion is provided.

## Contract

- Paths are `namespaces/{namespace}/{collection}/{key}`. IDs are single validated
  segments. Encode application identifiers containing slashes explicitly.
- A namespace separates paths, not IAM permissions. Backend authorization remains
  necessary; server SDKs do not use Firebase client security rules.
- Firestore documents contain a single `data` map; reserve that envelope for this
  adapter. Applications receive the unwrapped dict and an opaque version string.
- `create` fails if present. `put` replaces the entire payload; it is not a patch.
  An `expected_version` on put/delete is checked atomically by Firestore.
- Preserve the returned version exactly, including nanoseconds, for the same
  document. A stale or missing versioned target raises `VersionConflict`.
- `get_many` preserves order, duplicates and missing results. Batches are not one
  cross-document snapshot. No unbounded collection listing is provided.
- Operational SDK failures and cancellation propagate. Retries are disabled;
  timeouts may have unknown write outcomes, so reconcile before retrying.
- Maps do not preserve key order. Keep order-sensitive source as serialized text.
  Document size/depth limits still apply. Declare index exemptions for large
  unqueried fields in deployment configuration.

## SQL integration

Do not put SDK calls into SQL transaction hooks and assume atomicity. A usecase
can use SQL repositories and a document repository independently. Required eventual
delivery should use `app-prebuilt-outbox` with an application-owned publisher.
Adapters do not depend on one another or import the outbox package.

Use immutable event/document keys, compare payloads on duplicate creates, and
handle source revisions for mutable projections. The outbox can redeliver and
reorder events. SQL source/outbox payload cleanup follows confirmed persistence;
the application defines retention. Best-effort after-commit callbacks do not
guarantee delivery. Do not move leases, quota counters, authentication state, or
version ledgers merely because they happen to be JSON columns.

## Verification

Unit tests can inject a `DocumentStore` double. Contract tests must also run against
Firestore Emulator (`DOCKER=1 bash scripts/run-tests.sh sqlite app-document-store`
in app-common). Production IAM, billing, limits and latency need cloud verification.
Emulator mode requires `FIRESTORE_EMULATOR_HOST=host:port` and
`DOCUMENT_STORE_MODE=emulator`; production rejects an ambient emulator endpoint.

See the package README for usage examples and API semantics.
