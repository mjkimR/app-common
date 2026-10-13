"""Package-aware warnings must distinguish real imports, scope, and ownership."""

import json
from pathlib import Path

import pytest
from app_tools.architecture import RULES

from tests.unit.architecture.support import app_violations, rules_check, scan, severity


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
    exit_code, document = rules_check(tmp_path, path)
    assert exit_code == 0
    [diagnostic] = app_violations(document)
    assert diagnostic["rule_id"] == "RULE-app-http-client-construction"
    assert diagnostic["severity"] == "warning"
    assert "get_http_" in diagnostic["remediation"]
    assert RULES[diagnostic["rule_id"]].guide == "http"


@pytest.mark.parametrize(
    "code",
    [
        "from datetime import datetime as D\nD.now()",
        "import datetime as dt\ndt.datetime.utcnow()",
        "from datetime import date\ndate.today()",
    ],
)
def test_clock_aliases(tmp_path, code):
    assert [v.rule for v in scan(source(tmp_path, code))] == ["RULE-app-direct-current-time"]


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
    assert scan(source(tmp_path, code)) == []


def test_unrelated_package_does_not_inherit_workspace_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="workspace"\ndependencies=["app-http-client"]')
    child = tmp_path / "child"
    child.mkdir()
    path = source(child, "import httpx\nhttpx.Client()", dependencies=[])
    assert scan(path) == []


def test_http_implementation_may_create_its_clients(tmp_path):
    path = source(tmp_path, "import httpx\nhttpx.Client()", dependencies=[], name="app-http-client")
    assert scan(path) == []


@pytest.mark.parametrize(
    "code",
    [
        "from app_http_client import get_http_client\nasync def call():\n    client = get_http_client()\n    await client.aclose()",
        "from app_http_client import get_http_client as get\nasync def call():\n    async with get() as client:\n        pass",
        "from app_http_client import get_http_sync_client\nget_http_sync_client().close()",
    ],
)
def test_shared_client_shutdown_warns(tmp_path, code):
    assert [v.rule for v in scan(source(tmp_path, code))] == ["RULE-app-shared-client-close"]


def test_reassigned_shared_client_is_not_mistaken_for_shared_instance(tmp_path):
    path = source(
        tmp_path,
        "from app_http_client import get_http_client\nclient = get_http_client()\nclient = other\nclient.aclose()",
    )
    assert scan(path) == []


def test_undeclared_app_common_dependency(tmp_path):
    path = source(tmp_path, "from app_file_storage import provider", dependencies=[])
    violations = scan(path)
    assert len(violations) == 1
    assert violations[0].rule == "RULE-app-undeclared-dependency"


def test_devkit_must_be_declared_where_it_is_imported(tmp_path):
    path = source(tmp_path, "from devkit.advisory import AdvisoryError", dependencies=["app-layer-base"])
    [violation] = scan(path)
    assert violation.rule == "RULE-app-undeclared-dependency"
    assert "Git source" in violation.fix
    path = source(tmp_path, "from devkit.advisory import AdvisoryError", dependencies=["app-layer-base", "devkit>=0.1"])
    assert scan(path) == []


def test_optional_and_normalized_dependency_declarations(tmp_path):
    path = source(tmp_path, "from app_http_client import get_http_client", dependencies=[])
    with (tmp_path / "pyproject.toml").open("a") as stream:
        stream.write(
            "[project.optional-dependencies]\nhttp=[\"App_HTTP.Client[extra]>=1; python_version >= '3.12'\"]\n"
        )
    assert scan(path) == []


def test_warning_suppression_and_mixed_error_exit_status(tmp_path):
    path = source(
        tmp_path,
        "import httpx\nhttpx.Client()  # arch: ignore[RULE-app-http-client-construction] -- Dedicated credentials\n",
    )
    assert scan(path) == []
    router = path.with_name("router.py")
    router.write_text("from feature.repos import Repo\nimport httpx\nhttpx.Client()")
    exit_code, document = rules_check(tmp_path, router)
    assert exit_code == 1
    assert sorted(v["severity"] for v in app_violations(document)) == ["error", "warning"]


@pytest.mark.parametrize(
    "code",
    [
        "import httpx\nf = lambda httpx: httpx.Client()",
        "import httpx\n[httpx.Client() for httpx in custom_clients]",
        "import httpx\nfor httpx in clients:\n    httpx.Client()",
    ],
)
def test_nested_binding_forms_do_not_misidentify_client(tmp_path, code):
    assert scan(source(tmp_path, code)) == []


def test_unknown_and_unused_suppressions_warn(tmp_path):
    path = source(tmp_path, "value = 1  # arch: ignore[RULE-app-direct-current-time, ARCH_TYPO] -- stale\n")
    warnings = scan(path)
    assert [v.rule for v in warnings] == ["RULE-app-invalid-suppression", "RULE-app-invalid-suppression"]
    assert all(severity(v) == "warning" for v in warnings)


def test_db_factory_is_only_flagged_in_application_layers(tmp_path):
    path = source(tmp_path, 'from sqlalchemy.ext.asyncio import create_async_engine as create\ncreate("url")')
    assert scan(path) == []
    service = path.with_name("services.py")
    path.rename(service)
    assert [v.rule for v in scan(service)] == ["RULE-app-db-factory-in-layer"]


def test_every_rule_guide_is_a_bundled_reference():
    from app_tools.architecture.rule import guide_document

    rules_dir = Path(__file__).resolve().parents[3] / "src/app_tools/bundle/rules"
    for spec in RULES.values():
        assert (rules_dir / guide_document(spec.guide)).resolve().is_file(), spec.id
