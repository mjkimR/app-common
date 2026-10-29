from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path

import pytest
from app_tools.update import devkit_pins, rewrite_manifest, update_project
from click.testing import CliRunner
from devkit.advisory import AdvisoryError
from devkit_dist.cli import cli as devkit_cli

COMMIT = "a" * 40
OLD = "b" * 40
DEVKIT = {"git": "https://github.com/mjkimR/devkit", "subdirectory": "packages/devkit", "rev": "c" * 40}
ADVISORY = {**DEVKIT, "subdirectory": "packages/devkit-advisory"}
DEVKIT_SOURCE = (
    f'devkit-agt = {{ git = "{DEVKIT["git"]}", subdirectory = "{DEVKIT["subdirectory"]}", rev = "{DEVKIT["rev"]}" }}'
)
ADVISORY_SOURCE = f'devkit-advisory = {{ git = "{ADVISORY["git"]}", subdirectory = "{ADVISORY["subdirectory"]}", rev = "{ADVISORY["rev"]}" }}'
APP_COMMON_PYPROJECT = f"""
[tool.uv.sources]
{DEVKIT_SOURCE}
{ADVISORY_SOURCE}
""".encode()


class Recorder:
    """Stands in for git and uv; records every command."""

    def __init__(self, failing: str | None = None, ls_remote: str = f"{COMMIT}\trefs/heads/main\n") -> None:
        self.calls: list[list[str]] = []
        self.failing = failing
        self.ls_remote = ls_remote

    def __call__(self, command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(command))
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, self.ls_remote, "")
        failed = self.failing is not None and " ".join(command) == self.failing
        return subprocess.CompletedProcess(command, 1 if failed else 0, "", "resolution failed" if failed else "")


def fetch(url: str) -> bytes:
    assert url == f"https://raw.githubusercontent.com/mjkimR/app-common/{COMMIT}/pyproject.toml"
    return APP_COMMON_PYPROJECT


def url_manifest(path: Path) -> None:
    (path / "pyproject.toml").write_text("""[project]
name = "consumer"
dependencies = [
    "app-layer-base @ git+https://github.com/mjkimR/app-common.git@v0.1.0#subdirectory=packages/base/app-layer-base",
]
""")


def sources_manifest(path: Path) -> None:
    """The form consumers use: a uv workspace whose root pins every app-common source by commit."""
    (path / "pyproject.toml").write_text(f"""[tool.uv.workspace]
members = ["apps/*"]

[dependency-groups]
dev = ["app-tools"]

# app-common packages are pinned by commit.
[tool.uv.sources]
app-layer-base = {{ git = "https://github.com/mjkimR/app-common.git", subdirectory = "packages/base/app-layer-base", rev = "{OLD}" }}
app-tools = {{ git = "https://github.com/mjkimR/app-common", subdirectory = "tools/app-tools", tag = "v0.1.0" }}
other = {{ git = "https://github.com/example/other", rev = "{OLD}" }}
""")
    member = path / "apps/hub"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "hub"\ndependencies = ["app-layer-base"]\n')


def test_uv_sources_form_is_pinned_with_devkit_and_synced(tmp_path: Path):
    sources_manifest(tmp_path)
    run = Recorder()
    result = update_project(tmp_path, run=run, fetch=fetch)
    manifest = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    sources = manifest["tool"]["uv"]["sources"]
    assert sources["app-layer-base"]["rev"] == COMMIT
    assert sources["app-tools"]["rev"] == COMMIT and "tag" not in sources["app-tools"]
    assert sources["other"]["rev"] == OLD
    assert sources["devkit-agt"] == DEVKIT and sources["devkit-advisory"] == ADVISORY
    # Sources apply to direct dependencies only.
    assert manifest["dependency-groups"]["dev"] == ["app-tools", "devkit-agt", "devkit-advisory"]
    assert "# app-common packages are pinned by commit." in (tmp_path / "pyproject.toml").read_text()
    assert result.commit == COMMIT
    assert [(c.app_common, c.devkit) for c in result.changes] == [(2, True)]
    assert run.calls[1:] == [["uv", "lock"], ["uv", "sync"], ["uv", "run", "--no-sync", "devkit", "sync"]]


