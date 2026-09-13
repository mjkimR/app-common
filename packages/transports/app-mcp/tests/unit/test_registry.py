from typing import Any

import pytest
from app_error import Actor, AppError, Retry
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult


async def _echo(_: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    return ToolResult.success({"value": arguments["value"]})


async def _fails(_: ToolContext, __: dict[str, Any]) -> ToolResult:
    raise AppError("Action required", code="ACTION_REQUIRED", actor=Actor.USER, retry=Retry.AFTER_FIX)


async def test_registry_enforces_scopes_before_invocation():
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo a value", _echo, frozenset({"tools:echo"})))

    denied = await registry.invoke("echo", ToolContext(subject="user-1"), {"value": "hello"})
    allowed = await registry.invoke(
        "echo", ToolContext(subject="user-1", scopes=frozenset({"tools:echo"})), {"value": "hello"}
    )

    assert denied.is_error is True
    assert denied.error is not None
    assert denied.error["code"] == "MCP_FORBIDDEN"
    assert allowed.content == {"value": "hello"}


async def test_registry_converts_app_errors_and_hides_unexpected_failures():
    registry = ToolRegistry()
    registry.register(ToolDefinition("fails", "Fails intentionally", _fails))

    result = await registry.invoke("fails", ToolContext(subject="user-1"), {})
    missing = await registry.invoke("missing", ToolContext(subject="user-1"), {})

    assert result.error is not None
    assert result.error["code"] == "ACTION_REQUIRED"
    assert result.error["advisory"]["mode"] == "INTERACTION"
    assert missing.error is not None
    assert missing.error["code"] == "MCP_TOOL_NOT_FOUND"


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo a value", _echo))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ToolDefinition("echo", "Echo a value", _echo))
