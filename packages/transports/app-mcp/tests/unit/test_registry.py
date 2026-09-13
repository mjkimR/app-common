import pytest
from app_error import Actor, AppError, Retry
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult, ToolRisk, create_http_app, create_mcp
from pydantic import BaseModel


class EchoArguments(BaseModel):
    value: str


class EchoResult(BaseModel):
    value: str


async def _echo(_: ToolContext, arguments: EchoArguments) -> ToolResult:
    return ToolResult.success(EchoResult(value=arguments.value))


async def _fails(_: ToolContext, __: EchoArguments) -> ToolResult:
    raise AppError("Action required", code="ACTION_REQUIRED", actor=Actor.USER, retry=Retry.AFTER_FIX)


async def test_registry_enforces_scopes_before_invocation():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition("echo", "Echo a value", _echo, EchoArguments, EchoResult, frozenset({"tools:echo"}))
    )

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
    registry.register(ToolDefinition("fails", "Fails intentionally", _fails, EchoArguments))

    result = await registry.invoke("fails", ToolContext(subject="user-1"), {"value": "ignored"})
    missing = await registry.invoke("missing", ToolContext(subject="user-1"), {})

    assert result.error is not None
    assert result.error["code"] == "ACTION_REQUIRED"
    assert result.error["advisory"]["mode"] == "INTERACTION"
    assert missing.error is not None
    assert missing.error["code"] == "MCP_TOOL_NOT_FOUND"


def test_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo a value", _echo, EchoArguments))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ToolDefinition("echo", "Echo a value", _echo, EchoArguments))


async def test_registry_requires_confirmation_and_idempotency_key():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            "record.delete",
            "Delete a record",
            _echo,
            EchoArguments,
            required_scopes=frozenset({"records:delete"}),
            risk=ToolRisk.DESTRUCTIVE,
            requires_confirmation=True,
            idempotency_key_required=True,
        )
    )

    context = ToolContext(subject="user-1", scopes=frozenset({"records:delete"}))
    confirmation = await registry.invoke("record.delete", context, {"value": "x"})
    invoked = await registry.invoke(
        "record.delete",
        ToolContext(
            subject="user-1",
            scopes=frozenset({"records:delete"}),
            confirmed_tools=frozenset({"record.delete"}),
            idempotency_key="request-1",
        ),
        {"value": "x"},
    )

    assert confirmation.error is not None
    assert confirmation.error["code"] == "MCP_CONFIRMATION_REQUIRED"
    assert invoked.content == {"value": "x"}


async def test_fastmcp_factory_registers_tools_and_creates_http_app():
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo a value", _echo, EchoArguments))

    async def context_provider() -> ToolContext:
        return ToolContext(subject="agent-1")

    mcp = create_mcp("test-mcp", registry, context_provider)
    app = create_http_app(mcp, path="/mcp")

    assert mcp.name == "test-mcp"
    assert app is not None
