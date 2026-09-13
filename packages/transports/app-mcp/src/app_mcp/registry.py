"""Tool registry and invocation policy independent of a concrete MCP SDK."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app_error import Actor, AppError, Retry

from app_mcp.context import ToolContext
from app_mcp.result import ToolResult

ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A tool's stable contract and the scopes needed to invoke it."""

    name: str
    description: str
    handler: ToolHandler
    required_scopes: frozenset[str] = frozenset()


class ToolRegistry:
    """Registers tools and enforces authorization before handlers execute."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"A tool named {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return registered tools in deterministic name order."""
        return tuple(self._tools[name] for name in sorted(self._tools))

    async def invoke(self, name: str, context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
        """Invoke an authorized tool without exposing unexpected failures."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.from_app_error(
                AppError(
                    f"Unknown MCP tool: {name}",
                    code="MCP_TOOL_NOT_FOUND",
                    actor=Actor.USER,
                    retry=Retry.UNSAFE,
                )
            )
        if not context.permits(tool.required_scopes):
            return ToolResult.from_app_error(
                AppError(
                    "The caller is not authorized to invoke this tool.",
                    code="MCP_FORBIDDEN",
                    actor=Actor.USER,
                    retry=Retry.UNSAFE,
                    guardrail=True,
                )
            )
        try:
            return await tool.handler(context, arguments)
        except AppError as error:
            return ToolResult.from_app_error(error)
        except Exception:
            return ToolResult.internal_error()
