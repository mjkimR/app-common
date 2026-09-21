# app-prebuilt-search

Semantic search over your existing SQLAlchemy data, using app-layer-base transactions and app-vector-store. Implement a source that extracts searchable items and hydrates hits; the prebuilt handles embeddings, incremental sync, filters, candidate paging, grouping and synchronization status.

`SearchService` uses SQLite or PostgreSQL; `SearchEngine` accepts application-owned runtimes, including non-DB snapshots. AI catalog, LangChain, background workers and a second document database are not required. Search never synchronizes implicitly.

## Install and migrate

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-search"
# Optionally install fastembed for the built-in local provider.
```

The package exposes the `fastembed` extra for local model inference. An injected embedding provider needs no extra. Keep app-common Git dependencies on the same pushed ref.

For `SearchService`, import `app_prebuilt_search.models` in your Alembic `env.py` before reading the shared `app_layer_base.base.models.mixin.Base.metadata`, then generate/review/apply a migration. The one new table is `search_index_states`, keyed by `(index_name, scope_id, profile_id)`; it stores the last successful sync time and counts and acts as the synchronization lock. No runtime `create_all` is performed. Source content stays in your existing tables. Qdrant stores identifiers, fingerprint, declared filter fields and explicitly supplied `index_metadata`. A custom runtime owns its state storage and does not require this table. The engine also stores one vectorless sync marker per scope/profile in Qdrant; it contains only the scope and a random generation, is excluded from search candidates, and is not source content.

## Implement a source

A source returns a complete scope snapshot for sync, and current authorized items for requested hits. A source item is identified by `(source_id, item_id)` within the scope. One document can yield an overview plus several blocks/chunks/units.

```python
from collections.abc import AsyncIterator, Mapping, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app_prebuilt_search import SearchHit, SearchItem
from app_prebuilt_search.filters import FilterValue


# Document is your application's SQLAlchemy model.
class DocumentSearchSource:
    def to_item(self, doc) -> SearchItem:
        return SearchItem(
            source_id=str(doc.id),
            item_id="overview",
            text=f"{doc.title}\n{doc.body}",
            title=doc.title,
            filters={"kind": doc.kind, "tags": doc.tags},
            metadata={"updated_at": doc.updated_at.isoformat()},
        )

    async def iter_items(self, session: AsyncSession, scope: str) -> AsyncIterator[SearchItem]:
        rows = await session.stream_scalars(select(Document).where(Document.project_id == scope))
        async for doc in rows:
            yield self.to_item(doc)

    async def hydrate(
        self,
        session: AsyncSession,
        scope: str,
        hits: Sequence[SearchHit],
        filters: Mapping[str, FilterValue],
    ) -> Sequence[SearchItem]:
        ids = {hit.source_id for hit in hits}
        rows = await session.scalars(
            select(Document).where(
                Document.project_id == scope,
                Document.id.in_(ids),
            )
        )
        # Apply caller-specific visibility/authorization here too.
        return [self.to_item(doc) for doc in rows]
```

Always apply scope and authorization in the source query; vector tenant indexes are not authorization. Authenticate/authorize the requested scope before calling the service. Source methods must not commit/rollback, change transaction settings or retain the supplied session. Hydration returns only requested identities, with current filter values; omit deleted or inaccessible items. The service rechecks declared filters against those values, preserves ranking and removes duplicates. For multi-item sources, hydrate only the requested `(source_id, item_id)` pairs.

Sync must enumerate the entire scope, not only the current user’s visible subset; authorize whole-scope indexing separately from per-user search. Source iteration failures must raise. Never treat an unavailable or partial source as an empty snapshot: a successful empty snapshot deliberately deletes all indexed items for that scope/profile.

## Wire and use

```python
from app_prebuilt_search import (
    FastEmbedProvider,
    KeywordArrayFilter,
    KeywordFilter,
    SearchIndex,
    SearchService,
)
from app_vector_store import QdrantSettings, open_qdrant

embedder = FastEmbedProvider(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    dimension=384,
    embedding_id="multilingual-minilm:model-artifact-v1",
    cache_dir="./data/models",
)


async def example(session_maker):
    async with open_qdrant(QdrantSettings(mode="local", path="./data/vectors")) as client:
        search = SearchService(
            session_maker=session_maker,
            vector_client=client,
            embedder=embedder,
            source=DocumentSearchSource(),
            index=SearchIndex(
                name="my-app.documents",
                recipe_version="v1",
                filters={"kind": KeywordFilter(), "tags": KeywordArrayFilter()},
            ),
        )
        report = await search.sync(scope="project-a")
        result = await search.search(
            scope="project-a",
            query="Authentication requirements",
            filters={"kind": "requirement", "tags": "backend"},
            limit=10,
            group_by_source=True,
        )
        status = await search.status(scope="project-a")
        return report, result, status
