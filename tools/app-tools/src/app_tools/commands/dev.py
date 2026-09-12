from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import click

APP_COMMON_SENTINEL = Path("packages") / "base" / "app-layer-base"


def is_app_common_root(path: Path) -> bool:
    """Check if the given directory is the app-common repository root."""
    return (path / APP_COMMON_SENTINEL).is_dir()


def find_app_common_root(search_start: Path, target_path: str | None = None) -> Path | None:
    """Find the app-common root directory with -1 to +1 depth exploration.

    Candidates checked in order:
    1. Explicit target_path (if provided)
    2. Current directory (search_start)
    3. Same level: search_start.parent / "app-common"
    4. Sibling directories under search_start.parent
    5. Subdirectory (+1 depth): search_start / "app-common"
    6. Grandparent level (-1 depth): search_start.parent.parent / "app-common"
    7. Sibling directories under search_start.parent.parent
    """
    if target_path:
        p = Path(target_path).resolve()
        if is_app_common_root(p):
            return p
        return None

    resolved_start = search_start.resolve()

    # 1. Search start itself
    if is_app_common_root(resolved_start):
        return resolved_start

    # 2. Same level '../app-common'
    same_level = resolved_start.parent / "app-common"
    if is_app_common_root(same_level):
        return same_level.resolve()

    # 3. Siblings under search_start.parent
    try:
        for sibling in resolved_start.parent.iterdir():
            if sibling.is_dir() and is_app_common_root(sibling):
                return sibling.resolve()
    except (PermissionError, FileNotFoundError):
        pass

    # 4. Child (+1 depth): search_start / "app-common"
    child = resolved_start / "app-common"
    if is_app_common_root(child):
        return child.resolve()

    # 5. Grandparent level (-1 depth): search_start.parent.parent / "app-common"
    grandparent_same = resolved_start.parent.parent / "app-common"
    if is_app_common_root(grandparent_same):
        return grandparent_same.resolve()

    # 6. Siblings under search_start.parent.parent
    try:
        for sibling in resolved_start.parent.parent.iterdir():
            if sibling.is_dir() and is_app_common_root(sibling):
                return sibling.resolve()
    except (PermissionError, FileNotFoundError):
        pass

    return None


def discover_python_packages(app_common_root: Path) -> dict[str, Path]:
    """Discover Python packages provided by app-common.

    Scans packages/*/*/src/* and tools/*/src/*.
    Returns mapping of package_name -> absolute source path.
    """
    packages: dict[str, Path] = {}
    search_dirs = [
        app_common_root / "packages",
        app_common_root / "tools",
    ]

    for base_dir in search_dirs:
        if not base_dir.is_dir():
            continue
        for src_dir in base_dir.glob("**/src"):
            if not src_dir.is_dir():
                continue
            for item in src_dir.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    packages[item.name] = item.resolve()

    return packages


def discover_node_packages(app_common_root: Path) -> dict[str, Path]:
    """Discover Node/NPM packages provided by app-common (e.g. packages/ui/*).

    Returns mapping of npm_package_name -> package root path.
    """
    packages: dict[str, Path] = {}
    ui_dir = app_common_root / "packages" / "ui"
    if not ui_dir.is_dir():
        return packages

    for pkg_dir in ui_dir.iterdir():
        if not pkg_dir.is_dir():
            continue
        pkg_json = pkg_dir / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                name = data.get("name")
                if name:
                    packages[name] = pkg_dir.resolve()
            except (json.JSONDecodeError, OSError):
                continue

    return packages


def find_site_packages(project_root: Path) -> Path | None:
    """Locate site-packages directory in project venv or active virtualenv."""
    venv_dir: Path | None = None

    # Check local .venv first (standard for uv projects)
    local_venv = project_root / ".venv"
    if local_venv.is_dir():
        venv_dir = local_venv
    else:
        # Fallback to active VIRTUAL_ENV env var
        env_venv = os.environ.get("VIRTUAL_ENV")
        if env_venv:
            candidate = Path(env_venv)
            if candidate.is_dir():
                venv_dir = candidate

    if not venv_dir or not venv_dir.is_dir():
        return None

    # POSIX: lib/pythonX.Y/site-packages
    lib_dir = venv_dir / "lib"
    if lib_dir.is_dir():
        for py_dir in sorted(lib_dir.glob("python*"), reverse=True):
            sp = py_dir / "site-packages"
            if sp.is_dir():
                return sp

    # Windows: Lib/site-packages
    win_sp = venv_dir / "Lib" / "site-packages"
    if win_sp.is_dir():
        return win_sp

    return None


def find_node_modules(project_root: Path) -> Path | None:
    """Locate node_modules directory in project root."""
    nm = project_root / "node_modules"
    return nm if nm.is_dir() else None


@click.group("dev")
def dev():
    """Manage local development links to app-common packages."""
    pass


