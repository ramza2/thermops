"""sklearn 기반 회귀 모델."""
from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor


def train_hist_gradient_boosting(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: dict[str, Any] | None = None,
) -> HistGradientBoostingRegressor:
    default: dict[str, Any] = {
        "max_iter": 100,
        "learning_rate": 0.05,
        "max_depth": 6,
        "random_state": 42,
    }
    default.update(params or {})
    model = HistGradientBoostingRegressor(**default)
    model.fit(X_train, y_train)
    return model


def train_random_forest(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    params: dict[str, Any] | None = None,
) -> RandomForestRegressor:
    default: dict[str, Any] = {
        "n_estimators": 100,
        "max_depth": 8,
        "random_state": 42,
        "n_jobs": -1,
    }
    default.update(params or {})
    model = RandomForestRegressor(**default)
    model.fit(X_train, y_train)
    return model
