"""JSON-serializable results at the MCP application boundary."""

from dataclasses import dataclass
from typing import Any

from app_error import AppError
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A transport-neutral success or failure result for a tool invocation."""

    content: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @classmethod
    def success(cls, content: BaseModel | dict[str, Any]) -> "ToolResult":
        return cls(content=content.model_dump(mode="json") if isinstance(content, BaseModel) else content)

    @classmethod
    def from_app_error(cls, error: AppError) -> "ToolResult":
        """Expose an explicit advisory; callers must apply their own execution policy."""
        return cls(
            error={
                "code": error.code,
                "message": error.message,
                "advisory": error.advisory.to_dict(),
            }
        )

    @classmethod
    def internal_error(cls) -> "ToolResult":
        """Avoid leaking an unexpected exception's implementation details."""
        return cls(error={"code": "MCP_TOOL_FAILED", "message": "The tool could not complete safely."})

    @property
    def is_error(self) -> bool:
        return self.error is not None
