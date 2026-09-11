from __future__ import annotations

from enum import IntEnum, StrEnum


class ExitCode(IntEnum):
    """Process exit codes for CLI execution."""

    OK = 0
    FAILED = 1
    INCOMPLETE = 2
    USAGE = 64


class Actor(StrEnum):
    """Who takes the next step to resolve the error."""

    TOOL = "TOOL"  # The agent or automated tool itself (e.g. running `fix`)
    USER = "USER"  # A human user (e.g. credentials, permission, decision)
    DEVELOPER = "DEVELOPER"  # A software developer or code-editing agent
    NONE = "NONE"  # Nobody at present (e.g. wait for external condition)


class Retry(StrEnum):
    """Whether retrying the operation is safe."""

    SAFE = "SAFE"  # Safe to retry without changing state (transient/timing issue)
    AFTER_FIX = "AFTER_FIX"  # Safe only after `fix` or remediation has been applied
    UNSAFE = "UNSAFE"  # Not safe to retry (risk of duplicate execution or half-done state)


class ActionMode(StrEnum):
    """Directive mode for calling agents or workflow engines."""

    AUTO = "AUTO"  # Run the fix command, retry once
    INTERACTION = "INTERACTION"  # Ask the user for confirmation/input
    DEFER = "DEFER"  # Wait then retry (e.g. rate limit, lock)
    BLOCKED = "BLOCKED"  # A guardrail refused; do not attempt workaround
    HALT = "HALT"  # Stop immediately; unsafe to retry
    MAINTENANCE = "MAINTENANCE"  # Code defect; tool/code needs patching
