"""Keep embedded Qdrant's synchronous storage on one owner thread.

The native async facade does not offload local operations. Dispatch its local
backend (including nested native calls) to a serial executor; remote clients are
untouched. The backend stays an AsyncQdrantLocal for native local-mode checks.
"""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from qdrant_client.local.async_qdrant_local import AsyncQdrantLocal


async def drain[T](future: asyncio.Future[T]) -> T:
    """Finish submitted work, preserving cancellation even if that work fails."""
    cancelled: asyncio.CancelledError | None = None
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError as exc:
            cancelled = exc
        except BaseException:
            break
    if cancelled is not None:
        # Retrieve the exception to avoid an unobserved-future warning.
        if not future.cancelled():
            future.exception()
        raise cancelled
    return future.result()


def _run[T](method: Callable[..., Awaitable[T]], args: tuple[Any, ...], kwargs: dict[str, Any]) -> T:
    async def invoke() -> T:
        return await method(*args, **kwargs)

    return asyncio.run(invoke())


class ThreadedLocal(AsyncQdrantLocal):
    """Internal dispatch facade; the native backend is only used in its owner thread."""

    def __init__(self, native: AsyncQdrantLocal, executor: ThreadPoolExecutor) -> None:
        # Do not initialize a second storage owner. All native public members are
        # delegated; private dispatch members below belong to this facade only.
        self._native = native
        self._executor = executor
        self._closing = False

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_") or name == "close":
            return object.__getattribute__(self, name)
        member = getattr(self._native, name)
        return partial(self._dispatch, member) if inspect.iscoroutinefunction(member) else member

    async def _dispatch[T](self, method: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        if self._closing:
            raise RuntimeError("Local Qdrant client is closing")
        future = asyncio.get_running_loop().run_in_executor(self._executor, partial(_run, method, args, kwargs))
        return await drain(future)

    async def close(self, **kwargs: Any) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            future = asyncio.get_running_loop().run_in_executor(
                self._executor, partial(_run, self._native.close, (), kwargs)
            )
            await drain(future)
        finally:
            # All previously queued operations and close have drained in FIFO order.
            self._executor.shutdown(wait=True)
