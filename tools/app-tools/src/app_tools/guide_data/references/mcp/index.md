# app-mcp

Use `app-mcp` for MCP tools. It is protocol-neutral: do not import FastAPI or a
particular MCP SDK into domain handlers.

1. The transport authenticates the caller and constructs `ToolContext`; never
   accept `subject` or `scopes` from tool arguments.
2. Register a `ToolDefinition` with the smallest required scope set.
3. Return `ToolResult.success(...)` from handlers and raise `AppError` for
   expected failures. `ToolRegistry` translates it into a structured result.
4. Never automatically execute `AppError.fix`. Confirmation and execution policy
   belong to the MCP client or server.
5. Put stdio, Streamable HTTP, or FastAPI mounting code in a separate integration
   package or application layer, not in `app-mcp`.

```python
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult

registry = ToolRegistry()


async def read_status(context: ToolContext, _: dict[str, object]) -> ToolResult:
    return ToolResult.success({"subject": context.subject, "status": "ok"})


registry.register(ToolDefinition("status.get", "Read status", read_status, frozenset({"status:read"})))
```
