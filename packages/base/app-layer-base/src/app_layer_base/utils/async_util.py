"""Drain blocking work before cancellation releases its caller's resources."""

import asyncio
from collections.abc import Callable


async def run_blocking[**P, R](function: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """Run in a thread, retaining ownership until it finishes, even on repeated cancel.

    Cancellation cannot stop a Python worker thread. Propagate it only after the
    worker finishes, retrieving any worker exception. Callers must bound external
    operations with their own I/O timeouts; this helper does not terminate them.
    """
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            cancelled = error
        except BaseException:
            break
    if cancelled is not None:
        if not task.cancelled():
            task.exception()
        raise cancelled
    return task.result()
