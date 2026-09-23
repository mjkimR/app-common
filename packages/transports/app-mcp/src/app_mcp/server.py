"""FastMCP transport backed by the registry's model and policy contracts."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools import ToolResult as FastMCPToolResult
from mcp.types import ToolAnnotations
from pydantic import BaseModel, PrivateAttr

from app_mcp.context import ToolContext
from app_mcp.policy import ToolRisk
from app_mcp.registry import ToolDefinition, ToolRegistry

ContextProvider = Callable[[], Awaitable[ToolContext]]


class _Response[T](BaseModel):
    ok: bool
    result: T | None
    error: dict[str, Any] | None


class _RegistryTool(Tool):
    _registry: ToolRegistry = PrivateAttr()
    _context_provider: ContextProvider = PrivateAttr()

    async def run(self, arguments: dict[str, Any]) -> FastMCPToolResult:
        result = await self._registry.invoke(self.name, await self._context_provider(), arguments)
        return FastMCPToolResult(
            structured_content={"ok": not result.is_error, "result": result.content, "error": result.error},
            is_error=result.is_error,
        )


def _create_tool(
    definition: ToolDefinition, registry: ToolRegistry, context_provider: ContextProvider
) -> _RegistryTool:
    # Publish the model itself, rather than reconstructing a function signature:
    # aliases, constraints, nested definitions and default factories retain their semantics.
    response_type = _Response[definition.output_model or dict[str, Any]]
    tool = _RegistryTool(
        name=definition.name,
        description=definition.description,
        parameters=definition.input_model.model_json_schema(),
        output_schema=response_type.model_json_schema(mode="serialization", by_alias=False),
        annotations=ToolAnnotations(
            read_only_hint=definition.risk == ToolRisk.READ,
            destructive_hint=definition.risk == ToolRisk.DESTRUCTIVE,
        ),
    )
    tool._registry = registry
    tool._context_provider = context_provider
    return tool


def create_mcp(name: str, registry: ToolRegistry, context_provider: ContextProvider) -> FastMCP:
    """Register explicit tools; the host authenticates every transport request.

    ``context_provider`` derives identity and scopes from trusted request state,
    never from tool arguments. FastAPI router dependencies do not protect mounts.
    """
    mcp = FastMCP(name)
    for definition in registry.definitions():
        mcp.add_tool(_create_tool(definition, registry, context_provider))
    return mcp


def create_http_app(mcp: FastMCP, path: str = "/mcp", *, stateless_http: bool = False) -> Any:
    """Return an ASGI app whose lifespan must be composed with the host lifespan."""
    return mcp.http_app(path=path, stateless_http=stateless_http)
