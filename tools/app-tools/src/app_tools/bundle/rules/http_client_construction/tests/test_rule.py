"""``RULE-app-http-client-construction``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def project(dependencies: list[str], name: str = "consumer") -> dict[str, str]:
    """A package manifest; the module under test goes to ``src/consumer/main.py``."""
    return {"pyproject.toml": f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n'}


@pytest.mark.parametrize(
    "code",
    [
        "import httpx as hx\nhx.AsyncClient()",
        "from httpx import Client as C\nC()",
        "import httpx\nfactory = httpx.AsyncClient\nfactory()",
    ],
)
def test_constructor_aliases_warn(tmp_path: Path, code: str) -> None:
    files = {**project(["app-http-client"]), "src/consumer/main.py": code}
    [violation] = check(RULE, tmp_path, files)
    assert violation.severity.value == "warning" and "get_http_" in violation.remediation


@pytest.mark.parametrize(
    "code",
    [
        "import httpx\ndef call(httpx):\n    httpx.Client()",
        "from httpx import Client\ndef call():\n    Client = custom\n    Client()",
        "import httpx\nhttpx = custom\nhttpx.Client()",
        "class Client:\n    pass\nClient()",
        "import httpx\nf = lambda httpx: httpx.Client()",
        "import httpx\n[httpx.Client() for httpx in custom_clients]",
        "import httpx\nfor httpx in clients:\n    httpx.Client()",
    ],
)
def test_shadowed_names_are_not_clients(tmp_path: Path, code: str) -> None:
    assert check(RULE, tmp_path, {**project(["app-http-client"]), "src/consumer/main.py": code}) == []


def test_only_packages_declaring_app_http_client_are_checked(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": '[project]\nname="workspace"\ndependencies=["app-http-client"]',
        **{f"child/{name}": text for name, text in project([]).items()},
        "child/src/consumer/main.py": "import httpx\nhttpx.Client()",
    }
    assert check(RULE, tmp_path, files) == []


def test_app_http_client_may_create_its_clients(tmp_path: Path) -> None:
    files = {**project([], name="app-http-client"), "src/consumer/main.py": "import httpx\nhttpx.Client()"}
    assert check(RULE, tmp_path, files) == []


def test_a_reasoned_suppression_hides_the_warning(tmp_path: Path) -> None:
    code = "import httpx\nhttpx.Client()  # arch: ignore[RULE-app-http-client-construction] -- dedicated credentials\n"
    assert check(RULE, tmp_path, {**project(["app-http-client"]), "src/consumer/main.py": code}) == []
