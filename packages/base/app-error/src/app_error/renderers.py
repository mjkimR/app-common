from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app_error.base import AppError


def render_cli_lines(error: AppError) -> list[str]:
    """Render error and its advisory for CLI/stderr output."""
    return error.advisory.lines(str(error))


def render_mcp_text(error: AppError) -> str:
    """Render prompt-friendly text block for Model Context Protocol (MCP) tool failures."""
    lines = error.advisory.lines(str(error))
    return "\n".join(lines)


def serialize_error(error: AppError, include_advisory: bool = True) -> dict[str, Any]:
    """Serialize AppError to dictionary."""
    data: dict[str, Any] = {
        "code": error.code,
        "message": str(error),
        "exit_code": int(error.exit_code),
    }
    if include_advisory:
        data["advisory"] = error.advisory.to_dict()
    return data
