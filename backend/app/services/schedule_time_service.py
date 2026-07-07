"""데이터 적재 스케줄 시각 계산 (R10-S6)."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Seoul"
SUPPORTED_TYPES = frozenset({"MANUAL", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "CRON"})


def _zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def _as_naive_local(dt: datetime, tz_name: str | None) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(_zone(tz_name)).replace(tzinfo=None)
    return dt


def _time_of_day_from_start(start_at: datetime | None) -> tuple[int, int]:
    if start_at:
        return start_at.hour, start_at.minute
    return 0, 0


def compute_next_run_at(
    schedule: dict[str, Any],
    from_time: datetime | None = None,
) -> datetime | None:
    schedule_type = str(schedule.get("schedule_type") or "MANUAL").upper()
    if schedule_type in ("MANUAL", "CRON"):
        return None

    tz_name = schedule.get("timezone") or DEFAULT_TZ
    ref = _as_naive_local(from_time or datetime.now(_zone(tz_name)), tz_name)
    start_at = schedule.get("start_at")
    if isinstance(start_at, str):
        start_at = datetime.fromisoformat(start_at.replace("Z", ""))
    hour, minute = _time_of_day_from_start(start_at)

    if schedule_type == "HOURLY":
        candidate = ref.replace(minute=minute, second=0, microsecond=0)
        if candidate <= ref:
            candidate += timedelta(hours=1)
        return candidate

    if schedule_type == "DAILY":
        candidate = ref.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= ref:
            candidate += timedelta(days=1)
        return candidate

    if schedule_type == "WEEKLY":
        if not start_at:
            weekday = ref.weekday()
        else:
            weekday = start_at.weekday()
        candidate = ref.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (weekday - candidate.weekday()) % 7
        if days_ahead == 0 and candidate <= ref:
            days_ahead = 7
        return candidate + timedelta(days=days_ahead)

    if schedule_type == "MONTHLY":
        day = start_at.day if start_at else ref.day
        year, month = ref.year, ref.month
        last_day = monthrange(year, month)[1]
        use_day = min(day, last_day)
        candidate = ref.replace(day=use_day, hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= ref:
            month += 1
            if month > 12:
                month = 1
                year += 1
            last_day = monthrange(year, month)[1]
            use_day = min(day, last_day)
            candidate = datetime(year, month, use_day, hour, minute)
        return candidate

    return None


def is_schedule_due(schedule: dict[str, Any], now: datetime | None = None) -> bool:
    if not schedule.get("active_yn"):
        return False
    meta = schedule.get("metadata_json") or {}
    if meta.get("archived_at"):
        return False
    schedule_type = str(schedule.get("schedule_type") or "MANUAL").upper()
    if schedule_type in ("MANUAL", "CRON"):
        return False

    tz_name = schedule.get("timezone") or DEFAULT_TZ
    ref = _as_naive_local(now or datetime.now(_zone(tz_name)), tz_name)

    start_at = schedule.get("start_at")
    if isinstance(start_at, str):
        start_at = datetime.fromisoformat(start_at.replace("Z", ""))
    if start_at and ref < start_at:
        return False

    end_at = schedule.get("end_at")
    if isinstance(end_at, str):
        end_at = datetime.fromisoformat(end_at.replace("Z", ""))
    if end_at and ref >= end_at:
        return False

    if schedule.get("last_run_status") == "RUNNING":
        return False

    next_run = schedule.get("next_run_at")
    if isinstance(next_run, str):
        next_run = datetime.fromisoformat(next_run.replace("Z", ""))
    if next_run is None:
        return True
    return next_run <= ref
