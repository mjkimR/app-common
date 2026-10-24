"""``RULE-app-service-commit``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

from devkit_agt.features.rules.services.testing import check, load_rule

RULE = load_rule(__file__)


def test_a_service_committing_is_reported(tmp_path: Path) -> None:
    found = check(
        RULE, tmp_path, {"app/features/items/services.py": "async def run(session):\n    await session.commit()\n"}
    )
    assert [(v.file, v.line, v.severity.value) for v in found] == [("app/features/items/services.py", 2, "error")]
    assert "UseCase" in found[0].remediation


def test_other_modules_tests_and_migrations_are_not_checked(tmp_path: Path) -> None:
    files = {
        "app/features/items/usecases.py": "session.commit()\n",
        "tests/services.py": "session.commit()\n",
        "migrations/services.py": "session.commit()\n",
        "alembic/services.py": "session.commit()\n",
    }
    assert check(RULE, tmp_path, files) == []


def test_only_a_reasoned_inline_comment_naming_the_rule_suppresses(tmp_path: Path) -> None:
    source = (
        'note = "# arch: ignore[RULE-app-service-commit] -- not a comment"; session.commit()\n'
        "session.commit()  # arch: ignore[RULE-app-service-commit] -- legacy boundary\n"
        "session.rollback()  # arch: ignore[RULE-app-hook-super-call] -- wrong rule\n"
        "session.commit()  # arch: ignore[RULE-app-service-commit]\n"
        "session.commit()  # noqa\n"
    )
    assert [v.line for v in check(RULE, tmp_path, {"services.py": source})] == [1, 3, 4, 5]
