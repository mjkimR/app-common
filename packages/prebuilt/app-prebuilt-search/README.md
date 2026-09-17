# app-prebuilt-search

Semantic search over your existing SQLAlchemy data, using app-layer-base transactions and app-vector-store. Implement a source that extracts searchable items and hydrates hits; the prebuilt handles embeddings, incremental sync, filters, candidate paging, grouping and synchronization status.

Requires SQLite or PostgreSQL. AI catalog, LangChain, background workers and a second document database are not required. Search never synchronizes implicitly.

## Install and migrate

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-search"
# Optionally install fastembed for the built-in local provider.
```

The package exposes the `fastembed` extra for local model inference. An injected embedding provider needs no extra. Keep app-common Git dependencies on the same pushed ref.

Import `app_prebuilt_search.models` in your Alembic `env.py` before reading the shared `app_layer_base.base.models.mixin.Base.metadata`, then generate/review/apply a migration. The one new table is `search_index_states`, keyed by `(index_name, scope_id, profile_id)`; it stores the last successful sync time and counts and acts as the synchronization lock. No runtime `create_all` is performed. Source content stays in your existing tables. Qdrant stores only identifiers, fingerprint and declared filter fields.

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
- `NumericFilter`: numeric equality or `NumericRange(gt=..., gte=..., lt=..., lte=...)`.
- All query fields combine with AND and the mandatory scope filter. Unknown fields and invalid types are rejected. Omitted source fields do not match a query on that field. Filter field names are simple identifiers; they are stored under `filters` in the Qdrant payload.
- Matching runs in Qdrant before ranking and again against current source values. Stale indexes can still omit newly matching documents; run sync to update membership.
- `SearchResult.items` contains current content/metadata and similarity scores. `total` is the returned count, not a global match count. `group_by_source=True` returns at most one item per source, choosing the first valid ranked hit.
- Candidate batches continue past stale/unauthorized/duplicate hits. `candidate_limit_reached` reports hitting the configured bound before filling `limit`. Defaults: embedding batches 64, candidate batches 64, candidate budget 2000.
- `index_ready` means the selected collection exists and this scope/profile has successfully synced at least once. `last_synced_at` is historical, not proof that the index matches current DB content. `status` also exposes collection presence separately. Missing indexes return `index_ready=False` without embedding or creating a collection.

## Synchronization and transaction policy

A profile hashes embedding identity, dimension, recipe version and filter declarations. Each index/profile uses its own collection. Change `recipe_version` for extraction/chunking changes. Old profiles remain untouched; remove obsolete collections explicitly after consumers have switched. Index names must be unique across applications/databases sharing the same Qdrant deployment, and scope IDs must be stable and globally unique within an index.

`sync` acquires a DB lock before source enumeration, then reconciles the complete snapshot:

1. Validate/enumerate items; reject duplicate identities.
2. Ensure the collection and payload indexes and read existing scoped fingerprints.
3. Re-embed changed text/profile; refresh metadata-only filter changes without recomputing vectors.
4. Delete stale IDs only after enumeration and all updates have succeeded.
5. Record success in the same DB transaction.

Source snapshots/inventory are currently held in memory. Embedding, upserts and deletes are batched. This first version targets bounded corpora and explicit sync, not a continuous high-volume indexing worker.

PostgreSQL locks the index/scope/profile row; SQLite uses `BEGIN IMMEDIATE`, serializing database writes. The lock is held across embedding and Qdrant I/O, so slow sync can delay writers (database-wide for SQLite). Default PostgreSQL READ COMMITTED is expected. These locks serialize sync calls, not arbitrary source writers on PostgreSQL; changes during/after enumeration are picked up by the next sync. Apps needing a fully consistent multi-query source snapshot must provide their own source locking/revision policy.

`search` and `status` keep external I/O outside DB transactions. Hydration/status use short database-enforced read-only transactions; SQLite query-only state is reset before returning the connection. The service owns its sessions: do not wrap service calls in an existing DB transaction, and do not use a shared in-memory SQLite connection concurrently for sync and search. File-backed SQLite or PostgreSQL provides independent connections.

DB and Qdrant writes are not atomic. A failed sync can leave some vector changes visible; the last successful DB marker is unchanged. Stable IDs and fingerprint comparison make a subsequent sync repair/reconcile the index. Cancellation drains the active sync before releasing its DB lock; callers may receive cancellation even if the sync completed successfully. Network timeouts can have uncertain remote outcomes, so reconcile again after failures. No automatic retry, durable job queue, progress/error history, implicit on-save indexing or atomic profile cutover is provided. Add an outbox-driven worker separately when those become necessary.

## Validation

Run `just lint app-prebuilt-search`, `just check app-prebuilt-search`, and `bash scripts/run-tests.sh sqlite app-prebuilt-search`. Run the same test command with `postgres` for actual row-lock/read-only verification (Docker required). Tests use deterministic vectors and do not claim semantic relevance quality.