```

For FastAPI, hold `open_qdrant` in the app lifespan, store shared clients/providers there, and inject `SearchService` via `Annotated[SearchService, Depends(...)]`. Use the existing app-layer-base session maker. The service borrows clients and never closes them. Sources carrying caller-specific authorization must be constructed per request; do not mutate a shared source's credentials.

`FastEmbedProvider` lazily imports/loads its model in a worker thread and uses separate passage/query embedding methods. It serializes inference and drains cancelled thread work. `embedding_id` is a caller-maintained model/artifact version label, not an automatic model pin: provide/pin the intended model assets and change the label when they change. Other providers implement `embedding_id`, `dimension`, `embed_documents(texts)` and `embed_query(text)`.

## Filters and results

- `KeywordFilter`: exact string equality.
- `KeywordArrayFilter`: a query string must occur in the source's list of strings.
- `BooleanFilter`: exact boolean equality; integers and strings are rejected.
- `NumericFilter`: numeric equality or `NumericRange(gt=..., gte=..., lt=..., lte=...)`.
- All query fields combine with AND and the mandatory scope filter. Unknown fields and invalid types are rejected. Omitted source fields do not match a query on that field. Filter field names are simple identifiers; they are stored under `filters` in the Qdrant payload.
- By default, matching runs in Qdrant before ranking and again against current source values. Set `candidate_filters={}` to retrieve scope-only candidates while retaining final `filters` checks. Stale indexes can still omit new items until sync.
- `SearchResult.items` contains current content/metadata and similarity scores. `total` is the returned count, not a global match count. `group_by_source=True` returns at most one item per source, choosing the first valid ranked hit. Alternatively, `group_by=lambda item: (item.source_id, item.metadata["target_id"])` groups chunks into logical targets using current hydrated data; the callback must return a hashable key. Do not combine both grouping options.
- Candidate batches continue past stale/unauthorized/duplicate hits. `candidate_limit_reached` reports hitting the configured bound before filling `limit`. Defaults: embedding batches 64, candidate batches 64, candidate budget 2000.
- `index_ready` means this scope/profile has a successful runtime record whose generation matches its marker in the selected collection. A collection recreated by another scope does not make this scope ready. `last_synced_at` is historical, not proof that the index matches current DB content. `status` also exposes collection presence separately. Missing indexes return `index_ready=False` without embedding or creating a collection.

## Synchronization and transaction policy

A profile hashes embedding identity, dimension, recipe version and filter declarations. Each index/profile uses its own collection. Change `recipe_version` for extraction/chunking changes. Old profiles remain untouched; remove obsolete collections explicitly after consumers have switched. Index names must be unique across applications/databases sharing the same Qdrant deployment, and scope IDs must be stable and globally unique within an index.

`SearchService.sync` acquires a DB lock before source enumeration, then reconciles the complete snapshot:

1. Validate/enumerate items; reject duplicate identities.
2. Ensure the collection and payload indexes and read existing scoped fingerprints.
3. Re-embed changed text/profile; refresh filter or index-metadata changes without recomputing vectors.
4. Delete stale IDs only after enumeration and all updates have succeeded.
5. Record success in the same DB transaction.

Source snapshots/inventory are currently held in memory. Embedding, upserts, per-point payload replacements and deletes are batched. This first version targets bounded corpora and explicit sync, not a continuous high-volume indexing worker.

PostgreSQL locks the index/scope/profile row; SQLite uses `BEGIN IMMEDIATE`, serializing database writes. The lock is held across embedding and Qdrant I/O, so slow sync can delay writers (database-wide for SQLite). Default PostgreSQL READ COMMITTED is expected. These locks serialize sync calls, not arbitrary source writers on PostgreSQL; changes during/after enumeration are picked up by the next sync. Apps needing a fully consistent multi-query source snapshot must provide their own source locking/revision policy.

`search` and `status` keep external I/O outside DB transactions. Hydration/status use short database-enforced read-only transactions; SQLite query-only state is reset before returning the connection. The service owns its sessions: do not wrap service calls in an existing DB transaction, and do not use a shared in-memory SQLite connection concurrently for sync and search. File-backed SQLite or PostgreSQL provides independent connections.

DB and Qdrant writes are not atomic. A failed sync can leave some vector changes visible; the last successful DB marker is unchanged. Stable IDs and fingerprint comparison make a subsequent sync repair/reconcile the index. Cancellation during external sync work drains that work before releasing the runtime lock (including repeated cancellation); source iteration/state callbacks stay in the caller task. Cancellation before vector work begins can stop immediately. Successful drained writes are recorded before propagating cancellation when possible; callers may receive cancellation even if the sync completed successfully. Network timeouts can have uncertain remote outcomes, so reconcile again after failures. No automatic retry, durable job queue, progress/error history, implicit on-save indexing or atomic profile cutover is provided. A durable reconciliation worker or outbox integration is a separate concern; neither is required to use the engine.

## Application-owned runtime

`SearchService(session_maker=..., source=..., ...)` keeps the original SQLAlchemy
API and delegates to `SQLAlchemySearchRuntime`. For a caller-owned transaction,
domain repositories or a canonical snapshot outside the DB, use `SearchEngine`:

```python
from app_prebuilt_search import BooleanFilter, SearchEngine, SearchIndex

