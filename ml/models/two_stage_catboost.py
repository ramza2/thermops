"""2-Stage CatBoost: Stage1 기본 예측 + Stage2 잔차 보정."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from models.catboost_model import build_catboost_params, train_catboost


class TwoStageCatBoostRegressor:
    """Stage1 CatBoost로 target 예측 후, train 잔차로 Stage2를 학습한다."""

    stage_count = 2
    stage1_model_type = "catboost"
    stage2_model_type = "catboost"

    def __init__(self, hyperparams: dict[str, Any] | None = None):
        self.hyperparams = hyperparams or {}
        self.stage1_: Any = None
        self.stage2_: Any = None
        self.feature_names_: list[str] | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.feature_names_ = list(X.columns)
        self.stage1_ = train_catboost(X, y, self.hyperparams)
        stage1_train_pred = np.asarray(self.stage1_.predict(X))
        residual = y.values - stage1_train_pred
        self.stage2_ = train_catboost(
            X,
            pd.Series(residual, index=y.index),
            self.hyperparams,
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        s1 = np.asarray(self.stage1_.predict(X))
        s2 = np.asarray(self.stage2_.predict(X))
        return np.clip(s1 + s2, 0, None)

    def predict_stage1(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.stage1_.predict(X))

    def get_params_summary(self) -> dict[str, Any]:
        params = build_catboost_params(self.hyperparams)
        return {
            "stage_count": self.stage_count,
            "stage1_model_type": self.stage1_model_type,
            "stage2_model_type": self.stage2_model_type,
            "catboost_iterations": params.get("iterations"),
            "catboost_depth": params.get("depth"),
            "catboost_learning_rate": params.get("learning_rate"),
        }

    def get_feature_importance(self) -> dict[str, list[float]] | None:
        try:
            return {
                "stage1": list(self.stage1_.get_feature_importance()),
                "stage2": list(self.stage2_.get_feature_importance()),
            }
        except Exception:
            return None
