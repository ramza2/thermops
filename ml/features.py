"""Feature 생성 모듈 — 열수요·기상·달력 결합 및 파생 Feature 계산."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Feature Set 템플릿 (논문 반영 메모 §4)
FEATURE_SET_TEMPLATES: dict[str, dict[str, Any]] = {
    "FS-TPL-MINIMAL": {
        "feature_set_name": "Minimal Weather Feature Set",
        "target_domain": "HEAT_DEMAND",
        "features": ["temperature", "hour", "day_of_week", "month"],
        "description": "최소 기상·시간 Feature",
    },
    "FS-TPL-BEHAVIOR": {
        "feature_set_name": "Behavior Pattern Feature Set",
        "target_domain": "HEAT_DEMAND",
        "features": ["temperature", "hour", "day_of_week", "month", "is_weekend", "is_holiday"],
        "description": "행동 패턴(주말·공휴일) Feature",
    },
    "FS-TPL-WEATHER-EXT": {
        "feature_set_name": "Weather Extended Feature Set",
        "target_domain": "HEAT_DEMAND",
        "features": [
            "temperature", "humidity", "rainfall", "wind_speed",
            "hour", "day_of_week", "month", "is_weekend", "is_holiday",
        ],
        "description": "기상 확장 Feature",
    },
    "FS-TPL-LAG-ROLL": {
        "feature_set_name": "Lag/Rolling Feature Set",
        "target_domain": "HEAT_DEMAND",
        "features": [
            "temperature", "humidity", "rainfall", "wind_speed",
            "hour", "day_of_week", "month", "is_weekend", "is_holiday",
            "demand_lag_24h", "demand_lag_168h", "demand_ma_24h", "demand_ma_168h",
            "temperature_lag_24h", "humidity_lag_24h", "temperature_ma_24h",
        ],
        "description": "Lag·이동평균 Feature",
    },
    "FS-TPL-COMFORT": {
        "feature_set_name": "Comfort Index Feature Set",
        "target_domain": "HEAT_DEMAND",
        "features": [
            "temperature", "humidity", "rainfall", "wind_speed",
            "hour", "day_of_week", "month", "is_weekend", "is_holiday",
            "demand_lag_24h", "demand_lag_168h", "demand_ma_24h", "demand_ma_168h",
            "temperature_lag_24h", "humidity_lag_24h", "temperature_ma_24h",
            "heating_degree_days", "cooling_degree_days", "comfort_distance",
        ],
        "description": "쾌적도·난방도일 Feature",
    },
    "FS-TPL-TWO-STAGE": {
        "feature_set_name": "Two-Stage Ready Feature Set",
        "target_domain": "HEAT_DEMAND",
        "features": [
            "month", "day_of_week", "hour", "month_sin", "month_cos", "hour_sin", "hour_cos",
            "is_weekend", "is_holiday", "season_winter", "season_summer",
            "temperature", "humidity", "rainfall", "wind_speed", "temperature_diff_24h",
            "demand_lag_24h", "demand_lag_168h", "demand_ma_24h", "demand_ma_168h",
            "temperature_lag_24h", "humidity_lag_24h", "temperature_ma_24h",
            "heating_degree_days", "cooling_degree_days", "comfort_distance",
        ],
        "description": "2-Stage CatBoost 준비 풀 Feature",
    },
}

ALL_COMPUTED_FEATURES = [
    "month", "day_of_week", "hour", "month_sin", "month_cos", "hour_sin", "hour_cos",
    "is_weekend", "is_holiday", "season_winter", "season_summer",
    "temperature", "humidity", "rainfall", "wind_speed", "temperature_diff_24h",
    "demand_lag_24h", "demand_lag_168h", "demand_ma_24h", "demand_ma_168h",
    "temperature_lag_24h", "humidity_lag_24h", "temperature_ma_24h",
    "heating_degree_days", "cooling_degree_days", "comfort_distance",
]


def _comfort_distance(temp: pd.Series) -> pd.Series:
    low_gap = (18 - temp).clip(lower=0)
    high_gap = (temp - 24).clip(lower=0)
    return pd.concat([low_gap, high_gap], axis=1).max(axis=1)


def build_feature_frame(
    heat_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    calendar_df: pd.DataFrame,
    site_weather_map: dict[str, str],
) -> pd.DataFrame:
    """열수요·기상·달력을 결합하고 전체 Feature를 계산한다."""
    if heat_df.empty:
        return pd.DataFrame()

    df = heat_df.copy()
    df["measured_at"] = pd.to_datetime(df["measured_at"])
    df = df.sort_values(["site_id", "measured_at"]).reset_index(drop=True)

    df["weather_area_id"] = df["site_id"].map(site_weather_map)
    w = weather_df.copy()
    w["measured_at"] = pd.to_datetime(w["measured_at"]).dt.floor("h")
    w = w.sort_values(["weather_area_id", "measured_at"])
    df["weather_key"] = df["measured_at"].dt.floor("h")
    df = df.merge(
        w[
            [
                "weather_area_id",
                "measured_at",
                "temperature",
                "humidity",
                "rainfall",
                "wind_speed",
            ]
        ].rename(columns={"measured_at": "weather_key"}),
        on=["weather_area_id", "weather_key"],
        how="left",
    )

    cal = calendar_df.copy()
    cal["calendar_date"] = pd.to_datetime(cal["calendar_date"]).dt.date
    df["calendar_date"] = df["measured_at"].dt.date
    df = df.merge(
        cal[
            [
                "calendar_date",
                "day_of_week",
                "is_weekend",
                "is_holiday",
                "season",
            ]
        ],
        on="calendar_date",
        how="left",
    )

    ts = df["measured_at"]
    df["month"] = ts.dt.month
    df["hour"] = ts.dt.hour
    if "day_of_week" not in df.columns or df["day_of_week"].isna().any():
        df["day_of_week"] = ts.dt.dayofweek

    df["month_sin"] = (2 * math.pi * df["month"] / 12).map(math.sin)
    df["month_cos"] = (2 * math.pi * df["month"] / 12).map(math.cos)
    df["hour_sin"] = (2 * math.pi * df["hour"] / 24).map(math.sin)
    df["hour_cos"] = (2 * math.pi * df["hour"] / 24).map(math.cos)

    df["is_weekend"] = df["is_weekend"].fillna("N").map(lambda x: 1 if str(x).upper() == "Y" else 0)
    df["is_holiday"] = df["is_holiday"].fillna("N").map(lambda x: 1 if str(x).upper() == "Y" else 0)
    df["season_winter"] = df["season"].fillna("").map(lambda s: 1 if str(s).upper() == "WINTER" else 0)
    df["season_summer"] = df["season"].fillna("").map(lambda s: 1 if str(s).upper() == "SUMMER" else 0)

    temp = pd.to_numeric(df["temperature"], errors="coerce")
    df["heating_degree_days"] = (18 - temp).clip(lower=0)
    df["cooling_degree_days"] = (temp - 24).clip(lower=0)
    df["comfort_distance"] = _comfort_distance(temp)

    for col, lag in [("heat_demand", 24), ("heat_demand", 168)]:
        name = f"demand_lag_{lag}h"
        df[name] = df.groupby("site_id")["heat_demand"].shift(lag)

    for col, lag in [("temperature", 24), ("humidity", 24)]:
        name = f"{col}_lag_{lag}h" if col == "temperature" else "humidity_lag_24h"
        df[name] = df.groupby("site_id")[col].shift(lag)

    df["temperature_diff_24h"] = df.groupby("site_id")["temperature"].diff(24)

    df["demand_ma_24h"] = df.groupby("site_id")["heat_demand"].transform(
        lambda x: x.rolling(24, min_periods=1).mean()
    )
    df["demand_ma_168h"] = df.groupby("site_id")["heat_demand"].transform(
        lambda x: x.rolling(168, min_periods=1).mean()
    )
    df["temperature_ma_24h"] = df.groupby("site_id")["temperature"].transform(
        lambda x: x.rolling(24, min_periods=1).mean()
    )

    return df


def select_feature_columns(df: pd.DataFrame, feature_names: list[str]) -> list[str]:
    """Feature Set에 포함된 컬럼만 반환 (존재하는 것만)."""
    return [c for c in feature_names if c in df.columns]


def rows_to_preview(df: pd.DataFrame, feature_names: list[str], limit: int = 10) -> list[dict[str, Any]]:
    """API 미리보기용 행 목록."""
    cols = ["site_id", "measured_at", "heat_demand", *select_feature_columns(df, feature_names)]
    out: list[dict[str, Any]] = []
    for _, row in df.tail(limit).iterrows():
        item: dict[str, Any] = {}
        for c in cols:
            val = row.get(c)
            if pd.isna(val):
                item[c] = None
            elif hasattr(val, "isoformat"):
                item[c] = val.isoformat()
            elif isinstance(val, (float, int)):
                item[c] = float(val) if isinstance(val, float) else int(val)
            else:
                item[c] = val
        item["feature_at"] = item.get("measured_at")
        out.append(item)
    return out


# 하위 호환
def build_lag_features(df: pd.DataFrame, value_col: str = "heat_demand", group_col: str = "site_id") -> pd.DataFrame:
    df = df.sort_values([group_col, "measured_at"]).copy()
    df["demand_lag_24h"] = df.groupby(group_col)[value_col].shift(24)
    df["demand_lag_168h"] = df.groupby(group_col)[value_col].shift(168)
    df["demand_ma_24h"] = df.groupby(group_col)[value_col].transform(lambda x: x.rolling(24, min_periods=1).mean())
    df["hour"] = pd.to_datetime(df["measured_at"]).dt.hour
    df["day_of_week"] = pd.to_datetime(df["measured_at"]).dt.dayofweek
    return df


def join_weather(df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    weather_df = weather_df.rename(columns={"measured_at": "weather_at"})
    df["weather_at"] = pd.to_datetime(df["measured_at"]).dt.floor("h")
    weather_df["weather_at"] = pd.to_datetime(weather_df["weather_at"]).dt.floor("h")
    return df.merge(
        weather_df[["weather_at", "temperature", "humidity"]],
        on="weather_at",
        how="left",
    )
