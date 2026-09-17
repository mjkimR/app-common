"""Machine-readable project diagnostics and health checks for app-common consumers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

from app_tools.commands.dev import find_app_common_root

ALL_PACKAGES = (
    "app-error",
    "app-layer-base",
    "app-testing-base",
    "app-mcp",
    "app-file-storage",
    "app-vector-store",
    "app-http-client",
    "app-ai-catalog",
    "app-prebuilt-user",
    "app-prebuilt-outbox",
    "app-prebuilt-search",
    "app-ui-base",
    "app-tools",
)

PACKAGE_SKILL_RECOMMENDATIONS = {package: "app-common" for package in ALL_PACKAGES}


def inspect_environment(root: Path) -> dict[str, Any]:
    advisories: list[dict[str, str]] = []

    # 1. Manifest
    manifest = root / "pyproject.toml"
    manifest_found = manifest.exists()
    manifest_text = manifest.read_text(encoding="utf-8") if manifest_found else ""

    if not manifest_found:
        advisories.append(
            {
                "code": "MISSING_MANIFEST",
                "message": "pyproject.toml was not found in project root.",
                "fix": "Run 'uv init' or ensure you are in the project root.",
            }
        )

    # 2. Declared packages
    declared_packages = sorted(pkg for pkg in ALL_PACKAGES if pkg in manifest_text)

    # 3. Agent skills
    skills_dir = root / ".agents/skills"
    linked_skills: list[str] = []
    missing_skills: list[str] = []

    if skills_dir.is_dir():
        linked_skills = sorted(d.name for d in skills_dir.iterdir() if d.is_dir() or d.is_symlink())
        for pkg in declared_packages:
            rec_skill = PACKAGE_SKILL_RECOMMENDATIONS.get(pkg)
            if rec_skill and rec_skill not in linked_skills and rec_skill not in missing_skills:
                missing_skills.append(rec_skill)
    else:
        advisories.append(
            {
                "code": "SKILLS_NOT_LINKED",
                "message": "Agent skills directory (.agents/skills) is not linked.",
                "fix": "Declare app-common in apm.yml and run 'apm install'.",
            }
        )

    if missing_skills:
        advisories.append(
            {
                "code": "MISSING_RECOMMENDED_SKILLS",
                "message": f"Recommended skills for declared packages are missing: {', '.join(missing_skills)}.",
                "fix": "Run 'apm install' to provision the configured skills.",
            }
        )

    # 4. Environment (.env) & Database
    env_file = root / ".env"
    has_env = env_file.exists()
    db_url = os.getenv("DATABASE_URL")
    if not db_url and has_env:
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip("'\"")
                    break
        except Exception:
            pass

    db_status = "unconfigured"
    if db_url:
        if db_url.startswith("sqlite"):
            db_status = "sqlite_configured"
        elif "postgres" in db_url:
            db_status = "postgres_configured"
        else:
            db_status = "configured"
    elif "app-layer-base" in declared_packages:
        advisories.append(
            {
                "code": "DATABASE_URL_UNSET",
                "message": "DATABASE_URL is not set in environment or .env.",
                "fix": "Add DATABASE_URL='sqlite+aiosqlite:///app.db' (or postgres) to your .env file.",
            }
        )

    status = (
        "error"
        if any(a["code"] in ("MISSING_MANIFEST", "SKILLS_NOT_LINKED") for a in advisories)
        else ("warning" if advisories else "ok")
    )

    return {
        "status": status,
        "app_common_root": str(root),
        "manifest_found": manifest_found,
        "declared_packages": declared_packages,
        "agent_skills_directory": str(skills_dir) if skills_dir.is_dir() else None,
        "linked_skills": linked_skills,
        "missing_recommended_skills": missing_skills,
        "has_env_file": has_env,
        "database": {"status": db_status, "url_configured": bool(db_url)},
        "mcp": {"declared": "app-mcp" in manifest_text, "next_check": "register tools and expose registry contracts"},
        "advisories": advisories,
    }


@click.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable report.")
def doctor(as_json: bool) -> None:
    """Inspect app-common availability, installed packages, and agent assets."""
    cwd = Path.cwd().resolve()
    root = next(
        (candidate for candidate in (cwd, *cwd.parents) if (candidate / "packages/base/app-layer-base").is_dir()),
        find_app_common_root(cwd) or cwd,
    )

    report = inspect_environment(root)

    if as_json:
        click.echo(json.dumps(report, indent=2, sort_keys=True))
        if report["status"] == "error":
            raise SystemExit(1)
        return

    status_str = report["status"].upper()
    click.echo(f"Project Health Status: {status_str}")
    click.echo(f"  app-common root:   {report['app_common_root'] or 'not found'}")
    click.echo(f"  manifest:          {'found' if report['manifest_found'] else 'not found'}")
    click.echo(f"  declared packages: {', '.join(report['declared_packages']) or 'none'}")
    click.echo(
        f"  agent skills:      {len(report['linked_skills'])} linked ({report['agent_skills_directory'] or 'not linked'})"
    )
    click.echo(f"  database:          {report['database']['status']}")
    click.echo(f"  MCP:               {'declared' if report['mcp']['declared'] else 'not declared'}")

    if report["advisories"]:
        click.echo("\nAdvisories:")
        for adv in report["advisories"]:
            click.echo(f"  [{adv['code']}] {adv['message']}")
            click.echo(f"    Fix: {adv['fix']}")

    if report["status"] == "error":
        raise SystemExit(1)
