"""Package-aware warnings must distinguish real imports, scope, and ownership."""

import json
from pathlib import Path

import pytest
from app_tools.commands.check_arch import check_arch, scan_directory
from click.testing import CliRunner


def source(tmp_path: Path, code: str, dependencies=("app-http-client", "app-layer-base"), name="consumer") -> Path:
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n')
    path = tmp_path / "src/consumer/main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)
    return path


@pytest.mark.parametrize(
    "code",
    [
        "import httpx as hx\nhx.AsyncClient()",
        "from httpx import Client as C\nC()",
        "import httpx\nfactory = httpx.AsyncClient\nfactory()",
    ],
)
def test_http_constructor_aliases_warn_without_failing(tmp_path, code):
    path = source(tmp_path, code)
    result = CliRunner().invoke(check_arch, [str(path), "--json"])
    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["status"] == "passed"
    assert report["warnings_count"] == 1
    assert report["errors_count"] == 0
    diagnostic = report["violations"][0]
    assert diagnostic["rule"] == "ARCH_HTTP_CLIENT_CONSTRUCTION"
    assert diagnostic["guide"] == "http"
    assert "get_http_" in diagnostic["fix"]


@pytest.mark.parametrize(
    "code",
    [
        "from datetime import datetime as D\nD.now()",
        "import datetime as dt\ndt.datetime.utcnow()",
        "from datetime import date\ndate.today()",
    ],
)
def test_clock_aliases(tmp_path, code):
    assert [v.rule for v in scan_directory([source(tmp_path, code)])] == ["ARCH_DIRECT_CURRENT_TIME"]


@pytest.mark.parametrize(
    "code",
    [
        "import httpx\ndef call(httpx):\n    httpx.Client()",
        "from httpx import Client\ndef call():\n    Client = custom\n    Client()",
        "import httpx\nhttpx = custom\nhttpx.Client()",
        "class Client:\n    pass\nClient()",
        'import datetime\ndatetime.timedelta(days=1)\ndatetime.datetime.fromisoformat("2026-01-01")',
        "from sqlalchemy import func\nfunc.now()",
        "from time import monotonic\nmonotonic()",
    ],
)
def test_shadowed_names_and_non_clock_datetime_usage_are_allowed(tmp_path, code):
    assert scan_directory([source(tmp_path, code)]) == []


def test_unrelated_package_does_not_inherit_workspace_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="workspace"\ndependencies=["app-http-client"]')
    child = tmp_path / "child"
    child.mkdir()
    path = source(child, "import httpx\nhttpx.Client()", dependencies=[])
    assert scan_directory([path]) == []


def test_http_implementation_may_create_its_clients(tmp_path):
    path = source(tmp_path, "import httpx\nhttpx.Client()", dependencies=[], name="app-http-client")
    assert scan_directory([path]) == []


@pytest.mark.parametrize(
    "code",
    [
        "from app_http_client import get_http_client\nasync def call():\n    client = get_http_client()\n    await client.aclose()",
        "from app_http_client import get_http_client as get\nasync def call():\n    async with get() as client:\n        pass",
        "from app_http_client import get_http_sync_client\nget_http_sync_client().close()",
    ],
)
def test_shared_client_shutdown_warns(tmp_path, code):
    assert [v.rule for v in scan_directory([source(tmp_path, code)])] == ["ARCH_SHARED_CLIENT_CLOSE"]


def test_reassigned_shared_client_is_not_mistaken_for_shared_instance(tmp_path):
    path = source(
        tmp_path,
        "from app_http_client import get_http_client\nclient = get_http_client()\nclient = other\nclient.aclose()",
    )
    assert scan_directory([path]) == []


def test_undeclared_app_common_dependency(tmp_path):
    path = source(tmp_path, "from app_file_storage import provider", dependencies=[])
    violations = scan_directory([path])
    assert len(violations) == 1
    assert violations[0].rule == "ARCH_UNDECLARED_DEPENDENCY"


def test_optional_and_normalized_dependency_declarations(tmp_path):
    path = source(tmp_path, "from app_http_client import get_http_client", dependencies=[])
    with (tmp_path / "pyproject.toml").open("a") as stream:
        stream.write(
            "[project.optional-dependencies]\nhttp=[\"App_HTTP.Client[extra]>=1; python_version >= '3.12'\"]\n"
        )
    assert scan_directory([path]) == []


def test_warning_suppression_and_mixed_error_exit_status(tmp_path):
    path = source(
        tmp_path,
        "import httpx\nhttpx.Client()  # arch: ignore[ARCH_HTTP_CLIENT_CONSTRUCTION] -- Dedicated credentials\n",
    )
    assert scan_directory([path]) == []
    router = path.with_name("router.py")
    router.write_text("from feature.repos import Repo\nimport httpx\nhttpx.Client()")
    result = CliRunner().invoke(check_arch, [str(router), "--json"])
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["errors_count"] == report["warnings_count"] == 1


@pytest.mark.parametrize(
    "code",
    [
        "import httpx\nf = lambda httpx: httpx.Client()",
        "import httpx\n[httpx.Client() for httpx in custom_clients]",
        "import httpx\nfor httpx in clients:\n    httpx.Client()",
    ],
)
def test_nested_binding_forms_do_not_misidentify_client(tmp_path, code):
    assert scan_directory([source(tmp_path, code)]) == []


def test_unknown_and_unused_suppressions_warn(tmp_path):
    path = source(tmp_path, "value = 1  # arch: ignore[ARCH_DIRECT_CURRENT_TIME, ARCH_TYPO] -- stale\n")
    warnings = scan_directory([path])
    assert [v.rule for v in warnings] == ["ARCH_INVALID_SUPPRESSION", "ARCH_INVALID_SUPPRESSION"]
    assert all(v.severity == "warning" for v in warnings)


def test_db_factory_is_only_flagged_in_application_layers(tmp_path):
    path = source(tmp_path, 'from sqlalchemy.ext.asyncio import create_async_engine as create\ncreate("url")')
    assert scan_directory([path]) == []
    service = path.with_name("services.py")
    path.rename(service)
    assert [v.rule for v in scan_directory([service])] == ["ARCH_DB_FACTORY_IN_LAYER"]


def test_new_guides_are_available_through_cli():
    from app_tools.cli import cli

    for topic in ("backend/time", "backend/session"):
        result = CliRunner().invoke(cli, ["guide", "show", topic])
        assert result.exit_code == 0
        assert "get_current_utc_time" in result.output or "get_session" in result.output
