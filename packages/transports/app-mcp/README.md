# app-mcp

FastMCP transport and policy boundary for explicitly registered application tools.
Requires Python 3.12+ and FastMCP 4.x (at least 4.0.3).

```python
from pydantic import BaseModel, Field
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult, create_mcp, create_http_app


class StatusArguments(BaseModel):
    name: str = Field(min_length=1, description="Resource name")


class StatusResult(BaseModel):
    name: str
    status: str


async def get_status(context: ToolContext, arguments: StatusArguments) -> ToolResult:
    return ToolResult.success(StatusResult(name=arguments.name, status="ok"))


registry = ToolRegistry()
registry.register(
    ToolDefinition(
        name="status.get",
        description="Read resource status",
        handler=get_status,
        input_model=StatusArguments,
        output_model=StatusResult,
        required_scopes=frozenset({"status:read"}),
    )
)
# authenticated_context is an application-owned async callable returning ToolContext.
mcp = create_mcp("my-service", registry, authenticated_context)
mcp_app = create_http_app(mcp, path="/", stateless_http=True)
```

Mount `mcp_app` at `/mcp` **before** any SPA catch-all route. Compose
`mcp_app.lifespan(app)` with the host's existing lifespan; mounting alone does not
start the MCP session manager. `mcp.http_app(...)` remains available for additional
FastMCP transport options.

The host must authenticate every HTTP request, including initialization and tool
listing. FastAPI router dependencies do not protect mounted ASGI applications.
Derive `ToolContext` identity and scopes from trusted request state, never tool
arguments. The registry enforces scopes before invoking a handler; it does not
filter tool discovery by caller or implement resource-level authorization.

Input models retain aliases, constraints, field descriptions and default factories.
Tools return `{ok, result, error}` as structured content, with a matching output
schema. Output keys use model field names, including when output models declare
aliases; input aliases retain their normal validation behavior. Failures also set the MCP `isError` flag. Expected `AppError` advisories are
returned without executing their suggested fixes; unexpected failures are sanitized.
Output validation failures are server errors, not invalid caller arguments.

Set `risk=ToolRisk.WRITE` or `DESTRUCTIVE` for mutation tools. Annotations are hints,
not authorization. Confirmation and idempotency requirements are optional; the host
owns trusted confirmation, deduplication persistence and audit storage. A required
idempotency key only checks presence, and does not prevent repeated execution.
