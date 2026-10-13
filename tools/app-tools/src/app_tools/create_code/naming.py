"""Names and template rendering shared by the backend and web scaffolds."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any

from app_tools.errors import AppToolsError, invalid_input


@dataclass(frozen=True)
class FeatureResult:
    feature: str
    singular_name: str
    plural_name: str
    feature_dir: Path
    files: list[Path]
    dry_run: bool
    router: str | None = None  # backend only: "updated", "unchanged" or "skipped"
    notices: list[AppToolsError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "singular_name": self.singular_name,
            "plural_name": self.plural_name,
            "feature_dir": str(self.feature_dir),
            "files": [str(path) for path in self.files],
            "router": self.router,
            "dry_run": self.dry_run,
            "notices": [item.to_dict() for item in self.notices],
        }


def pluralize(name: str) -> str:
    if name.endswith("y"):
        return name[:-1] + "ies"
    if name.endswith("s"):
        return name + "es"
    return name + "s"


def to_snake_case(name: str) -> str:
    """CamelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def check_name(name: str) -> None:
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
        raise invalid_input(
            f"Feature name '{name}' is not CamelCase.",
            code="APP_SCAFFOLD_NAME_INVALID",
            fix="Pass --name in CamelCase, for example --name Article.",
        )


def refuse_existing(feature_dir: Path) -> None:
    if feature_dir.exists():
        raise invalid_input(
            f"{feature_dir} already exists; scaffolding never overwrites files.",
            code="APP_SCAFFOLD_TARGET_EXISTS",
            fix="Choose another --name or --plural, or another --prefix.",
            target_files=[str(feature_dir)],
        )


def render(templates: Path, mapping: dict[str, str]) -> list[tuple[Path, str]]:
    """Each template's output path relative to the feature directory and its content.

    File names may contain ``__singular_name__`` and ``__class_name__``.
    """
    rendered = []
    for template in sorted(templates.rglob("*.tmpl")):
        relative = template.relative_to(templates).with_suffix("").as_posix()
        relative = relative.replace("__singular_name__", mapping["singular_name"]).replace(
            "__class_name__", mapping["class_name"]
        )
        rendered.append((Path(relative), Template(template.read_text(encoding="utf-8")).substitute(mapping)))
    return rendered
