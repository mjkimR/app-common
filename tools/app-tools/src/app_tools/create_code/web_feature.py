"""The Svelte 5 web feature scaffold (runes state, view and dialog)."""

from __future__ import annotations

from pathlib import Path

from app_tools.create_code.naming import (
    FeatureResult,
    check_name,
    pluralize,
    refuse_existing,
    render,
    to_snake_case,
)

TEMPLATES = Path(__file__).parent / "templates" / "web_feature"


def default_prefix(base_dir: Path) -> str:
    """``src/lib/features`` in a web project, ``web/src/lib/features`` from a repository root that has one."""
    if (base_dir / "src/lib").exists() and (base_dir / "package.json").exists():
        return "src/lib/features"
    if (base_dir / "web/src/lib").exists():
        return "web/src/lib/features"
    return "src/lib/features"


def create_web_feature(
    name: str,
    plural: str | None = None,
    base_dir: Path | None = None,
    feature_prefix: str | None = None,
    dry_run: bool = False,
) -> FeatureResult:
    """Render the web feature skeleton under ``<prefix>/<singular>``."""
    check_name(name)
    base_dir = base_dir or Path.cwd()
    singular_name = to_snake_case(name)
    plural_name = plural or pluralize(singular_name)
    feature_dir = base_dir / (feature_prefix or default_prefix(base_dir)) / singular_name
    refuse_existing(feature_dir)
    mapping = {"class_name": name, "singular_name": singular_name, "plural_name": plural_name}
    files = []
    for relative, content in render(TEMPLATES, mapping):
        output = feature_dir / relative
        files.append(output)
        if not dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content.strip() + "\n", encoding="utf-8")
    return FeatureResult(name, singular_name, plural_name, feature_dir, files, dry_run)
