"""Trusted identity and authorization context for a single tool invocation."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Identity supplied by an authenticated MCP transport, never by tool input."""

    subject: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    request_id: str | None = None

    def permits(self, required_scopes: frozenset[str]) -> bool:
        """Return whether this caller has every scope required by a tool."""
        return required_scopes.issubset(self.scopes)
