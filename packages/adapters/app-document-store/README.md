# app-document-store

Standalone async document storage using Firestore. Applications own domain models,
collection names, authorization, retention, and SQL coordination. This package does
not depend on app-layer-base, FastAPI, or other adapters.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<pushed-ref>#subdirectory=packages/adapters/app-document-store"
```

Firestore Native mode is the first provider. `DocumentStore` is a structural
protocol for application repositories and test doubles, not a SQL query translator.
There is no automatic database creation, collection scan, SQL migration, or
multi-document transaction API.

## Configuration and ownership

`FirestoreSettings` reads `DOCUMENT_STORE_` variables:

| Suffix | Default | Meaning |
| --- | --- | --- |
| `PROJECT_ID` | required | Explicit GCP project ID |
| `DATABASE_ID` | `(default)` | An already provisioned Firestore database |
| `NAMESPACE` | required | Application path scope, e.g. `autohub` |
| `MODE` | `firestore` | `firestore` or explicitly `emulator` |
| `TIMEOUT` | `10` | Per-RPC timeout in seconds; pass to the store |

Production uses Google Application Default Credentials. On Cloud Run, attach a
service account with the required Firestore IAM permissions; do not ship service
account key files. Server clients use IAM, not Firebase client security rules.
Namespaces separate document paths but do not restrict a service account's access.
Applications must authorize access before calling a repository.

The application creates one client per event loop/lifespan and passes it to stores:

```python
from app_document_store import FirestoreDocumentStore, FirestoreSettings, open_firestore


async def example() -> None:
    settings = FirestoreSettings()
    async with open_firestore(settings) as client:
        reports = FirestoreDocumentStore(client, "reports", namespace=settings.namespace, timeout=settings.timeout)
        version = await reports.create("session-123", {"body": "First report", "format_version": 1})
        version = await reports.put("session-123", {"body": "Revised report"}, expected_version=version)
        document = await reports.get("session-123")
        assert document is not None
        assert document.data == {"body": "Revised report"}
        await reports.delete("session-123", expected_version=version)
```

For FastAPI, enter `open_firestore` inside the application's lifespan, construct
repositories there, and inject them into usecases. No singleton or FastAPI dependency
is installed by this adapter. `create_firestore_client` also supports explicit
ownership; pair it with `await close_firestore_client(client)`. The latter closes
the async gRPC transport that the SDK 2.x inherited `close()` does not close.

## Document contract

The storage path is `namespaces/{namespace}/{collection}/{key}`. All three IDs
are individual path segments: empty IDs, slashes, `.`/`..`, reserved `__name__`
syntax, and IDs over 1500 UTF-8 bytes are rejected. App identifiers containing `/`
need an application-owned encoding or stable hash.

The Firestore document contains exactly `{"data": <application dict>}`. This
envelope allows an atomic conditional replacement of the complete payload using
Firestore's update-time precondition. It is a dedicated collection format, not
an adapter for arbitrary pre-existing Firestore collections. Do not add sibling
fields beside `data`. Raw documents with a different shape raise `InvalidDocument`.
An out-of-band writer must also preserve this envelope.

| Operation | Contract |
| --- | --- |
| `get(key)` | `Document(key, data, version)` or `None` if absent |
| `get_many(keys)` | Results in input order, including duplicates and `None` entries |
| `create(key, data)` | Create only; existing key raises `DocumentAlreadyExists` |
| `put(key, data)` | Unconditional upsert; replaces the complete payload, including removal of old fields |
| `put(..., expected_version=v)` | Existing document must match `v`, otherwise `VersionConflict` |
| `delete(key)` | Missing document is a no-op; no recursive subcollection deletion |
| `delete(..., expected_version=v)` | Missing or changed document raises `VersionConflict` |

Create and put return an opaque version string. Pass it unchanged, only to the
same document in the same database. It preserves Firestore timestamp nanoseconds;
do not convert it to a Python microsecond datetime. Versions are concurrency tokens,
not event IDs, application revision counters, or a cross-document ordering scheme.

Batch reads deduplicate network requests, validate all keys before I/O, and use
batches of 100 by default (`batch_size` is configurable). Multiple batches do not
promise a shared point-in-time snapshot. Empty input does no I/O.

Payload values follow the Firestore SDK's supported value types and encoding
rules, including timestamps and bytes. The SDK/server enforce field-depth and
document-size limits. Firestore maps do not preserve insertion order: serialize
order-sensitive planroot source to a string. The 1 MiB document limit includes
the envelope and other metadata; large artifacts need a separate storage design.
Declare index exemptions for large, unqueried fields such as `data.body` in
deployment configuration. This package does not manage indexes or TTL policies.

## Failure and delivery semantics

Only duplicate creation and conditional-write conflicts become adapter errors.
Authentication, permission, quota, transport, and timeout errors propagate from
the SDK; they are never reported as missing documents or successful writes.
Cancellation also propagates. RPC retries are explicitly disabled. A timeout can
have an unknown write outcome; read/reconcile before retrying a conditional write.
An application may retry idempotent operations under its own retry budget.

Firestore writes do not participate in SQLAlchemy transactions. If a SQL state
change must eventually produce a document, use the existing `app-prebuilt-outbox`
and inject an application publisher that calls this adapter. Outbox delivery can
repeat or arrive out of order: use stable document/event IDs and source revision
checks. A duplicate create is safe to acknowledge only after verifying the stored
payload matches the intended immutable event. After-commit callbacks alone are
best-effort and unsuitable for durable report delivery.

The application must arrange SQL/outbox payload retention and remove source bodies
only after confirmed archival. Adding Firestore while retaining every body in SQL
does not save SQL storage.

## Tests and emulator

```bash
just lint app-document-store
just check app-document-store
bash scripts/run-tests.sh sqlite app-document-store
DOCKER=1 bash scripts/run-tests.sh sqlite app-document-store
```

The last command runs real emulator contract tests, also included in `just
test-docker` and the existing Docker CI job. It starts the pinned official Google
Cloud CLI emulator image. Backend startup errors fail this test leg rather than
silently skipping it. Emulator tests use a fixed `demo-document-store` project and
fresh namespaces; they never select a developer's cloud project.

Alternatively start an emulator yourself and export
`FIRESTORE_EMULATOR_HOST=127.0.0.1:8080` before running the same command. The fixture
uses this endpoint instead of Docker. The application must explicitly set
`DOCUMENT_STORE_MODE=emulator`; production mode rejects an ambient emulator host.
The endpoint has no URL scheme. No application credentials are needed in emulator
mode. External emulators retain test documents until reset.

The suite checks full replacement, namespace isolation, create-only collisions,
batch ordering/missing keys, competing versioned writes, and conditional deletion.
Unit tests cover operational failures, nanosecond tokens, and client shutdown.
The emulator does not verify production IAM, billing, all limits, or latency;
check those separately in a provisioned project before deployment.

See the [consumer guide](../../../agents/skills/app-common/references/document/index.md).
