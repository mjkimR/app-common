from pathlib import Path

import pytest
from app_tools.commands.check_arch import check_arch, scan_directory
from click.testing import CliRunner


def test_scan_detects_router_repo_import(tmp_path: Path):
    api_file = tmp_path / "app/api/v1/items.py"
    api_file.parent.mkdir(parents=True)
    api_file.write_text("from app.features.items.repos import ItemRepository\n")

    violations = scan_directory([tmp_path])
    assert len(violations) == 1
    assert violations[0].rule == "ARCH_ROUTER_REPO_IMPORT"


def test_scan_detects_hook_super_call(tmp_path: Path):
    service_file = tmp_path / "app/features/items/services.py"
    service_file.parent.mkdir(parents=True)
    service_file.write_text(
        "class AuditHook:\n    async def create_pre(self, op):\n        await super().create_pre(op)\n"
    )

    violations = scan_directory([tmp_path])
    assert len(violations) == 1
    assert violations[0].rule == "ARCH_HOOK_SUPER_CALL"


def test_scan_detects_service_commit(tmp_path: Path):
    service_file = tmp_path / "app/features/items/services.py"
    service_file.parent.mkdir(parents=True)
    service_file.write_text(
        "class ItemService:\n    async def do_something(self, session):\n        await session.commit()\n"
    )

    violations = scan_directory([tmp_path])
    assert len(violations) == 1
    assert violations[0].rule == "ARCH_SERVICE_COMMIT"


def test_scan_passes_for_clean_code(tmp_path: Path):
    api_file = tmp_path / "app/api/v1/items.py"
    api_file.parent.mkdir(parents=True)
    api_file.write_text(
        "from app.features.items.usecases.crud import GetItemUseCase\nfrom app.features.items.schemas import ItemRead\n"
    )

    service_file = tmp_path / "app/features/items/services.py"
    service_file.parent.mkdir(parents=True, exist_ok=True)
    service_file.write_text("class AuditHook:\n    async def create_pre(self, op):\n        return op\n")

    violations = scan_directory([tmp_path])
    assert len(violations) == 0


def test_check_arch_cli_json_mode(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(check_arch, [str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert '"status": "passed"' in result.output


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
    assert [v.rule for v in scan_directory([path])] == ["ARCH_ROUTER_REPO_IMPORT"]


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
    assert scan_directory([path]) == []


def test_suppression_requires_code_reason_and_actual_comment(tmp_path):
    path = tmp_path / "services.py"
    path.write_text(
        'note = "# arch: ignore[ARCH_SERVICE_COMMIT] -- not a comment"; session.commit()\n'
        "session.commit()  # arch: ignore[ARCH_SERVICE_COMMIT] -- legacy boundary\n"
        "session.rollback()  # arch: ignore[ARCH_HOOK_SUPER_CALL] -- wrong code\n"
        "session.commit()  # arch: ignore[ARCH_SERVICE_COMMIT]\n"
        "session.commit()  # noqa\n"
    )
    assert [v.line for v in scan_directory([path]) if v.severity == "error"] == [1, 3, 4, 5]


def test_parse_errors_fail_and_overlapping_targets_are_deduplicated(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def broken(")
    result = CliRunner().invoke(check_arch, [str(tmp_path), str(path), "--json"])
    assert result.exit_code == 1
    assert '"violations_count": 1' in result.output
    assert "ARCH_PARSE_ERROR" in result.output


def test_app_error_rejects_external_imports_but_allows_stdlib_and_relative_imports(tmp_path):
    path = tmp_path / "packages/base/app-error/src/app_error/module.py"
    path.parent.mkdir(parents=True)
    path.write_text("import dataclasses\nfrom .types import Error\nimport httpx\n")
    violations = scan_directory([path])
    assert [(v.rule, v.line) for v in violations] == [("ARCH_ERROR_DEPENDENCY", 3)]


def test_adapter_isolation_in_scoped_scan(tmp_path):
    for name in ("app_first", "app_second"):
        root = tmp_path / f"packages/adapters/{name}/src/{name}"
        root.mkdir(parents=True)
        (root / "__init__.py").touch()
    path = tmp_path / "packages/adapters/app_first/src/app_first/client.py"
    path.write_text("from app_second.client import Client\nimport app_first\n")
    assert [v.rule for v in scan_directory([path])] == ["ARCH_ADAPTER_DEPENDENCY"]
