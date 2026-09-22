import sys

import pytest
from app_tools.runner.execution import execute
from app_tools.runner.planning import Step


@pytest.mark.parametrize("raw,code", [(False, 0), (True, 0), (False, 1)])
def test_wrapped_suites_keep_order_without_duplicate_raw_or_failure_output(tmp_path, capsys, raw, code):
    original = "noise\n3 passed, 1 skipped in 0.10s\nmore noise\nTests  8 passed (8)\n"
    script = f"import sys; print({original!r}, end=''); sys.exit({code})"
    step = Step(tmp_path, (sys.executable, "-c", script), "npm test")
    assert execute(step, tmp_path, raw=raw) == code
    output = capsys.readouterr().out
    assert output.count("3 passed, 1 skipped in 0.10s") == 1
    assert output.count("Tests  8 passed (8)") == 1
    assert output.index("3 passed") < output.index("Tests  8")
    assert ("noise" in output) == (raw or code != 0)
    assert next(tmp_path.glob("*.log")).read_text() == original


def test_repeated_warnings_show_first_location_and_preserve_original_count(tmp_path, capsys):
    original = (
        "tests/test_db.py::test_one\n"
        "  lib/db.py:12: UserWarning: In-memory database\n"
        "    source_code()\n\n"
        "tests/test_db.py::test_two\n"
        "  lib/db.py:40: UserWarning: In-memory database\n"
        "    source_code()\n\n"
        "2 passed, 2 warnings in 0.10s\n"
    )
    step = Step(tmp_path, (sys.executable, "-c", f"print({original!r}, end='')"), "pytest")
    assert execute(step, tmp_path) == 0
    output = capsys.readouterr().out
    assert output.count("WARN UserWarning: In-memory database") == 1
    assert "[lib/db.py:12]" in output
    assert "lib/db.py:40" not in output
    assert "source_code" not in output
    assert "2 passed, 2 warnings in 0.10s" in output
    assert next(tmp_path.glob("*.log")).read_text() == original
