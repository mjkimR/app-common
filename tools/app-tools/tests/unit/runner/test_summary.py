"""Verify compact output against terminal formats and real subprocess boundaries."""

import pytest
from app_tools.runner.planning import plan_tool
from app_tools.runner.summary import MAX_LINE, MAX_SUMMARY, MAX_WARNING_MESSAGE, MAX_WARNINGS, summaries


@pytest.mark.parametrize(
    "line",
    [
        "===== 42 passed, 2 skipped, 3 deselected, 1 xfailed, 4 warnings in 1.23s =====",
        "42 passed, 1 xpassed, 2 rerun in 65.20s (0:01:05)",
        "no tests ran in 0.01s",
        " Test Files  2 passed | 1 skipped (3)",
        "      Tests  12 passed | 2 skipped | 1 todo (15)",
        "  12 passed (1.2m)",
        "  2 flaky",
        "  3 did not run",
        "12 files already formatted",
        "1 file reformatted, 12 files left unchanged",
        "All checks passed!",
        "Found 3 errors (3 fixed, 0 remaining).",
        "0 errors, 2 warnings, 0 informations",
        "svelte-check found 0 errors and 2 warnings in 1 file",
        "✖ 2 problems (0 errors, 2 warnings)",
        "All matched files use Prettier code style!",
    ],
)
def test_recognizes_terminal_summaries_with_color_and_crlf(tmp_path, line):
    log = tmp_path / "output.log"
    log.write_bytes(f"uninteresting output\n\x1b[32m{line}\x1b[0m\r\n".encode())
    assert list(summaries(log)) == [line.strip().strip("=").strip()]


@pytest.mark.parametrize("line", ["TOTAL   100  10  90%", "TOTAL   100  10  20  2  88.5%"])
def test_coverage_total_has_context(tmp_path, line):
    log = tmp_path / "output.log"
    log.write_text(line)
    assert list(summaries(log)) == [f"Coverage: {line}"]


def test_does_not_infer_results_from_progress_or_arbitrary_messages(tmp_path):
    log = tmp_path / "output.log"
    log.write_text(
        "tests/test_sample.py::test_ok PASSED\n"
        "collected 42 items\n"
        "test example: 42 passed\n"
        "Tests 12 passed (13) extra text\n"
        "verbose success output\n"
    )
    assert list(summaries(log)) == []


def test_summary_budget_and_long_lines_are_bounded(tmp_path):
    log = tmp_path / "output.log"
    log.write_text("x" * (MAX_LINE * 100) + "42 passed\n" + "12 passed in 0.10s\n" * MAX_SUMMARY)
    result = list(summaries(log))
    assert result[0] == "12 passed in 0.10s"
    assert "summaries omitted" in result[-1]
    assert sum(len(line) + 1 for line in result[:-1]) <= MAX_SUMMARY


def test_explicit_uv_keeps_active_environment_choice(tmp_path):
    step = plan_tool(tmp_path, "uv", ("run", "--active", "python"))
    assert step.argv == ("uv", "run", "--active", "python")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("lib/db.py:12: UserWarning: In-memory database", "WARN UserWarning: In-memory database [lib/db.py:12]"),
        (
            "src/app.py:2:3 - warning: Unused import (reportUnusedImport)",
            "WARN Unused import (reportUnusedImport) [src/app.py:2:3]",
        ),
        (
            "(node:123) [DEP0040] DeprecationWarning: Deprecated module",
            "WARN [DEP0040] DeprecationWarning: Deprecated module",
        ),
        ("warning: Deprecated configuration", "WARN Deprecated configuration"),
        ("src/App.svelte:2:3\nWarn: Missing label (svelte)", "WARN Missing label (svelte) [src/App.svelte:2:3]"),
        (
            "/project/src/app.ts\n  2:3  warning  Unused variable  no-unused-vars",
            "WARN Unused variable no-unused-vars [/project/src/app.ts:2:3]",
        ),
    ],
)
def test_warning_messages_include_context_without_source_excerpts(tmp_path, text, expected):
    log = tmp_path / "output.log"
    log.write_text(f"\x1b[33m{text}\x1b[0m\n  unrelated source excerpt\n")
    assert list(summaries(log)) == [expected]


def test_warning_budget_does_not_hide_test_results(tmp_path):
    log = tmp_path / "output.log"
    log.write_text("".join(f"warning: issue {i}\n" for i in range(500)) + "12 passed, 500 warnings in 0.10s\n")
    result = list(summaries(log))
    assert sum(len(line) + 1 for line in result if line.startswith("WARN ")) <= MAX_WARNINGS
    assert sum("warnings omitted" in line for line in result) == 1
    assert result[-1] == "12 passed, 500 warnings in 0.10s"


@pytest.mark.parametrize("length", [700, MAX_LINE * 100])
def test_long_warning_message_keeps_category_and_location(tmp_path, length):
    log = tmp_path / "output.log"
    log.write_text("lib/db.py:12: UserWarning: " + "x" * length)
    result = list(summaries(log))
    assert len(result) == 1
    assert result[0].startswith("WARN UserWarning: ")
    assert result[0].endswith("... [lib/db.py:12]")
    assert len(result[0]) < MAX_WARNING_MESSAGE + 100


def test_suppressed_warning_details_are_not_invented(tmp_path):
    log = tmp_path / "output.log"
    log.write_text("2 passed, 1 warning in 0.10s\n")
    assert list(summaries(log)) == ["2 passed, 1 warning in 0.10s"]