def test_requirement_url_form_is_pinned(tmp_path: Path):
    url_manifest(tmp_path)
    update_project(tmp_path, ref=COMMIT, sync=False, run=Recorder(), fetch=fetch)
    text = (tmp_path / "pyproject.toml").read_text()
    assert f"app-common.git@{COMMIT}#subdirectory=packages/base/app-layer-base" in text
    assert tomllib.loads(text)["tool"]["uv"]["sources"]["devkit-agt"] == DEVKIT
    assert tomllib.loads(text)["dependency-groups"]["dev"] == ["devkit-agt", "devkit-advisory"]


def test_a_direct_devkit_declaration_is_kept(tmp_path: Path):
    sources_manifest(tmp_path)
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(manifest.read_text().replace('dev = ["app-tools"]', 'dev = ["app-tools", "devkit-agt>=0.1"]'))
    manifest.write_text(
        manifest.read_text().replace(
            "[dependency-groups]", '[project]\ndependencies = ["devkit-advisory>=0.1"]\n\n[dependency-groups]'
        )
    )
    update_project(tmp_path, sync=False, run=Recorder(), fetch=fetch)
    document = tomllib.loads(manifest.read_text())
    assert document["dependency-groups"]["dev"] == ["app-tools", "devkit-agt>=0.1"]
    assert document["project"]["dependencies"] == ["devkit-advisory>=0.1"]


