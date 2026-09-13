# app-mcp

`app-mcp` is the inbound MCP tool boundary for app-common. It intentionally has
no dependency on FastAPI or an MCP SDK: a deployment may use stdio, Streamable
HTTP, or a framework-specific server without changing its tool contracts.

## Responsibilities

- Register stable tool names, descriptions, handlers, and required scopes.
- Require a trusted `ToolContext` supplied by the authenticated transport.
- Convert `AppError` into structured tool failures.
- Never execute an advisory `fix`; the server or client owns that policy.

An SDK integration adapts protocol requests into `ToolContext` and
`ToolRegistry.invoke()`. A FastAPI integration, if needed, is optional and
belongs outside this core package.

## Usage

```python
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult

registry = ToolRegistry()


async def get_status(context: ToolContext, _: dict[str, object]) -> ToolResult:
    return ToolResult.success({"subject": context.subject, "status": "ok"})


registry.register(ToolDefinition("status.get", "Return service status", get_status, frozenset({"status:read"})))
result = await registry.invoke("status.get", ToolContext("agent-1", frozenset({"status:read"})), {})
```
