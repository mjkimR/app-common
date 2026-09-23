# app-mcp

Use `app-mcp` to register explicit MCP tool contracts. Domain handlers receive a
Pydantic input model and a trusted `ToolContext`; keep transport dependencies out
of business logic.

1. Authenticate every HTTP request at the transport boundary, including discovery.
   Mounted ASGI apps do not inherit FastAPI router dependencies.
2. Register `ToolDefinition` with `input_model`, optional `output_model`, and the
   smallest required scope set. See the package README for a complete example.
3. Return `ToolResult.success(...)` or raise `AppError`. The transport preserves
   structured advisories and sets MCP `isError` on failure. Never execute a `fix`.
4. Set mutation risk explicitly. Scope checks run before handlers, but listing is
   not filtered. Resource-level access checks belong to the application.
5. Compose the ASGI lifespan with the host's existing startup/shutdown work. Mount
   `create_http_app(mcp, path="/", stateless_http=True)` at `/mcp` before SPA routes.
   FastMCP's `mcp.http_app(...)` exposes further transport options.
6. Confirmation and idempotency key checks are optional. Trusted confirmations,
   actual deduplication and audit persistence belong to the application.

The supported transport dependency is FastMCP `>=4.0.3,<5`. Model schemas retain
field constraints, descriptions, aliases and default factories. The public output
is an `{ok, result, error}` envelope around the declared output model.
