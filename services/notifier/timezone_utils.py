"""Timezone formatting and conversion utilities using zoneinfo."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# IRST: UTC+3:30
_IRST_TZ = timezone(timedelta(hours=3, minutes=30))
_EST_TZ = ZoneInfo("America/New_York")
_PST_TZ = ZoneInfo("America/Los_Angeles")


def format_dual_timestamp(dt: datetime | None = None) -> str:
    """Format a datetime into EST/EDT + PST/PDT + IRST string."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    dt_est = dt.astimezone(_EST_TZ)
    dt_pst = dt.astimezone(_PST_TZ)
    dt_irst = dt.astimezone(_IRST_TZ)

    est_label = dt_est.tzname() or "EST"
    pst_label = dt_pst.tzname() or "PST"

    est_str = dt_est.strftime("%I:%M %p %b %d").lstrip("0")
    pst_str = dt_pst.strftime("%I:%M %p %b %d").lstrip("0")
    irst_str = dt_irst.strftime("%H:%M %b %d")

    return f"{est_label} {est_str} | {pst_label} {pst_str} | IRST {irst_str}"