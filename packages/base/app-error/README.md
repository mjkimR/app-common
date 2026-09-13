# app-error

Core error hierarchy, structured advisories, and multi-channel formatting protocols for `app-common`.

## Features
- **Zero external dependencies**: Pure Python standard library (`dataclasses`, `enum`).
- **Agent Advisory Protocol**: `Actor`, `Retry`, `ActionMode`, and `Advisory` structures indicating who should act, whether retrying is safe, target files, and fix commands.
- **Multi-view formatting**: Native renderers for CLI stderr, MCP tool context, and dictionary serialization.

## HTTP and MCP boundaries

HTTP error responses are controlled only by the server-side `ERROR_ADVISORY_MODE`
setting. Request headers never enable operational advisory metadata. Use `auto`
(the default) to show advisories outside production, `always` only on an
authenticated/internal API, or `never` for public APIs.

An MCP integration should be a separate, authenticated adapter/tool boundary. It
may render a caught `AppError` with `render_mcp()` (or
`format_mcp_error()` from `app-layer-base`), but it must not change public HTTP
response behavior or automatically execute a `fix` value.
