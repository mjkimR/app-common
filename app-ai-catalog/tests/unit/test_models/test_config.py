import pytest
from app_ai_catalog.models.config import ConfigLoader


class TestConfigLoader:
    def test_load_yaml_with_env_success(self, monkeypatch, tmp_path):
        config_file = tmp_path / "catalog.yml"
        config_file.write_text(
            """
            api_key: ${TEST_API_KEY}
            fallback: ${MISSING_API_KEY:-default-key}
            """,
            encoding="utf-8",
        )
        monkeypatch.setenv("TEST_API_KEY", "test-key")

        loaded = ConfigLoader.load_yaml_with_env(str(config_file))

        assert loaded == {"api_key": "test-key", "fallback": "default-key"}

    def test_load_yaml_with_env_substitutes_after_yaml_parse(self, monkeypatch, tmp_path):
        config_file = tmp_path / "catalog.yml"
        config_file.write_text("api_key: ${TEST_API_KEY}", encoding="utf-8")
        monkeypatch.setenv("TEST_API_KEY", "key: value\nsecond-line")

        loaded = ConfigLoader.load_yaml_with_env(str(config_file))

        assert loaded == {"api_key": "key: value\nsecond-line"}

    def test_load_yaml_with_env_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            ConfigLoader.load_yaml_with_env(str(tmp_path / "missing.yml"))

    def test_load_yaml_with_env_missing_required_var(self, mocker, tmp_path):
        config_file = tmp_path / "catalog.yml"
        config_file.write_text("api_key: ${MISSING_API_KEY}", encoding="utf-8")
        mock_logger = mocker.patch("app_ai_catalog.models.config.logger")

        with pytest.raises(ValueError, match="Required infrastructure configuration key is missing"):
            ConfigLoader.load_yaml_with_env(str(config_file))

        mock_logger.error.assert_called_once_with(
            "Environment variable 'MISSING_API_KEY' is required by config but is not set."
        )
