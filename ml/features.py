"""Feature 생성 모듈."""
from __future__ import annotations

import pandas as pd


def build_lag_features(df: pd.DataFrame, value_col: str = "heat_demand", group_col: str = "site_id") -> pd.DataFrame:
    df = df.sort_values([group_col, "measured_at"]).copy()
    for lag in [24, 168]:
        df[f"lag_{lag}h_demand"] = df.groupby(group_col)[value_col].shift(lag)
    df["rolling_24h_avg"] = df.groupby(group_col)[value_col].transform(lambda x: x.rolling(24, min_periods=1).mean())
    df["hour_of_day"] = pd.to_datetime(df["measured_at"]).dt.hour
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
