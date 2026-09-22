"""The non-CRUD execution contract must hold without a database or transport."""

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

import pytest
from app_layer_base.application import Command, TransactionScope, TransactionScopeError, execute_command


@dataclass
class Input:
    value: int


@dataclass
class Output:
    value: int


class Resource:
    def __init__(self, *, fail_enter=False, fail_commit=False):
        self.events = []
        self.fail_enter = fail_enter
        self.fail_commit = fail_commit

    @asynccontextmanager
    async def transaction(self, *, write=False):
        self.events.append(("open", write))
        try:
            if self.fail_enter:
                raise ValueError("enter failure")
            yield object()
            if self.fail_commit:
                raise ValueError("commit failure")
            self.events.append("commit")
        except BaseException:
            self.events.append("rollback")
            raise
        finally:
            self.events.append("close")


async def test_nested_scopes_have_one_owner_and_one_reset():
    resource = Resource()
    scope = TransactionScope(resource.transaction, on_exit=lambda: resource.events.append("reset"))
    async with scope.transaction(write=True) as outer:
        async with scope.transaction(write=True) as inner:
            assert inner is outer and scope.tx is outer
        assert resource.events == [("open", True)]
    assert resource.events == [("open", True), "commit", "close", "reset"]
    assert not scope.in_tx


async def test_upgrade_rejected_before_work_without_poisoning_owner():
    resource = Resource()
    scope = TransactionScope(resource.transaction)
    async with scope.transaction() as outer:
        with pytest.raises(TransactionScopeError, match="upgrade"):
            async with scope.transaction(write=True):
                pytest.fail("unsafe upgrade")
        assert scope.tx is outer
    assert resource.events == [("open", False), "commit", "close"]


@pytest.mark.parametrize("failure", ["enter", "body", "commit", "cancel"])
async def test_failure_clears_scope_and_allows_reuse(failure):
    resource = Resource(fail_enter=failure == "enter", fail_commit=failure == "commit")
    scope = TransactionScope(resource.transaction, on_exit=lambda: resource.events.append("reset"))
    expected = asyncio.CancelledError if failure == "cancel" else ValueError
    with pytest.raises(expected):
        async with scope.transaction():
            async with scope.transaction():
                if failure == "body":
                    raise ValueError("body failure")
                if failure == "cancel":
                    raise asyncio.CancelledError
    assert resource.events == [("open", False), "rollback", "close", "reset"]
    assert not scope.in_tx
    with pytest.raises(TransactionScopeError):
        _ = scope.tx
    resource.fail_enter = resource.fail_commit = False
    async with scope.transaction():
        assert scope.in_tx
    assert resource.events[-3:] == ["commit", "close", "reset"]


async def test_caught_inner_error_leaves_commit_decision_to_owner():
    resource = Resource()
    scope = TransactionScope(resource.transaction)
    async with scope.transaction():
        with pytest.raises(ValueError):
            async with scope.transaction():
                raise ValueError("handled")
    assert resource.events == [("open", False), "commit", "close"]


async def test_concurrent_task_cannot_join_or_access_current_transaction():
    resource = Resource()
    scope = TransactionScope(resource.transaction)

    async def other():
        with pytest.raises(TransactionScopeError, match="concurrent"):
            _ = scope.tx
        with pytest.raises(TransactionScopeError, match="concurrent"):
            async with scope.transaction():
                pytest.fail("cross-task join")

    async with scope.transaction() as outer:
        await asyncio.create_task(other())
        assert scope.tx is outer
    assert resource.events == [("open", False), "commit", "close"]


async def test_concurrent_task_rejected_while_factory_is_entering():
    entered, release = asyncio.Event(), asyncio.Event()

    @asynccontextmanager
    async def factory(*, write=False):
        entered.set()
        await release.wait()
        yield object()

    scope = TransactionScope(factory)

    async def owner():
        async with scope.transaction():
            pass

    task = asyncio.create_task(owner())
    await entered.wait()
    try:
        with pytest.raises(TransactionScopeError, match="concurrent"):
            async with scope.transaction():
                pytest.fail("second factory entry")
    finally:
        release.set()
        await task


async def test_command_result_checked_before_commit_and_input_before_entry():
    resource = Resource()

    async def correct(ctx: object, inp: Input) -> Output:
        resource.events.append("handler")
        return Output(inp.value)

    command = Command("sample", correct, Input, Output)
    assert await execute_command(command, Input(2), scope=resource.transaction()) == Output(2)
    assert resource.events == [("open", False), "handler", "commit", "close"]
    resource.events.clear()
    with pytest.raises(TypeError, match="input"):
        await execute_command(command, {}, scope=resource.transaction())
    assert resource.events == []

    async def wrong(ctx, inp):
        return {"value": inp.value}

    with pytest.raises(TypeError, match="output"):
        await execute_command(Command("wrong", wrong, Input, Output), Input(2), scope=resource.transaction())
    assert resource.events == [("open", False), "rollback", "close"]


async def test_command_failure_identity_propagates_and_commit_failure_is_not_hidden():
    resource = Resource()
    error = ValueError("domain failure")

    async def fail(ctx, inp):
        raise error

    with pytest.raises(ValueError) as caught:
        await execute_command(Command("fail", fail, Input, Output), Input(1), scope=resource.transaction())
    assert caught.value is error
    assert resource.events == [("open", False), "rollback", "close"]

    async def success(ctx, inp):
        return Output(1)

    resource.fail_commit = True
    with pytest.raises(ValueError, match="commit failure"):
        await execute_command(Command("success", success, Input, Output), Input(1), scope=resource.transaction())


async def test_suppressing_scope_cannot_turn_failure_into_success():
    @asynccontextmanager
    async def broken_scope():
        with suppress(ValueError):
            yield object()

    async def fail(ctx, inp):
        raise ValueError("failure")

    with pytest.raises(RuntimeError, match="suppressed"):
        await execute_command(Command("fail", fail, Input, Output), Input(1), scope=broken_scope())
