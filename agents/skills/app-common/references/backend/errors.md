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
- `Actor.USER`: Human user provided invalid input or lacks permission (fix user input).
- `Actor.AGENT`: AI agent can autonomously fix the error (e.g. invalid parameter format, missing file).
- `Actor.DEV`: System bug, schema mismatch, or configuration error requiring developer fix.
- `Actor.NONE`: No action required / informational.

### 2. `Retry` (Is it safe to retry?)
- `Retry.SAFE`: Operation is idempotent; safe to retry immediately or after backoff.
- `Retry.UNSAFE`: Retrying without changes will fail again or cause duplicate mutations.

### 3. `ActionMode` (Directive for agents)
Derived automatically from `actor` and `retry`:
- `ActionMode.AGENT_FIX`: Agent can modify code or arguments and retry.
- `ActionMode.ASK_USER`: Agent must prompt the user for clarification.
- `ActionMode.REPORT_BLOCKER`: Agent must stop and report an unrecoverable failure.

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
