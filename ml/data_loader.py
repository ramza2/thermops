"""데이터 로딩 모듈."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text


def get_db_url() -> str:
    return os.getenv("THERMOps_DB_URL", "postgresql://thermops:thermops@localhost:5432/thermops")


def load_heat_demand(site_ids: list[str] | None = None, start_at: datetime | None = None, end_at: datetime | None = None) -> pd.DataFrame:
    engine = create_engine(get_db_url())
    query = "SELECT site_id, measured_at, heat_demand, supply_temp, return_temp FROM tb_heat_demand_actual WHERE 1=1"
    params: dict = {}
    if site_ids:
        query += " AND site_id = ANY(:site_ids)"
        params["site_ids"] = site_ids
    if start_at:
        query += " AND measured_at >= :start_at"
        params["start_at"] = start_at
    if end_at:
        query += " AND measured_at <= :end_at"
        params["end_at"] = end_at
    query += " ORDER BY site_id, measured_at"
    return pd.read_sql(text(query), engine, params=params)


def load_weather(weather_area_id: str, start_at: datetime | None = None, end_at: datetime | None = None) -> pd.DataFrame:
    engine = create_engine(get_db_url())
    query = "SELECT * FROM tb_weather_observation WHERE weather_area_id = :area_id"
    params: dict = {"area_id": weather_area_id}
    if start_at:
        query += " AND measured_at >= :start_at"
        params["start_at"] = start_at
    if end_at:
        query += " AND measured_at <= :end_at"
        params["end_at"] = end_at
    return pd.read_sql(text(query), engine, params=params)
