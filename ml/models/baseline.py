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
