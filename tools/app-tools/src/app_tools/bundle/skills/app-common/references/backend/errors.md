# Structured Errors and Agent Advisories (`devkit.advisory`)

app-common errors are `devkit.advisory.AdvisoryError` subclasses: each carries a stable
code and advisory fields saying who acts next, whether a retry is safe, and how to fix
it. `devkit` is a dependency of every app-common package that raises errors, so the
module is always installed with them. The protocol itself (fields, modes, the
`[ACTION]` texts) is specified by devkit's `advisory` guide; this page covers its use
in applications.

## Raising errors

Raise a subclass with a stable `UPPER_SNAKE` code rather than a generic `ValueError` or a
raw `HTTPException`:

```python
from devkit.advisory import Actor, AdvisoryError, Retry


class BookNotFoundError(AdvisoryError):
    code = "BOOK_NOT_FOUND"
    actor = Actor.USER
    retry = Retry.AFTER_FIX


raise BookNotFoundError(
    "Book with id 42 does not exist.",
    "Listed books: GET /api/v1/books",  # positional arguments after the message are [DETAIL] lines
    fix="Verify the book ID from the listing endpoint.",
    what_to_report="The requested book ID does not exist.",
)
```

In an app-layer-base application, HTTP errors subclass `CustomException`
(`app_layer_base.base.exceptions.base`), an `AdvisoryError` that adds `status_code`,
`title` and `log_message`; its `details=` keyword becomes the detail lines.

## Advisory fields

- `actor`: `TOOL` (the calling agent can run the fix), `USER` (a person decides),
  `DEVELOPER` (the code needs repair), `NONE` (nobody can act now).
- `retry`: `SAFE`, `AFTER_FIX` or `UNSAFE` (duplicate or half-done work).
- `guardrail=True`: a deliberate refusal (`BLOCKED`).
- `input_error=True`: malformed input the caller corrects before retrying (`INPUT_ERROR`).
- `fix`, `what_to_report`, `target_files`, `retry_after`: the remediation shown to the agent.

`error.mode` derives the directive (`AUTO`, `INTERACTION`, `DEFER`, `BLOCKED`, `HALT`,
`MAINTENANCE`, `INPUT_ERROR`). An `AUTO` error (actor `TOOL`, retry not `UNSAFE`) must
carry a `fix`; constructing one without it raises `ValueError`. The factories
`AdvisoryError.invalid_input`, `.blocked`, `.auto_fix` and `.interaction` set every field
that decides the mode.

## Rendering and serialization

```python
error.render()  # the [ERROR]/[ACTION]/... block, for CLI stderr or an MCP tool result
error.to_dict(include_advisory=True)  # {code, level, message, exit_code, advisory}
error.to_problem_details(status=404)  # RFC 7807 body; the caller chooses the HTTP status
```

`format_mcp_error(error)` in app-layer-base returns `error.render()`. HTTP responses
expose the advisory only as `ERROR_ADVISORY_MODE` allows (see the backend guide);
request headers never enable it.

## Warnings and notices

An operation that succeeds but must report something returns an `AdvisoryError` with
`level=Level.WARNING` or `Level.NOTICE` alongside its result; it is never raised.
