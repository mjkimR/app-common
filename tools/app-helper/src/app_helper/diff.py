import hashlib
import tempfile
from pathlib import Path

import click

from app_helper import git
from app_helper.clipboard import copy_file
from app_helper.errors import handle_cli_errors


def _diff_path(diff: str, filename: str | None) -> Path:
    if filename:
        if "." not in Path(filename).name:
            filename = f"{filename}.txt"
    else:
        digest = hashlib.sha1(diff.encode("utf-8")).hexdigest()[:7]
        filename = f"diff-{digest}.txt"

    return Path(tempfile.gettempdir()) / filename


def write_diff_file(filename: str | None = None, stage: bool = True) -> Path:
    """Dump the staged diff to a temp file and return its path."""
    git.ensure_repo()
    if stage:
        git.stage_all()

    try:
        diff = git.get_diff(git.STAGED)
    except ValueError as e:
        raise ValueError("No staged changes found.") from e

    path = _diff_path(diff, filename)
    path.write_text(f"{diff}\n", encoding="utf-8")
    return path


@click.command("copy-diff")
@click.argument("filename", required=False)
@click.option(
    "--no-add",
    is_flag=True,
    default=False,
    help="Skip `git add .` and use whatever is already staged.",
)
@handle_cli_errors
def copy_diff(filename: str | None, no_add: bool):
    """Write the staged diff to a temp file and copy that file to the clipboard.

    Stages everything with `git add .` first, so untracked files are included. The clipboard
    holds the file itself, so it can be pasted as an attachment into a chat UI.
    """
    path = write_diff_file(filename=filename, stage=not no_add)

    try:
        copy_file(path)
    except RuntimeError as e:
        click.echo(f"⚠️  {e}")
        click.echo(f"Path: {path}")
        return

    click.echo("✅ Copied diff file to clipboard!")
    click.echo(f"Path: {path}")
