"""DB-compatible UTC timestamps (naive, for TIMESTAMP WITHOUT TIME ZONE)."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
