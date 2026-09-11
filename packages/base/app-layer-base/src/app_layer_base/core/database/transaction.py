from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_layer_base.core.database import engine
from app_layer_base.core.log import logger

AfterCommitCallback = Callable[[], Awaitable[None]]

_AFTER_COMMIT_KEY = "app_layer_base.after_commit_callbacks"


def register_after_commit(session: AsyncSession, callback: AfterCommitCallback) -> None:
    """Queue ``callback`` to run once, after this session's transaction commits.

    This is the seam for side effects that must not happen until the write is
    durable: publishing a domain event, invalidating a cache, sending a
    notification. Registering from inside a service hook keeps those effects off
    the rolled-back path -- a hook that published inline would fire even when the
    surrounding transaction later rolls back (a dual write).

    Semantics -- read these before relying on it:

    - **At-most-once, best-effort.** The callback runs outside the transaction,
      so a failure cannot roll anything back; ``run_after_commit`` logs and
      swallows it. If the effect *must* happen, it is not an after-commit
      callback -- write it into the same transaction (see ``OutboxHook``).
    - **Capture plain data, not ORM objects.** By the time the callback runs the
      transaction is committed and the session is being torn down; a captured
      ``model_dump()``/dict is safe, a live ORM instance is not.
    - **Only the OWNING transaction dispatches.** ``AsyncTransaction`` drains the
      queue after its own commit. A session pulled into a *joined*
      ``AsyncTransaction`` leaves dispatch to whoever owns the outer boundary; a
      session never wrapped by an ``AsyncTransaction`` at all never dispatches --
      a deliberate escape-hatch caveat, not a bug.
    """
    session.info.setdefault(_AFTER_COMMIT_KEY, []).append(callback)


def pending_after_commit(session: AsyncSession) -> list[AfterCommitCallback]:
    """The callbacks queued on ``session`` but not yet dispatched (introspection/tests)."""
    return list(session.info.get(_AFTER_COMMIT_KEY, ()))


async def run_after_commit(session: AsyncSession) -> None:
    """Dispatch and clear the after-commit queue, in registration order.

    Best-effort and at-most-once: a failing callback is logged and the rest still
    run, because the transaction is already committed and there is nothing to undo.
    """
    callbacks = session.info.pop(_AFTER_COMMIT_KEY, None)
    if not callbacks:
        return
    for callback in callbacks:
        try:
            await callback()
        except Exception:
            logger.exception(
                "after-commit callback failed; the transaction is already committed, so this "
                "side effect is lost (at-most-once). Use an outbox if it must not be lost."
            )


class AsyncTransaction:
    """Async context manager owning one SQLAlchemy session and its transaction.

    Owning mode (the default): opens an ``AsyncSession``, yields it, commits on a
    clean exit or rolls back on error, then always closes. After a successful
    commit it dispatches the callbacks queued via ``register_after_commit``.

    Example:

        async with AsyncTransaction() as session:
            await session.execute(...)

    Joined mode (escape hatch -- pass ``session=``): participates in a transaction
    someone else owns. It yields that session and does NOTHING on exit -- no
    commit, no rollback, no close, no after-commit dispatch -- so the whole
    boundary stays with the owner. It exists for the rare, deliberate case where
    code that opens its own ``AsyncTransaction`` (e.g. a prebuilt use case) has to
    be pulled into an outer transaction without refactoring it first. Prefer the
    sanctioned path -- one transaction calling several services -- which never
    needs this; reach for joined mode only when the dependency-tangling risk is
    low or the refactor is imminent.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Initialize an AsyncTransaction.

        Args:
            session_maker: Optional ``async_sessionmaker`` for owning mode. Defaults
                to ``app_layer_base.core.database.engine.get_session_maker()``.
            session: Optional existing session to JOIN instead of owning. When given,
                this transaction never commits, rolls back, or closes -- the owner
                does. See the class docstring; this is a discouraged escape hatch.
        """
        self._external_session = session
        self._owns_session = session is None
        self._session_maker = session_maker
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        """Return the joined session, or create and return a new one."""
        if self._external_session is not None:
            self._session = self._external_session
            return self._session

        session_maker = self._session_maker or engine.get_session_maker()
        self._session = session_maker()
        if self._session is None:
            raise RuntimeError("Failed to create AsyncSession")
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Owning mode: commit (then dispatch after-commit) or roll back, then close.

        Joined mode: do nothing -- the owner of the outer transaction handles the
        commit/rollback, the close, and the after-commit dispatch.
        """
        if self._session is None or not self._owns_session:
            return

        try:
            if exc_type is None:
                await self._session.commit()
                await run_after_commit(self._session)
            else:
                await self._session.rollback()
                # Leave no queued callbacks behind on a rolled-back transaction. In
                # owning mode the fresh session is dropped right after, so this is
                # belt-and-suspenders -- but it keeps the "any exit leaves the session
                # clean" invariant explicit and holds if a session is ever reused.
                self._session.info.pop(_AFTER_COMMIT_KEY, None)
        finally:
            await self._session.close()
