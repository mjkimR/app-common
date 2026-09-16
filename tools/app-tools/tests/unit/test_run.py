"""Exercise command boundaries, real subprocess output, and project discovery."""

import json
import sys

import pytest
from app_tools.cli import cli
from app_tools.runner.execution import MAX_OUTPUT, execute
from app_tools.runner.planning import Step, discover, plan_task, plan_tool
from click.testing import CliRunner


def manifest(root, name="pkg", extra=""):
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.0.0"\n{extra}')
    return root


def node(root, scripts):
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(json.dumps({"scripts": scripts}))
    return root


def test_discovers_packages_without_generated_or_nested_repository_targets(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["packages/*"]\n')
    package = manifest(tmp_path / "packages/core")
    (package / "tests").mkdir()
    web = node(tmp_path / "web", {"test": "vitest run"})
    manifest(tmp_path / ".venv/fake")
    node(tmp_path / "web/node_modules/fake", {"test": "exit 1"})
    nested = manifest(tmp_path / "another-repo")
    (nested / ".git").write_text("gitdir: elsewhere")
    assert set(discover(tmp_path)) == {tmp_path, package, web}
    steps, _ = plan_task(tmp_path, "test")
    assert [(step.cwd, step.argv[:3]) for step in steps] == [
        (package, ("uv", "run", "--no-sync")),
        (web, ("npm", "run", "test")),
    ]
    scoped, _ = plan_task(web, "test")
    assert len(scoped) == 1
    assert scoped[0].cwd == web


def test_pyright_inherits_workspace_config_without_rechecking_other_packages(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pyright]\ntypeCheckingMode = "basic"\n')
    package = manifest(tmp_path / "packages/core")
    (package / "src").mkdir()
    steps, _ = plan_task(tmp_path, "check")
    assert steps[0].argv[-3:] == ("--project", str(tmp_path / "pyproject.toml"), str(package / "src"))


def test_pyright_configuration_does_not_cross_git_boundary(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pyright]\n")
    package = manifest(tmp_path / "repo")
    (package / ".git").mkdir()
    steps, skipped = plan_task(package, "check")
    assert steps == []
    assert "no Pyright" in skipped[0]


def test_lint_is_read_only_unless_fix_requested(tmp_path):
    manifest(tmp_path)
    normal, _ = plan_task(tmp_path, "lint")
    fixing, _ = plan_task(tmp_path, "lint", fix=True)
    assert "--check" in normal[0].argv
    assert "--fix" not in normal[1].argv
    assert "--check" not in fixing[0].argv
    assert "--fix" in fixing[1].argv


def test_npm_scripts_are_preserved_and_fix_is_explicit(tmp_path):
    node(tmp_path, {"test": "vitest run && playwright test", "lint": "prettier --check . && eslint ."})
    steps, _ = plan_task(tmp_path, "test")
    assert steps[0].argv == ("npm", "run", "test")
    with pytest.raises(ValueError, match="lint:fix"):
        plan_task(tmp_path, "lint", fix=True)
    node(tmp_path, {"lint:fix": "prettier --write . && eslint . --fix"})
    steps, _ = plan_task(tmp_path, "lint", fix=True)
    assert steps[0].argv == ("npm", "run", "lint:fix")


def test_tool_uses_local_node_binary_and_never_downloads(tmp_path):
    with pytest.raises(ValueError, match="install project dependencies"):
        plan_tool(tmp_path, "vitest", ("run",))
    binary = tmp_path / "node_modules/.bin/vitest"
    binary.parent.mkdir(parents=True)
    binary.touch()
    assert plan_tool(tmp_path, "vitest", ("run",)).argv == (str(binary), "run")


def test_tool_arguments_after_separator_are_not_parsed_by_wrapper(tmp_path, monkeypatch):
    calls = []

    def record(step, log_dir, raw, warn_after):
        calls.append((step, raw))
        return 5

    monkeypatch.setattr("app_tools.commands.run.execute", record)
    result = CliRunner().invoke(cli, ["run", "pytest", "--path", str(tmp_path), "--", "--raw", "-k", "a or b"])
    assert result.exit_code == 5
    assert calls[0][0].argv == ("uv", "run", "--no-sync", "pytest", "--raw", "-k", "a or b")
    assert calls[0][1] is False


def test_generic_execution_keeps_exit_code_cwd_stdout_and_stderr(tmp_path):
    script = "import os,sys; print(os.getcwd()); print('stderr error', file=sys.stderr); sys.exit(7)"
    result = CliRunner().invoke(cli, ["run", "--path", str(tmp_path), "--", sys.executable, "-c", script])
    assert result.exit_code == 7
    assert str(tmp_path) in result.output
    assert "stderr error" in result.output
    assert "FAIL(7)" in result.output


def test_success_is_compact_and_original_output_is_recoverable(tmp_path, capsys):
    step = Step(tmp_path, (sys.executable, "-c", "print('verbose success output')"), "sample")
    assert execute(step, tmp_path) == 0
    output = capsys.readouterr().out
    assert "PASS" in output
    assert "verbose success output" not in output
    assert next(tmp_path.glob("*.log")).read_text().strip() == "verbose success output"


def test_raw_prints_success_output(tmp_path):
    result = CliRunner().invoke(
        cli, ["run", "--raw", "--path", str(tmp_path), "--", sys.executable, "-c", "print('visible')"]
    )
    assert result.exit_code == 0
    assert "visible" in result.output


def test_large_failure_is_bounded_and_log_is_complete(tmp_path, capsys):
    script = f"import sys; print('START'); print('x' * {MAX_OUTPUT * 3}); print('END'); sys.exit(1)"
    assert execute(Step(tmp_path, (sys.executable, "-c", script), "large"), tmp_path) == 1
    output = capsys.readouterr().out
    assert "START" in output and "END" in output and "output omitted" in output
    assert len(output) < MAX_OUTPUT + 2000
    assert next(tmp_path.glob("*.log")).stat().st_size > MAX_OUTPUT * 3


def test_missing_command_is_a_reported_failure(tmp_path, capsys):
    assert execute(Step(tmp_path, (str(tmp_path / "absent"),), "absent"), tmp_path) == 127
    assert "FAIL(127)" in capsys.readouterr().out


def test_all_task_steps_execute_after_failure(tmp_path, monkeypatch):
    manifest(tmp_path)
    calls = []

    def record(step, log_dir, raw, warn_after):
        calls.append(step)
        return 3 if len(calls) == 1 else 0

    monkeypatch.setattr("app_tools.commands.run.execute", record)
    result = CliRunner().invoke(cli, ["run", "lint", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert len(calls) == 2
    assert "1 passed, 1 failed" in result.output


@pytest.mark.parametrize("args", [["test", "--fix"], ["test", "--", "-k", "foo"], ["unknown"]])
def test_invalid_arguments_fail_before_execution(tmp_path, args):
    result = CliRunner().invoke(cli, ["run", "--path", str(tmp_path), *args])
    assert result.exit_code != 0
    assert "PASS" not in result.output


def test_empty_directory_is_not_reported_as_success(tmp_path):
    result = CliRunner().invoke(cli, ["run", "test", "--path", str(tmp_path)])
    assert result.exit_code != 0
    assert "No runnable targets" in result.output


def test_workspace_exclusions_are_respected_but_explicit_path_can_run_them(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\nexclude = ["packages/experimental"]\n'
    )
    included = manifest(tmp_path / "packages/core")
    excluded = manifest(tmp_path / "packages/experimental")
    manifest(tmp_path / "unregistered")
    steps, _ = plan_task(tmp_path, "lint")
    assert {step.cwd for step in steps} == {included}
    scoped, _ = plan_task(excluded, "lint")
    assert {step.cwd for step in scoped} == {excluded}


def test_pytest_options_remain_owned_by_project(tmp_path):
    manifest(tmp_path, extra='[tool.pytest.ini_options]\naddopts = "-n auto"\ntestpaths = ["specs"]\n')
    steps, _ = plan_task(tmp_path, "test")
    assert steps[0].argv == ("uv", "run", "--no-sync", "pytest")


def test_raw_generic_command_does_not_expand_shell_characters(tmp_path):
    argument = "$(echo bad); a b"
    result = CliRunner().invoke(
        cli,
        [
            "run",
            "--raw",
            "--path",
            str(tmp_path),
            "--",
            sys.executable,
            "-c",
            "import sys; print(sys.argv[1])",
            argument,
        ],
    )
    assert result.exit_code == 0
    assert argument in result.output


@pytest.mark.parametrize("code", [0, 7])
@pytest.mark.parametrize("raw", [False, True])
def test_slow_command_warns_once_and_preserves_result(tmp_path, mocker, capsys, code, raw):
    import subprocess

    process = mocker.Mock()
    process.wait.side_effect = [subprocess.TimeoutExpired("test", 2), code]
    mocker.patch("app_tools.runner.execution.subprocess.Popen", return_value=process)
    assert execute(Step(tmp_path, ("test",), "test"), tmp_path, raw, warn_after=2) == code
    assert process.wait.call_args_list == [mocker.call(timeout=2), mocker.call()]
    output = capsys.readouterr()
    assert output.err.count("RUN_SLOW_COMMAND") == 1
    assert "still running" in output.err


def test_slow_warning_can_be_disabled(tmp_path, mocker, capsys):
    process = mocker.Mock()
    process.wait.return_value = 0
    mocker.patch("app_tools.runner.execution.subprocess.Popen", return_value=process)
    assert execute(Step(tmp_path, ("test",), "test"), tmp_path, warn_after=0) == 0
    process.wait.assert_called_once_with(timeout=None)
    assert "RUN_SLOW_COMMAND" not in capsys.readouterr().err


@pytest.mark.parametrize("value", ["-1", "nan", "inf"])
def test_invalid_warning_threshold_is_rejected(value):
    result = CliRunner().invoke(cli, ["run", "--warn-after", value, "--", "echo", "ok"])
    assert result.exit_code == 2


def test_cli_forwards_warning_threshold(tmp_path, mocker):
    execute_mock = mocker.patch("app_tools.commands.run.execute", return_value=0)
    result = CliRunner().invoke(cli, ["run", "--warn-after", "15", "--path", str(tmp_path), "--", "echo", "ok"])
    assert result.exit_code == 0
    assert execute_mock.call_args.kwargs == {"warn_after": 15}


@pytest.mark.parametrize("options", [["--no-warn"], ["--warn-after", "2", "--no-warn"]])
def test_no_warn_disables_runner_warning(tmp_path, mocker, options):
    execute_mock = mocker.patch("app_tools.commands.run.execute", return_value=0)
    result = CliRunner().invoke(cli, ["run", *options, "--path", str(tmp_path), "--", "echo", "ok"])
    assert result.exit_code == 0
    assert execute_mock.call_args.kwargs == {"warn_after": 0}


def test_architecture_lint_opt_in_inherits_and_can_be_overridden(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.app-tools]\ncheck-arch = true\n")
    package = manifest(tmp_path / "package")
    (package / "src").mkdir()
    steps, _ = plan_task(package, "lint")
    assert steps[-1].argv == (sys.executable, "-m", "app_tools.cli", "check-arch", "src")
    manifest(package, extra="[tool.app-tools]\ncheck-arch = false\n")
    steps, _ = plan_task(package, "lint")
    assert len(steps) == 2


def test_architecture_setting_does_not_cross_repository_boundary(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.app-tools]\ncheck-arch = true\n")
    package = manifest(tmp_path / "package")
    (package / ".git").mkdir()
    steps, _ = plan_task(package, "lint")
    assert len(steps) == 2


def test_successful_architecture_warnings_are_visible_in_compact_output(tmp_path, capsys):
    script = "print('noise'); print('WARN [ARCH_DIRECT_CURRENT_TIME] file.py:1: use UTC utility')"
    step = Step(tmp_path, (sys.executable, "-c", script), "check-arch")
    assert execute(step, tmp_path, warn_after=0) == 0
    output = capsys.readouterr().out
    assert "WARN [ARCH_DIRECT_CURRENT_TIME]" in output
    assert "noise" not in output
    assert "PASS" in output


def test_success_warning_output_is_bounded(tmp_path, capsys):
    script = "print(('WARN [ARCH_DIRECT_CURRENT_TIME] ' + 'x' * 100 + '\\n') * 300)"
    assert execute(Step(tmp_path, (sys.executable, "-c", script), "check-arch"), tmp_path) == 0
    output = capsys.readouterr().out
    assert len(output) < MAX_OUTPUT + 1000
    assert "warnings omitted" in output