# runtime implements SearchRuntime; client and embedder are application-owned.
engine = SearchEngine(
    runtime=runtime,
    vector_client=client,
    embedder=embedder,
    index=SearchIndex(
        name="my-app.documents",
        recipe_version="chunks-v1",
        filters={"archived": BooleanFilter()},
    ),
)
await engine.sync(scope="project-main")
result = await engine.search(
    scope="project-main",  # Vector namespace and readiness state.
    source_scope="project-branch",  # Current source to hydrate; defaults to scope.
    query="authentication",
    filters={"archived": False},
    group_by=lambda item: (item.source_id, item.metadata["target_id"]),
)
```

The runtime implements three operations (public types are exported at package root):

| Operation | Responsibility |
|---|---|
| `sync(IndexKey) -> AsyncContextManager[SearchSyncSession]` | Acquire the index lock **before** reading the source; yield a session with `iter_items()` and async `record_success(result)` that persists the complete result including `generation`; retain the lock until writes and success recording finish. Reject sync for read-only snapshots. |
| `read_state(IndexKey) -> SyncState` | Return last successful sync state from a short read scope. Readiness belongs to the vector namespace, not the hydrated snapshot. |
| `hydrate(SearchRequest, hits) -> Sequence[SearchItem]` | Load only requested, currently authorized identities from `request.source_scope` in a short read-only scope. The request carries the query and final/candidate filters. |

`IndexKey` contains index name, scope and profile identity. All writers of the same
key, across instances/workspaces, must use compatible locking. A local workspace lock
is insufficient for a shared remote index. The runtime also chooses whether source
writers are excluded or a stable versioned snapshot is read. Releasing the lock for
embedding requires a separate publication/fencing design; the engine does not provide it.

Runtime callbacks run in the caller task, so a custom runtime can join the caller's
transaction without sharing a session across tasks. It must not commit/close a transaction
owned by that caller. The vector/model reconciliation alone runs in a drained worker task.
Do not start a second DB transaction merely to reuse the SQLAlchemy facade.

When `source_scope != scope`, candidate filters default to empty (the mandatory
vector scope filter remains). This prevents old main metadata from hiding matches in
the current snapshot. Explicit `candidate_filters` can narrow candidates when the
application knows that is valid. Final `filters` are always validated and rechecked on
hydrated values. For different snapshots using the same textual scope, pass
`candidate_filters={}` explicitly. Paging still has a finite budget; branch-only
items without canonical vectors require another retriever, such as keyword search.

Scope routing is trusted integration input. Authorize the index/source pairing before
calling the engine, and constrain/authorize all source reads in the runtime. Do not
expose arbitrary `source_scope` values as an authorization mechanism. Construct runtime
instances with request-specific credentials when needed. Source selection, main/branch
write policy, hierarchy interpretation and hybrid fallback remain application concerns.

See [the executable snapshot runtime tests](tests/unit/test_runtime.py) for an example
that uses no SQLAlchemy sessions and covers alternate snapshots, forbidden publication,
stale metadata, grouping, partial enumeration and cancellation under a shared lock.

## Chunk metadata and adoption

Chunking remains source-owned. Supply each chunk as a stable `(source_id, item_id)`
and put only the needed indexed facts in `SearchItem.index_metadata`, for example:

```python
item = SearchItem(
    source_id="doc-1",
    item_id="unit-1:chunk-0",
    text="contextual embedding input",
    index_metadata={"source_hash": "...", "start": 0, "end": 80},
    metadata={"target_id": "unit-1"},
)
```

`index_metadata` accepts JSON values and is persisted in Qdrant. `SearchHit.index_metadata`
is the metadata **from the indexed snapshot**; the runtime compares it to the current
source before applying offsets. It may drop stale hits or return a current excerpt with
application-defined flags in `metadata`. The engine preserves the candidate cosine score;
it does not claim that a stale score describes the current excerpt. Title/text/display
`metadata` are never copied to Qdrant automatically. Changes only to indexed metadata
refresh payloads without re-embedding; display-only changes need no index write.

Existing profiles, point IDs and collections remain compatible when adopting these
APIs alone; old hits have empty indexed metadata until sync refreshes them. Change
`recipe_version` when extraction/chunking semantics change. Switching from a consumer's
separate vector implementation may require a new collection and full reindex because
its identity/payload/vector schema can differ. This package extension does not migrate
consumer indexes or install a worker, tokenizer, BM25 retriever or branch policy.

Readiness generations live in the existing `last_result` JSON, so no additional DB
migration is needed. After upgrading, run one sync per scope/profile: legacy state
without a generation is reported as not ready. Unchanged items reuse their vectors.
Raw unfiltered collection scrolls include sync markers; use the mandatory `scope_id`
filter when enumerating searchable points. A marker confirms a completed sync, not
current source freshness or a checksum of every point. Selective external point
deletions still require reconciliation. If vector publication succeeds but recording
state fails, the generation mismatch reports not ready until the next successful sync.

## Validation

Run `just lint app-prebuilt-search`, `just check app-prebuilt-search`, and `bash scripts/run-tests.sh sqlite app-prebuilt-search`. Run the same test command with `postgres` for actual row-lock/read-only verification (Docker required). Tests use deterministic vectors and do not claim semantic relevance quality.
