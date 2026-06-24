"""LightGBM / XGBoost 학습 구조."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def train_lightgbm(X_train: pd.DataFrame, y_train: pd.Series, params: dict[str, Any] | None = None):
    import lightgbm as lgb

    default = {"n_estimators": 100, "learning_rate": 0.05, "max_depth": 6, "verbose": -1}
    default.update(params or {})
    model = lgb.LGBMRegressor(**default)
    model.fit(X_train, y_train)
    return model


def train_xgboost(X_train: pd.DataFrame, y_train: pd.Series, params: dict[str, Any] | None = None):
    import xgboost as xgb

    default = {"n_estimators": 100, "learning_rate": 0.05, "max_depth": 6}
    default.update(params or {})
    model = xgb.XGBRegressor(**default)
    model.fit(X_train, y_train)
    return model


def predict_model(model, X: pd.DataFrame) -> np.ndarray:
    return model.predict(X)
