"""Consumer-declared import boundaries, independent of CRUD naming conventions."""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

from app_tools.architecture_hygiene import ArchViolation


@dataclass(frozen=True)
class Boundary:
    name: str
    source: str
    forbidden_imports: tuple[str, ...]


def _module_name(value: object) -> bool:
    return isinstance(value, str) and bool(value) and all(part.isidentifier() for part in value.split("."))


def _contains(prefix: str, module: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _manifest(path: Path) -> Path | None:
    directory = path.resolve() if path.is_dir() else path.resolve().parent
    for parent in (directory, *directory.parents):
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
        if (parent / ".git").exists():
            break
    return None


def _read(manifest: Path) -> tuple[Boundary, ...]:
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    config = data.get("tool", {}).get("app-tools", {}).get("architecture", {})
    if not isinstance(config, dict) or set(config) - {"boundaries"}:
        raise ValueError("architecture must be a table containing only boundaries")
    entries = config.get("boundaries", [])
    if not isinstance(entries, list):
        raise ValueError("architecture.boundaries must be an array of tables")
    boundaries = []
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "source", "forbidden_imports"}:
            raise ValueError("each boundary requires exactly name, source, and forbidden_imports")
        name, source, forbidden = entry["name"], entry["source"], entry["forbidden_imports"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("boundary names must be nonempty, unique strings")
        if not _module_name(source):
            raise ValueError(f"boundary {name!r}: source must be a dotted module name")
        if not isinstance(forbidden, list) or not forbidden or not all(_module_name(item) for item in forbidden):
            raise ValueError(f"boundary {name!r}: forbidden_imports must be a nonempty list of dotted module names")
        boundaries.append(Boundary(name, source, tuple(forbidden)))
        names.add(name)
    return tuple(boundaries)


class BoundaryChecks:
    """One scan's configuration cache; report malformed configurations once."""

    def __init__(self) -> None:
        self.configs: dict[Path, tuple[Boundary, ...] | None] = {}
        self.violations: list[ArchViolation] = []

    def configuration(self, path: Path) -> tuple[Path | None, tuple[Boundary, ...] | None]:
        manifest = _manifest(path)
        if manifest is None:
            return None, ()
        if manifest not in self.configs:
            try:
                self.configs[manifest] = _read(manifest)
            except (ValueError, UnicodeDecodeError, AttributeError) as exc:
                self.configs[manifest] = None
                self.violations.append(
                    ArchViolation(
                        "ARCH_CONFIG_ERROR",
                        str(manifest),
                        1,
                        f"Invalid architecture configuration: {exc}",
                        "Fix tool.app-tools.architecture.boundaries and rerun check-arch.",
                    )
                )
        return manifest, self.configs[manifest]

    def inspect(self, path: Path, tree: ast.AST) -> list[ArchViolation]:
        manifest, boundaries = self.configuration(path)
        if manifest is None or not boundaries:
            return []
        relative = path.resolve().relative_to(manifest.parent).with_suffix("")
        parts = list(relative.parts)
        if parts[0] == "src":
            parts.pop(0)
        is_package = parts[-1] == "__init__"
        if is_package:
            parts.pop()
        module = ".".join(parts)
        package = parts if is_package else parts[:-1]
        active = [boundary for boundary in boundaries if _contains(boundary.source, module)]
        violations = []
        for node in ast.walk(tree):
            imports: list[str] = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    if node.level > len(package):
                        continue
                    base = ".".join([*package[: len(package) - node.level + 1], *([base] if base else [])])
                imports = [base, *[f"{base}.{alias.name}" for alias in node.names if alias.name != "*"]]
            else:
                continue
            for boundary in active:
                blocked = sorted(
                    {name for name in imports if any(_contains(p, name) for p in boundary.forbidden_imports)}
                )
                if blocked:
                    violations.append(
                        ArchViolation(
                            "ARCH_FORBIDDEN_IMPORT",
                            str(path),
                            node.lineno,
                            f"Boundary {boundary.name!r}: {module!r} imports forbidden module {blocked[0]!r}.",
                            "Move the dependency behind the declared application boundary.",
                        )
                    )
        return violations
