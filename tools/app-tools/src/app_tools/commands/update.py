"""Update app-common Git dependencies in a downstream project's uv manifest."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

import click

GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/mjkimR/app-common/releases/latest"
APP_COMMON_REF_PATTERN = re.compile(
    r"(git\+https://github\.com/mjkimR/app-common\.git@)([^#\"'\s]+)(#subdirectory=[^\"'\s]+)"
)


def latest_release_tag() -> str:
    """Return the latest published app-common release tag."""
    request = Request(GITHUB_LATEST_RELEASE_URL, headers={"Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag:
        raise click.ClickException("GitHub did not return a latest app-common release tag.")
    return tag


def update_app_common_refs(manifest_text: str, ref: str) -> tuple[str, int]:
    """Replace every app-common Git ref in dependency URLs with *ref*."""
    return APP_COMMON_REF_PATTERN.subn(lambda match: f"{match.group(1)}{ref}{match.group(3)}", manifest_text)


def run_uv(*args: str, cwd: Path) -> None:
    """Run an uv command in the consumer project and surface failures as CLI errors."""
    try:
        subprocess.run(["uv", *args], cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise click.ClickException("uv is required to lock and sync dependencies, but was not found on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(f"uv {' '.join(args)} failed with exit code {exc.returncode}.") from exc


@click.command("update")
@click.option("--ref", "release_ref", help="Release tag or Git ref to install. Defaults to the latest GitHub release.")
@click.option("--dry-run", is_flag=True, help="Show the selected ref without changing files or running uv.")
@click.option("--no-sync", is_flag=True, help="Update pyproject.toml and uv.lock, but do not install into .venv.")
def update(release_ref: str | None, dry_run: bool, no_sync: bool) -> None:
    """Update app-common package dependencies; manage skills separately with APM."""
    project_root = Path.cwd().resolve()
    manifest = project_root / "pyproject.toml"
    if not manifest.is_file():
        raise click.ClickException("pyproject.toml was not found in the current directory.")

    ref = release_ref or latest_release_tag()
    original = manifest.read_text(encoding="utf-8")
    updated, changes = update_app_common_refs(original, ref)
    if changes == 0:
        raise click.ClickException(
            "No app-common Git dependency URLs were found. Expected git+https://github.com/mjkimR/app-common.git@<ref>#subdirectory=..."
        )

    click.echo(f"app-common ref: {ref}")
    click.echo(f"dependencies to update: {changes}")
    if dry_run:
        click.echo("Dry run: no files were changed and uv was not run.")
        return

    manifest.write_text(updated, encoding="utf-8")
    run_uv("lock", cwd=project_root)
    if not no_sync:
        run_uv("sync", cwd=project_root)
    click.echo("app-common packages updated. Manage skill refs and installation separately with APM.")
