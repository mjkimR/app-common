from pathlib import Path

from app_tools.commands.doctor import doctor, inspect_environment
from click.testing import CliRunner


def test_inspect_environment_detects_skills_and_packages(tmp_path: Path):
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text('[project]\ndependencies = ["app-layer-base", "app-error"]\n')

    skills_dir = tmp_path / ".agents/skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "app-backend-core").mkdir()

    report = inspect_environment(tmp_path)
    assert report["manifest_found"] is True
    assert "app-layer-base" in report["declared_packages"]
    assert "app-error" in report["declared_packages"]
    assert "app-backend-core" in report["linked_skills"]
    assert report["missing_recommended_skills"] == []


def test_inspect_environment_reports_missing_skills(tmp_path: Path):
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text('[project]\ndependencies = ["app-file-storage"]\n')

    skills_dir = tmp_path / ".agents/skills"
    skills_dir.mkdir(parents=True)

    report = inspect_environment(tmp_path)
    assert "app-file-storage" in report["missing_recommended_skills"]
    assert any(adv["code"] == "MISSING_RECOMMENDED_SKILLS" for adv in report["advisories"])


def test_doctor_cli_json_mode(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(doctor, ["--json"])
    assert result.exit_code == 0
    assert '"declared_packages"' in result.output
    assert '"status"' in result.output
