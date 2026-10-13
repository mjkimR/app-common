from __future__ import annotations

import json
from pathlib import Path

from app_tools.doctor import diagnose
from click.testing import CliRunner
from devkit.cli import cli as devkit_cli

RECEIPT = {
    "schema": 1,
    "packages": [
        {"package": "app-tools", "package_version": "0.1.0", "bundle": "app-common", "bundle_version": "0.1.0"}
    ],
    "selection": {"agents": ["claude-code"], "presets": {"app-common": ["all"]}},
    "assets": [],
    "files": {},
}


def consumer(tmp_path: Path, *dependencies: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(f"[project]\ndependencies = {json.dumps(list(dependencies))}\n")
    return tmp_path


def test_unsynced_bundle_is_a_problem_with_its_fix(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
    report = diagnose(consumer(tmp_path, "app-layer-base", "app-http-client"))
    assert report.packages == ["app-http-client", "app-layer-base"]
    assert report.bundle == "not-synced"
    assert report.database == "sqlite"
    [problem] = report.problems
    assert problem.code == "APP_BUNDLE_NOT_SYNCED"
    assert problem.fix == "uv run devkit sync"


def test_synced_project_with_apm_leftovers_and_no_database(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    root = consumer(tmp_path, "app-layer-base")
    (root / ".devkit").mkdir()
    (root / ".devkit/installation.json").write_text(json.dumps(RECEIPT))
    (root / "apm.yml").write_text("dependencies:\n  apm:\n    - git: mjkimR/app-common\n")
    report = diagnose(root)
    assert report.bundle == "synced"
    assert report.problems == []
    assert [n.code for n in report.notices] == [
        "APP_ADVISORY_GUIDE_MISSING",
        "APP_APM_SUPERSEDED",
        "APP_DATABASE_URL_UNSET",
    ]
    assert report.notices[0].fix == "uv run devkit add advisory:python"


def test_selected_advisory_guide_is_not_reported(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
    root = consumer(tmp_path, "app-layer-base")
    (root / ".devkit").mkdir()
    receipt = {
        **RECEIPT,
        "selection": {"agents": [], "presets": {"app-common": ["all"], "advisory": ["core", "python"]}},
    }
    (root / ".devkit/installation.json").write_text(json.dumps(receipt))
    assert diagnose(root).notices == []


def test_database_url_from_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    root = consumer(tmp_path, "app-layer-base")
    (root / ".env").write_text("DATABASE_URL='postgresql+psycopg://u:p@h/db'\n")
    assert diagnose(root).database == "postgres"


def test_cli_exits_one_while_a_problem_remains(tmp_path: Path):
    root = consumer(tmp_path, "app-mcp")
    result = CliRunner().invoke(devkit_cli, ["app", "doctor", "--project", str(root), "--format", "json"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["packages"] == ["app-mcp"]
    assert [e["code"] for e in report["errors"]] == ["APP_BUNDLE_NOT_SYNCED"]
