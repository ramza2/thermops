"""기상청 단기예보 응답 파서 (R10-S5)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
KMA_BASE_TIME_CANDIDATES = ("0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300")

CATEGORY_FIELD_MAP: dict[str, str] = {
    "TMP": "temperature",
    "REH": "humidity",
    "WSD": "wind_speed",
    "PCP": "precipitation",
    "POP": "precipitation_probability",
    "SKY": "sky_condition",
    "PTY": "precipitation_type",
}


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def parse_kma_datetime(date_text: str, time_text: str) -> datetime:
    date_val = str(date_text).strip()
    time_val = str(time_text).strip().zfill(4)
    return datetime(
        int(date_val[0:4]),
        int(date_val[4:6]),
        int(date_val[6:8]),
        int(time_val[0:2]),
        int(time_val[2:4]),
    )


def resolve_latest_kma_base_time(
    now: datetime | None = None,
    *,
    delay_minutes: int = 60,
) -> tuple[str, str, datetime]:
    """KST 기준 사용 가능한 최신 base_date/base_time 선택."""
    ref = now or now_kst()
    adjusted = ref - timedelta(minutes=int(delay_minutes))
    base_date = adjusted.strftime("%Y%m%d")
    adjusted_hhmm = adjusted.strftime("%H%M")

    chosen_time: str | None = None
    for candidate in reversed(KMA_BASE_TIME_CANDIDATES):
        if candidate <= adjusted_hhmm:
            chosen_time = candidate
            break

    if chosen_time is None:
        prev_day = adjusted - timedelta(days=1)
        base_date = prev_day.strftime("%Y%m%d")
        chosen_time = KMA_BASE_TIME_CANDIDATES[-1]

    base_at = parse_kma_datetime(base_date, chosen_time)
    return base_date, chosen_time, base_at


def parse_precipitation_value(value: Any) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if text in {"강수없음", "없음", "0"}:
        return 0.0, None
    match = re.search(r"(-?\d+(?:\.\d+)?)", text.replace(",", ""))
    if match:
        return float(match.group(1)), None
    return None, f"강수량 파싱 실패: {text}"


def parse_numeric_value(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pivot_kma_short_forecast_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f"항목 {idx + 1}: 객체가 아닌 응답은 건너뜁니다.")
            continue
        base_date = item.get("baseDate") or item.get("base_date")
        base_time = item.get("baseTime") or item.get("base_time")
        fcst_date = item.get("fcstDate") or item.get("fcst_date")
        fcst_time = item.get("fcstTime") or item.get("fcst_time")
        category = str(item.get("category") or "").strip().upper()
        if not all([base_date, base_time, fcst_date, fcst_time, category]):
            warnings.append(f"항목 {idx + 1}: 필수 필드가 없어 건너뜁니다.")
            continue
        key = (str(base_date), str(base_time), str(fcst_date), str(fcst_time))
        bucket = grouped.setdefault(
            key,
            {
                "baseDate": str(base_date),
                "baseTime": str(base_time),
                "fcstDate": str(fcst_date),
                "fcstTime": str(fcst_time),
                "raw_category_values_json": {},
            },
        )
        bucket["raw_category_values_json"][category] = item.get("fcstValue")

    rows: list[dict[str, Any]] = []
    for bucket in grouped.values():
        try:
            forecast_base_at = parse_kma_datetime(bucket["baseDate"], bucket["baseTime"])
            forecast_target_at = parse_kma_datetime(bucket["fcstDate"], bucket["fcstTime"])
        except (ValueError, IndexError) as exc:
            warnings.append(f"시각 파싱 실패: {exc}")
            continue
        horizon = int((forecast_target_at - forecast_base_at).total_seconds() // 3600)
        raw_cats = bucket["raw_category_values_json"]
        row: dict[str, Any] = {
            "forecast_base_at": forecast_base_at.isoformat(),
            "forecast_target_at": forecast_target_at.isoformat(),
            "forecast_horizon_hours": horizon,
            "raw_category_values_json": raw_cats,
        }
        for cat, field in CATEGORY_FIELD_MAP.items():
            raw_val = raw_cats.get(cat)
            if cat == "PCP":
                num, warn = parse_precipitation_value(raw_val)
                if warn:
                    warnings.append(warn)
                row[field] = num
            elif cat in ("SKY", "PTY"):
                row[field] = str(raw_val).strip() if raw_val is not None else None
            else:
                row[field] = parse_numeric_value(raw_val)
        rows.append(row)

    rows.sort(key=lambda r: r["forecast_target_at"])
    return rows, warnings


def match_forecast_rows_to_period(
    rows: list[dict[str, Any]],
    *,
    start_at: datetime,
    end_at: datetime,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    matched: list[dict[str, Any]] = []
    for row in rows:
        target_text = row.get("forecast_target_at")
        if not target_text:
            continue
        target_at = datetime.fromisoformat(str(target_text))
        if start_at <= target_at <= end_at:
            matched.append(row)
    if not matched and rows:
        warnings.append("예측 기간에 맞는 단기예보 행이 없습니다.")
    return matched, warnings


def build_forecast_cache_key(
    *,
    source_system: str,
    nx: int,
    ny: int,
    base_date: str,
    base_time: str,
    source_operation_id: str | None = None,
) -> str:
    op = source_operation_id or ""
    return f"{source_system}|{nx}|{ny}|{base_date}|{base_time}|{op}"
