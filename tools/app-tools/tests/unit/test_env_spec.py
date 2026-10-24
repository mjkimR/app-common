from __future__ import annotations

import json

from click.testing import CliRunner
from devkit_dist.cli import cli as devkit_cli


def env_spec(settings_type: str):
    return CliRunner().invoke(devkit_cli, ["app", "env-spec", "--type", settings_type, "--format", "json"])


def names(settings_type: str) -> list[str]:
    result = env_spec(settings_type)
    assert result.exit_code == 0, result.output
    return [variable["name"] for variable in json.loads(result.stdout)["variables"]]


def test_vector_spec_lists_storage_fields_without_a_config():
    listed = names("vector_db")
    for suffix in ("MODE", "PATH", "URL", "API_KEY", "TIMEOUT"):
        assert f"VECTOR_DB_{suffix}" in listed
    assert "VECTOR_DB_PROVIDER" not in listed


def test_provider_types_add_the_provider_settings():
    assert names("file_storage") == ["FS_PROVIDER"]
    local = names("file_storage_local")
    assert "FS_PROVIDER" in local and any(name.startswith("FS_LOCAL_") for name in local)
    assert any(name.startswith("FS_S3_") for name in names("file_storage_s3"))


def test_secrets_are_hidden_and_text_is_one_fact_per_line():
    result = CliRunner().invoke(devkit_cli, ["app", "env-spec", "--type", "auth"])
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines and all(line.startswith("[ENV: ") for line in lines)
    assert any("default=<hidden>" in line for line in lines if "type=SecretStr" in line)
