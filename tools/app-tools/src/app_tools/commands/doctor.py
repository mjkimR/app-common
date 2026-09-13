"""Machine-readable project diagnostics for app-common consumers."""

import json
from pathlib import Path

import click

from app_tools.commands.dev import find_app_common_root


@click.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable report.")
def doctor(as_json: bool) -> None:
    """Inspect app-common availability, installed packages, and agent assets."""
    cwd = Path.cwd().resolve()
    root = next(
        (candidate for candidate in (cwd, *cwd.parents) if (candidate / "packages/base/app-layer-base").is_dir()),
        find_app_common_root(cwd),
    )
    manifest = (root or cwd) / "pyproject.toml"
    manifest_text = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    report = {
        "app_common_root": str(root) if root else None,
        "manifest_found": manifest.exists(),
        "declared_packages": sorted(
            package
            for package in (
                "app-layer-base",
                "app-error",
                "app-testing-base",
                "app-mcp",
                "app-file-storage",
                "app-vector-store",
            )
            if package in manifest_text
        ),
        "agent_skills_directory": str((root or cwd) / ".agents/skills")
        if ((root or cwd) / ".agents/skills").is_dir()
        else None,
        "mcp": {"declared": "app-mcp" in manifest_text, "next_check": "register tools and expose registry contracts"},
    }
    if as_json:
        click.echo(json.dumps(report, sort_keys=True))
        return
    click.echo(f"app-common root: {report['app_common_root'] or 'not found'}")
    click.echo(f"manifest: {'found' if report['manifest_found'] else 'not found'}")
    click.echo(f"declared packages: {', '.join(report['declared_packages']) or 'none'}")
    click.echo(f"agent skills: {report['agent_skills_directory'] or 'not linked'}")
    click.echo(f"MCP: {'declared' if report['mcp']['declared'] else 'not declared'}")
