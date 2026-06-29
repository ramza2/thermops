"""CatBoost 회귀 모델."""
from __future__ import annotations

from typing import Any

import pandas as pd

CATBOOST_DEFAULT: dict[str, Any] = {
    "loss_function": "RMSE",
    "iterations": 300,
    "learning_rate": 0.05,
    "depth": 6,
    "random_seed": 42,
    "verbose": False,
}


def _ensure_catboost():
    try:
        from catboost import CatBoostRegressor

        return CatBoostRegressor
    except ImportError as exc:
        raise ImportError(
            "catboost 패키지가 설치되어 있지 않습니다. "
            "pip install catboost 후 model_type=CATBOOST 또는 TWO_STAGE_CATBOOST 학습을 다시 시도하세요."
        ) from exc


def build_catboost_params(
    hyperparams: dict[str, Any] | None = None,
    train_size: int | None = None,
) -> dict[str, Any]:
    params = dict(CATBOOST_DEFAULT)
    hp = dict(hyperparams or {})
    hp.pop("validation_ratio", None)

    if hp.get("iterations") is not None:
        params["iterations"] = int(hp["iterations"])
    elif hp.get("n_estimators") is not None:
        params["iterations"] = int(hp["n_estimators"])

    if hp.get("learning_rate") is not None:
        params["learning_rate"] = float(hp["learning_rate"])
    if hp.get("depth") is not None:
        params["depth"] = int(hp["depth"])
    elif hp.get("max_depth") is not None:
        params["depth"] = int(hp["max_depth"])

    if train_size is not None and train_size < 500:
        params["iterations"] = min(int(params["iterations"]), 150)

    return params


def train_catboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    hyperparams: dict[str, Any] | None = None,
):
    CatBoostRegressor = _ensure_catboost()
    params = build_catboost_params(hyperparams, train_size=len(X_train))
    model = CatBoostRegressor(**params)
    # TODO: site_id 등 categorical feature 자동 감지·처리
    model.fit(X_train, y_train)
    return model
