"""The backend CRUD feature scaffold (FastAPI layered architecture)."""

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
from app_tools.errors import AppToolsError, warning

TEMPLATES = Path(__file__).parent / "templates" / "feature"
ROUTER = Path("app/router.py")
SESSION_IMPORT = "from app.core.database.deps import get_session"
ROOT_INCLUDE = "router.include_router(v1_router)"


def register_router(
    base_dir: Path, plural_name: str, import_prefix: str, *, dry_run: bool
) -> tuple[str, AppToolsError | None]:
    """Import and include the feature's v1 router in ``app/router.py``."""
    router_path = base_dir / ROUTER
    if not router_path.is_file() or not router_path.read_text(encoding="utf-8").strip():
        return "skipped", warning(
            f"{router_path} is missing or empty; the feature router was not registered.",
            code="APP_SCAFFOLD_ROUTER_NOT_UPDATED",
            fix=f"Include {import_prefix}.{plural_name}.api.v1.router in the application's v1 router.",
        )
    lines = router_path.read_text(encoding="utf-8").splitlines()
    import_line = f"from {import_prefix}.{plural_name}.api.v1 import router as v1_{plural_name}_router"
    include_line = f"v1_router.include_router(v1_{plural_name}_router)"
    changed = False
    if not any(import_line in line for line in lines):
        imports = [i for i, line in enumerate(lines) if line.startswith(f"from {import_prefix}.")]
        if imports:
            lines.insert(imports[-1] + 1, import_line)
        elif SESSION_IMPORT in lines:
            lines.insert(lines.index(SESSION_IMPORT) + 1, import_line)
        else:
            lines.insert(0, import_line)
        changed = True
    if not any(include_line in line for line in lines):
        includes = [i for i, line in enumerate(lines) if line.strip().startswith("v1_router.include_router(")]
        if includes:
            lines.insert(includes[-1] + 1, include_line)
        elif ROOT_INCLUDE in lines:
            lines.insert(lines.index(ROOT_INCLUDE), include_line)
        else:
            lines.append(include_line)
        changed = True
    if changed and not dry_run:
        router_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ("updated" if changed else "unchanged"), None


def create_feature(
    name: str,
    plural: str | None = None,
    base_dir: Path | None = None,
    feature_prefix: str | None = None,
    dry_run: bool = False,
) -> FeatureResult:
    """Render the backend feature skeleton under ``<prefix>/<plural>`` and register its router."""
    check_name(name)
    base_dir = base_dir or Path.cwd()
    singular_name = to_snake_case(name)
    plural_name = plural or pluralize(singular_name)
    prefix = feature_prefix or "app/features"
    import_prefix = prefix.replace("/", ".")
    feature_dir = base_dir / prefix / plural_name
    refuse_existing(feature_dir)
    mapping = {
        "class_name": name,
        "singular_name": singular_name,
        "plural_name": plural_name,
        "import_prefix": import_prefix,
    }
    files = []
    for relative, content in render(TEMPLATES, mapping):
        output = feature_dir / relative
        files.append(output)
        if not dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content.strip(), encoding="utf-8")
    router, problem = register_router(base_dir, plural_name, import_prefix, dry_run=dry_run)
    notices = [problem] if problem else []
    return FeatureResult(name, singular_name, plural_name, feature_dir, files, dry_run, router, notices)
