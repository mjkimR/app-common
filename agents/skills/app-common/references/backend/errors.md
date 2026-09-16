# Structured Error Protocol & Agent Advisory (`app-error`)

`app-error` provides structured exception classes and advisory metadata indicating who should act, whether retrying is safe, and how to fix the issue.

## Raising `AppError`

Raise structured exceptions inheriting from `AppError` rather than generic `ValueError` or raw `HTTPException`:

```python
from app_error import AppError, Actor, Retry


class ResourceNotFoundError(AppError):
    code = "RESOURCE_NOT_FOUND"
    actor = Actor.USER
    retry = Retry.UNSAFE


raise ResourceNotFoundError(
    "Book with id 42 does not exist",
    code="BOOK_NOT_FOUND",
    actor=Actor.USER,
    retry=Retry.UNSAFE,
    fix="Verify the book ID from the listing endpoint.",
    what_to_report="The requested book ID does not exist in the database.",
)
```

---

## Advisory Fields & Types

### 1. `Actor` (Who should take action?)
- `Actor.TOOL`: The calling agent/tool can correct its input or apply the supplied fix.
- `Actor.USER`: A person must decide or provide missing configuration.
- `Actor.DEVELOPER`: The application's code needs repair.
- `Actor.NONE`: Nobody can act now.

### 2. `Retry` (Is it safe to retry?)
- `Retry.SAFE`: Retrying the unchanged operation is safe.
- `Retry.AFTER_FIX`: Apply the fix before retrying.
- `Retry.UNSAFE`: Retrying risks duplicate or partially completed work.

### 3. `ActionMode` (Directive for agents)
`Advisory.mode` derives the directive in priority order: a guardrail yields
`BLOCKED`; a developer-owned failure yields `MAINTENANCE`; an unsafe retry yields
`HALT`; tool/user ownership yields `AUTO`/`INTERACTION`; remaining cases yield
`DEFER` for safe retries and `HALT` otherwise. These are the enum member names.

### 4. Remediation Properties
- `fix`: Direct, actionable string instruction for how to fix the issue.
- `what_to_report`: Summarized explanation suitable for user-facing output.
- `target_files`: List of file paths related to the error.
- `retry_after`: Suggested wait time before retrying.

---

## Rendering & Serialization

```python
error = BookNotFoundError(...)

# Formatted lines for CLI stderr
lines: list[str] = error.lines()

# Formatted block for Model Context Protocol (MCP) tool results
mcp_text: str = error.render_mcp()

# Dictionary serialization for API JSON responses
payload: dict = error.to_dict(include_advisory=True)
```

## Domain-specific contracts

Subclass `AppError` to retain application error codes and class defaults. Its
initializer, advisory fields, mode derivation, and serialization are shared.
An application may subclass `Advisory` for an existing CLI presentation and return
that subtype from its error's `advisory` property; keep its wording at the application
boundary instead of copying the enums or retry/actor decision logic.
