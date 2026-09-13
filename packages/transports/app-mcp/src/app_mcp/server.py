"""FastMCP server factory backed by app-mcp policy enforcement."""

from collections.abc import Awaitable, Callable
from inspect import Parameter, Signature
from typing import Any

from fastmcp import FastMCP

from app_mcp.context import ToolContext
from app_mcp.registry import ToolRegistry

ContextProvider = Callable[[], Awaitable[ToolContext]]


def _tool_signature(model: type[Any]) -> Signature:
    """Expose Pydantic fields as FastMCP's keyword-only tool arguments."""
    parameters = [
        Parameter(
            name,
            Parameter.KEYWORD_ONLY,
            default=Parameter.empty if field.is_required() else field.default,
            annotation=field.annotation,
        )
        for name, field in model.model_fields.items()
    ]
    return Signature(parameters, return_annotation=dict[str, Any])


def create_mcp(name: str, registry: ToolRegistry, context_provider: ContextProvider) -> FastMCP:
    """Create a FastMCP server that invokes every tool through ``registry``.

    ``context_provider`` is the FastAPI authentication boundary: it must derive
    identity, scopes, confirmations, and idempotency metadata from trusted
    request state, never from MCP tool arguments.
    """
    mcp = FastMCP(name)

    for definition in registry.definitions():

        async def invoke_tool(_tool_name: str = definition.name, **arguments: Any) -> dict[str, Any]:
            result = await registry.invoke(_tool_name, await context_provider(), arguments)
            return {"ok": not result.is_error, "result": result.content, "error": result.error}

        invoke_tool.__name__ = definition.name.replace(".", "_").replace("-", "_")
        invoke_tool.__signature__ = _tool_signature(definition.input_model)
        invoke_tool.__annotations__ = {
            name: field.annotation for name, field in definition.input_model.model_fields.items()
        } | {"return": dict[str, Any]}
        mcp.tool(name=definition.name, description=definition.description)(invoke_tool)

    return mcp


def create_http_app(mcp: FastMCP, path: str = "/mcp") -> Any:
    """Return the ASGI app to mount in FastAPI, including FastMCP lifespan."""
    return mcp.http_app(path=path)
