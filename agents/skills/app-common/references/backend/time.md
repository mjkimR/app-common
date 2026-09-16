# Current time with app-layer-base

Read when adding current-time or calendar-date logic to code using app-layer-base.
Datetime types, parsing, arithmetic, and unrelated packages do not need this guidance.

```python
from app_layer_base.utils.time_util import get_current_utc_date, get_current_utc_time

created_at = get_current_utc_time()  # timezone-aware UTC datetime
utc_day = get_current_utc_date()    # date according to the UTC calendar
```

Keep local-calendar requirements explicit. `date.today()` and `datetime.now(local_tz)`
are not semantically interchangeable with UTC; convert the UTC instant to the intended
timezone before taking its date. DB `func.now()` is a database clock and should remain
in server defaults. Use a monotonic clock for elapsed durations.

`ARCH_DIRECT_CURRENT_TIME` warns on direct `datetime.now/utcnow/today` and `date.today`
calls, including import aliases. It offers guidance without automatic rewriting.
Intentional local-clock integrations may use a rule-specific, reasoned inline exception.
Tests may patch the clock at the module lookup used by the code under test.
