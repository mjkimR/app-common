"""One command shape for function-based application features."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

type CommandHandler[ContextT, InputT, OutputT] = Callable[[ContextT, InputT], Awaitable[OutputT]]


@dataclass(frozen=True)
class Command[ContextT, InputT, OutputT]:
    """Transport-neutral registration; applications may extend it with their policies.

    Inputs and outputs are concrete DTO classes (dataclasses and Pydantic models
    both work). A handler is an async function taking exactly context and input.
    Validate the registry with app-testing-base's assert_command_contracts.
    """

    name: str
    handler: CommandHandler[ContextT, InputT, OutputT]
    inp: type[InputT]
    out: type[OutputT]


async def execute_command[ContextT, InputT, OutputT](
    command: Command[ContextT, InputT, OutputT],
    inp: InputT,
    *,
    scope: AbstractAsyncContextManager[ContextT],
) -> OutputT:
    """Run a typed command inside an application-provided scope.

    Input type errors precede scope entry. Output type errors propagate through
    scope exit, allowing the owning transaction to roll back before committing.
    No coercion, exception translation, retries, or implicit transaction occurs.
    The supplied scope must propagate errors and own its cleanup.
    """
    if not isinstance(inp, command.inp):
        raise TypeError(f"Command {command.name!r} requires input {command.inp.__name__}")
    async with scope as ctx:
        result = await command.handler(ctx, inp)
        if not isinstance(result, command.out):
            raise TypeError(f"Command {command.name!r} requires output {command.out.__name__}")
        return result
    raise RuntimeError("Command scope suppressed an exception")
