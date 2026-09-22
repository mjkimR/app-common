"""The workspace runner preserves package isolation, failures, and bounded concurrency."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
STUB = r"""#!/bin/bash
previous=""
module=""
for arg in "$@"; do
    if [ "$previous" = "--path" ]; then module="${arg##*/}"; break; fi
    previous="$arg"
done
[ -n "$module" ] || exit 0
printf '%s\n' "$@" > "$RUNNER_EVENTS/$module-start"
sleep 0.02
printf '%s\n' "$@" > "$RUNNER_EVENTS/$module-end"
echo "finished $module"
[ "$module" != "${FAIL_MODULE:-}" ] || exit 7
[ "$module" != "${EMPTY_MODULE:-}" ] || exit 5
exit 0
"""


@pytest.fixture
def runner(tmp_path):
    for manifest in [*ROOT.glob("packages/*/*/pyproject.toml"), *ROOT.glob("tools/*/pyproject.toml")]:
        suite = tmp_path / manifest.parent.relative_to(ROOT) / "tests"
        (suite / "unit").mkdir(parents=True)
        (suite / "unit/test_sample.py").touch()
        if manifest.parent.name == "app-tools":
            (suite / "integration").mkdir()
            (suite / "integration/test_sample.py").touch()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("run-tests.sh", "_lib.sh"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text(STUB)
    uv.chmod(0o755)
    events = tmp_path / "events"
    events.mkdir()

    def run(db="sqlite", module="all", paths=(), **settings):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"COVERAGE", "DOCKER", "TEST_JOBS", "PYTEST_OPTIONS", "TEST_TIER"}
        }
        env.update(PATH=f"{binary}{os.pathsep}{env['PATH']}", RUNNER_EVENTS=str(events), **settings)
        result = subprocess.run(
            ["bash", str(scripts / "run-tests.sh"), db, module, *paths],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        records = []
        for path in events.iterdir():
            module, phase = path.name.rsplit("-", 1)
            records.append(
                {
                    "module": module,
                    "phase": phase,
                    "time": path.stat().st_mtime_ns,
                    "args": path.read_text().splitlines(),
                }
            )
        records.sort(key=lambda record: record["time"])
        return result, records

    return run


def concurrency(records):
    active = maximum = 0
    for record in records:
        active += 1 if record["phase"] == "start" else -1
        maximum = max(maximum, active)
    assert active == 0
    return maximum


def test_parallel_packages_are_bounded_and_all_finish_after_a_failure(runner):
    result, records = runner(TEST_JOBS="3", FAIL_MODULE="app-prebuilt-user", EMPTY_MODULE="app-mcp")
    assert result.returncode == 7, result.stdout + result.stderr
    assert len([r for r in records if r["phase"] == "end"]) == 13
    assert 1 < concurrency(records) <= 3
    assert "No tests collected for app-mcp" in result.stdout
    assert result.stdout.index("finished app-error") < result.stdout.index("finished app-prebuilt-user")


@pytest.mark.parametrize(
    ("db", "settings"),
    [("sqlite", {"TEST_JOBS": "1"}), ("postgres", {}), ("sqlite", {"DOCKER": "1"}), ("sqlite", {"COVERAGE": "1"})],
)
def test_infrastructure_coverage_and_explicit_serial_runs_stay_serial(runner, db, settings):
    result, records = runner(db=db, **settings)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(records) == 26
    assert concurrency(records) == 1


def test_focused_package_preserves_paths_with_spaces(runner):
    path = "tools/app-tools/tests/a file.py::test_case"
    result, records = runner(module="app-tools", paths=(path,))
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(records) == 2
    assert records[0]["args"][-1] == "tests/a file.py::test_case"


@pytest.mark.parametrize("jobs", ["0", "-1", "many"])
def test_invalid_concurrency_fails_before_starting_tests(runner, jobs):
    result, records = runner(TEST_JOBS=jobs)
    assert result.returncode == 2
    assert "positive integer" in result.stderr
    assert records == []


def test_unit_selection_runs_every_package_with_only_unit_paths(runner):
    result, records = runner(TEST_TIER="unit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(records) == 26
    assert all(record["args"][-1] == "tests/unit" for record in records)


def test_integration_selection_reports_absent_tiers_without_running_them(runner):
    result, records = runner(TEST_TIER="integration")
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(records) == 2
    assert records[0]["module"] == "app-tools"
    assert records[0]["args"][-1] == "tests/integration"
    assert "No integration tests in app-error." in result.stdout


@pytest.mark.parametrize("settings, paths", [({"TEST_TIER": "invalid"}, ()), ({"TEST_TIER": "unit"}, ("tests",))])
def test_invalid_or_ambiguous_tier_selection_fails_before_launch(runner, settings, paths):
    result, records = runner(paths=paths, **settings)
    assert result.returncode == 2
    assert records == []
