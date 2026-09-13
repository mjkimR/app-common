from __future__ import annotations

import subprocess
from pathlib import Path

from app_tools.cli import cli
from click.testing import CliRunner


def write_consumer_manifest(path: Path, ref: str = "v0.1.0") -> None:
    path.joinpath("pyproject.toml").write_text(
        f"""[project]
dependencies = [
    "app-layer-base @ git+https://github.com/mjkimR/app-common.git@{ref}#subdirectory=packages/base/app-layer-base",
    "app-error @ git+https://github.com/mjkimR/app-common.git@{ref}#subdirectory=packages/base/app-error",
]
""",
        encoding="utf-8",
    )


def test_update_uses_explicit_ref_and_syncs(tmp_path: Path, monkeypatch) -> None:
    write_consumer_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], cwd: Path, check: bool) -> None:
        calls.append((command, cwd))

    monkeypatch.setattr(subprocess, "run", fake_run)
    skill_calls: list[tuple[str, str, Path]] = []
    monkeypatch.setattr(
        "app_tools.commands.update.sync_skills",
        lambda ref, target, cwd: skill_calls.append((ref, target, cwd)),
    )

    result = CliRunner().invoke(cli, ["update", "--ref", "v1.2.3"])

    assert result.exit_code == 0
    assert "dependencies to update: 2" in result.output
    assert "@v1.2.3#subdirectory=" in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert calls == [(["uv", "lock"], tmp_path), (["uv", "sync"], tmp_path)]
    assert skill_calls == [("v1.2.3", "antigravity", tmp_path)]


def test_update_dry_run_leaves_manifest_unchanged(tmp_path: Path, monkeypatch) -> None:
    write_consumer_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    original = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")

    result = CliRunner().invoke(cli, ["update", "--ref", "v1.2.3", "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run" in result.output
    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == original


def test_update_requires_app_common_git_dependency(tmp_path: Path, monkeypatch) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project]\ndependencies = []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["update", "--ref", "v1.2.3"])

    assert result.exit_code == 1
    assert "No app-common Git dependency URLs" in result.output


def test_update_uses_latest_release_by_default(tmp_path: Path, monkeypatch) -> None:
    write_consumer_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app_tools.commands.update.latest_release_tag", lambda: "v9.9.9")

    result = CliRunner().invoke(cli, ["update", "--dry-run"])

    assert result.exit_code == 0
    assert "app-common ref: v9.9.9" in result.output
