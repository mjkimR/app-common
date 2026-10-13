"""Point a consumer's installed app-common packages at a local checkout, and back.

Installed package directories are moved aside as ``<name>.bak`` and replaced by symlinks into
the checkout; the manifests and the lock file of the consumer are never touched.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app_tools.errors import AppToolsError, invalid_input, notice, warning

APP_COMMON_SENTINEL = Path("packages") / "base" / "app-layer-base"
BUNDLE_PACKAGE = "app_tools"  # ships the app-common devkit bundle

Kind = Literal["python", "node"]


@dataclass(frozen=True)
class LinkAction:
    kind: Kind
    package: str
    action: Literal["linked", "relinked", "restored"]
    source: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "package": self.package,
            "action": self.action,
            "source": str(self.source) if self.source else None,
        }


@dataclass(frozen=True)
class PackageState:
    kind: Kind
    package: str
    state: Literal["linked", "installed", "anomaly", "orphan-backup", "not-installed"]
    target: Path | None = None
    backup: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "package": self.package,
            "state": self.state,
            "target": str(self.target) if self.target else None,
            "backup": self.backup,
        }


@dataclass(frozen=True)
class LinkResult:
    root: Path | None
    actions: list[LinkAction]
    dry_run: bool
    notices: list[AppToolsError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_common_root": str(self.root) if self.root else None,
            "actions": [action.to_dict() for action in self.actions],
            "dry_run": self.dry_run,
            "notices": [item.to_dict() for item in self.notices],
        }


@dataclass(frozen=True)
class StatusResult:
    root: Path | None
    packages: list[PackageState]
    problems: list[AppToolsError]

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_common_root": str(self.root) if self.root else None,
            "packages": [package.to_dict() for package in self.packages],
            "errors": [problem.to_dict() for problem in self.problems],
        }


def is_app_common_root(path: Path) -> bool:
    return (path / APP_COMMON_SENTINEL).is_dir()


def find_app_common_root(start: Path, target_path: Path | None = None) -> Path | None:
    """An explicit checkout, else the first app-common checkout within one level up or down of ``start``."""
    if target_path is not None:
        return target_path.resolve() if is_app_common_root(target_path) else None
    start = start.resolve()
    candidates = [start, start.parent / "app-common"]
    candidates += _children(start.parent)
    candidates += [start / "app-common", start.parent.parent / "app-common"]
    candidates += _children(start.parent.parent)
    return next((path.resolve() for path in candidates if is_app_common_root(path)), None)


def _children(directory: Path) -> list[Path]:
    try:
        return sorted(path for path in directory.iterdir() if path.is_dir())
    except OSError:
        return []


def python_packages(root: Path) -> dict[str, Path]:
    """Import name to source directory, for every package under packages/ and tools/."""
    packages: dict[str, Path] = {}
    for base in (root / "packages", root / "tools"):
        for src in sorted(base.glob("**/src")) if base.is_dir() else []:
            for item in sorted(src.iterdir()):
                if item.is_dir() and (item / "__init__.py").exists():
                    packages[item.name] = item.resolve()
    return packages


def node_packages(root: Path) -> dict[str, Path]:
    """npm package name to package directory, for every package under packages/ui/."""
    packages: dict[str, Path] = {}
    ui = root / "packages" / "ui"
    for directory in sorted(ui.iterdir()) if ui.is_dir() else []:
        try:
            name = json.loads((directory / "package.json").read_text(encoding="utf-8")).get("name")
        except (OSError, ValueError):
            continue
        if name:
            packages[name] = directory.resolve()
    return packages


def site_packages(project: Path) -> Path | None:
    venv = project / ".venv"
    if not venv.is_dir():
        active = os.environ.get("VIRTUAL_ENV")
        venv = Path(active) if active else venv
    for candidate in sorted((venv / "lib").glob("python*/site-packages"), reverse=True):
        if candidate.is_dir():
            return candidate
    return None


def node_modules(project: Path) -> Path | None:
    directory = project / "node_modules"
    return directory if directory.is_dir() else None


def _bundle_notice(package: str, where: str) -> AppToolsError | None:
    if package != BUNDLE_PACKAGE:
        return None
    return warning(
        f"The app-common devkit bundle now comes from {where}; deployed skills and rules still show the previous one.",
        code="APP_DEV_BUNDLE_SOURCE_CHANGED",
        fix="uv run devkit sync",
    )


def _link_one(
    kind: Kind, installed_dir: Path, package: str, source: Path, dry_run: bool, notices: list[AppToolsError]
) -> LinkAction | None:
    target = installed_dir / package
    backup = installed_dir / f"{package}.bak"
    if target.is_symlink():
        if target.resolve() == source:
            return None
        if not dry_run:
            target.unlink()
            os.symlink(source, target, target_is_directory=True)
        return LinkAction(kind, package, "relinked", source)
    if not target.is_dir():
        return None  # not installed in this project
    if backup.exists():
        notices.append(
            warning(
                f"{backup} already exists; the installed {package} was replaced without a new backup.",
                code="APP_DEV_BACKUP_EXISTS",
            )
        )
        if not dry_run:
            shutil.rmtree(target)
    elif not dry_run:
        shutil.move(target, backup)
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(source, target, target_is_directory=True)
    return LinkAction(kind, package, "linked", source)


def link(project: Path, *, target_path: Path | None = None, dry_run: bool = False) -> LinkResult:
    root = find_app_common_root(project, target_path)
    if root is None:
        raise invalid_input(
            "No app-common checkout was found next to this project (one directory level up or down).",
            code="APP_DEV_ROOT_NOT_FOUND",
            fix="uv run devkit app dev link --target-path <app-common checkout>",
        )
    notices: list[AppToolsError] = []
    actions: list[LinkAction] = []
    venv = site_packages(project)
    if venv is None:
        notices.append(
            notice("No virtual environment was found; Python packages were not linked.", code="APP_DEV_NO_VENV")
        )
    else:
        for package, source in python_packages(root).items():
            action = _link_one("python", venv, package, source, dry_run, notices)
            if action is not None:
                actions.append(action)
                bundle = _bundle_notice(package, str(source))
                if bundle is not None:
                    notices.append(bundle)
    modules = node_modules(project)
    ui_packages = node_packages(root)
    if modules is None:
        if ui_packages:
            notices.append(
                notice(
                    "No node_modules directory was found; UI packages were not linked.", code="APP_DEV_NO_NODE_MODULES"
                )
            )
    else:
        for package, source in ui_packages.items():
            if (modules / package).exists() and not any((source / "dist").glob("*")):
                notices.append(
                    warning(
                        f"{package} has no build output in {source / 'dist'}.",
                        code="APP_DEV_UI_NOT_BUILT",
                        fix=f"just --justfile {root / 'justfile'} build-ui",
                    )
                )
            action = _link_one("node", modules, package, source, dry_run, notices)
            if action is not None:
                actions.append(action)
    return LinkResult(root, actions, dry_run, notices)


def _restore(kind: Kind, backup: Path, original: Path, dry_run: bool) -> LinkAction:
    if not dry_run:
        if original.is_symlink() or original.is_file():
            original.unlink()
        elif original.exists():
            shutil.rmtree(original)
        shutil.move(backup, original)
    return LinkAction(kind, original.name if kind == "python" else _node_name(original), "restored")


def _node_name(path: Path) -> str:
    return f"{path.parent.name}/{path.name}" if path.parent.name.startswith("@") else path.name


def unlink(project: Path, *, dry_run: bool = False) -> LinkResult:
    notices: list[AppToolsError] = []
    actions: list[LinkAction] = []
    venv = site_packages(project)
    if venv is None:
        notices.append(
            notice("No virtual environment was found; no Python package was restored.", code="APP_DEV_NO_VENV")
        )
    else:
        for backup in sorted(venv.glob("*.bak")):
            actions.append(_restore("python", backup, venv / backup.stem, dry_run))
            bundle = _bundle_notice(backup.stem, "the installed app-tools")
            if bundle is not None:
                notices.append(bundle)
    modules = node_modules(project)
    if modules is not None:
        for backup in sorted(modules.glob("**/*.bak")):
            actions.append(_restore("node", backup, backup.with_name(backup.name.removesuffix(".bak")), dry_run))
    return LinkResult(None, actions, dry_run, notices)


def _state(kind: Kind, directory: Path, package: str) -> PackageState:
    path = directory / package
    backup = (directory / f"{package}.bak").exists()
    if path.is_symlink():
        return PackageState(kind, package, "linked", path.resolve(), backup)
    if path.is_dir():
        return PackageState(kind, package, "anomaly" if backup else "installed", None, backup)
    if backup:
        return PackageState(kind, package, "orphan-backup", None, True)
    return PackageState(kind, package, "not-installed")


def status(project: Path, *, target_path: Path | None = None) -> StatusResult:
    root = find_app_common_root(project, target_path)
    states: list[PackageState] = []
    venv = site_packages(project)
    if venv is not None:
        names = set(python_packages(root)) if root else set()
        names.update(backup.stem for backup in venv.glob("app_*.bak"))
        states += [_state("python", venv, name) for name in sorted(names)]
    modules = node_modules(project)
    if modules is not None and root is not None:
        states += [_state("node", modules, name) for name in sorted(node_packages(root))]
    problems = [
        AppToolsError.interaction(
            f"{state.package}: "
            + (
                "both the installed package and its .bak backup exist."
                if state.state == "anomaly"
                else "a .bak backup exists but the package is missing."
            ),
            code="APP_DEV_LINK_ANOMALY",
            fix="uv run devkit app dev unlink",
        )
        for state in states
        if state.state in ("anomaly", "orphan-backup")
    ]
    return StatusResult(root, states, problems)
