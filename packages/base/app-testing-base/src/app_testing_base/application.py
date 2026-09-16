"""Opt-in contracts for non-CRUD consumers with application-owned fixtures."""

import inspect
from collections.abc import Iterable
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, get_type_hints

import pytest
from app_layer_base.application import Command, TransactionScopeError


def assert_command_contracts(
    commands: Iterable[Command[Any, Any, Any]], *, context: type, feature_package: str
) -> None:
    """Check registry uniqueness, feature ownership and exact DTO annotations.

    Public entry points live in feature ``commands.py`` modules and use the
    shape ``async def operation(ctx: Context, inp: Input) -> Output``. Names of
    parameters are immaterial. No defaults, variadics, or keyword-only inputs.
    This inspects trusted application code; it does not execute handlers.
    """
    names: set[str] = set()
    for command in commands:
        assert isinstance(command, Command), f"{command!r} must use the shared Command registration"
        label = f"Command {command.name!r}"
        assert command.name and command.name not in names, f"{label}: name must be nonempty and unique"
        names.add(command.name)
        handler = command.handler
        assert inspect.iscoroutinefunction(handler), f"{label}: handler must be an async function"
        assert handler.__module__.startswith(feature_package + ".") and handler.__module__.endswith(".commands"), (
            f"{label}: handler must belong to {feature_package}.<feature>.commands"
        )
        assert not handler.__name__.startswith("_"), f"{label}: handler must be public"
        parameters = list(inspect.signature(handler).parameters.values())
        assert len(parameters) == 2 and all(
            p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            and p.default is inspect.Parameter.empty
            for p in parameters
        ), f"{label}: handler must take exactly context and input, without defaults"
        annotations = get_type_hints(handler)
        expected = (context, command.inp, command.out)
        assert all(isinstance(t, type) and t is not Any for t in expected), (
            f"{label}: use concrete context and DTO types"
        )
        actual = (annotations.get(parameters[0].name), annotations.get(parameters[1].name), annotations.get("return"))
        assert actual == expected, f"{label}: handler annotations {actual!r} do not match registry {expected!r}"


class TransactionContext[TxT](Protocol):
    @property
    def tx(self) -> TxT: ...

    @property
    def in_tx(self) -> bool: ...

    def transaction(self, write: bool = False) -> AbstractAsyncContextManager[TxT]: ...


async def assert_transaction_scope_contract(context: TransactionContext[Any]) -> None:
    """Exercise a fresh context's joining, upgrade rejection and failure cleanup.

    Supply a disposable context from the consumer's own store fixture. This
    opens real scopes but writes no domain data. Keep backend-specific tests for
    durable commits, rollback, locks and after-commit callbacks in the consumer.
    """
    assert not context.in_tx
    with pytest.raises(TransactionScopeError):
        _ = context.tx
    async with context.transaction() as outer:
        assert context.in_tx and context.tx is outer
        async with context.transaction() as inner:
            assert inner is outer
        with pytest.raises(TransactionScopeError, match="upgrade"):
            async with context.transaction(write=True):
                pytest.fail("A non-write outer scope must reject a nested write")
        assert context.tx is outer
    assert not context.in_tx

    failure = ValueError("transaction contract failure")
    with pytest.raises(ValueError) as caught:
        async with context.transaction(write=True) as outer:
            async with context.transaction(write=True) as inner:
                assert inner is outer
                raise failure
    assert caught.value is failure
    assert not context.in_tx
    with pytest.raises(TransactionScopeError):
        _ = context.tx
    async with context.transaction(write=True) as outer, context.transaction() as inner:
        assert inner is outer
    assert not context.in_tx
