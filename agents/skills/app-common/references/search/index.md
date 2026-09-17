# app-prebuilt-search

Use for semantic search over existing app-layer-base SQLAlchemy data. Depend on
app-prebuilt-search; add the fastembed extra only for local inference. AI catalog is not required.

- Register `app_prebuilt_search.models` in Alembic before reading shared Base.metadata;
  migrate `search_index_states`. No runtime schema creation is performed.
- Construct `SearchService(session_maker=..., vector_client=..., embedder=..., source=...,
  index=SearchIndex(name=..., recipe_version=..., filters=...))`.
- Implement `SearchSource.iter_items(session, scope)` as a complete async iterator of
  `SearchItem(source_id, item_id, text, filters, title, metadata)` and
  `hydrate(session, scope, hits, filters)` returning current authorized items for requested identities.
  Always constrain source DB reads by scope. Do not commit, rollback or keep the supplied session.
- Declare `KeywordFilter`, `KeywordArrayFilter` or `NumericFilter` fields. Queries are exact AND
  conditions; numeric ranges use `NumericRange`. The service enforces scope and checks filters again
  on hydrated data. Domain hierarchy/ACL interpretation remains in the source.
- Call `sync(scope=...)` explicitly; `search(scope=..., query=..., filters=..., limit=...)` never syncs.
  `status(scope=...)` distinguishes collection availability from a successful per-scope/profile sync.
  Readiness is not freshness. Group hits with `group_by_source=True`; inspect `candidate_limit_reached`.
- Index/profile collections separate embedding identity, dimension, recipe and filter schema.
  Change model identity/recipe when inputs or artifacts change. Old collections are retained.
- Search uses short read-only DB transactions only for hydration/status. Sync owns a write transaction
  across model/Qdrant work: PostgreSQL scope/profile row lock; SQLite BEGIN IMMEDIATE (database-wide writes).
  Do not wrap service calls in a caller transaction. Sync locks do not block arbitrary PostgreSQL source
  writers; their later edits need another sync. In-memory SQLite shared connections are not concurrent-safe.
- Sync enumerates the complete snapshot before mutation; never return a partial snapshot as success.
  It holds the snapshot in memory, batches embedding/upserts/deletes, and updates only payload when filters change.
  Failed Qdrant/DB writes are not atomic together; rerun sync with stable IDs to reconcile.
- The caller owns Qdrant lifecycle (`open_qdrant`). FastEmbedProvider is lazy and optional; supply
  model_name, dimension, embedding_id, optional cache_dir. It uses distinct document/query embedding paths.
- No router, automatic worker/outbox integration, or source document tables are installed.
