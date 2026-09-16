"""Single-task transaction participation over an application-owned resource."""

from asyncio import Task, current_task
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol


class TransactionFactory[TxT](Protocol):
    def __call__(self, *, write: bool = False) -> AbstractAsyncContextManager[TxT]: ...


class TransactionScopeError(RuntimeError):
    """The caller violated transaction ownership or requested an unsafe upgrade."""


class TransactionScope[TxT]:
    """Join the current transaction or open one via the supplied factory.

    ``write`` requests the application's stronger write/locking policy; false
    does not imply a SQL read-only transaction. A nested write cannot upgrade
    an outer non-write scope. Choose the stronger policy at the outer boundary.

    Nested failures propagate without savepoints or rollback-only marking. If an
    owner catches a failure, it explicitly chooses whether to continue/commit.
    Concurrent tasks must use separate scopes. Only the outer factory commits,
    rolls back, closes, and dispatches callbacks. on_exit runs once after that
    boundary exits (also on failure) and must be a non-raising state reset.
    """

    def __init__(self, factory: TransactionFactory[TxT], *, on_exit: Callable[[], None] | None = None) -> None:
        self._factory = factory
        self._on_exit = on_exit
        self._tx: TxT | None = None
        self._write = False
        self._owner: Task[object] | None = None

    @property
    def tx(self) -> TxT:
        if self._tx is None:
            raise TransactionScopeError("No transaction is open; use async with context.transaction()")
        self._check_owner()
        return self._tx

    @property
    def in_tx(self) -> bool:
        return self._tx is not None

    def _check_owner(self) -> None:
        if self._owner is not None and self._owner is not current_task():
            raise TransactionScopeError("A transaction scope cannot be shared across concurrent tasks")

    @asynccontextmanager
    async def transaction(self, write: bool = False) -> AsyncIterator[TxT]:
        self._check_owner()
        if self._tx is not None:
            if write and not self._write:
                raise TransactionScopeError(
                    "Cannot upgrade a nested transaction to write; open the outer scope with write=True"
                )
            yield self._tx
            return
        if self._owner is not None:
            raise TransactionScopeError("Transaction scope is entering or exiting")
        self._owner = current_task()
        self._write = write
        try:
            async with self._factory(write=write) as tx:
                self._tx = tx
                try:
                    yield tx
                finally:
                    # Access is invalid while commit/rollback/close is in progress.
                    self._tx = None
        finally:
            self._tx = None
            self._write = False
            self._owner = None
            if self._on_exit is not None:
                self._on_exit()
