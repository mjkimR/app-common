"""Check that a consumer project is set up for app-common: packages, devkit bundle and database URL."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devkit.advisory import AdvisoryError
from devkit_dist.features.project.repositories.receipt import load_receipt

from app_tools.errors import AppToolsError, invalid_input, notice, warning
from app_tools.guide import load_catalog
from app_tools.manifests import declared_requirements, dependency_name, project_roots, read_manifest
from app_tools.update import apm_superseded

BUNDLE = "app-common"
TOOLING_PACKAGES = {"app-tools", "@app-common/ui-base"}  # packages that raise no devkit.advisory errors


@dataclass(frozen=True)
class DoctorReport:
    project: Path
    packages: list[str]
    bundle: str  # "synced", "not-synced" or "unreadable"
    database: str  # "sqlite", "postgres", "other" or "unset"
    problems: list[AdvisoryError]
    notices: list[AppToolsError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": str(self.project),
            "packages": self.packages,
            "bundle": self.bundle,
            "database": self.database,
            "errors": [problem.to_dict() for problem in self.problems],
            "notices": [item.to_dict() for item in self.notices],
        }


def _database_url(project: Path) -> str | None:
    url = os.environ.get("DATABASE_URL")
    env_file = project / ".env"
    if url or not env_file.is_file():
        return url
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return None


def _database_kind(url: str | None) -> str:
    if not url:
        return "unset"
    if url.startswith("sqlite"):
        return "sqlite"
    return "postgres" if "postgres" in url else "other"


def diagnose(project: Path) -> DoctorReport:
    project = project.resolve()
    if not (project / "pyproject.toml").is_file():
        raise invalid_input(
            f"{project} has no pyproject.toml.",
            code="APP_MANIFEST_MISSING",
            fix="Run the command from the project root.",
        )
    known = load_catalog().known_packages
    packages = sorted(
        {
            name
            for folder in project_roots(project)
            for spec in declared_requirements(read_manifest(folder / "pyproject.toml"))
            if (name := dependency_name(spec)) in known
        }
    )
    problems: list[AdvisoryError] = []
    notices: list[AppToolsError] = []
    try:
        receipt = load_receipt(project)
    except AdvisoryError as exc:  # devkit's ReceiptError carries its own advisory
        problems.append(exc)
        bundle = "unreadable"
    else:
        synced = receipt is not None and any(record.bundle == BUNDLE for record in receipt.packages)
        bundle = "synced" if synced else "not-synced"
        if not synced:
            problems.append(
                AppToolsError.auto_fix(
                    "The app-common devkit bundle is not deployed: the skill, rules and guidance are missing.",
                    code="APP_BUNDLE_NOT_SYNCED",
                    fix="uv run devkit sync",
                )
            )
        runtime = set(packages) - TOOLING_PACKAGES
        if receipt is not None and runtime and "python" not in receipt.selection.presets.get("advisory", ()):
            notices.append(
                notice(
                    "app-common errors are devkit.advisory errors; the advisory library guide is not deployed.",
                    code="APP_ADVISORY_GUIDE_MISSING",
                    fix="uv run devkit add advisory:python",
                )
            )
    apm = apm_superseded(project)
    if apm is not None:
        notices.append(apm)
    database = _database_kind(_database_url(project))
    if database == "unset" and "app-layer-base" in packages:
        notices.append(
            warning(
                "DATABASE_URL is set neither in the environment nor in .env.",
                code="APP_DATABASE_URL_UNSET",
                fix="Add DATABASE_URL=sqlite+aiosqlite:///./app.db (or a PostgreSQL URL) to .env.",
            )
        )
    return DoctorReport(project, packages, bundle, database, problems, notices)
