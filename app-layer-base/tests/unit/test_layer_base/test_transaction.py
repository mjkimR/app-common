"""Unit tests for AsyncTransaction and the after-commit seam."""

from unittest.mock import AsyncMock

import pytest
from app_layer_base.core.database.transaction import (
    AsyncTransaction,
    pending_after_commit,
    register_after_commit,
    run_after_commit,
)


def _fake_session() -> AsyncMock:
    """A session stand-in with a real ``.info`` dict and awaitable lifecycle methods."""
    session = AsyncMock()
    session.info = {}
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


# =============================================================================
# register / run / pending
# =============================================================================


class TestAfterCommitQueue:
    async def test_callbacks_run_in_registration_order_then_clear(self):
        session = _fake_session()
        calls: list[str] = []

        register_after_commit(session, lambda: _record(calls, "a"))
        register_after_commit(session, lambda: _record(calls, "b"))
        assert len(pending_after_commit(session)) == 2

        await run_after_commit(session)

        assert calls == ["a", "b"]
        assert pending_after_commit(session) == []

    async def test_run_on_empty_queue_is_a_noop(self):
        session = _fake_session()
        await run_after_commit(session)  # must not raise

    async def test_a_failing_callback_is_swallowed_and_the_rest_still_run(self):
        session = _fake_session()
        calls: list[str] = []

        async def boom():
            raise RuntimeError("publish failed")

        register_after_commit(session, boom)
        register_after_commit(session, lambda: _record(calls, "after"))

        await run_after_commit(session)  # at-most-once, best-effort: no raise

        assert calls == ["after"], "a failing callback must not stop the others"


async def _record(sink: list[str], value: str) -> None:
    sink.append(value)


# =============================================================================
# AsyncTransaction: owning mode
# =============================================================================


class TestOwningTransaction:
    async def test_commit_then_dispatch_then_close_on_clean_exit(self):
        session = _fake_session()
        fired: list[str] = []

        async with AsyncTransaction(session_maker=lambda: session) as s:
            assert s is session
            register_after_commit(session, lambda: _record(fired, "published"))

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        session.close.assert_awaited_once()
        assert fired == ["published"], "after-commit callback must fire after a successful commit"

    async def test_rollback_and_no_dispatch_on_error(self):
        session = _fake_session()
        fired: list[str] = []

        with pytest.raises(ValueError):
            async with AsyncTransaction(session_maker=lambda: session):
                register_after_commit(session, lambda: _record(fired, "published"))
                raise ValueError("boom")

        session.commit.assert_not_awaited()
        session.rollback.assert_awaited_once()
        session.close.assert_awaited_once()
        assert fired == [], "a rolled-back transaction must not publish its events"
        assert pending_after_commit(session) == [], "rollback must leave no queued callbacks behind"


# =============================================================================
# AsyncTransaction: joined mode (escape hatch)
# =============================================================================


class TestJoinedTransaction:
    async def test_yields_the_injected_session(self):
        external = _fake_session()

        async with AsyncTransaction(session=external) as s:
            assert s is external

    async def test_does_not_commit_rollback_close_or_dispatch(self):
        external = _fake_session()
        fired: list[str] = []

        async with AsyncTransaction(session=external):
            register_after_commit(external, lambda: _record(fired, "published"))

        # The owner of the outer transaction handles all of this, not the joined one.
        external.commit.assert_not_awaited()
        external.rollback.assert_not_awaited()
        external.close.assert_not_awaited()
        assert fired == [], "joined mode must leave after-commit dispatch to the owner"
        assert len(pending_after_commit(external)) == 1, "the callback stays queued for the owner"

    async def test_does_not_swallow_errors(self):
        external = _fake_session()

        with pytest.raises(ValueError):
            async with AsyncTransaction(session=external):
                raise ValueError("boom")

        # Still no lifecycle calls -- the exception propagates to the owner untouched.
        external.rollback.assert_not_awaited()
        external.close.assert_not_awaited()


# =============================================================================
# A session maker that returns a MagicMock (not None) still works
# =============================================================================


async def test_default_session_maker_is_used_when_none_passed(monkeypatch):
    session = _fake_session()
    from app_layer_base.core.database import engine as engine_mod

    monkeypatch.setattr(engine_mod, "get_session_maker", lambda: (lambda: session))

    async with AsyncTransaction() as s:
        assert s is session

    session.commit.assert_awaited_once()
