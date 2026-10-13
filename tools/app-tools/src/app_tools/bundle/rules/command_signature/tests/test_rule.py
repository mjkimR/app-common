"""``RULE-app-command-signature``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)

CONFIG = """[project]
name = "consumer"
[[tool.app-tools.architecture.commands]]
source = "consumer.features"
"""


def project(
    source: str, module: str = "src/consumer/features/books/commands.py", config: str = CONFIG
) -> dict[str, str]:
    return {"pyproject.toml": config, module: source}


@pytest.mark.parametrize(
    "source",
    [
        "async def show(ctx: Ctx, inp: Input) -> Output: ...",
        'async def show(ctx: "consumer.Ctx", _: "Empty") -> "Output": ...',
        "def _helper(x): ...\nasync def show(ctx: Ctx, inp: Input) -> Output: ...",
        "from .schemas import Input as In\nasync def show(ctx: Ctx, inp: In) -> Output: ...",
    ],
)
def test_accepts_the_command_shape(tmp_path: Path, source: str) -> None:
    assert check(RULE, tmp_path, project(source)) == []


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
def test_rejects_signature_drift(tmp_path: Path, source: str) -> None:
    [violation] = check(RULE, tmp_path, project(source))
    assert violation.severity.value == "error"


@pytest.mark.parametrize(
    "module", ["src/consumer/features/books/usecases.py", "src/consumer/features_extra/books/commands.py"]
)
def test_only_configured_command_modules_are_checked(tmp_path: Path, module: str) -> None:
    assert check(RULE, tmp_path, project("def show(): ...", module)) == []


def test_flat_layout_and_explicit_suppression(tmp_path: Path) -> None:
    source = "def show(): ...  # arch: ignore[RULE-app-command-signature] -- transitional API\n"
    assert check(RULE, tmp_path, project(source, "consumer/features/books/commands.py")) == []


def test_the_checks_are_opt_in(tmp_path: Path) -> None:
    assert check(RULE, tmp_path, project("def show(): ...", config='[project]\nname = "consumer"')) == []
