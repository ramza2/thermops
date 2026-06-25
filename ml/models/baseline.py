"""Baseline 모델."""
from __future__ import annotations

import numpy as np
import pandas as pd


class SeasonalNaiveBaseline:
    def __init__(self, lag_hours: int = 168):
        self.lag_hours = lag_hours
        self.history_: pd.DataFrame | None = None

    def fit(self, df: pd.DataFrame, target_col: str = "heat_demand"):
        self.history_ = df.sort_values("measured_at").copy()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self.history_ is None:
            raise ValueError("Model not fitted")
        merged = df.merge(
            self.history_[["measured_at", "heat_demand"]].rename(
                columns={"measured_at": "lag_time", "heat_demand": "pred"}
            ),
            left_on=pd.to_datetime(df["measured_at"]) - pd.Timedelta(hours=self.lag_hours),
            right_on="lag_time",
            how="left",
        )
        return merged["pred"].fillna(self.history_["heat_demand"].mean()).values


class FeatureColumnBaseline:
    """Feature Matrix의 특정 컬럼 값을 예측값으로 사용 (lag/MA baseline)."""

    def __init__(self, column: str, fallback_column: str | None = None):
        self.column = column
        self.fallback_column = fallback_column
        self.fallback_value_: float = 0.0

    def fit(self, X: pd.DataFrame, y: pd.Series):
        col = self.column if self.column in X.columns else self.fallback_column
        if col and col in X.columns:
            self.fallback_value_ = float(X[col].dropna().mean()) if X[col].notna().any() else float(y.mean())
        else:
            self.fallback_value_ = float(y.mean())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        col = self.column if self.column in X.columns else self.fallback_column
        if col and col in X.columns:
            return X[col].fillna(self.fallback_value_).astype(float).values
        return np.full(len(X), self.fallback_value_)


def lag24h_baseline() -> FeatureColumnBaseline:
    return FeatureColumnBaseline("demand_lag_24h", fallback_column="lag_24h_demand")


def moving_average_baseline() -> FeatureColumnBaseline:
    return FeatureColumnBaseline("demand_ma_24h", fallback_column="rolling_24h_avg")
