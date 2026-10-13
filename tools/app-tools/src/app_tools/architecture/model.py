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

    @property
    def slug(self) -> str:
        """The rule's package directory under the bundle's ``rules/`` (``RULE-app-service-commit``: ``service_commit``)."""
        return self.id.removeprefix("RULE-app-").replace("-", "_")


def _spec(slug: str, description: str, severity: Literal["error", "warning"]) -> RuleSpec:
    return RuleSpec(f"RULE-app-{slug}", f"app-{slug}", description, severity)


RULES: dict[str, RuleSpec] = {
    spec.id: spec
    for spec in (
        _spec("router-repo-import", "Router/API modules do not import repository modules.", "error"),
        _spec("service-commit", "Services do not call commit() or rollback().", "error"),
        _spec("hook-super-call", "Hook methods other than __init__ do not chain through super().", "error"),
        _spec(
            "adapter-dependency",
            "An adapter package does not import a sibling adapter in the source checkout.",
            "error",
        ),
        _spec("forbidden-import", "Modules respect the boundaries declared in tool.app-tools.architecture.", "error"),
        _spec(
            "command-signature",
            "Public command functions are undecorated async functions with typed context, input and output.",
            "error",
        ),
        _spec("command-transaction", "Command modules leave the execution scope to their caller.", "error"),
        _spec("architecture-config", "tool.app-tools.architecture in pyproject.toml is well formed.", "error"),
        _spec("parse-error", "Python sources can be parsed for architecture checks.", "error"),
        _spec(
            "http-client-construction",
            "Packages declaring app-http-client use the shared HTTP client getters.",
            "warning",
        ),
        _spec("shared-client-close", "Application code does not close the shared HTTP client.", "warning"),
        _spec(
            "direct-current-time",
            "Packages declaring app-layer-base read the clock through its UTC time utilities.",
            "warning",
        ),
        _spec(
            "db-factory-in-layer",
            "Routers and services do not build their own DB engine or session factory.",
            "warning",
        ),
        _spec(
            "undeclared-dependency",
            "Directly imported app-common packages are declared by the importing package.",
            "warning",
        ),
        _spec(
            "invalid-suppression", "Every `# arch: ignore[...]` comment names a rule reported on its line.", "warning"
        ),
    )
}
