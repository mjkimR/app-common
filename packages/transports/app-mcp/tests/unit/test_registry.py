import pytest
from app_error import Actor, AppError, Retry
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult, ToolRisk, create_http_app, create_mcp
from pydantic import BaseModel, Field, model_validator


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


class Step(BaseModel):
    key: str
    after: list[str] = Field(default_factory=list)


class PlanArguments(BaseModel):
    token: str = Field(min_length=8)
    steps: list[Step]

    @model_validator(mode="after")
    def _known_steps(self) -> "PlanArguments":
        keys = {step.key for step in self.steps}
        if any(parent not in keys for step in self.steps for parent in step.after):
            raise ValueError("Dependency target does not exist in this scope")
        return self


async def test_invalid_arguments_name_each_problem_without_echoing_values():
    registry = ToolRegistry()
    registry.register(ToolDefinition("plan", "Plan", _echo, PlanArguments))
    context = ToolContext(subject="user-1")

    fields = await registry.invoke("plan", context, {"token": "secret", "steps": [{"after": []}]})
    graph = await registry.invoke("plan", context, {"token": "long-secret", "steps": [{"key": "a", "after": ["b"]}]})

    assert fields.error is not None and fields.error["code"] == "MCP_INVALID_ARGUMENTS"
    assert fields.error["advisory"]["details"] == [
        "token: String should have at least 8 characters",
        "steps.0.key: Field required",
    ]
    assert fields.error["advisory"]["fix"]
    assert "secret" not in str(fields.error)
    assert graph.error is not None
    assert graph.error["advisory"]["details"] == [
        "(arguments): Value error, Dependency target does not exist in this scope"
    ]


async def test_invalid_argument_details_are_capped():
    registry = ToolRegistry()
    registry.register(ToolDefinition("plan", "Plan", _echo, PlanArguments))

    result = await registry.invoke("plan", ToolContext(subject="user-1"), {"token": "12345678", "steps": [{}] * 25})

    assert result.error is not None
    details = result.error["advisory"]["details"]
    assert len(details) == 21
    assert details[-1] == "... and 5 more"


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
