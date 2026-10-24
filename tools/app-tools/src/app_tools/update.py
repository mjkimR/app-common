"""Move a consumer project's app-common dependencies, and the devkit pins they need, to one app-common commit."""

from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import tomlkit
from tomlkit.items import AoT, Array, InlineTable, Table

from app_tools.errors import AppToolsError, invalid_input, notice, step_failed, unavailable, warning
from app_tools.manifests import declared_requirements, dependency_name, is_app_common_git, project_roots

APP_COMMON_REMOTE = "https://github.com/mjkimR/app-common"
RAW_PYPROJECT = "https://raw.githubusercontent.com/mjkimR/app-common/{sha}/pyproject.toml"
REQUIREMENT_URL = re.compile(
    r"(git\+https://github\.com/mjkimR/app-common(?:\.git)?@)([^#\"'\s]+)(#subdirectory=[^\"'\s]+)"
)
COMMIT = re.compile(r"[0-9a-f]{40}")
REF_KEYS = ("rev", "tag", "branch")
# The harness, advisory library and distribution API app-tools imports are pinned
# by app-common at one devkit revision.
DEVKIT_PACKAGES = ("devkit-agt", "devkit-advisory", "devkit-dist")

Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]
Fetcher = Callable[[str], bytes]


def run_command(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), cwd=cwd, capture_output=True, text=True, check=False)


def fetch_url(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:
        return response.read()


@dataclass(frozen=True)
class ManifestChange:
    path: Path
    app_common: int  # dependency URLs and uv sources moved to the commit
    devkit: bool  # a devkit source (or its direct declaration) was set to app-common's pin

    def to_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "app_common": self.app_common, "devkit": self.devkit}


@dataclass(frozen=True)
class UpdateResult:
    ref: str
    commit: str
    pins: dict[str, dict[str, Any]]  # app-common's uv source per DEVKIT_PACKAGES name it pins
    changes: list[ManifestChange]
    commands: list[str]
    dry_run: bool
    notices: list[AppToolsError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "commit": self.commit,
            "devkit": self.pins.get("devkit-agt"),
            "devkit_advisory": self.pins.get("devkit-advisory"),
            "manifests": [change.to_dict() for change in self.changes],
            "commands": self.commands,
            "dry_run": self.dry_run,
            "notices": [item.to_dict() for item in self.notices],
        }