def test_sources_declared_only_by_members_still_pin_devkit_at_the_root(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["apps/*"]\n')
    member = tmp_path / "apps/hub"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(f"""[project]
name = "hub"
dependencies = ["app-layer-base"]

[tool.uv.sources]
app-layer-base = {{ git = "https://github.com/mjkimR/app-common", subdirectory = "packages/base/app-layer-base", rev = "{OLD}" }}
""")
    update_project(tmp_path, sync=False, run=Recorder(), fetch=fetch)
    root = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert root["tool"]["uv"]["sources"]["devkit-advisory"] == ADVISORY
    assert root["dependency-groups"]["dev"] == ["devkit-agt", "devkit-advisory"]
    hub = tomllib.loads((member / "pyproject.toml").read_text())
    assert hub["tool"]["uv"]["sources"]["app-layer-base"]["rev"] == COMMIT
    assert "devkit-agt" not in hub["tool"]["uv"]["sources"] and "devkit-advisory" not in hub["tool"]["uv"]["sources"]


def test_branch_and_tag_resolve_to_commits(tmp_path: Path):
    url_manifest(tmp_path)
    run = Recorder(ls_remote=f"{OLD}\trefs/tags/v1.0.0\n{COMMIT}\trefs/tags/v1.0.0^{{}}\n")
    result = update_project(tmp_path, ref="v1.0.0", dry_run=True, run=run, fetch=fetch)
    assert result.commit == COMMIT  # the peeled tag, not the tag object
    assert run.calls == [
        [
            "git",
            "ls-remote",
            "https://github.com/mjkimR/app-common",
            "refs/heads/v1.0.0",
            "refs/tags/v1.0.0",
            "refs/tags/v1.0.0^{}",
        ]
    ]


def test_unknown_ref_is_an_input_error(tmp_path: Path):
    url_manifest(tmp_path)
    with pytest.raises(AdvisoryError) as raised:
        update_project(tmp_path, ref="nope", run=Recorder(ls_remote=""), fetch=fetch)
    assert raised.value.code == "APP_UPDATE_REF_NOT_FOUND"


def test_dry_run_changes_nothing(tmp_path: Path):
    sources_manifest(tmp_path)
    before = (tmp_path / "pyproject.toml").read_text()
    run = Recorder()
    result = update_project(tmp_path, dry_run=True, run=run, fetch=fetch)
    assert (tmp_path / "pyproject.toml").read_text() == before
    assert [call[0] for call in run.calls] == ["git"]
    assert result.commands == ["uv lock", "uv sync", "uv run --no-sync devkit sync"]


def test_failed_lock_restores_the_manifests(tmp_path: Path):
    sources_manifest(tmp_path)
    before = (tmp_path / "pyproject.toml").read_text()
    with pytest.raises(AdvisoryError) as raised:
        update_project(tmp_path, run=Recorder(failing="uv lock"), fetch=fetch)
    assert raised.value.code == "APP_STEP_FAILED"
    assert (tmp_path / "pyproject.toml").read_text() == before
    assert f"restored: {tmp_path / 'pyproject.toml'}" in raised.value.details


def test_apm_consumer_is_told_to_migrate_and_not_synced_by_devkit(tmp_path: Path):
    sources_manifest(tmp_path)
    (tmp_path / "apm.yml").write_text("dependencies:\n  apm:\n    - git: mjkimR/app-common\n")
    run = Recorder()
    result = update_project(tmp_path, run=run, fetch=fetch)
    assert [notice.code for notice in result.notices] == ["APP_APM_SUPERSEDED"]
    assert ["uv", "run", "--no-sync", "devkit", "sync"] not in run.calls


def test_commit_before_devkit_leaves_devkit_alone(tmp_path: Path):
    url_manifest(tmp_path)
    result = update_project(tmp_path, ref=COMMIT, sync=False, run=Recorder(), fetch=lambda url: b"[project]\n")
    assert "devkit" not in (tmp_path / "pyproject.toml").read_text()
    assert [notice.code for notice in result.notices] == ["APP_UPDATE_DEVKIT_UNPINNED"]


def test_commit_pinning_devkit_only_leaves_devkit_advisory_alone(tmp_path: Path):
    url_manifest(tmp_path)
    old = f"[tool.uv.sources]\n{DEVKIT_SOURCE}\n".encode()
    update_project(tmp_path, ref=COMMIT, sync=False, run=Recorder(), fetch=lambda url: old)
    manifest = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert manifest["tool"]["uv"]["sources"] == {"devkit-agt": DEVKIT}
    assert manifest["dependency-groups"]["dev"] == ["devkit-agt"]


def test_project_without_app_common_dependencies(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = []\n")
    with pytest.raises(AdvisoryError) as raised:
        update_project(tmp_path, ref=COMMIT, run=Recorder(), fetch=fetch)
    assert raised.value.code == "APP_UPDATE_NO_DEPENDENCIES"


def test_cli_reports_the_plan(tmp_path: Path, monkeypatch):
    sources_manifest(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app_tools.update.run_command", Recorder())
    monkeypatch.setattr("app_tools.update.fetch_url", fetch)
    result = CliRunner().invoke(devkit_cli, ["app", "update", "--dry-run", "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["commit"] == COMMIT and report["dry_run"] is True
    assert report["devkit"] == DEVKIT and report["devkit_advisory"] == ADVISORY


def test_split_devkit_packages_are_updated_together(tmp_path: Path):
    sources_manifest(tmp_path)
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        manifest.read_text()
        + f'devkit-core = {{ git = "{DEVKIT["git"]}.git", subdirectory = "packages/devkit-core", rev = "{OLD}" }}\n'
        + f'devkit-spec = {{ git = "{DEVKIT["git"]}", subdirectory = "packages/devkit-spec", tag = "v0.1.0" }}\n'
    )
    dist = {**DEVKIT, "subdirectory": "packages/devkit-dist"}
    upstream = (
        APP_COMMON_PYPROJECT
        + (
            f'devkit-dist = {{ git = "{dist["git"]}", subdirectory = "{dist["subdirectory"]}", rev = "{dist["rev"]}" }}\n'
        ).encode()
    )
    update_project(tmp_path, ref=COMMIT, sync=False, run=Recorder(), fetch=lambda _: upstream)
    document = tomllib.loads(manifest.read_text())
    sources = document["tool"]["uv"]["sources"]
    assert sources["devkit-dist"] == dist
    assert "devkit-dist" in document["dependency-groups"]["dev"]
    assert not {"devkit-core", "devkit-spec"} & set(document["dependency-groups"]["dev"])
    assert sources["devkit-core"]["rev"] == DEVKIT["rev"]
    assert sources["devkit-core"]["git"] == DEVKIT["git"]
    assert sources["devkit-core"]["subdirectory"] == "packages/devkit-core"
    assert sources["devkit-spec"]["rev"] == DEVKIT["rev"]
    assert "tag" not in sources["devkit-spec"]


def test_unrelated_devkit_source_is_preserved():
    text = f'''[tool.uv.sources]
devkit-custom = {{ git = "https://github.com/example/custom", rev = "{OLD}" }}
'''
    pins = devkit_pins(COMMIT, fetch)
    updated, _, _ = rewrite_manifest(text, COMMIT, pins, declares_devkit=False)
    assert updated == text


def test_transitive_devkit_sources_are_aligned_but_never_declared(tmp_path: Path):
    """devkit-core, devkit-cli and devkit-docs reach a project through devkit-agt and devkit-dist: a source keeps
    their ref in step, a dependency entry is not needed."""
    sources_manifest(tmp_path)
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        manifest.read_text().replace('dev = ["app-tools"]', 'dev = ["app-tools", "devkit-agt", "devkit-advisory"]')
        + "".join(
            f'{name} = {{ git = "{DEVKIT["git"]}", subdirectory = "packages/{name}", rev = "{OLD}" }}\n'
            for name in ("devkit-core", "devkit-cli", "devkit-docs")
        )
    )
    update_project(tmp_path, sync=False, run=Recorder(), fetch=fetch)
    document = tomllib.loads(manifest.read_text())
    assert document["dependency-groups"]["dev"] == ["app-tools", "devkit-agt", "devkit-advisory"]
    sources = document["tool"]["uv"]["sources"]
    assert all(sources[name]["rev"] == DEVKIT["rev"] for name in ("devkit-core", "devkit-cli", "devkit-docs"))


def test_a_current_project_is_left_unchanged(tmp_path: Path):
    sources_manifest(tmp_path)
    update_project(tmp_path, sync=False, run=Recorder(), fetch=fetch)
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        manifest.read_text()
        + f'devkit-core = {{ git = "{DEVKIT["git"]}", subdirectory = "packages/devkit-core", rev = "{DEVKIT["rev"]}" }}\n'
    )
    before = manifest.read_text()
    result = update_project(tmp_path, sync=False, run=Recorder(), fetch=fetch)
    assert manifest.read_text() == before
    assert [change.devkit for change in result.changes] == [False]


def test_devkit_override_urls_follow_the_pins():
    rev = DEVKIT["rev"]
    text = f"""[tool.uv]
# Same devkit commit as the sources.
override-dependencies = [
    "devkit-agt @ git+https://github.com/mjkimR/devkit@{OLD}#subdirectory=packages/devkit",
    "devkit-advisory @ git+https://github.com/mjkimR/devkit.git#subdirectory=packages/devkit-advisory&rev={OLD}",
    "devkit-core[x] @ git+https://github.com/mjkimR/devkit.git@v0.1.0#subdirectory=packages/devkit-core ; python_version >= '3.12'",
    "devkit-cli @ git+https://github.com/mjkimR/devkit#subdirectory=packages/devkit-cli",
    "devkit-custom @ git+https://github.com/example/custom@{OLD}",
    "requests>=2",
]

[tool.uv.sources]
{DEVKIT_SOURCE}
"""
    updated, _, devkit = rewrite_manifest(text, COMMIT, devkit_pins(COMMIT, fetch), declares_devkit=False)
    assert devkit
    assert "# Same devkit commit as the sources." in updated
    assert tomllib.loads(updated)["tool"]["uv"]["override-dependencies"] == [
        f"devkit-agt @ git+https://github.com/mjkimR/devkit@{rev}#subdirectory=packages/devkit",
        f"devkit-advisory @ git+https://github.com/mjkimR/devkit.git#subdirectory=packages/devkit-advisory&rev={rev}",
        f"devkit-core[x] @ git+https://github.com/mjkimR/devkit.git@{rev}#subdirectory=packages/devkit-core ; python_version >= '3.12'",
        "devkit-cli @ git+https://github.com/mjkimR/devkit#subdirectory=packages/devkit-cli",
        f"devkit-custom @ git+https://github.com/example/custom@{OLD}",
        "requests>=2",
    ]
    again, _, devkit = rewrite_manifest(updated, COMMIT, devkit_pins(COMMIT, fetch), declares_devkit=False)
    assert again == updated and not devkit


def test_override_urls_are_left_alone_when_app_common_pins_no_devkit():
    text = f'[tool.uv]\noverride-dependencies = ["devkit-agt @ git+https://github.com/mjkimR/devkit@{OLD}"]\n'
    assert rewrite_manifest(text, COMMIT, {}, declares_devkit=False)[0] == text