@dev.command("link")
@click.option(
    "--target-path",
    "-t",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Explicit path to the app-common repository root.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview actions without modifying files or symlinks.",
)
def link_cmd(target_path: str | None, dry_run: bool):
    """Symlink installed app-common packages to local source directories."""
    cwd = Path.cwd()
    app_common_root = find_app_common_root(cwd, target_path)

    if not app_common_root:
        click.echo(
            click.style(
                "Error: Could not locate app-common repository root (checked -1 to +1 depth).\n"
                "Please specify --target-path <path_to_app_common>.",
                fg="red",
            ),
            err=True,
        )
        sys.exit(1)

    click.echo(click.style(f"Using app-common at: {app_common_root}", fg="cyan", bold=True))

    py_packages = discover_python_packages(app_common_root)
    node_packages = discover_node_packages(app_common_root)

    site_packages = find_site_packages(cwd)
    node_modules = find_node_modules(cwd)

    linked_count = 0

    # 1. Link Python packages
    click.echo("\n[Python Packages]")
    if not site_packages:
        click.echo(
            click.style(
                "  No virtual environment (.venv) found. Skipping Python linking.",
                fg="yellow",
            )
        )
    else:
        click.echo(f"  site-packages: {site_packages}")
        for pkg_name, src_path in sorted(py_packages.items()):
            target_installed = site_packages / pkg_name
            bak_path = site_packages / f"{pkg_name}.bak"

            if target_installed.is_symlink():
                current_target = target_installed.resolve()
                if current_target == src_path:
                    click.echo(f"  already linked: {pkg_name} -> {src_path}")
                    continue
                else:
                    click.echo(f"  updating link: {pkg_name} ({current_target} -> {src_path})")
                    if not dry_run:
                        target_installed.unlink()
                        os.symlink(src_path, target_installed, target_is_directory=True)
                    linked_count += 1
                    continue

            if target_installed.is_dir():
                # Back up existing installed directory
                if not bak_path.exists():
                    click.echo(f"  backing up: {pkg_name} -> {pkg_name}.bak")
                    if not dry_run:
                        shutil.move(target_installed, bak_path)
                else:
                    click.echo(
                        click.style(
                            f"  warning: backup {pkg_name}.bak already exists. Replacing installed directory.",
                            fg="yellow",
                        )
                    )
                    if not dry_run:
                        shutil.rmtree(target_installed)

                click.echo(click.style(f"  linking: {pkg_name} -> {src_path}", fg="green"))
                if not dry_run:
                    os.symlink(src_path, target_installed, target_is_directory=True)
                linked_count += 1
            else:
                # Package is not installed in the venv
                pass

    # 2. Link Node packages
    click.echo("\n[Node/NPM Packages]")
    if not node_modules:
        click.echo(click.style("  No node_modules directory found. Skipping Node linking.", fg="yellow"))
    else:
        for pkg_name, src_path in sorted(node_packages.items()):
            target_installed = node_modules / pkg_name
            bak_path = node_modules / f"{pkg_name}.bak"

            if target_installed.is_symlink():
                current_target = target_installed.resolve()
                if current_target == src_path:
                    click.echo(f"  already linked: {pkg_name} -> {src_path}")
                    continue
                else:
                    click.echo(f"  updating link: {pkg_name} ({current_target} -> {src_path})")
                    if not dry_run:
                        target_installed.unlink()
                        os.symlink(src_path, target_installed, target_is_directory=True)
                    linked_count += 1
                    continue

            if target_installed.is_dir():
                if not bak_path.exists():
                    click.echo(f"  backing up: {pkg_name} -> {pkg_name}.bak")
                    if not dry_run:
                        shutil.move(target_installed, bak_path)
                else:
                    click.echo(
                        click.style(
                            f"  warning: backup {pkg_name}.bak already exists. Replacing installed directory.",
                            fg="yellow",
                        )
                    )
                    if not dry_run:
                        shutil.rmtree(target_installed)

                click.echo(click.style(f"  linking: {pkg_name} -> {src_path}", fg="green"))
                if not dry_run:
                    target_installed.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(src_path, target_installed, target_is_directory=True)
                linked_count += 1

    click.echo(
        click.style(
            f"\nDone. {linked_count} package(s) linked in development mode.",
            fg="green",
            bold=True,
        )
    )
    if dry_run:
        click.echo(click.style("(Dry-run mode: no changes were made)", fg="yellow"))


