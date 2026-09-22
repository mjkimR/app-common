from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import tomllib
from pathlib import Path

from app_tools.cli import cli
from app_tools.commands.guide import BUNDLE
from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[5]


def invoke(root: Path, *args: str):
    return CliRunner().invoke(cli, ["guide", "--project", str(root), *args])


def test_standalone_error_does_not_recommend_backend(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["app_error>=0.1"]\n')
    result = invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "  backend/errors  " in result.output
    assert "  backend  " not in result.output
    assert "  storage  " not in result.output


def test_offline_show_uninstalled_package(tmp_path: Path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("guide attempted network or subprocess execution")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = invoke(tmp_path, "show", "storage/setup")
    assert result.exit_code == 0, result.output
    assert "Guide version:" in result.output
    assert "declared: (none detected)" in result.output
    assert "S3" in result.output
    assert invoke(tmp_path, "show", "../../pyproject.toml").exit_code != 0


def test_declared_locked_and_project_environment_are_distinct(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("""[project]
dependencies = ["app-error"]
[tool.uv.sources]
app-error = {git = "https://github.com/mjkimR/app-common.git", rev = "v9.9.9"}
""")
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "app-file-storage"\nversion = "9.9.9"\n')
    info = tmp_path / ".venv/lib/python3.12/site-packages/app_http_client-9.9.9.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: app-http-client\nVersion: 9.9.9\n")
    result = invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "declared: app-error\n" in result.output
    assert "locked: app-file-storage=9.9.9" in result.output
    assert "installed: app-http-client=9.9.9" in result.output
    assert "version mismatch" in result.output
    assert "v9.9.9" in result.output
    assert "  storage  " not in result.output
    assert "  http  " in result.output


def test_workspace_frontend_and_groups(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("""[tool.uv.workspace]
members = ["packages/*"]
exclude = ["packages/unused"]
[dependency-groups]
dev = ["app-testing-base", {include-group = "lint"}]
""")
    for member in ("api", "unused"):
        folder = tmp_path / "packages" / member
        folder.mkdir(parents=True)
        name = "app-layer-base" if member == "api" else "app-file-storage"
        (folder / "pyproject.toml").write_text(f'[project]\ndependencies = ["{name}"]\n')
    web = tmp_path / "web"
    web.mkdir()
    (web / "package.json").write_text(json.dumps({"dependencies": {"@app-common/ui-base": "0.1.0"}}))
    result = invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "  backend  " in result.output
    assert "  testing  " in result.output
    assert "  ui  " in result.output
    assert "  storage  " not in result.output
    selected = invoke(tmp_path / "packages/api")
    assert "  ui  " not in selected.output


def test_malformed_manifest_is_actionable(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("not toml")
    result = invoke(tmp_path)
    assert result.exit_code == 1
    assert "Cannot read" in result.output


def test_source_override(tmp_path: Path):
    data = tmp_path / "tools/app-tools/src/app_tools/guide_data"
    shutil.copytree(BUNDLE, data)
    (data / "references/storage/setup.md").write_text("Local checkout guidance\n")
    result = invoke(tmp_path, "--source", str(tmp_path), "show", "storage/setup")
    assert result.exit_code == 0, result.output
    assert "Local checkout guidance" in result.output


def test_bundle_is_self_contained_and_versioned():
    source = REPO / "agents/skills/app-common"
    assert source.is_dir() and not source.is_symlink()
    assert BUNDLE.resolve() == source
    assert (REPO / "agents/apm.yml").is_file()
    catalog = json.loads((BUNDLE / "catalog.json").read_text())
    project = tomllib.loads((REPO / "tools/app-tools/pyproject.toml").read_text())
    assert catalog["version"] == project["project"]["version"]
    for entry in catalog["guides"].values():
        assert (BUNDLE / entry["path"]).is_file()
    for document in BUNDLE.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            if "://" not in link and not link.startswith("#"):
                assert (document.parent / link.split("#")[0]).is_file(), (document, link)
    assert list(BUNDLE.rglob("SKILL.md")) == [BUNDLE / "SKILL.md"]
