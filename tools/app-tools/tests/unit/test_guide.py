from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import tomllib
from pathlib import Path

from app_tools.guide import CHECKOUT_SKILL, SKILL
from click.testing import CliRunner
from devkit_dist.cli import cli as devkit_cli

TOOL = Path(__file__).resolve().parents[2]


def guide(*args: str):
    return CliRunner().invoke(devkit_cli, ["app", "guide", *args])


def topics(root: Path, *args: str) -> list[str]:
    result = guide("list", "--project", str(root), "--format", "json", *args)
    assert result.exit_code == 0, result.output
    return [topic["topic"] for topic in json.loads(result.stdout)["topics"]]


def test_declared_packages_select_their_topics(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["app_http_client>=0.1"]\n')
    assert topics(tmp_path) == ["http", "http/setup"]


def test_text_output_is_one_fact_per_line(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["app-http-client"]\n')
    result = guide("list", "--project", str(tmp_path))
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert all(re.fullmatch(r"\[[A-Z_]+: .*\]", line) for line in lines), lines
    assert "[PACKAGE: app-http-client declared=yes locked=- installed=-]" in lines
    assert any(line.startswith("[TOPIC: http packages=app-http-client path=") for line in lines)


def test_offline_show_uninstalled_package(tmp_path: Path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("guide attempted network or subprocess execution")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = guide("show", "storage/setup", "--project", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("[DOCUMENT: storage/setup path=")
    assert "S3" in result.stdout


def test_unknown_topic_is_an_input_error(tmp_path: Path):
    result = guide("show", "../../pyproject.toml", "--project", str(tmp_path), "--format", "json")
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "APP_GUIDE_UNKNOWN_TOPIC"


def test_no_topics_is_a_notice_with_the_next_command(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = []\n")
    result = guide("list", "--project", str(tmp_path))
    assert result.exit_code == 0
    assert "[OK: topics=0]" in result.stdout
    assert "(APP_GUIDE_NO_TOPICS)" in result.stderr
    assert "devkit app guide list --all" in result.stderr


def test_declared_locked_and_project_environment_are_distinct(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("""[project]
dependencies = ["app-layer-base"]
[tool.uv.sources]
app-layer-base = {git = "https://github.com/mjkimR/app-common.git", rev = "v9.9.9"}
""")
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "app-file-storage"\nversion = "9.9.9"\n')
    info = tmp_path / ".venv/lib/python3.12/site-packages/app_http_client-9.9.9.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: app-http-client\nVersion: 9.9.9\n")
    result = guide("list", "--project", str(tmp_path), "--format", "json")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert list(report["packages"]["declared"]) == ["app-layer-base"]
    assert report["packages"]["locked"] == {"app-file-storage": "9.9.9"}
    assert report["packages"]["installed"] == {"app-http-client": "9.9.9"}
    assert report["packages"]["refs"] == ["v9.9.9"]
    assert [n["code"] for n in report["notices"]] == ["APP_GUIDE_VERSION_MISMATCH"]
    names = [topic["topic"] for topic in report["topics"]]
    assert "http" in names and "backend" in names and "storage" not in names


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
    names = topics(tmp_path)
    assert {"backend", "testing", "ui"} <= set(names)
    assert "storage" not in names
    assert "ui" not in topics(tmp_path / "packages/api")


def test_malformed_manifest_is_actionable(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("not toml")
    result = guide("list", "--project", str(tmp_path), "--format", "json")
    assert result.exit_code == 2
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "APP_MANIFEST_INVALID"
    assert error["advisory"]["target_files"] == [str(tmp_path / "pyproject.toml")]


def test_source_override(tmp_path: Path):
    data = tmp_path / CHECKOUT_SKILL
    shutil.copytree(SKILL, data)
    (data / "references/storage/setup.md").write_text("Local checkout guidance\n")
    result = guide("show", "storage/setup", "--project", str(tmp_path), "--source", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "Local checkout guidance" in result.stdout


def test_bundle_skill_is_self_contained_and_versioned():
    catalog = json.loads((SKILL / "catalog.json").read_text())
    project = tomllib.loads((TOOL / "pyproject.toml").read_text())
    bundle = tomllib.loads((SKILL.parents[1] / "bundle.toml").read_text())
    assert catalog["version"] == project["project"]["version"] == bundle["version"]
    for entry in catalog["guides"].values():
        assert (SKILL / entry["path"]).is_file()
    for document in SKILL.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            if "://" not in link and not link.startswith("#"):
                assert (document.parent / link.split("#")[0]).is_file(), (document, link)
    assert list(SKILL.rglob("SKILL.md")) == [SKILL / "SKILL.md"]
    assert not any(path.is_symlink() for path in SKILL.rglob("*"))
