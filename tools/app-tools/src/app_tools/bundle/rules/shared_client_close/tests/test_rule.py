"""``RULE-app-shared-client-close``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from devkit_agt.features.rules.services.testing import check, load_rule

RULE = load_rule(__file__)


def project(dependencies: list[str], name: str = "consumer") -> dict[str, str]:
    """A package manifest; the module under test goes to ``src/consumer/main.py``."""
    return {"pyproject.toml": f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n'}


@pytest.mark.parametrize(
    "code",
    [
        "from app_http_client import get_http_client\nasync def call():\n    client = get_http_client()\n    await client.aclose()",
        "from app_http_client import get_http_client as get\nasync def call():\n    async with get() as client:\n        pass",
        "from app_http_client import get_http_sync_client\nget_http_sync_client().close()",
    ],
)
def test_closing_the_shared_client_warns(tmp_path: Path, code: str) -> None:
    [violation] = check(RULE, tmp_path, {**project(["app-http-client"]), "src/consumer/main.py": code})
    assert violation.severity.value == "warning"


def test_a_reassigned_variable_is_not_the_shared_client(tmp_path: Path) -> None:
    code = "from app_http_client import get_http_client\nclient = get_http_client()\nclient = other\nclient.aclose()"
    assert check(RULE, tmp_path, {**project(["app-http-client"]), "src/consumer/main.py": code}) == []
