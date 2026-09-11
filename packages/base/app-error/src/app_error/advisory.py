from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app_error.types import ActionMode, Actor, Retry

_ACTION_TEXT: dict[ActionMode, str] = {
    ActionMode.AUTO: (
        "AUTO — Run the [FIX] command once, then retry the operation once.\n"
        "This is the only mode that authorizes a retry. Stop after it either way."
    ),
    ActionMode.INTERACTION: (
        "INTERACTION — Stop and ask the user. Do not retry, and do not\n"
        "improvise a way around this. [FIX], when present, is the command\n"
        "for once they agree."
    ),
    ActionMode.DEFER: (
        "DEFER — Nothing is broken and nothing here is yours to fix.\n"
        "Do not retry now. Report the cause and when it can be retried."
    ),
    ActionMode.BLOCKED: (
        "BLOCKED — A deliberate guardrail refused this. Report it and stop.\n"
        "Do not propose or apply a way around it; changing the rule is the\n"
        "user's decision, not a fix."
    ),
    ActionMode.HALT: (
        "HALT — Stop here. Do not retry, do not work around it, and do not\n"
        "finish the job by hand. Report what happened, including anything\n"
        "left half-done."
    ),
    ActionMode.MAINTENANCE: (
        "MAINTENANCE — A codebase defect or tool failure occurred.\n"
        "Report it and stop; repairing the code/tool is a separate task.\n"
        "[TARGET] names the affected files."
    ),
}

_CONTINUATION = " " * len("[ACTION] ")


@dataclass(frozen=True)
class Advisory:
    """Structured directive and metadata for calling agents and automated runners."""

    code: str = "GENERAL_ERROR"
    actor: Actor = Actor.NONE
    retry: Retry = Retry.UNSAFE
    guardrail: bool = False
    retry_after: str | None = None
    fix: str | None = None
    what_to_report: str | None = None
    target_files: tuple[str, ...] = ()
    details: tuple[str, ...] = ()

    @property
    def mode(self) -> ActionMode:
        if self.guardrail:
            return ActionMode.BLOCKED
        if self.actor is Actor.DEVELOPER:
            return ActionMode.MAINTENANCE
        if self.retry is Retry.UNSAFE:
            return ActionMode.HALT
        if self.actor is Actor.TOOL:
            return ActionMode.AUTO
        if self.actor is Actor.USER:
            return ActionMode.INTERACTION
        return ActionMode.DEFER if self.retry is Retry.SAFE else ActionMode.HALT

    def lines(self, message: str | None = None) -> list[str]:
        """Render the advisory block as formatted CLI/stderr lines."""
        rendered: list[str] = []
        if message is not None:
            rendered.append(f"[ERROR]  ({self.code}) {message}")

        head, *rest = _ACTION_TEXT[self.mode].splitlines()
        rendered.append(f"[ACTION] {head}")
        rendered.extend(f"{_CONTINUATION}{line}" for line in rest)

        if self.retry_after:
            rendered.append(f"[WHEN]   Not before: {self.retry_after}")
        if self.target_files:
            rendered.append(f"[TARGET] {', '.join(self.target_files)}")
        if self.fix:
            rendered.append(f"[FIX]    {self.fix}")
        if self.what_to_report:
            rendered.append(f"[REPORT] {self.what_to_report}")
        rendered.extend(f"[DETAIL] {detail}" for detail in self.details)
        return rendered

    def to_dict(self) -> dict[str, Any]:
        """Serialize advisory metadata to a dictionary."""
        return {
            "code": self.code,
            "mode": self.mode.value,
            "actor": self.actor.value,
            "retry": self.retry.value,
            "guardrail": self.guardrail,
            "retry_after": self.retry_after,
            "fix": self.fix,
            "what_to_report": self.what_to_report,
            "target_files": list(self.target_files),
            "details": list(self.details),
        }
