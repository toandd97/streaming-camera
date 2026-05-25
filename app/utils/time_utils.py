"""
Time utility functions.
"""
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def elapsed_ms(since: datetime) -> float:
    """Return milliseconds elapsed since a given datetime."""
    delta = now_utc() - since.replace(tzinfo=timezone.utc) if since.tzinfo is None else now_utc() - since
    return delta.total_seconds() * 1000


def elapsed_seconds(since: datetime) -> float:
    """Return seconds elapsed since a given datetime."""
    delta = now_utc() - since.replace(tzinfo=timezone.utc) if since.tzinfo is None else now_utc() - since
    return delta.total_seconds()


def format_uptime(seconds: float) -> str:
    """Format uptime seconds into human-readable string: e.g. '2h 15m 30s'."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"