@dev.command("unlink")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview actions without restoring files or removing symlinks.",
)
def unlink_cmd(dry_run: bool):
    """Restore original packages and remove local development symlinks."""
    cwd = Path.cwd()
    site_packages = find_site_packages(cwd)
    node_modules = find_node_modules(cwd)

    restored_count = 0

    # 1. Restore Python packages
    click.echo("\n[Python Packages]")
    if not site_packages:
        click.echo(click.style("  No virtual environment (.venv) found.", fg="yellow"))
    else:
        # Search for .bak files in site-packages
        for bak in sorted(site_packages.glob("*.bak")):
            original_name = bak.stem  # e.g., app_layer_base
            original_path = site_packages / original_name

            if original_path.is_symlink():
                click.echo(f"  removing symlink: {original_name}")
                if not dry_run:
                    original_path.unlink()
            elif original_path.exists():
                click.echo(
                    click.style(
                        f"  warning: {original_name} exists and is not a symlink. Removing to restore backup.",
                        fg="yellow",
                    )
                )
                if not dry_run:
                    if original_path.is_dir():
                        shutil.rmtree(original_path)
                    else:
                        original_path.unlink()

            click.echo(click.style(f"  restoring backup: {bak.name} -> {original_name}", fg="green"))
            if not dry_run:
                shutil.move(bak, original_path)
            restored_count += 1

    # 2. Restore Node packages
    click.echo("\n[Node/NPM Packages]")
    if not node_modules:
        click.echo(click.style("  No node_modules directory found.", fg="yellow"))
    else:
        for bak in sorted(node_modules.glob("**/*.bak")):
            rel = bak.relative_to(node_modules)
            original_rel_str = str(rel)[:-4]  # strip '.bak'
            original_path = node_modules / original_rel_str

            if original_path.is_symlink():
                click.echo(f"  removing symlink: {original_rel_str}")
                if not dry_run:
                    original_path.unlink()
            elif original_path.exists():
                if not dry_run:
                    if original_path.is_dir():
                        shutil.rmtree(original_path)
                    else:
                        original_path.unlink()

            click.echo(
                click.style(
                    f"  restoring backup: {bak.name} -> {original_path.name}",
                    fg="green",
                )
            )
            if not dry_run:
                shutil.move(bak, original_path)
            restored_count += 1

    click.echo(
        click.style(
            f"\nDone. {restored_count} package(s) restored to original state.",
            fg="green",
            bold=True,
        )
    )
    if dry_run:
        click.echo(click.style("(Dry-run mode: no changes were made)", fg="yellow"))


@dev.command("status")
@click.option(
    "--target-path",
    "-t",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Explicit path to the app-common repository root.",
)
def status_cmd(target_path: str | None):
    """Show status of app-common packages in the current project."""
    cwd = Path.cwd()
    app_common_root = find_app_common_root(cwd, target_path)

    if app_common_root:
        click.echo(click.style(f"app-common root: {app_common_root}\n", fg="cyan", bold=True))
        py_packages = discover_python_packages(app_common_root)
        node_packages = discover_node_packages(app_common_root)
    else:
        click.echo(
            click.style(
                "app-common root: Not detected (checked -1 to +1 depth)\n",
                fg="yellow",
            )
        )
        py_packages = {}
        node_packages = {}

    site_packages = find_site_packages(cwd)
    node_modules = find_node_modules(cwd)

    # 1. Python Status
    click.echo("[Python Packages]")
    if not site_packages:
        click.echo("  No virtual environment (.venv) detected.")
    else:
        all_py_names = set(py_packages.keys())
        for bak in site_packages.glob("app_*.bak"):
            all_py_names.add(bak.stem)

        for pkg_name in sorted(all_py_names):
            pkg_path = site_packages / pkg_name
            bak_path = site_packages / f"{pkg_name}.bak"

            if pkg_path.is_symlink():
                target = pkg_path.resolve()
                bak_info = " (backup: yes)" if bak_path.exists() else " (backup: NO)"
                click.echo(click.style(f"  [LINKED]        {pkg_name}", fg="green") + f" -> {target}{bak_info}")
            elif pkg_path.is_dir():
                if bak_path.exists():
                    click.echo(
                        click.style(
                            f"  [ANOMALY]       {pkg_name} (installed AND .bak exists)",
                            fg="yellow",
                        )
                    )
                else:
                    click.echo(f"  [NORMAL]        {pkg_name} (installed)")
            elif bak_path.exists():
                click.echo(
                    click.style(
                        f"  [ORPHAN_BAK]    {pkg_name}.bak exists, but package is missing",
                        fg="yellow",
                    )
                )
            else:
                click.echo(f"  [NOT INSTALLED] {pkg_name}")

    # 2. Node Status
    click.echo("\n[Node/NPM Packages]")
    if not node_modules:
        click.echo("  No node_modules directory detected.")
    else:
        for pkg_name in sorted(node_packages.keys()):
            pkg_path = node_modules / pkg_name
            bak_path = node_modules / f"{pkg_name}.bak"

            if pkg_path.is_symlink():
                target = pkg_path.resolve()
                bak_info = " (backup: yes)" if bak_path.exists() else " (backup: NO)"
                click.echo(click.style(f"  [LINKED]        {pkg_name}", fg="green") + f" -> {target}{bak_info}")
            elif pkg_path.is_dir():
                if bak_path.exists():
                    click.echo(
                        click.style(
                            f"  [ANOMALY]       {pkg_name} (installed AND .bak exists)",
                            fg="yellow",
                        )
                    )
                else:
                    click.echo(f"  [NORMAL]        {pkg_name} (installed)")
            elif bak_path.exists():
                click.echo(
                    click.style(
                        f"  [ORPHAN_BAK]    {pkg_name}.bak exists, but package is missing",
                        fg="yellow",
                    )
                )
            else:
                click.echo(f"  [NOT INSTALLED] {pkg_name}")
