"""MCP tool boundary primitives; transports and SDK integrations remain optional."""

from app_mcp.context import ToolContext
from app_mcp.policy import AuditEvent, AuditHook, ToolRisk
from app_mcp.registry import ToolDefinition, ToolHandler, ToolRegistry
from app_mcp.result import ToolResult

__all__ = [
    "AuditEvent",
    "AuditHook",
    "ToolContext",
    "ToolDefinition",
    "ToolHandler",
    "ToolRegistry",
    "ToolResult",
    "ToolRisk",
]
