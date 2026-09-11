import app_layer_base.core.log as log


def test_request_id_context_roundtrip():
    # Setting request id should be reflected in subsequent reads.
    log.set_request_id("abc123")
    assert log.get_request_id() == "abc123"


def test_format_record_sets_extra_request_id_left_justified():
    # global_patcher should always populate record['extra']['request_id'] with padding.
    log.set_request_id("id")
    record = {"extra": {}}
    log.global_patcher(record)

    assert record["extra"]["request_id"] == "id".ljust(8)


def test_format_record_sets_na_when_request_id_empty():
    # Empty request_id should become N/A padded.
    log.set_request_id("")
    record = {"extra": {}}
    log.global_patcher(record)

    assert record["extra"]["request_id"] == "N/A".ljust(8)


def test_setup_logger_with_log_path(monkeypatch, tmp_path):
    log_file = tmp_path / "test.log"

    class DummySettings:
        LOG_PATH = str(log_file)
        LOG_LEVEL = "INFO"
        LOG_JSON_FORMAT = False

    monkeypatch.setattr(log, "get_app_settings", lambda: DummySettings())

    configured = log.setup_logger()
    assert configured is log.logger
    # Both console and file handlers registered
    assert len(configured._core.handlers) == 2


def test_setup_logger_without_log_path(monkeypatch):
    class DummySettingsNone:
        LOG_PATH = None
        LOG_LEVEL = "INFO"
        LOG_JSON_FORMAT = False

    monkeypatch.setattr(log, "get_app_settings", lambda: DummySettingsNone())

    configured = log.setup_logger()
    assert configured is log.logger
    # Only console handler registered
    assert len(configured._core.handlers) == 1

    class DummySettingsEmpty:
        LOG_PATH = ""
        LOG_LEVEL = "INFO"
        LOG_JSON_FORMAT = True

    monkeypatch.setattr(log, "get_app_settings", lambda: DummySettingsEmpty())

    configured = log.setup_logger()
    assert configured is log.logger
    # Only console handler registered
    assert len(configured._core.handlers) == 1
