from app_tools.commands.get_env_spec import get_env_spec, get_env_variable_specs
from click.testing import CliRunner
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RequiredSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REQUIRED_")
    location: str
    api_key: SecretStr | None = None


def test_flat_spec_does_not_require_runtime_configuration():
    specs = get_env_variable_specs(RequiredSettings)
    assert "REQUIRED_LOCATION" in specs
    assert "REQUIRED_API_KEY" in specs


def test_vector_spec_lists_new_storage_fields_without_a_config(monkeypatch):
    for suffix in ("MODE", "PATH", "URL", "API_KEY", "TIMEOUT"):
        monkeypatch.delenv(f"VECTOR_DB_{suffix}", raising=False)
    result = CliRunner().invoke(get_env_spec, ["--type", "vector_db"])
    assert result.exit_code == 0, result.output
    for suffix in ("MODE", "PATH", "URL", "API_KEY", "TIMEOUT"):
        assert f"VECTOR_DB_{suffix}" in result.output
    assert "VECTOR_DB_PROVIDER" not in result.output
