# app-prebuilt-search

Use for semantic search over existing data. SearchService provides app-layer-base SQLAlchemy scopes; SearchEngine accepts application-owned runtimes. Depend on
app-prebuilt-search; add the fastembed extra only for local inference. AI catalog is not required.

- For SearchService, register `app_prebuilt_search.models` in Alembic before reading shared Base.metadata;
  migrate `search_index_states`. No runtime schema creation is performed.
- Construct `SearchService(session_maker=..., vector_client=..., embedder=..., source=...,
  index=SearchIndex(name=..., recipe_version=..., filters=...))`.
- Implement `SearchSource.iter_items(session, scope)` as a complete async iterator of
  `SearchItem(source_id, item_id, text, filters, title, metadata)` and
  `hydrate(session, scope, hits, filters)` returning current authorized items for requested identities.
  Always constrain source DB reads by scope. Do not commit, rollback or keep the supplied session.
- Declare `KeywordFilter`, `KeywordArrayFilter`, `BooleanFilter` or `NumericFilter` fields. Queries are exact AND
  conditions; numeric ranges use `NumericRange`. The service enforces scope and checks filters again
  on hydrated data. Domain hierarchy/ACL interpretation remains in the source.
- Call `sync(scope=...)` explicitly; `search(scope=..., query=..., filters=..., limit=...)` never syncs.
  `status(scope=...)` distinguishes collection availability from a successful per-scope/profile sync.
  Readiness is not freshness. Group hits with `group_by_source=True`; inspect `candidate_limit_reached`.
- Index/profile collections separate embedding identity, dimension, recipe and filter schema.
  Change model identity/recipe when inputs or artifacts change. Old collections are retained.
- SearchService uses short read-only DB transactions only for hydration/status. Its sync owns a write transaction
  across model/Qdrant work: PostgreSQL scope/profile row lock; SQLite BEGIN IMMEDIATE (database-wide writes).
  Do not wrap service calls in a caller transaction. Sync locks do not block arbitrary PostgreSQL source
  writers; their later edits need another sync. In-memory SQLite shared connections are not concurrent-safe.
- Sync enumerates the complete snapshot before mutation; never return a partial snapshot as success.
  It holds the snapshot in memory, batches embedding/upserts/deletes, and updates only payload when filters change.
  Failed Qdrant/DB writes are not atomic together; rerun sync with stable IDs to reconcile.
- The caller owns Qdrant lifecycle (`open_qdrant`). FastEmbedProvider is lazy and optional; supply
  model_name, dimension, embedding_id, optional cache_dir. It uses distinct document/query embedding paths.
- No router, automatic worker/outbox integration, or source document tables are installed.

## Application-owned execution and snapshots

- Use `SearchEngine(runtime=..., vector_client=..., embedder=..., index=...)` when the application owns transactions, repositories or non-DB snapshots. The existing SearchService constructor remains supported through SQLAlchemySearchRuntime.
- Implement SearchRuntime: `sync(IndexKey)` yields SearchSyncSession (`iter_items()` and async `record_success(result)`); `read_state(IndexKey)` returns SyncState; `hydrate(SearchRequest, hits)` returns current authorized SearchItems from a short read-only scope.
- Acquire the index/scope/profile lock before source enumeration and retain it through vector writes and completion. Coordinate every writer across processes/workspaces; a workspace-local lock does not protect a shared remote index. The runtime owns snapshot consistency and denies forbidden publication.
- Runtime callbacks stay in the caller task and can join its transaction without committing it. External reconciliation drains on cancellation before lock release. Do not reuse the SQLAlchemy facade inside an outer transaction.
- `scope` selects vectors/readiness; `source_scope` selects hydration. Authorize this pairing before calling the engine. Different scopes default to scope-only vector candidates. Use `candidate_filters={}` explicitly for alternate snapshots with the same scope name. Final `filters` always apply to current hydrated data; relaxing candidates never relaxes the mandatory vector scope.
- `SearchItem.index_metadata` explicitly persists JSON facts such as source hash and chunk offsets. `SearchHit.index_metadata` is from the indexed snapshot; hydration must validate it before using offsets or claiming freshness. Current display metadata stays source-owned. Old payloads yield empty indexed metadata.
- Use `group_by=lambda item: (item.source_id, item.metadata["target_id"])` for target-level chunk grouping, or existing `group_by_source=True` for documents. Only one grouping option at a time. Grouping uses current hydrated items and retains candidate ranking.
- Source chunking, canonical/branch policy, stale-score annotations, hierarchy meaning and hybrid fallback remain application concerns. No consumer replacement, automatic migration or outbox coupling is required.
