"""Policy metadata and audit events for MCP tool invocations."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolRisk(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event: str
    tool_name: str
    subject: str
    request_id: str | None
    details: dict[str, Any]


AuditHook = Callable[[AuditEvent], Awaitable[None]]
