"""Read-only access to the manifests of a consumer project (pyproject.toml, uv.lock, package.json)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from app_tools.errors import manifest_invalid

APP_COMMON_GIT = re.compile(r"github\.com/mjkimR/app-common(?:\.git)?/?$")


def read_manifest(path: Path) -> dict[str, Any]:
    """A TOML or JSON manifest as a mapping; ``{}`` when the file does not exist."""
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    except (OSError, ValueError) as exc:
        raise manifest_invalid(str(path), exc) from exc
    if not isinstance(data, dict):
        raise manifest_invalid(str(path), "the document is not an object")
    return data


def dependency_name(spec: str) -> str:
    """The normalized distribution name of a PEP 508 requirement."""
    match = re.match(r"[A-Za-z0-9_.-]+", spec)
    return re.sub(r"[-_.]+", "-", match[0]).lower() if match else ""


def is_app_common_git(url: object) -> bool:
    return isinstance(url, str) and APP_COMMON_GIT.search(url.removeprefix("git+")) is not None


def project_roots(root: Path) -> list[Path]:
    """``root`` and the members of its uv workspace, without the excluded ones."""
    workspace = read_manifest(root / "pyproject.toml").get("tool", {}).get("uv", {}).get("workspace", {})
    excludes = {path.resolve() for pattern in workspace.get("exclude", []) for path in root.glob(pattern)}
    roots = {root.resolve()}
    for pattern in workspace.get("members", []):
        roots.update(
            path.resolve()
            for path in root.glob(pattern)
            if path.is_dir() and (path / "pyproject.toml").is_file() and path.resolve() not in excludes
        )
    return sorted(roots)


def declared_requirements(manifest: dict[str, Any]) -> list[str]:
    """Every requirement string of a pyproject: dependencies, optional dependencies and dependency groups."""
    project = manifest.get("project", {})
    specs = [spec for spec in project.get("dependencies", []) if isinstance(spec, str)]
    for group in project.get("optional-dependencies", {}).values():
        specs.extend(spec for spec in group if isinstance(spec, str))
    for group in manifest.get("dependency-groups", {}).values():
        specs.extend(spec for spec in group if isinstance(spec, str))
    return specs
