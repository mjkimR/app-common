from pathlib import Path

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
