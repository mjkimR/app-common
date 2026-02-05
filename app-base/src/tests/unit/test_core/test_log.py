import app_base.core.log as log


def test_request_id_context_roundtrip():
    # Setting request id should be reflected in subsequent reads.
    log.set_request_id("abc123")
    assert log.get_request_id() == "abc123"


def test_format_record_sets_extra_request_id_left_justified():
    # format_record should always populate record['extra']['request_id'] with padding.
    log.set_request_id("id")
    record = {"extra": {}}
    log.format_record(record)

    assert record["extra"]["request_id"] == "id".ljust(8)


def test_format_record_sets_na_when_request_id_empty():
    # Empty request_id should become N/A padded.
    log.set_request_id("")
    record = {"extra": {}}
    log.format_record(record)

    assert record["extra"]["request_id"] == "N/A".ljust(8)


def test_setup_logger_smoke(monkeypatch):
    # setup_logger should configure handlers without raising.
    class DummySettings:
        LOG_PATH = "/tmp/app.log"
        LOG_LEVEL = "INFO"
        LOG_JSON_FORMAT = False

    monkeypatch.setattr(log, "get_app_settings", lambda: DummySettings())

    configured = log.setup_logger()
    assert configured is log.logger
