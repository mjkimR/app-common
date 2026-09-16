# Non-CRUD command features

Use this path for operations that coordinate domain repositories under a caller-owned
transaction. It is a supported alternative to CRUD services/hooks. A consistent feature
shape helps agents place changes correctly, lets checks catch drift, and gives reviewers
a familiar structure even where there is little duplicated code to remove.

## Feature shape

```text
features/<feature>/
  commands.py  # public async entry points: context + input DTO -> output DTO
  schemas.py   # feature input/output DTOs
  usecases.py  # complex orchestration, when needed
```

Keep existing shared domain DTOs in their owning module; do not duplicate a model just
to put it in schemas.py. A small operation can live directly in commands.py. Move complex
or reusable domain orchestration into usecases.py; it uses the same caller's context.
Private local helpers are allowed. Do not add public utility functions, classes, decorators,
variadic arguments or implicit/default inputs to commands.py. Empty requests use an empty DTO.

```python
# features/documents/commands.py
from my_app.context import Ctx
from my_app.features.documents.schemas import RenameIn, RenameResult


async def rename(ctx: Ctx, inp: RenameIn) -> RenameResult:
    document = await ctx.tx.documents.rename(inp.id, inp.title)
    ctx.invalidate()
    return RenameResult(id=document.id, title=document.title)
```

Commands do not depend on HTTP, CLI, MCP or SQL implementation types. They use the
repository bundle supplied by the context. They never commit, roll back or open a
transaction. Register each public operation once in the application/transport registry;
transport-specific metadata can extend the frozen `Command` dataclass.

## Execution ownership

```python
from contextlib import asynccontextmanager

from app_layer_base.application import Command, execute_command

rename_command = Command("document.rename", rename, RenameIn, RenameResult)


@asynccontextmanager
async def scope():
    async with ctx.transaction(write=True):
        # Application-owned authorization/preflight belongs here.
        yield ctx


result = await execute_command(rename_command, payload, scope=scope())
```

`execute_command` rejects the wrong input type before scope entry and the wrong output
type before scope exit/commit. It does not coerce data, retry or translate exceptions.
The scope yields the application context and must propagate errors. Dataclass and Pydantic
DTOs both work; HTTP decoding and error envelopes remain transport/application concerns.

An operation that waits or polls may need several short transactions. Its application
scope can complete preflight before yielding a context without an active transaction;
a dedicated usecase then owns each short transaction. Keep this policy explicit at
registration/execution and test it. Do not hold write locks while waiting or silently
open a second transaction from an ordinary command.

## Transaction context

Compose `TransactionScope(store.tx, on_exit=reset_cached_views)` into your context and
delegate `tx`, `in_tx` and `transaction(write=False)` to it. The factory accepts `write`
as a keyword and returns an async context manager yielding the domain repository bundle.
The factory owns commit/rollback/close; the scope owns participation and state cleanup.

- Nested calls reuse the same resource in the same asyncio task. They do not create
  savepoints, commit or dispatch after-commit callbacks.
- `write=True` requests the application's stronger locking policy. `write=False` does
  **not** promise database read-only mode; bookkeeping may still write.
- A nested write request inside a non-write outer scope raises `TransactionScopeError`.
  Select the stronger policy at the outer boundary; do not attempt an implicit upgrade.
- Concurrent tasks need separate contexts. A cross-task join/access fails explicitly.
- Errors propagate. An owner that catches a nested failure chooses whether to continue;
  there is no implicit rollback-only flag.
- Exit, including failed entry/commit and cancellation, clears the active resource and
  calls the non-raising `on_exit` reset once. Mid-transaction cache invalidation after a
  domain mutation still belongs to the application.

The application modules do not import database/transport implementations or initialize
settings/loggers. Existing `AsyncTransaction` can implement the factory's SQL lifecycle;
see [session ownership](session.md). The package's installed dependencies are unchanged.

## Enforce the convention

```toml
[[tool.app-tools.architecture.commands]]
source = "my_app.features"

[[tool.app-tools.architecture.boundaries]]
name = "features depend on domain contracts"
source = "my_app.features"
forbidden_imports = ["my_app.server", "my_app.application", "fastapi", "sqlalchemy", "app_layer_base.core.database", "app_layer_base.base"]
```

Run `app-tools check-arch src` in normal lint/CI. Command rules are opt-in and apply only
to `commands.py` below the configured module prefix, in src or flat layouts:

- `ARCH_COMMAND_SIGNATURE`: public entry points must be undecorated async functions with
  exactly two required positional, annotated arguments and a concrete return annotation.
- `ARCH_COMMAND_TRANSACTION`: calls named `.commit()`, `.rollback()`, `.begin()`,
  `.begin_nested()`, `.transaction()` or `.tx()` are forbidden in command modules,
  including private helpers. Move deliberate short-transaction work into a usecase.

These are AST conventions, not a type checker or interprocedural proof. Aliases, dynamic
code and behavior in called usecases require type checks, tests and review. Reuse the
existing explicit suppression syntax with a reason for a justified naming collision;
prefer fixing misplaced work. Invalid configuration fails with `ARCH_CONFIG_ERROR`.

Registry tests complement lint without invoking handlers:

```python
from app_testing_base.application import assert_command_contracts, assert_transaction_scope_contract


def test_commands():
    assert_command_contracts(COMMANDS, context=Ctx, feature_package="my_app.features")


async def test_context(store):
    await assert_transaction_scope_contract(Ctx(store))
```

The registry check verifies unique names, feature commands.py ownership, exact function
shape and matching context/input/output annotations. The scope helper uses the consumer's
fixture to verify nesting, upgrade rejection, failure propagation and reuse. Keep real
backend tests for durability, rollback, locking, callbacks and application preflight order.

For a new feature, add DTOs and command, register it, add behavior tests, then run architecture,
registry and relevant backend tests. Avoid making a new execution framework per feature.
