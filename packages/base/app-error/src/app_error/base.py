from __future__ import annotations

from typing import Any

from app_error.advisory import Advisory
from app_error.renderers import render_cli_lines, render_mcp_text, serialize_error
from app_error.types import ActionMode, Actor, ExitCode, Retry


class AppError(Exception):
    """Base application exception carrying structured guidance for agents and humans."""

    exit_code: ExitCode = ExitCode.FAILED
    code: str = "GENERAL_ERROR"
    actor: Actor = Actor.NONE
    retry: Retry = Retry.UNSAFE
    guardrail: bool = False

    def __init__(
        self,
        message: str,
        *hints: str,
        code: str | None = None,
        actor: Actor | None = None,
        retry: Retry | None = None,
        guardrail: bool | None = None,
        retry_after: str | None = None,
        fix: str | None = None,
        what_to_report: str | None = None,
        target_files: list[str] | tuple[str, ...] | None = None,
        details: list[str] | tuple[str, ...] | None = None,
        exit_code: ExitCode | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if actor is not None:
            self.actor = actor
        if retry is not None:
            self.retry = retry
        if guardrail is not None:
            self.guardrail = guardrail
        if exit_code is not None:
            self.exit_code = exit_code

        self.retry_after = retry_after
        self.fix = fix
        self.what_to_report = what_to_report
        self.target_files = list(target_files) if target_files else []
        self.details = list(details) if details else []
        self.hints = hints
        if hints and not self.details:
            self.details = list(hints)

    @property
    def advisory(self) -> Advisory:
        """Derive structured advisory metadata."""
        return Advisory(
            code=self.code,
            actor=self.actor,
            retry=self.retry,
            guardrail=self.guardrail,
            retry_after=self.retry_after,
            fix=self.fix,
            what_to_report=self.what_to_report,
            target_files=tuple(self.target_files),
            details=tuple(self.details),
        )

    @property
    def mode(self) -> ActionMode:
        """Derived action mode directive for agents."""
        return self.advisory.mode

    def lines(self) -> list[str]:
        """Render the advisory and error as formatted CLI lines."""
        return render_cli_lines(self)

    def render_mcp(self) -> str:
        """Render prompt-friendly text block for Model Context Protocol (MCP) tool response."""
        return render_mcp_text(self)

    def to_dict(self, include_advisory: bool = True) -> dict[str, Any]:
        """Serialize error and advisory metadata to a dictionary."""
        return serialize_error(self, include_advisory=include_advisory)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"