def resolve_commit(ref: str, run: Runner, cwd: Path) -> str:
    """The full commit SHA of ``ref`` (a commit, branch or tag) in the app-common repository."""
    if COMMIT.fullmatch(ref):
        return ref
    command = ["git", "ls-remote", APP_COMMON_REMOTE, f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"]
    completed = run(command, cwd)
    if completed.returncode != 0:
        raise unavailable(
            f"Cannot reach {APP_COMMON_REMOTE} to resolve '{ref}'.",
            *completed.stderr.strip().splitlines()[-5:],
            code="APP_UPDATE_REMOTE_UNAVAILABLE",
        )
    refs: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        sha, _, name = line.partition("\t")
        if name:
            refs[name] = sha
    for name in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"):
        if name in refs:
            return refs[name]
    raise invalid_input(
        f"'{ref}' is neither a branch, a tag nor a full commit SHA of app-common.",
        code="APP_UPDATE_REF_NOT_FOUND",
        fix="uv run devkit app update --ref <branch, tag or 40-character commit>",
    )


def devkit_pins(commit: str, fetch: Fetcher) -> dict[str, dict[str, Any]]:
    """The uv sources app-common pins at ``commit`` for ``DEVKIT_PACKAGES``; empty for a commit from before devkit."""
    url = RAW_PYPROJECT.format(sha=commit)
    try:
        manifest = tomllib.loads(fetch(url).decode("utf-8"))
    except (URLError, OSError) as exc:
        raise unavailable(f"Cannot read {url}: {exc}", code="APP_UPDATE_REMOTE_UNAVAILABLE") from exc
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise unavailable(f"{url} is not a TOML document: {exc}", code="APP_UPDATE_REMOTE_UNAVAILABLE") from exc
    sources = manifest.get("tool", {}).get("uv", {}).get("sources", {})
    return {name: dict(sources[name]) for name in DEVKIT_PACKAGES if isinstance(sources.get(name), dict)}


def _pin_entry(entry: Any, commit: str) -> bool:
    if not isinstance(entry, (InlineTable, Table)) or not is_app_common_git(entry.get("git")):
        return False
    for key in REF_KEYS:
        if key in entry:
            del entry[key]
    entry["rev"] = commit
    return True


def _devkit_table(source: dict[str, Any]) -> InlineTable:
    table = tomlkit.inline_table()
    table.update(source)
    return table


def rewrite_manifest(
    text: str, commit: str, pins: dict[str, dict[str, Any]], *, declares_devkit: bool
) -> tuple[str, int, bool]:
    """``text`` with every app-common reference at ``commit`` and, where a devkit package is pinned, its source.

    ``declares_devkit`` marks the manifest that must pin and declare every package of ``pins`` (the
    workspace root of a project with app-common dependencies); any other manifest that already pins one
    is kept in step.
    """
    text, count = REQUIREMENT_URL.subn(lambda match: f"{match[1]}{commit}{match[3]}", text)
    document = tomlkit.parse(text)
    sources = document.get("tool", {}).get("uv", {}).get("sources")
    if sources is not None:
        for name, source in list(sources.items()):
            if name in DEVKIT_PACKAGES:
                continue
            entries = source if isinstance(source, (Array, AoT, list)) else [source]
            count += sum(_pin_entry(entry, commit) for entry in entries)
    pins = dict(pins)
    anchor = pins.get("devkit-agt")
    if anchor is not None and sources is not None:
        # Consumers can also select core, CLI, spec, catalog or MCP from the same
        # repository. Their exact-version dependencies must share the harness ref.
        for name, source in sources.items():
            if (
                name in pins
                or not name.startswith("devkit-")
                or not isinstance(source, (InlineTable, Table))
                or str(source.get("git", "")).rstrip("/").removesuffix(".git")
                != str(anchor.get("git", "")).rstrip("/").removesuffix(".git")
            ):
                continue
            aligned = {key: value for key, value in source.items() if key not in REF_KEYS}
            aligned["git"] = anchor["git"]
            aligned.update({key: anchor[key] for key in REF_KEYS if key in anchor})
            pins[name] = aligned
    devkit = False
    for name, source in pins.items():
        if not ((sources is not None and name in sources) or declares_devkit):
            continue
        if sources is None:
            tool = document.setdefault("tool", tomlkit.table(is_super_table=True))
            uv = tool.setdefault("uv", tomlkit.table(is_super_table=True))
            sources = uv.setdefault("sources", tomlkit.table())
        current = sources.get(name)
        if current is None or dict(current) != source:
            sources[name] = _devkit_table(source)
            devkit = True
        # A project's source applies only to its direct dependencies, so the pin is declared too; a
        # declared devkit that nothing brings from Git would otherwise resolve from PyPI, where an
        # unrelated project owns the name. The revision is app-common's: uv rejects two URLs for one package.
        if declares_devkit and name not in {dependency_name(spec) for spec in declared_requirements(document)}:
            groups = document.setdefault("dependency-groups", tomlkit.table())
            groups.setdefault("dev", tomlkit.array()).append(name)
            devkit = True
    return tomlkit.dumps(document), count, devkit


def apm_superseded(root: Path) -> AppToolsError | None:
    apm = root / "apm.yml"
    if not apm.is_file() or "mjkimR/app-common" not in apm.read_text(encoding="utf-8", errors="replace"):
        return None
    return warning(
        "apm.yml still installs the app-common skill; devkit now deploys it from app-tools.",
        "Remove the app-common entry from apm.yml (and apm.yml, apm.lock.yaml and apm_modules/ when it was the only one).",
        "Delete .agents/skills/app-common and .claude/skills/app-common, which APM installed.",
        code="APP_APM_SUPERSEDED",
        fix="uv run devkit sync",
    )


def update_project(
    root: Path,
    ref: str = "main",
    *,
    dry_run: bool = False,
    sync: bool = True,
    run: Runner | None = None,
    fetch: Fetcher | None = None,
) -> UpdateResult:
    """Pin every app-common dependency of ``root`` to the commit of ``ref``, then lock, sync and redeploy."""
    run = run or run_command
    fetch = fetch or fetch_url
    root = root.resolve()
    if not (root / "pyproject.toml").is_file():
        raise invalid_input(
            f"{root} has no pyproject.toml.", code="APP_MANIFEST_MISSING", fix="Run the command from the project root."
        )
    commit = resolve_commit(ref, run, root)
    pins = devkit_pins(commit, fetch)
    notices: list[AppToolsError] = []
    if not pins:
        notices.append(
            notice(
                f"app-common {commit[:12]} does not pin devkit; the devkit sources were left as they are.",
                code="APP_UPDATE_DEVKIT_UNPINNED",
            )
        )
    manifests = {
        folder / "pyproject.toml": (folder / "pyproject.toml").read_text(encoding="utf-8")
        for folder in project_roots(root)
    }
    # Members may declare the app-common sources; the root pins devkit whenever any manifest uses app-common.
    uses_app_common = any(rewrite_manifest(text, commit, {}, declares_devkit=False)[1] for text in manifests.values())
    originals: dict[Path, str] = {}
    rewritten: dict[Path, str] = {}
    changes: list[ManifestChange] = []
    for path, text in manifests.items():
        is_root = path.parent == root
        updated, count, devkit = rewrite_manifest(text, commit, pins, declares_devkit=is_root and uses_app_common)
        if count or devkit:
            changes.append(ManifestChange(path, count, devkit))
        if updated != text:
            originals[path], rewritten[path] = text, updated
    if not any(change.app_common for change in changes):
        raise invalid_input(
            "No app-common dependency was found in pyproject.toml or its uv workspace members.",
            code="APP_UPDATE_NO_DEPENDENCIES",
            fix="Declare app-common packages as Git dependencies of https://github.com/mjkimR/app-common.",
            target_files=[str(root / "pyproject.toml")],
        )
    commands = [["uv", "lock"]]
    if sync:
        commands.append(["uv", "sync"])
    apm = apm_superseded(root)
    if apm is not None:
        notices.append(apm)
    elif sync:
        commands.append(["uv", "run", "--no-sync", "devkit", "sync"])
    result = UpdateResult(ref, commit, pins, changes, [" ".join(c) for c in commands], dry_run, notices)
    if dry_run:
        return result
    for path, text in rewritten.items():
        path.write_text(text, encoding="utf-8")
    for index, command in enumerate(commands):
        completed = run(command, root)
        if completed.returncode == 0:
            continue
        restored: list[str] = []
        if index == 0:  # nothing was locked: put the manifests back as they were
            for path, text in originals.items():
                path.write_text(text, encoding="utf-8")
                restored.append(str(path))
        raise step_failed(command, completed.stdout + completed.stderr, restored=restored)
    return result
