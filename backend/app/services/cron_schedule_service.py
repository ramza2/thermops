"""CRON 표현식 해석 / 다음 실행 시각 계산 (R10-S11).

5-field CRON만 지원: minute hour day_of_month month day_of_week
지원 문법: *, N, A-B, A,B,C, */N, A-B/N
미지원: 6-field(초), Quartz(?, L, W, #), @alias
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Seoul"
MAX_SEARCH_MINUTES = 4 * 366 * 24 * 60  # 최대 약 4년 (윤년 Feb 29 등)

FIELD_SPECS: dict[str, tuple[int, int]] = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day_of_month": (1, 31),
    "month": (1, 12),
    "day_of_week": (0, 7),
}


class CronParseError(ValueError):
    def __init__(self, message: str, *, error_code: str = "CRON_PARSE_ERROR"):
        self.error_code = error_code
        super().__init__(message)


@dataclass(frozen=True)
class CronParsedExpression:
    expression: str
    minute: frozenset[int]
    hour: frozenset[int]
    day_of_month: frozenset[int]
    month: frozenset[int]
    day_of_week: frozenset[int]  # 0=Sunday .. 6=Saturday (7 normalized to 0)
    day_of_month_any: bool
    day_of_week_any: bool


def _zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def normalize_cron_expression(expression: str | None) -> str:
    text = " ".join(str(expression or "").strip().split())
    return text


def normalize_day_of_week(value: int) -> int:
    """0 또는 7 → Sunday(0). 1=Mon .. 6=Sat."""
    if value == 7:
        return 0
    return value


def _python_weekday_to_cron(weekday: int) -> int:
    """datetime.weekday(): Mon=0..Sun=6 → cron: Sun=0, Mon=1..Sat=6."""
    return (weekday + 1) % 7


def _parse_field(field: str, name: str) -> frozenset[int]:
    lo, hi = FIELD_SPECS[name]
    raw = field.strip()
    if not raw:
        raise CronParseError(f"{name} 필드가 비어 있습니다.")
    for banned in ("?", "L", "W", "#"):
        if banned in raw.upper() if banned.isalpha() else banned in raw:
            raise CronParseError(
                "Quartz 문법 ?, L, W, #은 현재 지원하지 않습니다.",
                error_code="CRON_UNSUPPORTED_QUARTZ",
            )
    if any(ch.isalpha() for ch in raw):
        raise CronParseError(
            f"{name} 필드에 문자 이름은 지원하지 않습니다. 숫자와 *, -, /, , 만 사용하세요.",
            error_code="CRON_UNSUPPORTED_NAME",
        )

    values: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise CronParseError(f"{name} 필드 목록 형식이 올바르지 않습니다.")
        step = 1
        base = part
        if "/" in part:
            base, step_s = part.split("/", 1)
            if not step_s.isdigit() or int(step_s) <= 0:
                raise CronParseError(f"{name} 필드 step 값은 1 이상의 정수여야 합니다.")
            step = int(step_s)
            if not base:
                raise CronParseError(f"{name} 필드 step 기준이 비어 있습니다.")

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a_s, b_s = base.split("-", 1)
            if not a_s.isdigit() or not b_s.isdigit():
                raise CronParseError(f"{name} 필드 범위는 숫자여야 합니다.")
            start, end = int(a_s), int(b_s)
            if start > end:
                raise CronParseError(f"{name} 필드 범위 시작이 끝보다 클 수 없습니다.")
        else:
            if not base.isdigit():
                raise CronParseError(f"{name} 필드 값은 숫자여야 합니다.")
            start = end = int(base)

        if name == "day_of_week":
            # allow 0-7 before normalize; range check after normalize per value
            if start < 0 or end > 7:
                raise CronParseError("day_of_week 필드 값은 0~7 범위여야 합니다.")
        else:
            if start < lo or end > hi:
                raise CronParseError(f"{name} 필드 값은 {lo}~{hi} 범위여야 합니다.")

        for v in range(start, end + 1, step):
            if name == "day_of_week":
                if v < 0 or v > 7:
                    raise CronParseError("day_of_week 필드 값은 0~7 범위여야 합니다.")
                values.add(normalize_day_of_week(v))
            else:
                if v < lo or v > hi:
                    continue
                values.add(v)

    if not values:
        raise CronParseError(f"{name} 필드에서 유효한 값을 찾지 못했습니다.")
    return frozenset(values)


def parse_cron_expression(expression: str | None) -> CronParsedExpression:
    text = normalize_cron_expression(expression)
    if not text:
        raise CronParseError("CRON 표현식이 필요합니다.", error_code="CRON_REQUIRED")

    if any(ch in text for ch in ("?", "#")) or any(
        tok in text.upper().replace(",", " ").split() for tok in ("L", "W")
    ):
        raise CronParseError(
            "Quartz 문법 ?, L, W, #은 현재 지원하지 않습니다.",
            error_code="CRON_UNSUPPORTED_QUARTZ",
        )

    if text.startswith("@"):
        raise CronParseError(
            "@hourly/@daily 같은 alias는 현재 지원하지 않습니다.",
            error_code="CRON_UNSUPPORTED_ALIAS",
        )

    parts = text.split()
    if len(parts) == 6:
        raise CronParseError(
            "초 단위 6-field CRON은 현재 지원하지 않습니다.",
            error_code="CRON_UNSUPPORTED_SECONDS",
        )
    if len(parts) != 5:
        raise CronParseError(
            "CRON 표현식은 5개 필드여야 합니다. (분 시 일 월 요일)",
            error_code="CRON_FIELD_COUNT",
        )

    minute = _parse_field(parts[0], "minute")
    hour = _parse_field(parts[1], "hour")
    day_of_month = _parse_field(parts[2], "day_of_month")
    month = _parse_field(parts[3], "month")
    day_of_week = _parse_field(parts[4], "day_of_week")

    return CronParsedExpression(
        expression=text,
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month=month,
        day_of_week=day_of_week,
        day_of_month_any=parts[2].strip() == "*",
        day_of_week_any=parts[4].strip() == "*",
    )


def validate_cron_expression(expression: str | None) -> dict[str, Any]:
    try:
        parsed = parse_cron_expression(expression)
        return {
            "valid": True,
            "normalized_expression": parsed.expression,
            "errors": [],
            "warnings": [
                "day_of_week 0과 7은 모두 일요일로 처리됩니다.",
            ],
            "explanation": explain_cron_expression(parsed.expression),
        }
    except CronParseError as exc:
        return {
            "valid": False,
            "normalized_expression": normalize_cron_expression(expression),
            "errors": [str(exc)],
            "warnings": [],
            "explanation": None,
        }


def _matches_date(parsed: CronParsedExpression, dt: datetime) -> bool:
    if dt.month not in parsed.month:
        return False
    if dt.hour not in parsed.hour:
        return False
    if dt.minute not in parsed.minute:
        return False

    dom_ok = dt.day in parsed.day_of_month
    dow_ok = _python_weekday_to_cron(dt.weekday()) in parsed.day_of_week

    # 표준 cron: DOM·DOW 둘 다 제한이면 OR, 한쪽만 *이면 다른 쪽만 적용
    if parsed.day_of_month_any and parsed.day_of_week_any:
        return True
    if parsed.day_of_month_any:
        return dow_ok
    if parsed.day_of_week_any:
        return dom_ok
    return dom_ok or dow_ok


def _as_naive_local(dt: datetime, tz_name: str | None) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(_zone(tz_name)).replace(tzinfo=None)
    return dt


def compute_next_cron_run_at(
    expression: str | None,
    *,
    from_time: datetime | None = None,
    timezone: str | None = DEFAULT_TZ,
) -> datetime:
    parsed = parse_cron_expression(expression)
    tz_name = timezone or DEFAULT_TZ
    ref = _as_naive_local(from_time or datetime.now(_zone(tz_name)), tz_name)
    cursor = ref.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(MAX_SEARCH_MINUTES):
        last_day = monthrange(cursor.year, cursor.month)[1]
        if cursor.day > last_day:
            cursor = datetime(cursor.year, cursor.month, last_day, 23, 59) + timedelta(minutes=1)
            continue
        if cursor.month not in parsed.month:
            # 다음 허용 월의 1일로 점프
            year, month = cursor.year, cursor.month
            advanced = False
            for _m in range(12):
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                if month in parsed.month:
                    cursor = datetime(year, month, 1, 0, 0)
                    advanced = True
                    break
            if not advanced:
                cursor += timedelta(minutes=1)
            continue
        if _matches_date(parsed, cursor):
            return cursor
        cursor += timedelta(minutes=1)

    raise CronParseError(
        "다음 실행 예정 시각을 계산하지 못했습니다. 표현식 또는 탐색 한도를 확인하세요.",
        error_code="CRON_NEXT_RUN_NOT_FOUND",
    )


def is_cron_due(
    expression: str | None,
    next_run_at: datetime | None,
    *,
    now: datetime | None = None,
    timezone: str | None = DEFAULT_TZ,
) -> bool:
    """next_run_at <= now 이면 due. expression 유효성은 호출 측에서 보장."""
    if next_run_at is None:
        return False
    tz_name = timezone or DEFAULT_TZ
    ref = _as_naive_local(now or datetime.now(_zone(tz_name)), tz_name)
    nxt = _as_naive_local(next_run_at, tz_name)
    return nxt <= ref


def preview_cron_runs(
    expression: str | None,
    *,
    from_time: datetime | None = None,
    count: int = 10,
    timezone: str | None = DEFAULT_TZ,
) -> list[datetime]:
    n = max(1, min(int(count or 10), 50))
    tz_name = timezone or DEFAULT_TZ
    cursor = _as_naive_local(from_time or datetime.now(_zone(tz_name)), tz_name)
    out: list[datetime] = []
    for _ in range(n):
        nxt = compute_next_cron_run_at(expression, from_time=cursor, timezone=tz_name)
        out.append(nxt)
        cursor = nxt
    return out


def explain_cron_expression(expression: str | None) -> str:
    try:
        parsed = parse_cron_expression(expression)
    except CronParseError:
        return "CRON 표현식을 해석할 수 없습니다."

    parts: list[str] = []
    if parsed.minute == frozenset(range(0, 60)) and parsed.hour == frozenset(range(0, 24)):
        parts.append("매분")
    elif len(parsed.minute) == 1 and parsed.hour == frozenset(range(0, 24)):
        m = next(iter(parsed.minute))
        parts.append(f"매시간 {m:02d}분")
    elif len(parsed.minute) == 1 and len(parsed.hour) == 1:
        m = next(iter(parsed.minute))
        h = next(iter(parsed.hour))
        parts.append(f"{h:02d}:{m:02d}")
    else:
        parts.append(f"분={sorted(parsed.minute)[:8]}{'…' if len(parsed.minute) > 8 else ''}")
        parts.append(f"시={sorted(parsed.hour)[:8]}{'…' if len(parsed.hour) > 8 else ''}")

    if not parsed.day_of_week_any and parsed.day_of_week == frozenset({1, 2, 3, 4, 5}):
        parts.append("평일(월~금)")
    elif not parsed.day_of_week_any:
        dow_names = {0: "일", 1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토"}
        labels = [dow_names[d] for d in sorted(parsed.day_of_week)]
        parts.append("요일 " + ",".join(labels))

    if not parsed.day_of_month_any:
        if parsed.day_of_month == frozenset({1}):
            parts.append("매월 1일")
        else:
            days = sorted(parsed.day_of_month)
            parts.append(f"일={days[:8]}{'…' if len(days) > 8 else ''}")

    if parsed.month != frozenset(range(1, 13)):
        parts.append(f"월={sorted(parsed.month)}")

    return " / ".join(parts) + "에 실행됩니다."


def cron_validate_and_preview(
    expression: str | None,
    *,
    timezone: str | None = DEFAULT_TZ,
    from_time: datetime | None = None,
    count: int = 10,
) -> dict[str, Any]:
    validation = validate_cron_expression(expression)
    tz_name = timezone or DEFAULT_TZ
    result: dict[str, Any] = {
        "valid": validation["valid"],
        "normalized_expression": validation["normalized_expression"],
        "timezone": tz_name,
        "next_runs": [],
        "explanation": validation.get("explanation"),
        "warnings": list(validation.get("warnings") or []),
        "errors": list(validation.get("errors") or []),
    }
    if not validation["valid"]:
        return result
    try:
        runs = preview_cron_runs(
            validation["normalized_expression"],
            from_time=from_time,
            count=count,
            timezone=tz_name,
        )
        result["next_runs"] = [r.isoformat() for r in runs]
        result["next_run_at"] = runs[0].isoformat() if runs else None
    except CronParseError as exc:
        result["valid"] = False
        result["errors"] = [str(exc)]
    return result
