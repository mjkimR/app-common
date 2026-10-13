"""Select and read the bundled app-common guides without network access or package imports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from app_tools.errors import AppToolsError, invalid_input, notice, warning
from app_tools.manifests import (
    declared_requirements,
    dependency_name,
    is_app_common_git,
    project_roots,
    read_manifest,
)

SKILL = Path(__file__).resolve().parent / "bundle" / "skills" / "app-common"
CHECKOUT_SKILL = Path("tools/app-tools/src/app_tools/bundle/skills/app-common")
RELEASE_REF = re.compile(r"v?\d+\.\d+\.\d+")
UI_PACKAGE = "@app-common/ui-base"


@dataclass(frozen=True)
class Topic:
    topic: str
    packages: tuple[str, ...]
    path: Path

    def to_dict(self) -> dict[str, Any]:
        return {"topic": self.topic, "packages": list(self.packages), "path": str(self.path)}


@dataclass(frozen=True)
class ProjectState:
    """What the project declares, locks and installs, read from its files only."""

    declared: dict[str, list[str]]
    locked: dict[str, str]
    installed: dict[str, str]
    refs: list[str]

    def packages(self) -> list[str]:
        return sorted({*self.declared, *self.locked, *self.installed})

    def to_dict(self) -> dict[str, Any]:
        return {"declared": self.declared, "locked": self.locked, "installed": self.installed, "refs": self.refs}


@dataclass(frozen=True)
class GuideReport:
    project: Path
    source: Path
    version: str
    state: ProjectState
    topics: list[Topic]
    notices: list[AppToolsError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": str(self.project),
            "source": str(self.source),
            "version": self.version,
            "packages": self.state.to_dict(),
            "topics": [topic.to_dict() for topic in self.topics],
            "notices": [item.to_dict() for item in self.notices],
        }


@dataclass(frozen=True)
class Catalog:
    source: Path
    version: str
    guides: dict[str, Topic]

    @property
    def known_packages(self) -> set[str]:
        return {package for topic in self.guides.values() for package in topic.packages}


def load_catalog(checkout: Path | None = None) -> Catalog:
    """The guides of this installation, or of an app-common checkout for local development."""
    source = (checkout.resolve() / CHECKOUT_SKILL) if checkout else SKILL
    data = read_manifest(source / "catalog.json")
    if not data or not (source / "SKILL.md").is_file():
        raise invalid_input(
            f"No app-common guide bundle at {source}.",
            code="APP_GUIDE_SOURCE_INVALID",
            fix="Pass --source the root of an app-common checkout.",
        )
    guides = {
        name: Topic(name, tuple(entry["packages"]), source / entry["path"]) for name, entry in data["guides"].items()
    }
    return Catalog(source, str(data["version"]), guides)


def inspect_project(root: Path, known: set[str]) -> ProjectState:
    """Declarations, lock entries and installed distributions of ``root`` and its uv workspace members."""
    declared: dict[str, list[str]] = {}
    refs: set[str] = set()
    roots = project_roots(root)
    for folder in roots:
        manifest = read_manifest(folder / "pyproject.toml")
        for spec in declared_requirements(manifest):
            name = dependency_name(spec)
            if name in known:
                declared.setdefault(name, []).append(spec)
                match = re.search(r"app-common(?:\.git)?@([^#\s]+)", spec)
                if match:
                    refs.add(match[1])
        for name, source in manifest.get("tool", {}).get("uv", {}).get("sources", {}).items():
            if dependency_name(name) not in known:
                continue
            for entry in source if isinstance(source, list) else [source]:
                if isinstance(entry, dict) and is_app_common_git(entry.get("git")):
                    refs.add(entry.get("rev") or entry.get("tag") or entry.get("branch") or "un-pinned")
        for node_path in (folder / "package.json", folder / "web/package.json"):
            node = read_manifest(node_path)
            for group in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                for name, spec in node.get(group, {}).items():
                    if name in known:
                        declared.setdefault(name, []).append(str(spec))
    locked: dict[str, str] = {}
    for package in read_manifest(root / "uv.lock").get("package", []):
        name = dependency_name(package.get("name", ""))
        if name in known:
            locked[name] = package.get("version", "unknown")
            git = package.get("source", {}).get("git")
            if git:
                refs.add(git)
    installed: dict[str, str] = {}
    paths = [str(path) for path in (root / ".venv/lib").glob("python*/site-packages") if path.is_dir()]
    for dist in distributions(path=paths):
        name = dependency_name(dist.metadata.get("Name", ""))
        if name in known:
            installed[name] = dist.version
    for folder in roots:
        for node_path in (folder / "node_modules", folder / "web/node_modules"):
            node = read_manifest(node_path / UI_PACKAGE / "package.json")
            if node:
                installed[UI_PACKAGE] = node.get("version", "unknown")
    return ProjectState(declared, locked, installed, sorted(refs))


def _version_notices(catalog: Catalog, state: ProjectState) -> list[AppToolsError]:
    mismatches = {v for values in (state.locked, state.installed) for v in values.values() if v != catalog.version}
    mismatches.update(
        ref for ref in state.refs if RELEASE_REF.fullmatch(ref) and ref.removeprefix("v") != catalog.version
    )
    if not mismatches:
        return []
    return [
        warning(
            f"The guides are version {catalog.version}; the project uses app-common {', '.join(sorted(mismatches))}.",
            code="APP_GUIDE_VERSION_MISMATCH",
            fix="uv run devkit app guide list --source <app-common checkout at the project's ref>",
        )
    ]


def list_guides(project: Path, *, checkout: Path | None = None, all_topics: bool = False) -> GuideReport:
    """The topics for the packages ``project`` declares or installs (every topic with ``all_topics``)."""
    catalog = load_catalog(checkout)
    state = inspect_project(project.resolve(), catalog.known_packages)
    used = {*state.declared, *state.installed}
    topics = [topic for topic in catalog.guides.values() if all_topics or used.intersection(topic.packages)]
    notices = _version_notices(catalog, state)
    if not topics:
        notices.append(
            notice(
                "No app-common package is declared or installed here; setup guides are listed with --all.",
                code="APP_GUIDE_NO_TOPICS",
                fix="uv run devkit app guide list --all",
            )
        )
    return GuideReport(project.resolve(), catalog.source, catalog.version, state, topics, notices)


def show_guide(project: Path, topic: str, *, checkout: Path | None = None) -> tuple[GuideReport, str]:
    """One guide's report and text; a guide for an uninstalled package is readable too."""
    catalog = load_catalog(checkout)
    entry = catalog.guides.get(topic)
    if entry is None:
        raise invalid_input(
            f"Unknown guide topic '{topic}'.",
            code="APP_GUIDE_UNKNOWN_TOPIC",
            fix="uv run devkit app guide list --all",
        )
    state = inspect_project(project.resolve(), catalog.known_packages)
    report = GuideReport(
        project.resolve(), catalog.source, catalog.version, state, [entry], _version_notices(catalog, state)
    )
    return report, entry.path.read_text(encoding="utf-8")
