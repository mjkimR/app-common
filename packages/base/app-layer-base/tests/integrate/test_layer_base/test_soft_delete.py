"""
Integration tests for opt-in soft delete, against a real database.

The contract under test: deletes stamp instead of removing, every read hides
stamped rows unless explicitly asked (``include_deleted``), restore and purge
round out the lifecycle, and the service layer wires through with no changes.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app_layer_base.base.models.mixin import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app_layer_base.base.repos.base import BaseRepository
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
)
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

# =============================================================================
# Test Model, Repository & Service
# =============================================================================


class SoftDeleteNote(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "soft_delete_notes"
    name: Mapped[str] = mapped_column(String(100))


class NoteCreate(BaseModel):
    name: str


class NoteUpdate(BaseModel):
    name: str | None = None


class SoftDeleteNoteRepository(BaseRepository[SoftDeleteNote, NoteCreate, NoteUpdate, NoteUpdate]):
    model = SoftDeleteNote
    soft_delete_enabled = True


class NoteService(
    BaseCreateServiceMixin[SoftDeleteNoteRepository, SoftDeleteNote, NoteCreate, BaseContextKwargs],
    BaseGetServiceMixin[SoftDeleteNoteRepository, SoftDeleteNote, BaseContextKwargs],
    BaseGetMultiServiceMixin[SoftDeleteNoteRepository, SoftDeleteNote, BaseContextKwargs],
    BaseDeleteServiceMixin[SoftDeleteNoteRepository, SoftDeleteNote, BaseContextKwargs],
):
    def __init__(self, repo: SoftDeleteNoteRepository):
        self._repo = repo
        self.hooks = ()

    @property
    def repo(self) -> SoftDeleteNoteRepository:
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


class CompositeSoftDeleteItem(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "composite_soft_delete_items"
    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), primary_key=True)


class CompositeItemCreate(BaseModel):
    tenant_id: uuid.UUID
    code: str


class CompositeSoftDeleteRepository(
    BaseRepository[CompositeSoftDeleteItem, CompositeItemCreate, CompositeItemCreate, CompositeItemCreate]
):
    model = CompositeSoftDeleteItem
    soft_delete_enabled = True


@pytest.fixture
def repo() -> SoftDeleteNoteRepository:
    return SoftDeleteNoteRepository()


@pytest.fixture
def service(repo) -> NoteService:
    return NoteService(repo)


async def _create(repo, session, *names: str) -> list[SoftDeleteNote]:
    return [await repo.create(session, NoteCreate(name=name)) for name in names]


# =============================================================================
# Writes
# =============================================================================


class TestSoftDeleteWrites:
    async def test_delete_stamps_instead_of_deleting(self, repo, session):
        (note,) = await _create(repo, session, "a")

        assert await repo.delete_by_pk(session, note.id) is True

        row = await repo.get_by_pk(session, note.id, include_deleted=True)
        assert row is not None
        assert row.is_deleted
        assert row.deleted_at is not None

    async def test_delete_is_idempotent(self, repo, session):
        (note,) = await _create(repo, session, "a")

        assert await repo.delete_by_pk(session, note.id) is True
        assert await repo.delete_by_pk(session, note.id) is False  # already gone: no-op

    async def test_delete_multi_counts_only_newly_deleted(self, repo, session):
        notes = await _create(repo, session, "a", "b", "c")
        await repo.delete_by_pk(session, notes[0].id)

        deleted = await repo.delete_by_pk_multi(session, [n.id for n in notes])

        assert deleted == 2


# =============================================================================
# Reads
# =============================================================================


class TestSoftDeleteReads:
    async def test_reads_hide_deleted_rows_by_default(self, repo, session):
        gone, _kept = await _create(repo, session, "gone", "kept")
        await repo.delete_by_pk(session, gone.id)

        assert await repo.get_by_pk(session, gone.id) is None
        assert await repo.get(session, where=SoftDeleteNote.name == "gone") is None
        assert await repo.exists(session, where=SoftDeleteNote.name == "gone") is False
        assert [n.name for n in await repo.get_all(session)] == ["kept"]

        page = await repo.get_multi(session)
        assert [n.name for n in page.items] == ["kept"]
        assert page.total_count == 1

    async def test_include_deleted_opts_out_of_the_filter(self, repo, session):
        gone, _kept = await _create(repo, session, "gone", "kept")
        await repo.delete_by_pk(session, gone.id)

        assert await repo.get_by_pk(session, gone.id, include_deleted=True) is not None
        assert await repo.exists(session, where=SoftDeleteNote.name == "gone", include_deleted=True) is True
        assert len(await repo.get_all(session, include_deleted=True)) == 2

        page = await repo.get_multi(session, ListQueryOptions(include_deleted=True))
        assert len(page.items) == 2
        assert page.total_count == 2

    async def test_get_multi_fallback_count_respects_the_filter(self, repo, session):
        """limit == len(data) forces the COUNT(*) fallback, which must filter too."""
        notes = await _create(repo, session, "a", "b", "c")
        await repo.delete_by_pk_multi(session, [notes[0].id, notes[1].id])

        page = await repo.get_multi(session, ListQueryOptions(limit=1))
        assert page.total_count == 1

        page_all = await repo.get_multi(session, ListQueryOptions(limit=1, include_deleted=True))
        assert page_all.total_count == 3

    async def test_update_on_deleted_row_returns_none(self, repo, session):
        (note,) = await _create(repo, session, "a")
        await repo.delete_by_pk(session, note.id)

        assert await repo.update_by_pk(session, note.id, {"name": "resurrected?"}) is None


# =============================================================================
# Restore & Purge
# =============================================================================


class TestRestoreAndPurge:
    async def test_restore_brings_the_row_back(self, repo, session):
        (note,) = await _create(repo, session, "a")
        await repo.delete_by_pk(session, note.id)

        restored = await repo.restore_by_pk(session, note.id)

        assert restored is not None
        assert not restored.is_deleted
        assert restored.deleted_at is None
        assert await repo.get_by_pk(session, note.id) is not None

    async def test_restore_missing_row_returns_none(self, repo, session):
        assert await repo.restore_by_pk(session, uuid.uuid4()) is None

    async def test_restore_active_row_is_a_noop(self, repo, session):
        (note,) = await _create(repo, session, "a")

        restored = await repo.restore_by_pk(session, note.id)

        assert restored is not None
        assert not restored.is_deleted

    async def test_purge_hard_deletes_only_stamped_rows(self, repo, session):
        gone, kept = await _create(repo, session, "gone", "kept")
        await repo.delete_by_pk(session, gone.id)

        assert await repo.purge_soft_deleted(session) == 1

        assert await repo.get_by_pk(session, gone.id, include_deleted=True) is None
        assert await repo.get_by_pk(session, kept.id) is not None

    async def test_purge_limit_drains_the_backlog_in_batches(self, repo, session):
        notes = await _create(repo, session, "a", "b", "c")
        await repo.delete_by_pk_multi(session, [n.id for n in notes])

        assert await repo.purge_soft_deleted(session, limit=2) == 2
        assert len(await repo.get_all(session, include_deleted=True)) == 1
        assert await repo.purge_soft_deleted(session, limit=2) == 1
        assert await repo.purge_soft_deleted(session, limit=2) == 0

    async def test_purge_limit_combines_with_the_retention_window(self, repo, session):
        old, fresh = await _create(repo, session, "old", "fresh")
        await repo.delete_by_pk_multi(session, [old.id, fresh.id])
        stale_row = await repo.get_by_pk(session, old.id, include_deleted=True)
        assert stale_row is not None
        stale_row.deleted_at = datetime.now(UTC) - timedelta(days=2)
        await session.flush()

        assert await repo.purge_soft_deleted(session, older_than=timedelta(days=1), limit=10) == 1
        assert await repo.get_by_pk(session, fresh.id, include_deleted=True) is not None

    async def test_purge_limit_works_with_a_composite_primary_key(self, session):
        repo = CompositeSoftDeleteRepository()
        tenant = uuid.uuid4()
        for code in ("a", "b", "c"):
            await repo.create(session, CompositeItemCreate(tenant_id=tenant, code=code))
            await repo.delete_by_pk(session, [tenant, code])

        assert await repo.purge_soft_deleted(session, limit=2) == 2
        assert await repo.purge_soft_deleted(session, limit=2) == 1
        assert len(await repo.get_all(session, include_deleted=True)) == 0

    async def test_purge_limit_must_be_positive(self, repo, session):
        with pytest.raises(ValueError, match=r"must be positive"):
            await repo.purge_soft_deleted(session, limit=0)

    async def test_purge_respects_the_retention_window(self, repo, session):
        old, fresh = await _create(repo, session, "old", "fresh")
        await repo.delete_by_pk_multi(session, [old.id, fresh.id])

        stale_row = await repo.get_by_pk(session, old.id, include_deleted=True)
        assert stale_row is not None
        stale_row.deleted_at = datetime.now(UTC) - timedelta(days=2)
        await session.flush()

        assert await repo.purge_soft_deleted(session, older_than=timedelta(days=1)) == 1

        assert await repo.get_by_pk(session, old.id, include_deleted=True) is None
        assert await repo.get_by_pk(session, fresh.id, include_deleted=True) is not None


# =============================================================================
# Service wiring (no service-layer changes required)
# =============================================================================


class TestSoftDeleteThroughService:
    async def test_service_delete_soft_deletes_and_reads_hide_it(self, repo, service, session):
        note = await service.create(session, NoteCreate(name="a"))

        result = await service.delete(session, note.id)

        assert result.success is True
        assert await service.get(session, note.id) is None
        assert (await service.get_multi(session)).items == []
        assert await repo.get_by_pk(session, note.id, include_deleted=True) is not None

    async def test_service_delete_multi_reports_already_deleted_as_failed(self, service, session):
        a = await service.create(session, NoteCreate(name="a"))
        b = await service.create(session, NoteCreate(name="b"))
        await service.delete(session, a.id)

        result = await service.delete_multi(session, [a.id, b.id])

        assert result.deleted_count == 1
        assert result.failed_count == 1
