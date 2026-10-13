"""Architecture findings and the catalog of rules that report them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ArchViolation:
    rule: str
    file: str
    line: int
    message: str
    fix: str


def relative_parts(path: Path, root: Path | None) -> tuple[str, ...]:
    """The path components below ``root``: directories above the workspace never classify a file."""
    resolved = path.resolve()
    if root is not None and resolved.is_relative_to(root):
        return resolved.relative_to(root).parts
    return path.parts


@dataclass(frozen=True)
class RuleSpec:
    id: str
    name: str
    description: str
    severity: Literal["error", "warning"]
    guide: str  # skill reference topic, as listed in catalog.json


def _spec(slug: str, description: str, severity: Literal["error", "warning"], guide: str) -> RuleSpec:
    return RuleSpec(f"RULE-app-{slug}", f"app-{slug}", description, severity, guide)


RULES: dict[str, RuleSpec] = {
    spec.id: spec
    for spec in (
        _spec(
            "router-repo-import",
            "Router/API modules do not import repository modules.",
            "error",
            "backend",
        ),
        _spec("service-commit", "Services do not call commit() or rollback().", "error", "backend/session"),
        _spec(
            "hook-super-call",
            "Hook methods other than __init__ do not chain through super().",
            "error",
            "backend/hooks",
        ),
        _spec(
            "adapter-dependency",
            "An adapter package does not import a sibling adapter in the source checkout.",
            "error",
            "backend",
        ),
        _spec(
            "forbidden-import",
            "Modules respect the boundaries declared in tool.app-tools.architecture.",
            "error",
            "backend/commands",
        ),
        _spec(
            "command-signature",
            "Public command functions are undecorated async functions with typed context, input and output.",
            "error",
            "backend/commands",
        ),
        _spec(
            "command-transaction",
            "Command modules leave the execution scope to their caller.",
            "error",
            "backend/commands",
        ),
        _spec(
            "architecture-config",
            "tool.app-tools.architecture in pyproject.toml is well formed.",
            "error",
            "backend/commands",
        ),
        _spec("parse-error", "Python sources can be parsed for architecture checks.", "error", "backend"),
        _spec(
            "http-client-construction",
            "Packages declaring app-http-client use the shared HTTP client getters.",
            "warning",
            "http",
        ),
        _spec("shared-client-close", "Application code does not close the shared HTTP client.", "warning", "http"),
        _spec(
            "direct-current-time",
            "Packages declaring app-layer-base read the clock through its UTC time utilities.",
            "warning",
            "backend/time",
        ),
        _spec(
            "db-factory-in-layer",
            "Routers and services do not build their own DB engine or session factory.",
            "warning",
            "backend/session",
        ),
        _spec(
            "undeclared-dependency",
            "Directly imported app-common packages are declared by the importing package.",
            "warning",
            "local-dev",
        ),
        _spec(
            "invalid-suppression",
            "Every `# arch: ignore[...]` comment names a rule reported on its line.",
            "warning",
            "backend",
        ),
    )
}
