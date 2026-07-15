"""
Integration tests for AsyncTransaction against a real database session.

The unit tests cover the dispatch logic with fake sessions; these prove the two
assumptions that only a live SQLAlchemy session can: that ``AsyncSession.info``
is a usable per-transaction dict, and that a real commit (or savepoint release)
triggers the after-commit dispatch. The ``session`` fixture is requested only for
its side effect -- it patches the engine accessors so ``AsyncTransaction()`` binds
to the test database.
"""

import pytest
from app_layer_base.core.database.transaction import (
    AsyncTransaction,
    pending_after_commit,
    register_after_commit,
)


async def test_after_commit_dispatches_after_a_real_commit(session):
    fired: list[str] = []

    async with AsyncTransaction() as s:
        register_after_commit(s, lambda: _append(fired, "published"))
        assert fired == [], "must not publish before the block commits"

    assert fired == ["published"]


async def test_after_commit_is_skipped_on_rollback(session):
    fired: list[str] = []

    with pytest.raises(ValueError):
        async with AsyncTransaction() as s:
            register_after_commit(s, lambda: _append(fired, "published"))
            raise ValueError("boom")

    assert fired == [], "a rolled-back transaction must not publish"


async def test_joined_transaction_defers_dispatch_to_the_owner(session):
    """A joined AsyncTransaction is a pass-through; the outer owner commits and dispatches."""
    fired: list[str] = []

    async with AsyncTransaction() as outer:
        async with AsyncTransaction(session=outer) as inner:
            assert inner is outer, "joined mode must reuse the very same session"
            register_after_commit(inner, lambda: _append(fired, "published"))

        # The joined inner exited without committing, closing, or dispatching.
        assert fired == []
        assert len(pending_after_commit(outer)) == 1
        assert outer.is_active, "the outer session stays usable after the joined block"

    assert fired == ["published"], "the owner's commit dispatched the queued callback"


async def _append(sink: list[str], value: str) -> None:
    sink.append(value)
