# app-mcp

`app-mcp` is the FastMCP-based MCP package for app-common FastAPI applications.
It provides schema-aware tools, policy enforcement, and an ASGI app ready to
mount in FastAPI.

## Responsibilities

- Register stable tool names, descriptions, handlers, and required scopes.
- Require a trusted `ToolContext` supplied by the authenticated transport.
- Convert `AppError` into structured tool failures.
- Never execute an advisory `fix`; the server or client owns that policy.

`create_mcp()` registers the policy-aware registry with FastMCP. Mount the
result while passing its lifespan to FastAPI:

```python
mcp = create_mcp("my-service", registry, authenticated_context)
mcp_app = create_http_app(mcp)
app = FastAPI(lifespan=mcp_app.lifespan)
app.mount("/", mcp_app)
```

`authenticated_context` must derive identity and scopes from trusted FastAPI
authentication, never from MCP tool arguments.

## Usage

```python
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult

registry = ToolRegistry()


async def get_status(context: ToolContext, _: dict[str, object]) -> ToolResult:
    return ToolResult.success({"subject": context.subject, "status": "ok"})


registry.register(ToolDefinition("status.get", "Return service status", get_status, frozenset({"status:read"})))
result = await registry.invoke("status.get", ToolContext("agent-1", frozenset({"status:read"})), {})
```
