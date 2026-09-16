import datetime
from datetime import UTC

from app_layer_base.utils.time_util import get_current_utc_time


def test_get_current_utc_time_is_timezone_aware_and_utc():
    # Returned datetime should be timezone-aware and in UTC.
    now = get_current_utc_time()
    assert isinstance(now, datetime.datetime)
    assert now.tzinfo is UTC


def test_utc_date_uses_utc_day_at_local_midnight(monkeypatch):
    from app_layer_base.utils import time_util

    instant = datetime.datetime(2026, 9, 16, 16, 30, tzinfo=UTC)
    monkeypatch.setattr(time_util, "get_current_utc_time", lambda: instant)
    assert instant.astimezone(datetime.timezone(datetime.timedelta(hours=9))).date() == datetime.date(2026, 9, 17)
    assert time_util.get_current_utc_date() == datetime.date(2026, 9, 16)
