import datetime

from app_base.utils.time_util import get_current_utc_time


def test_get_current_utc_time_is_timezone_aware_and_utc():
    # Returned datetime should be timezone-aware and in UTC.
    now = get_current_utc_time()
    assert isinstance(now, datetime.datetime)
    assert now.tzinfo is datetime.timezone.utc
