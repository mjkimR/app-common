"""The bundle's rule packages together: one per catalog entry, run through `devkit rules check`.

Each rule's own behavior is tested in its folder (``bundle/rules/<slug>/tests/``).
"""

import re
import tomllib
from pathlib import Path

from app_tools.architecture import RULES
from click.testing import CliRunner
from devkit_agt.features.rules import RuleRegistry
from devkit_dist.cli import cli as devkit_cli

from tests.unit.architecture.support import BUNDLE, BUNDLE_RULES, app_violations, rules_check

GUIDE_SECTIONS = [
    "## 1. Overview",
    "## 2. Cause of Violation",
    "## 3. Remediation",
    "## 4. Configuration",
    "## 5. Exceptions",
]
SKILL_REFERENCE = re.compile(r"`(references/[\w/-]+\.md)`")


def test_every_catalog_entry_is_one_bundled_rule_package():
    registry = RuleRegistry()
    registry.discover_from_dir(BUNDLE_RULES)
    assert registry.errors == []
    assert sorted(rule.id for rule in registry.get_all()) == sorted(RULES)
    packages = sorted(path.name for path in BUNDLE_RULES.iterdir() if path.is_dir() and not path.name.startswith("_"))
    assert packages == sorted(spec.slug for spec in RULES.values())
    manifest = tomllib.loads((BUNDLE / "bundle.toml").read_text())
    declared = {asset["source"] for asset in manifest["assets"] if asset["kind"] == "rule"}
    assert declared == {f"rules/{spec.slug}" for spec in RULES.values()}


def test_every_rule_has_a_guide_and_tests():
    for spec in RULES.values():
        package = BUNDLE_RULES / spec.slug
        guide = (package / "guide.md").read_text()
        assert guide.startswith(f"# [{spec.id}] "), spec.id
        assert [line for line in guide.splitlines() if line in GUIDE_SECTIONS] == GUIDE_SECTIONS, spec.id
        for reference in SKILL_REFERENCE.findall(guide):
            assert (BUNDLE / "skills/app-common" / reference).is_file(), (spec.id, reference)
        assert (package / "tests/test_rule.py").is_file(), spec.id


def test_rules_check_passes_a_clean_workspace(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('ok')\n")
    exit_code, document = rules_check(tmp_path)
    assert exit_code == 0
    assert app_violations(document) == []


def test_findings_are_reported_under_their_rule(tmp_path: Path):
    service = tmp_path / "app/features/items/services.py"
    service.parent.mkdir(parents=True)
    service.write_text("async def run(session):\n    await session.commit()\n")
    exit_code, document = rules_check(tmp_path)
    assert exit_code == 1
    [violation] = app_violations(document)
    assert (violation["rule_id"], violation["file"], violation["line"]) == (
        "RULE-app-service-commit",
        "app/features/items/services.py",
        2,
    )
    assert violation["severity"] == "error" and "UseCase" in violation["remediation"]


def test_explain_prints_the_rule_guide(tmp_path: Path):
    args = ["rules", "explain", "RULE-app-service-commit", "-w", str(tmp_path), "--rules-dir", str(BUNDLE_RULES)]
    result = CliRunner().invoke(devkit_cli, args)
    assert result.exit_code == 0, result.output
    assert "# [RULE-app-service-commit] Services Do Not Commit" in result.stdout


def test_warnings_alone_do_not_fail_and_errors_do(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "consumer"\ndependencies = ["app-http-client"]\n')
    module = tmp_path / "src/consumer/main.py"
    module.parent.mkdir(parents=True)
    module.write_text("import httpx\nhttpx.Client()\n")
    assert rules_check(tmp_path, module)[0] == 0
    router = module.with_name("router.py")
    router.write_text("from feature.repos import Repo\nimport httpx\nhttpx.Client()")
    exit_code, document = rules_check(tmp_path, router)
    assert exit_code == 1
    assert sorted(v["severity"] for v in app_violations(document)) == ["error", "warning"]


def test_overlapping_targets_are_scanned_once(tmp_path: Path):
    path = tmp_path / "broken.py"
    path.write_text("def broken(")
    exit_code, document = rules_check(tmp_path, tmp_path, path)
    assert exit_code == 1
    assert [v["rule_id"] for v in app_violations(document)] == ["RULE-app-parse-error"]
