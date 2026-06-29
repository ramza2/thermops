"""DB-compatible UTC timestamps (naive, for TIMESTAMP WITHOUT TIME ZONE)."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_db_datetime(dt: datetime) -> datetime:
    """API timezone-aware datetime → DB naive UTC (TIMESTAMP WITHOUT TIME ZONE)."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
