from __future__ import annotations

import json
from pathlib import Path

import pytest
from app_tools.cli import cli
from app_tools.commands.dev import (
    discover_node_packages,
    discover_python_packages,
    find_app_common_root,
    is_app_common_root,
)
from click.testing import CliRunner


@pytest.fixture
def mock_app_common(tmp_path: Path) -> Path:
    """Create a mock app-common directory structure."""
    repo = tmp_path / "app-common"
    # Sentinel
    (repo / "packages" / "base" / "app-layer-base" / "src" / "app_layer_base").mkdir(parents=True)
    (repo / "packages" / "base" / "app-layer-base" / "src" / "app_layer_base" / "__init__.py").touch()

    # Another python package
    (repo / "packages" / "base" / "app-error" / "src" / "app_error").mkdir(parents=True)
    (repo / "packages" / "base" / "app-error" / "src" / "app_error" / "__init__.py").touch()

    # Node package
    ui_pkg = repo / "packages" / "ui" / "app-ui-base"
    ui_pkg.mkdir(parents=True)
    (ui_pkg / "package.json").write_text(
        json.dumps({"name": "@app-common/ui-base", "version": "0.1.0"}),
        encoding="utf-8",
    )

    return repo


@pytest.fixture
def mock_consumer_project(tmp_path: Path) -> Path:
    """Create a mock downstream consumer project with .venv and node_modules."""
    proj = tmp_path / "my-service"
    proj.mkdir()

    # Virtualenv
    sp = proj / ".venv" / "lib" / "python3.12" / "site-packages"
    sp.mkdir(parents=True)

    # Installed app_layer_base
    installed_pkg = sp / "app_layer_base"
    installed_pkg.mkdir()
    (installed_pkg / "__init__.py").write_text("# original installed", encoding="utf-8")

    # dist-info (should not be touched)
    dist_info = sp / "app_layer_base-0.1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").touch()

    # Node modules
    nm_ui = proj / "node_modules" / "@app-common" / "ui-base"
    nm_ui.mkdir(parents=True)
    (nm_ui / "package.json").write_text(
        json.dumps({"name": "@app-common/ui-base", "version": "0.1.0"}),
        encoding="utf-8",
    )

    return proj


def test_is_app_common_root(mock_app_common: Path, tmp_path: Path):
    assert is_app_common_root(mock_app_common) is True
    assert is_app_common_root(tmp_path) is False


def test_find_app_common_root_same_level(mock_app_common: Path, mock_consumer_project: Path):
    # Both are under tmp_path: tmp_path/app-common and tmp_path/my-service
    found = find_app_common_root(mock_consumer_project)
    assert found == mock_app_common.resolve()


def test_find_app_common_root_child_depth(tmp_path: Path):
    parent = tmp_path / "workspace"
    parent.mkdir()
    child_common = parent / "app-common"
    (child_common / "packages" / "base" / "app-layer-base" / "src" / "app_layer_base").mkdir(parents=True)

    found = find_app_common_root(parent)
    assert found == child_common.resolve()


def test_find_app_common_root_grandparent_depth(mock_app_common: Path, tmp_path: Path):
    nested_proj = tmp_path / "subdir" / "my-service"
    nested_proj.mkdir(parents=True)

    found = find_app_common_root(nested_proj)
    assert found == mock_app_common.resolve()


def test_discover_packages(mock_app_common: Path):
    py_pkgs = discover_python_packages(mock_app_common)
    assert "app_layer_base" in py_pkgs
    assert "app_error" in py_pkgs

    node_pkgs = discover_node_packages(mock_app_common)
    assert "@app-common/ui-base" in node_pkgs


def test_dev_link_and_unlink_flow(mock_app_common: Path, mock_consumer_project: Path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(mock_consumer_project)

    sp = mock_consumer_project / ".venv" / "lib" / "python3.12" / "site-packages"
    nm = mock_consumer_project / "node_modules" / "@app-common" / "ui-base"

    # 1. Dev Status (Before Link)
    result = runner.invoke(cli, ["dev", "status"])
    assert result.exit_code == 0
    assert "[NORMAL]        app_layer_base (installed)" in result.output
    assert "[NORMAL]        @app-common/ui-base (installed)" in result.output

    # 2. Dev Link
    result = runner.invoke(cli, ["dev", "link"])
    assert result.exit_code == 0
    assert "linking: app_layer_base" in result.output
    assert "linking: @app-common/ui-base" in result.output

    # Verify symlink and backup
    py_target = sp / "app_layer_base"
    py_bak = sp / "app_layer_base.bak"
    assert py_target.is_symlink()
    assert py_bak.is_dir()
    assert (py_bak / "__init__.py").read_text(encoding="utf-8") == "# original installed"
    # Verify dist-info intact
    assert (sp / "app_layer_base-0.1.0.dist-info").is_dir()

    node_target = nm
    node_bak = mock_consumer_project / "node_modules" / "@app-common" / "ui-base.bak"
    assert node_target.is_symlink()
    assert node_bak.is_dir()

    # 3. Dev Status (While Linked)
    result = runner.invoke(cli, ["dev", "status"])
    assert result.exit_code == 0
    assert "[LINKED]        app_layer_base" in result.output
    assert "(backup: yes)" in result.output
    assert "[LINKED]        @app-common/ui-base" in result.output

    # 4. Dev Unlink
    result = runner.invoke(cli, ["dev", "unlink"])
    assert result.exit_code == 0
    assert "restoring backup: app_layer_base.bak -> app_layer_base" in result.output

    # Verify restoration
    assert not py_target.is_symlink()
    assert py_target.is_dir()
    assert not py_bak.exists()
    assert (py_target / "__init__.py").read_text(encoding="utf-8") == "# original installed"

    assert not node_target.is_symlink()
    assert node_target.is_dir()
    assert not node_bak.exists()

    # 5. Dev Status (After Unlink)
    result = runner.invoke(cli, ["dev", "status"])
    assert result.exit_code == 0
    assert "[NORMAL]        app_layer_base (installed)" in result.output
    assert "[NORMAL]        @app-common/ui-base (installed)" in result.output


def test_dev_link_dry_run(mock_app_common: Path, mock_consumer_project: Path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(mock_consumer_project)

    sp = mock_consumer_project / ".venv" / "lib" / "python3.12" / "site-packages"
    py_target = sp / "app_layer_base"

    result = runner.invoke(cli, ["dev", "link", "--dry-run"])
    assert result.exit_code == 0
    assert "(Dry-run mode: no changes were made)" in result.output
    assert not py_target.is_symlink()
    assert not (sp / "app_layer_base.bak").exists()


def test_dev_link_app_common_not_found(tmp_path: Path, monkeypatch):
    empty_dir = tmp_path / "isolated"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    runner = CliRunner()
    result = runner.invoke(cli, ["dev", "link"])
    assert result.exit_code == 1
    assert "Could not locate app-common repository root" in result.output


def test_dev_link_node_dist_warning(mock_app_common: Path, mock_consumer_project: Path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(mock_consumer_project)

    # When dist/ does not exist
    result = runner.invoke(cli, ["dev", "link"])
    assert result.exit_code == 0
    assert "has no build output" in result.output
    assert "Run 'just build-ui' in app-common" in result.output

    # When dist/ exists with content
    dist_dir = mock_app_common / "packages" / "ui" / "app-ui-base" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.js").write_text("export {};")

    result = runner.invoke(cli, ["dev", "link"])
    assert result.exit_code == 0
    assert "has no build output" not in result.output
