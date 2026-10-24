from __future__ import annotations

import json
from pathlib import Path

import pytest
from app_tools.devlink import find_app_common_root, is_app_common_root, node_packages, python_packages
from click.testing import CliRunner
from devkit_dist.cli import cli as devkit_cli


def dev(*args: str):
    return CliRunner().invoke(devkit_cli, ["app", "dev", *args, "--format", "json"])


def write_package(src: Path, name: str) -> None:
    (src / name).mkdir(parents=True)
    (src / name / "__init__.py").touch()


@pytest.fixture
def app_common(tmp_path: Path) -> Path:
    repo = tmp_path / "app-common"
    write_package(repo / "packages/base/app-layer-base/src", "app_layer_base")
    write_package(repo / "tools/app-tools/src", "app_tools")
    ui = repo / "packages/ui/app-ui-base"
    ui.mkdir(parents=True)
    (ui / "package.json").write_text(json.dumps({"name": "@app-common/ui-base", "version": "0.1.0"}))
    return repo


@pytest.fixture
def consumer(tmp_path: Path, monkeypatch) -> Path:
    project = tmp_path / "my-service"
    site = project / ".venv/lib/python3.12/site-packages"
    for name in ("app_layer_base", "app_tools"):
        (site / name).mkdir(parents=True)
        (site / name / "__init__.py").write_text("# original installed")
    (site / "app_layer_base-0.1.0.dist-info").mkdir()
    ui = project / "node_modules/@app-common/ui-base"
    ui.mkdir(parents=True)
    (ui / "package.json").write_text("{}")
    monkeypatch.chdir(project)
    return project


def test_root_discovery(app_common: Path, consumer: Path, tmp_path: Path):
    assert is_app_common_root(app_common) and not is_app_common_root(tmp_path)
    assert find_app_common_root(consumer) == app_common.resolve()
    nested = tmp_path / "subdir/service"
    nested.mkdir(parents=True)
    assert find_app_common_root(nested) == app_common.resolve()
    assert set(python_packages(app_common)) == {"app_layer_base", "app_tools"}
    assert set(node_packages(app_common)) == {"@app-common/ui-base"}


def test_link_status_unlink_round_trip(app_common: Path, consumer: Path):
    site = consumer / ".venv/lib/python3.12/site-packages"
    ui = consumer / "node_modules/@app-common/ui-base"

    states = {p["package"]: p["state"] for p in json.loads(dev("status").stdout)["packages"]}
    assert states == {"app_layer_base": "installed", "app_tools": "installed", "@app-common/ui-base": "installed"}

    result = dev("link")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert {(a["package"], a["action"]) for a in report["actions"]} == {
        ("app_layer_base", "linked"),
        ("app_tools", "linked"),
        ("@app-common/ui-base", "linked"),
    }
    codes = [n["code"] for n in report["notices"]]
    assert "APP_DEV_BUNDLE_SOURCE_CHANGED" in codes  # app_tools ships the devkit bundle
    assert "APP_DEV_UI_NOT_BUILT" in codes
    assert (site / "app_layer_base").is_symlink()
    assert (site / "app_layer_base.bak/__init__.py").read_text() == "# original installed"
    assert (site / "app_layer_base-0.1.0.dist-info").is_dir()
    assert ui.is_symlink()

    states = {p["package"]: (p["state"], p["backup"]) for p in json.loads(dev("status").stdout)["packages"]}
    assert states["app_layer_base"] == ("linked", True)

    result = dev("unlink")
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)["actions"]) == 3
    assert not (site / "app_layer_base").is_symlink()
    assert (site / "app_layer_base/__init__.py").read_text() == "# original installed"
    assert not (site / "app_layer_base.bak").exists()
    assert ui.is_dir() and not ui.is_symlink()


def test_dry_run_changes_nothing(app_common: Path, consumer: Path):
    site = consumer / ".venv/lib/python3.12/site-packages"
    result = dev("link", "--dry-run")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["dry_run"] is True
    assert not (site / "app_layer_base").is_symlink()
    assert not (site / "app_layer_base.bak").exists()


def test_inconsistent_backups_fail_status(app_common: Path, consumer: Path):
    site = consumer / ".venv/lib/python3.12/site-packages"
    (site / "app_layer_base.bak").mkdir()
    result = dev("status")
    assert result.exit_code == 1
    assert [e["code"] for e in json.loads(result.stdout)["errors"]] == ["APP_DEV_LINK_ANOMALY"]


def test_missing_checkout_is_an_input_error(tmp_path: Path, monkeypatch):
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    monkeypatch.chdir(isolated)
    # An explicit path: pytest's sibling temporary directories may hold app-common checkouts.
    result = dev("link", "--target-path", str(isolated))
    assert result.exit_code == 2
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "APP_DEV_ROOT_NOT_FOUND"
    assert "--target-path" in error["advisory"]["fix"]


def test_built_ui_does_not_warn(app_common: Path, consumer: Path):
    dist = app_common / "packages/ui/app-ui-base/dist"
    dist.mkdir()
    (dist / "index.js").write_text("export {};")
    codes = [n["code"] for n in json.loads(dev("link").stdout)["notices"]]
    assert "APP_DEV_UI_NOT_BUILT" not in codes
