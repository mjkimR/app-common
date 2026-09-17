from types import SimpleNamespace

import pytest
from app_layer_base.base.models.mixin import Base
from app_prebuilt_search import KeywordArrayFilter, KeywordFilter, NumericFilter, SearchIndex, SearchItem, SearchService
from app_vector_store import QdrantSettings, open_qdrant
from sqlalchemy import JSON, String, select
from sqlalchemy.orm import Mapped, mapped_column

pytest_plugins = ["app_testing_base.plugin"]


class SourceRow(Base):
    __tablename__ = "search_test_source"
    scope: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    text: Mapped[str] = mapped_column(String)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)


class DatabaseSource:
    enumerations = 0
    fail_iteration = False

    def __init__(self):
        self.denied = set()

    def item(self, row):
        return SearchItem(source_id=row.source_id, item_id=row.item_id, text=row.text, filters=row.filters)

    async def iter_items(self, session, scope):
        self.enumerations += 1
        rows = (await session.scalars(select(SourceRow).where(SourceRow.scope == scope))).all()
        for row in rows:
            yield self.item(row)
            if self.fail_iteration:
                raise RuntimeError("incomplete snapshot")

    async def hydrate(self, session, scope, hits, filters):
        ids = {hit.source_id for hit in hits}
        rows = (
            await session.scalars(select(SourceRow).where(SourceRow.scope == scope, SourceRow.source_id.in_(ids)))
        ).all()
        requested = {(h.source_id, h.item_id) for h in hits}
        return [
            self.item(r)
            for r in reversed(rows)
            if (r.source_id, r.item_id) in requested and r.source_id not in self.denied
        ]


class Embedder:
    embedding_id = "deterministic-v1"
    dimension = 2

    def __init__(self):
        self.documents, self.queries = [], []
        self.failure = False

    async def embed_documents(self, texts):
        self.documents.extend(texts)
        if self.failure:
            raise RuntimeError("embedding failed")
        return [[1.0, 0.0] for _ in texts]

    async def embed_query(self, text):
        self.queries.append(text)
        return [1.0, 0.0]


@pytest.fixture
async def harness(session, session_maker):
    async with open_qdrant(QdrantSettings(mode="memory")) as client:
        source, embedder = DatabaseSource(), Embedder()
        index = SearchIndex(
            name="documents",
            recipe_version="v1",
            batch_size=2,
            candidate_batch_size=2,
            filters={"kind": KeywordFilter(), "price": NumericFilter(), "tags": KeywordArrayFilter()},
        )

        def make(**overrides):
            return SearchService(
                **{
                    "session_maker": session_maker,
                    "vector_client": client,
                    "source": source,
                    "embedder": embedder,
                    "index": index,
                    **overrides,
                }
            )

        async def put(source_id, *, scope="a", item_id="overview", text="body", filters=None):
            async with session_maker.begin() as session:
                await session.merge(
                    SourceRow(scope=scope, source_id=source_id, item_id=item_id, text=text, filters=filters or {})
                )

        yield SimpleNamespace(
            service=make(),
            make=make,
            source=source,
            embedder=embedder,
            client=client,
            put=put,
            maker=session_maker,
            row=SourceRow,
        )


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.real_commit)
