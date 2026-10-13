from pathlib import Path

import pytest

from tests.unit.architecture.support import app_violations, rules_check, scan, severity


def test_scan_detects_router_repo_import(tmp_path: Path):
    api_file = tmp_path / "app/api/v1/items.py"
    api_file.parent.mkdir(parents=True)
    api_file.write_text("from app.features.items.repos import ItemRepository\n")

    violations = scan(tmp_path)
    assert len(violations) == 1
    assert violations[0].rule == "RULE-app-router-repo-import"


def test_scan_detects_hook_super_call(tmp_path: Path):
    service_file = tmp_path / "app/features/items/services.py"
    service_file.parent.mkdir(parents=True)
    service_file.write_text(
        "class AuditHook:\n    async def create_pre(self, op):\n        await super().create_pre(op)\n"
    )

    violations = scan(tmp_path)
    assert len(violations) == 1
    assert violations[0].rule == "RULE-app-hook-super-call"


def test_scan_detects_service_commit(tmp_path: Path):
    service_file = tmp_path / "app/features/items/services.py"
    service_file.parent.mkdir(parents=True)
    service_file.write_text(
        "class ItemService:\n    async def do_something(self, session):\n        await session.commit()\n"
    )

    violations = scan(tmp_path)
    assert len(violations) == 1
    assert violations[0].rule == "RULE-app-service-commit"


def test_scan_passes_for_clean_code(tmp_path: Path):
    api_file = tmp_path / "app/api/v1/items.py"
    api_file.parent.mkdir(parents=True)
    api_file.write_text(
        "from app.features.items.usecases.crud import GetItemUseCase\nfrom app.features.items.schemas import ItemRead\n"
    )

    service_file = tmp_path / "app/features/items/services.py"
    service_file.parent.mkdir(parents=True, exist_ok=True)
    service_file.write_text("class AuditHook:\n    async def create_pre(self, op):\n        return op\n")

    violations = scan(tmp_path)
    assert len(violations) == 0


def test_rules_check_passes_a_clean_workspace(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('ok')\n")
    exit_code, document = rules_check(tmp_path)
    assert exit_code == 0
    assert app_violations(document) == []


def test_rules_check_reports_each_finding_under_its_rule(tmp_path: Path):
    service = tmp_path / "app/features/items/services.py"
    service.parent.mkdir(parents=True)
    service.write_text("async def run(session):\n    await session.commit()\n")
    exit_code, document = rules_check(tmp_path)
    assert exit_code == 1
    [violation] = app_violations(document)
    assert violation["rule_id"] == "RULE-app-service-commit"
    assert violation["file"] == "app/features/items/services.py"
    assert violation["line"] == 2
    assert violation["severity"] == "error"
    assert "UseCase" in violation["remediation"]


def test_rules_check_skips_tests_and_migrations(tmp_path: Path):
    for folder in ("tests", "migrations"):
        path = tmp_path / folder / "services.py"
        path.parent.mkdir(parents=True)
        path.write_text("session.commit()\n")
    assert app_violations(rules_check(tmp_path)[1]) == []


@pytest.mark.parametrize(
    "source",
    [
        "from feature.repos.item import Repository",
        "from feature import repos",
        "from . import repos",
        "import feature.repos.item",
    ],
)
def test_repository_import_forms(tmp_path, source):
    path = tmp_path / "router.py"
    path.write_text(source)
    assert [v.rule for v in scan(path)] == ["RULE-app-router-repo-import"]


@pytest.mark.parametrize(
    "source",
    [
        "from feature.repository_utils import helper",
        "from app_layer_base.base.repos.query_options import ListQueryOptions",
    ],
)
def test_repository_value_objects_are_not_layer_violations(tmp_path, source):
    path = tmp_path / "router.py"
    path.write_text(source)
    assert scan(path) == []


def test_suppression_requires_code_reason_and_actual_comment(tmp_path):
    path = tmp_path / "services.py"
    path.write_text(
        'note = "# arch: ignore[RULE-app-service-commit] -- not a comment"; session.commit()\n'
        "session.commit()  # arch: ignore[RULE-app-service-commit] -- legacy boundary\n"
        "session.rollback()  # arch: ignore[RULE-app-hook-super-call] -- wrong code\n"
        "session.commit()  # arch: ignore[RULE-app-service-commit]\n"
        "session.commit()  # noqa\n"
    )
    assert [v.line for v in scan(path) if severity(v) == "error"] == [1, 3, 4, 5]


def test_parse_errors_fail_and_overlapping_targets_are_deduplicated(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def broken(")
    exit_code, document = rules_check(tmp_path, tmp_path, path)
    assert exit_code == 1
    assert [v["rule_id"] for v in app_violations(document)] == ["RULE-app-parse-error"]


def test_unknown_and_unused_suppressions_warn(tmp_path):
    path = tmp_path / "services.py"
    path.write_text(
        "x = 1  # arch: ignore[RULE-app-service-commit] -- stale\ny = 2  # arch: ignore[ARCH_OLD] -- typo\n"
    )
    assert [(v.rule, v.line, v.message) for v in scan(path)] == [
        ("RULE-app-invalid-suppression", 1, "Unused suppression of RULE-app-service-commit."),
        ("RULE-app-invalid-suppression", 2, "Unknown suppression of ARCH_OLD."),
    ]


def test_adapter_isolation_in_scoped_scan(tmp_path):
    for name in ("app_first", "app_second"):
        root = tmp_path / f"packages/adapters/{name}/src/{name}"
        root.mkdir(parents=True)
        (root / "__init__.py").touch()
    path = tmp_path / "packages/adapters/app_first/src/app_first/client.py"
    path.write_text("from app_second.client import Client\nimport app_first\n")
    assert [v.rule for v in scan(path)] == ["RULE-app-adapter-dependency"]
