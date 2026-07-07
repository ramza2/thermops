"""개발용 외부 API 샘플 — Connector 검증 전용 (운영 기능 아님)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, text

from app.core.database import get_db
from app.core.response import ok
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

router = APIRouter(tags=["SampleExternal"])


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text_val = value.strip()
    if text_val.endswith("Z"):
        text_val = text_val[:-1] + "+00:00"
    return datetime.fromisoformat(text_val).replace(tzinfo=None)


@router.get("/sample-external/heat-demand")
async def sample_external_heat_demand(
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """REST API Connector 테스트용 열수요 JSON."""
    clauses = []
    params: dict = {}
    if start_at:
        clauses.append("measured_at >= :start_at")
        params["start_at"] = _parse_dt(start_at)
    if end_at:
        clauses.append("measured_at <= :end_at")
        params["end_at"] = _parse_dt(end_at)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = text(
        f"""
        SELECT site_id, measured_at, heat_demand, supply_temp
        FROM external_heat_demand_sample
        {where}
        ORDER BY measured_at DESC
        LIMIT 500
        """
    )
    rows = (await db.execute(sql, params)).mappings().all()
    items = [
        {
            "site_id": r["site_id"],
            "measured_at": r["measured_at"].isoformat() if r["measured_at"] else None,
            "heat_demand": float(r["heat_demand"]) if r["heat_demand"] is not None else None,
            "supply_temp": float(r["supply_temp"]) if r.get("supply_temp") is not None else None,
        }
        for r in rows
    ]
    return ok({"items": items, "count": len(items)})


@router.get("/sample-external/heat-demand-wide")
async def sample_external_heat_demand_wide(
    nd_id: str = Query(default="ND001"),
    nd_name: str = Query(default="테스트노드"),
    bas_ymd: str = Query(default="20260101"),
):
    """REST API Connector wide-hour 변환 테스트용 JSON (개발 전용)."""
    item: dict[str, str] = {
        "ND_ID": nd_id,
        "ND_KORN_NM": nd_name,
        "BAS_YMD": bas_ymd,
    }
    for hour in range(1, 25):
        item[f"HTDND_AMNT_{hour}HR"] = str(round(100.0 + hour * 0.5, 1))
    return ok({"items": [item], "count": 1})


@router.get("/sample-external/asos-hourly")
async def sample_external_asos_hourly(
    stn_id: str = Query(default="108"),
    tm: str = Query(default="2026-01-01 01:00"),
):
    """REST API Connector ASOS 관측 기상 변환 테스트용 JSON (개발 전용)."""
    item = {
        "stnId": stn_id,
        "tm": tm,
        "ta": "-3.2",
        "hm": "55.0",
        "ws": "1.8",
        "rn": "0.0",
        "pa": "1024.3",
        "ss": "0.0",
        "icsr": "0.0",
    }
    return ok({"items": [item], "count": 1})


@router.get("/sample-external/special-days")
async def sample_external_special_days(
    sol_year: str = Query(default="2026"),
    sol_month: str = Query(default="01"),
):
    """REST API Connector Calendar/특일 변환 테스트용 JSON (개발 전용)."""
    items = [
        {"locdate": f"{sol_year}{sol_month}01", "dateName": "신정", "isHoliday": "Y"},
        {"locdate": f"{sol_year}{sol_month}05", "dateName": "소한", "isHoliday": "N", "special_day_type": "SOLAR_TERM"},
    ]
    return ok({"items": items, "count": len(items)})


@router.get("/sample-external/weather")
async def sample_external_weather(
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """REST API Connector 테스트용 기상 JSON."""
    clauses = []
    params: dict = {}
    if start_at:
        clauses.append("measured_at >= :start_at")
        params["start_at"] = _parse_dt(start_at)
    if end_at:
        clauses.append("measured_at <= :end_at")
        params["end_at"] = _parse_dt(end_at)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = text(
        f"""
        SELECT weather_area_id, measured_at, temperature, humidity, rainfall, wind_speed, data_type
        FROM external_weather_sample
        {where}
        ORDER BY measured_at DESC
        LIMIT 500
        """
    )
    rows = (await db.execute(sql, params)).mappings().all()
    items = [
        {
            "weather_area_id": r["weather_area_id"],
            "measured_at": r["measured_at"].isoformat() if r["measured_at"] else None,
            "temperature": float(r["temperature"]) if r.get("temperature") is not None else None,
            "humidity": float(r["humidity"]) if r.get("humidity") is not None else None,
            "rainfall": float(r["rainfall"]) if r.get("rainfall") is not None else None,
            "wind_speed": float(r["wind_speed"]) if r.get("wind_speed") is not None else None,
            "data_type": r.get("data_type") or "OBSERVATION",
        }
        for r in rows
    ]
    return ok({"items": items, "count": len(items)})
