from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from app_layer_base.application import Command, TransactionScope
from app_testing_base.application import assert_command_contracts, assert_transaction_scope_contract


@dataclass
class Input:
    value: int


@dataclass
class Output:
    value: int


async def handler(ctx: object, inp: Input) -> Output:
    return Output(inp.value)


handler.__module__ = "consumer.features.example.commands"


def test_registry_contract():
    assert_command_contracts(
        [Command("example", handler, Input, Output)], context=object, feature_package="consumer.features"
    )


@pytest.mark.parametrize(
    "problem", ["duplicate", "input", "output", "context", "module", "sync", "signature", "annotation"]
)
def test_registry_contract_rejects_drift(problem):
    async def candidate(ctx: object, inp: Input) -> Output:
        return Output(inp.value)

    candidate.__module__ = handler.__module__
    if problem == "sync":

        def candidate(ctx: object, inp: Input) -> Output:
            return Output(inp.value)

        candidate.__module__ = handler.__module__
    if problem == "signature":

        async def candidate(ctx: object, inp: Input, extra=None) -> Output:
            return Output(inp.value)

        candidate.__module__ = handler.__module__
    if problem == "annotation":
        candidate.__annotations__ = {}
    if problem == "module":
        candidate.__module__ = "consumer.features_extra.example.commands"
    commands = [
        Command("example", candidate, Output if problem == "input" else Input, Input if problem == "output" else Output)
    ]
    if problem == "duplicate":
        commands *= 2
    with pytest.raises(AssertionError):
        assert_command_contracts(
            commands, context=str if problem == "context" else object, feature_package="consumer.features"
        )


async def test_scope_contract_uses_application_factory():
    events = []

    @asynccontextmanager
    async def factory(*, write=False):
        try:
            yield object()
            events.append("commit")
        except ValueError:
            events.append("rollback")
            raise

    await assert_transaction_scope_contract(TransactionScope(factory))
    assert events == ["commit", "rollback", "commit"]
