"""Tool registry and invocation policy independent of a concrete MCP SDK."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app_error import Actor, AppError, Retry
from pydantic import BaseModel, ValidationError

from app_mcp.context import ToolContext
from app_mcp.policy import AuditEvent, AuditHook, ToolRisk
from app_mcp.result import ToolResult

ToolHandler = Callable[[ToolContext, BaseModel], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A tool's stable contract and the scopes needed to invoke it."""

    name: str
    description: str
    handler: ToolHandler
    input_model: type[BaseModel]
    output_model: type[BaseModel] | None = None
    required_scopes: frozenset[str] = frozenset()
    risk: ToolRisk = ToolRisk.READ
    requires_confirmation: bool = False
    idempotency_key_required: bool = False
    audit_event: str | None = None

    def contract(self) -> dict[str, Any]:
        """Return the machine-readable contract used for MCP tool discovery."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(mode="serialization", by_alias=False)
            if self.output_model
            else None,
            "required_scopes": sorted(self.required_scopes),
            "risk": self.risk.value,
            "requires_confirmation": self.requires_confirmation,
            "idempotency_key_required": self.idempotency_key_required,
        }


class ToolRegistry:
    """Registers tools and enforces authorization before handlers execute."""

    def __init__(self, audit_hook: AuditHook | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._audit_hook = audit_hook

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"A tool named {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return registered tools in deterministic name order."""
        return tuple(self._tools[name] for name in sorted(self._tools))

    def contracts(self) -> tuple[dict[str, Any], ...]:
        return tuple(tool.contract() for tool in self.definitions())

    async def _audit(self, event: str, tool: ToolDefinition, context: ToolContext, **details: Any) -> None:
        if self._audit_hook is not None and tool.audit_event is not None:
            await self._audit_hook(AuditEvent(event, tool.name, context.subject, context.request_id, details))

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
        if tool.requires_confirmation and tool.name not in context.confirmed_tools:
            return ToolResult.from_app_error(
                AppError(
                    "Explicit confirmation is required.",
                    code="MCP_CONFIRMATION_REQUIRED",
                    actor=Actor.USER,
                    retry=Retry.AFTER_FIX,
                    guardrail=True,
                )
            )
        if tool.idempotency_key_required and not context.idempotency_key:
            return ToolResult.from_app_error(
                AppError(
                    "An idempotency key is required.",
                    code="MCP_IDEMPOTENCY_KEY_REQUIRED",
                    actor=Actor.USER,
                    retry=Retry.AFTER_FIX,
                    guardrail=True,
                )
            )
        try:
            try:
                validated = tool.input_model.model_validate(arguments)
            except ValidationError:
                return ToolResult.from_app_error(
                    AppError(
                        "Tool arguments do not match its schema.",
                        code="MCP_INVALID_ARGUMENTS",
                        actor=Actor.USER,
                        retry=Retry.AFTER_FIX,
                    )
                )
            await self._audit("started", tool, context)
            result = await tool.handler(context, validated)
            if not result.is_error and result.content is not None and tool.output_model is not None:
                result = ToolResult.success(tool.output_model.model_validate(result.content, by_name=True))
            await self._audit(
                "succeeded" if not result.is_error else "failed",
                tool,
                context,
                code=result.error and result.error.get("code"),
            )
            return result
        except AppError as error:
            return ToolResult.from_app_error(error)
        except Exception:
            return ToolResult.internal_error()
