import sys

from app_tools.cli import cli
from app_tools.runner.execution import MAX_OUTPUT, execute
from app_tools.runner.planning import Step
from click.testing import CliRunner


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
