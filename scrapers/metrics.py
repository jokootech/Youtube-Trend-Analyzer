"""Time parsing and velocity metric calculations for YouTube videos."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse_dt(iso_str: str) -> datetime:
    """Safely parse an ISO-8601 datetime string to a timezone-aware UTC datetime."""
    if not iso_str:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return datetime.fromtimestamp(0, tz=timezone.utc)


def get_cutoff_dt(days: int) -> datetime:
    """Return a timezone-aware UTC datetime representing N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def calculate_velocity(view_count: int, published_at: datetime | str) -> float:
    """Calculate view velocity (views per hour since publication)."""
    if view_count <= 0:
        return 0.0

    pub_dt = parse_dt(published_at) if isinstance(published_at, str) else published_at
    if pub_dt.timestamp() <= 0:
        return 0.0

    now = datetime.now(timezone.utc)
    delta_hours = max((now - pub_dt).total_seconds() / 3600.0, 0.1)
    return round(view_count / delta_hours, 2)