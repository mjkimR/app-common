"""Discover existing project manifests and plan commands without executing them."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

TASKS = {"lint", "check", "test"}
PYTHON_TOOLS = {"pytest", "ruff", "pyright"}
NODE_TOOLS = {"vite", "vitest", "svelte-check", "svelte-package", "eslint", "prettier", "tsc", "playwright"}
IGNORED = {"node_modules", "dist", "build", "htmlcov", "__pycache__", "tests", "fixtures", "templates"}


@dataclass(frozen=True)
class Step:
    cwd: Path
    argv: tuple[str, ...]
    label: str


def read_python(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def ancestors(path: Path):
    """Do not inherit configuration across repository boundaries."""
    for directory in (path, *path.parents):
        yield directory
        if (directory / ".git").exists():
            break


def pyright_config(path: Path) -> Path | None:
    for directory in ancestors(path):
        config = directory / "pyrightconfig.json"
        if config.exists():
            return config
        config = directory / "pyproject.toml"
        if config.exists() and "pyright" in read_python(config).get("tool", {}):
            return config
    return None


def discover(root: Path) -> list[Path]:
    """Find project directories, excluding generated trees and nested repositories."""
    found = []
    for current, dirs, files in os.walk(root, followlinks=False):
        directory = Path(current)
        dirs[:] = sorted(
            name
            for name in dirs
            if not name.startswith(".")
            and name not in IGNORED
            and not (directory / name).is_symlink()
            and not (directory / name / ".git").exists()
        )
        if "pyproject.toml" in files or "package.json" in files:
            found.append(directory)
    return found


def is_workspace_member(directory: Path) -> bool:
    for parent in ancestors(directory):
        config = parent / "pyproject.toml"
        if not config.exists():
            continue
        workspace = read_python(config).get("tool", {}).get("uv", {}).get("workspace")
        if workspace is None:
            continue
        if directory == parent:
            return True
        members = {p.resolve() for pattern in workspace.get("members", []) for p in parent.glob(pattern)}
        excluded = {p.resolve() for pattern in workspace.get("exclude", []) for p in parent.glob(pattern)}
        return directory in members and directory not in excluded
    return True


def python_step(directory: Path, tool: str, args: list[str]) -> Step:
    label = f"{tool} {args[0]}" if tool == "ruff" and args else tool
    return Step(directory, ("uv", "run", "--no-active", "--no-sync", tool, *args), label)


def architecture_enabled(directory: Path) -> bool:
    """Use the nearest explicit setting, without crossing a repository boundary."""
    for parent in ancestors(directory):
        config = parent / "pyproject.toml"
        if config.exists():
            settings = read_python(config).get("tool", {}).get("app-tools", {})
            if "check-arch" in settings:
                value = settings["check-arch"]
                if not isinstance(value, bool):
                    raise ValueError(f"{config}: tool.app-tools.check-arch must be a boolean")
                return value
    return False


def plan_task(root: Path, task: str, fix: bool = False) -> tuple[list[Step], list[str]]:
    steps: list[Step] = []
    skipped: list[str] = []
    for directory in discover(root):
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            data = read_python(pyproject)
            if "project" in data and (directory == root or is_workspace_member(directory)):
                if task == "lint":
                    steps.append(python_step(directory, "ruff", ["format", *([] if fix else ["--check"]), "."]))
                    steps.append(python_step(directory, "ruff", ["check", *(["--fix"] if fix else []), "."]))
                    if architecture_enabled(directory):
                        target = "src" if (directory / "src").is_dir() else "."
                        steps.append(
                            Step(directory, (sys.executable, "-m", "app_tools.cli", "check-arch", target), "check-arch")
                        )
                elif task == "test":
                    pytest = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
                    if (directory / "tests").exists() or pytest or (directory / "pytest.ini").exists():
                        steps.append(python_step(directory, "pytest", []))
                    else:
                        skipped.append(f"{directory}: no pytest suite configured")
                else:
                    config = pyright_config(directory)
                    if config:
                        args = ["--project", str(config)]
                        # A shared workspace config must not check every other package again.
                        if config.parent != directory:
                            args.append(str(directory / "src" if (directory / "src").exists() else directory))
                        steps.append(python_step(directory, "pyright", args))
                    else:
                        skipped.append(f"{directory}: no Pyright configuration")
        package = directory / "package.json"
        if package.exists():
            scripts = json.loads(package.read_text()).get("scripts", {})
            # Never guess whether a project's lint script accepts --fix.
            script = "lint:fix" if fix else task
            if script in scripts:
                steps.append(Step(directory, ("npm", "run", script), f"npm {script}"))
            elif fix and "lint" in scripts:
                raise ValueError(f"{directory}: lint --fix requires a lint:fix script in package.json")
            else:
                skipped.append(f"{directory}: no npm {script} script")
    return steps, skipped


def plan_tool(root: Path, tool: str, args: tuple[str, ...]) -> Step:
    if tool in PYTHON_TOOLS:
        return python_step(root, tool, list(args))
    if tool in NODE_TOOLS:
        for directory in ancestors(root):
            executable = directory / "node_modules" / ".bin" / tool
            if executable.is_file():
                return Step(root, (str(executable), *args), tool)
        raise ValueError(f"Local {tool} executable not found; install project dependencies first")
    if tool in {"npm", "uv"}:
        return Step(root, (tool, *args), tool)
    raise ValueError(f"Unknown tool {tool!r}; use 'app-tools run -- {tool} ...' for arbitrary commands")
