import asyncio
from threading import Event

import pytest
from app_layer_base.utils.async_util import run_blocking


@pytest.mark.asyncio
async def test_result_keywords_and_original_failure():
    assert await run_blocking(lambda value, *, factor: value * factor, 3, factor=2) == 6
    failure = ValueError("worker failure")

    def fail():
        raise failure

    with pytest.raises(ValueError) as caught:
        await run_blocking(fail)
    assert caught.value is failure


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_repeated_cancellation_drains_before_scope_exit(fail):
    started, release, finished = Event(), Event(), Event()
    exited = False

    def worker():
        try:
            started.set()
            assert release.wait(3)
            if fail:
                raise RuntimeError("late worker failure")
        finally:
            finished.set()

    async def caller():
        nonlocal exited
        try:
            await run_blocking(worker)
        finally:
            exited = True

    task = asyncio.create_task(caller())
    try:
        assert await asyncio.to_thread(started.wait, 1)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
            assert not exited and not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set() and exited
