"""Static command conventions must fail closed without executing consumer code."""

import pytest
from app_tools.architecture import RULES

from tests.unit.architecture.support import app_violations, rules_check, scan, severity

CONFIG = """[project]
name = "consumer"
[[tool.app-tools.architecture.commands]]
source = "consumer.features"
"""


def project(tmp_path, source, module="src/consumer/features/books/commands.py", config=CONFIG):
    (tmp_path / "pyproject.toml").write_text(config)
    path = tmp_path / module
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path


@pytest.mark.parametrize(
    "source",
    [
        "async def show(ctx: Ctx, inp: Input) -> Output: ...",
        'async def show(ctx: "consumer.Ctx", _: "Empty") -> "Output": ...',
        "def _helper(x): ...\nasync def show(ctx: Ctx, inp: Input) -> Output: ...",
        "from .schemas import Input as In\nasync def show(ctx: Ctx, inp: In) -> Output: ...",
    ],
)
def test_accepts_command_shape(tmp_path, source):
    assert scan(project(tmp_path, source)) == []


@pytest.mark.parametrize(
    "source",
    [
        "def show(ctx: Ctx, inp: Input) -> Output: ...",
        "async def show(ctx, inp: Input) -> Output: ...",
        "async def show(ctx: Ctx, inp: Input): ...",
        "async def show(ctx: Ctx, inp: Any) -> Output: ...",
        "async def show(ctx: Ctx, inp: Input) -> dict: ...",
        "async def show(ctx: Ctx, inp: Input, extra: Extra) -> Output: ...",
        "async def show(ctx: Ctx, *, inp: Input) -> Output: ...",
        "async def show(ctx: Ctx, inp: Input = None) -> Output: ...",
        "async def show(ctx: Ctx, *inp: Input) -> Output: ...",
        "@decorator\nasync def show(ctx: Ctx, inp: Input) -> Output: ...",
        "class Show: pass",
    ],
)
def test_rejects_signature_drift(tmp_path, source):
    violations = scan(project(tmp_path, source))
    assert [v.rule for v in violations] == ["RULE-app-command-signature"]
    assert severity(violations[0]) == "error"
    assert RULES[violations[0].rule].guide == "backend/commands"


@pytest.mark.parametrize(
    "call",
    [
        "ctx.tx.session.commit()",
        "ctx.tx.session.rollback()",
        "ctx.transaction()",
        "ctx.store.tx()",
        "session.begin()",
        "session.begin_nested()",
    ],
)
def test_rejects_transaction_control_even_in_private_helpers(tmp_path, call):
    path = project(tmp_path, f"async def _helper(ctx):\n    await {call}\n")
    exit_code, document = rules_check(tmp_path, path)
    assert exit_code == 1
    [violation] = app_violations(document)
    assert (violation["rule_id"], violation["line"]) == ("RULE-app-command-transaction", 2)


@pytest.mark.parametrize(
    "module", ["src/consumer/features/books/usecases.py", "src/consumer/features_extra/books/commands.py"]
)
def test_scoped_to_selected_command_modules(tmp_path, module):
    assert scan(project(tmp_path, "def show(): ...", module)) == []


def test_flat_layout_and_explicit_suppression(tmp_path):
    path = project(
        tmp_path,
        "def show(): ...  # arch: ignore[RULE-app-command-signature] -- transitional API\n",
        "consumer/features/books/commands.py",
    )
    assert scan(path) == []


@pytest.mark.parametrize(
    "config",
    [
        '[tool.app-tools.architecture]\ncommands = "bad"',
        '[[tool.app-tools.architecture.commands]]\nsource = "consumer.*"',
        CONFIG + "unknown = true",
        CONFIG + '[[tool.app-tools.architecture.commands]]\nsource = "consumer.features"',
    ],
)
def test_invalid_command_config(tmp_path, config):
    path = project(tmp_path, "", config=config)
    assert [v.rule for v in scan(path)] == ["RULE-app-architecture-config"]


def test_command_checks_remain_opt_in(tmp_path):
    path = project(tmp_path, "def show(): ...", config='[project]\nname = "consumer"')
    assert scan(path) == []
