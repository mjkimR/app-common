from uuid import UUID, uuid4

from app_error import Actor, AppError
from app_mcp import ToolContext, ToolDefinition, ToolRegistry, ToolResult, ToolRisk, create_mcp
from fastmcp import Client
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: int = Field(alias="limit", default=10, ge=1, le=100, description="Maximum rows")
    request_id: UUID = Field(default_factory=uuid4)


class Output(BaseModel):
    size: int
    request_id: UUID


async def echo(_, args):
    return ToolResult.success(Output(size=args.size, request_id=args.request_id))


async def context():
    return ToolContext("reader", frozenset({"read"}))


def server(handler=echo):
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo", handler, Arguments, Output, frozenset({"read"})))
    registry.register(
        ToolDefinition("delete", "Delete", echo, Arguments, Output, frozenset({"write"}), ToolRisk.DESTRUCTIVE)
    )
    return create_mcp("test", registry, context)


async def test_discovery_preserves_schema_and_call_uses_alias_defaults():
    async with Client(server()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        tool = tools["echo"]
        assert tool.input_schema == Arguments.model_json_schema()
        assert tool.annotations.read_only_hint
        assert tools["delete"].annotations.destructive_hint
        assert tool.output_schema["properties"]["result"]["anyOf"][0]["properties"]["size"]["type"] == "integer"
        first = await client.call_tool("echo", {})
        second = await client.call_tool("echo", {"limit": 5})
        assert first.structured_content["result"]["size"] == 10
        assert second.structured_content["result"]["size"] == 5
        assert first.structured_content["result"]["request_id"] != second.structured_content["result"]["request_id"]


async def test_validation_scope_and_app_errors_are_protocol_errors():
    async with Client(server()) as client:
        for name, args, code in [
            ("echo", {"limit": 0}, "MCP_INVALID_ARGUMENTS"),
            ("echo", {"subject": "admin"}, "MCP_INVALID_ARGUMENTS"),
            ("delete", {}, "MCP_FORBIDDEN"),
        ]:
            result = await client.call_tool(name, args, raise_on_error=False)
            assert result.is_error
            assert result.structured_content["ok"] is False
            assert result.structured_content["error"]["code"] == code

    async def conflict(_, args):
        raise AppError("Reload before retrying", code="CONFLICT", actor=Actor.USER)

    async with Client(server(conflict)) as client:
        result = await client.call_tool("echo", {}, raise_on_error=False)
        assert result.is_error
        assert result.structured_content["error"]["code"] == "CONFLICT"


async def test_invalid_output_is_server_failure_without_leaking_values():
    async def invalid(_, args):
        return ToolResult.success({"size": "private upstream payload"})

    async with Client(server(invalid)) as client:
        result = await client.call_tool("echo", {}, raise_on_error=False)
        assert result.is_error
        assert result.structured_content["error"]["code"] == "MCP_TOOL_FAILED"
        assert "private upstream payload" not in str(result)


async def test_output_aliases_match_the_published_field_name_contract():
    class AliasedOutput(BaseModel):
        model_config = ConfigDict(serialize_by_alias=True)
        internal: str = Field(alias="validationName", serialization_alias="wireName")

    async def aliased(_, args):
        return ToolResult.success(AliasedOutput(validationName="value"))

    registry = ToolRegistry()
    registry.register(ToolDefinition("alias", "Alias", aliased, Arguments, AliasedOutput))
    async with Client(create_mcp("aliases", registry, context)) as client:
        result = await client.call_tool("alias", {})
        assert result.structured_content["result"] == {"internal": "value"}
        # Client.call_tool also validates the response against the advertised schema.


async def test_unexpected_input_validator_errors_are_sanitized():
    class BrokenInput(BaseModel):
        @model_validator(mode="before")
        @classmethod
        def broken(cls, value):
            raise TypeError("private validator implementation")

    registry = ToolRegistry()
    registry.register(ToolDefinition("broken", "Broken", echo, BrokenInput))
    async with Client(create_mcp("broken", registry, context)) as client:
        result = await client.call_tool("broken", {}, raise_on_error=False)
        assert result.is_error
        assert result.structured_content["error"]["code"] == "MCP_TOOL_FAILED"
        assert "private validator implementation" not in str(result)
