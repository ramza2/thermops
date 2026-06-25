"""모델 학습 파이프라인 — Feature Dataset → 학습 → 평가."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from evaluation import compute_metrics
from models.baseline import FeatureColumnBaseline, lag24h_baseline, moving_average_baseline
from models.ml_models import train_lightgbm, predict_model
from models.sklearn_model import train_hist_gradient_boosting, train_random_forest


@dataclass
class TrainSplit:
    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    meta_train: pd.DataFrame
    meta_val: pd.DataFrame


@dataclass
class TrainResult:
    model: Any
    model_type: str
    metrics: dict[str, float]
    train_metrics: dict[str, float]
    feature_names: list[str]
    train_count: int
    validation_count: int
    val_predictions: np.ndarray
    y_val: np.ndarray
    val_meta: pd.DataFrame
    warnings: list[str]


def resolve_model_type(algorithm: str | None) -> str:
    if not algorithm:
        return "lightgbm"
    key = algorithm.lower().replace(" ", "").replace("-", "").replace("_", "")
    if key in ("baseline", "naivelag24h", "naive"):
        return "baseline_lag24h"
    if key in ("movingaverage", "baseline_ma", "movingavg", "ma"):
        return "baseline_ma"
    if "lightgbm" in key or key == "lgbm":
        return "lightgbm"
    if "randomforest" in key or key in ("rf", "randomforestregressor"):
        return "sklearn_rf"
    if "xgboost" in key or key == "xgb":
        raise ValueError("XGBoost는 이번 단계에서 지원하지 않습니다.")
    if "catboost" in key or "twostage" in key:
        raise ValueError("2-Stage CatBoost는 이번 단계에서 지원하지 않습니다.")
    return "sklearn_gbdt"


def model_name_for_type(model_type: str) -> str:
    return {
        "lightgbm": "heat_demand_lightgbm",
        "sklearn_gbdt": "heat_demand_gbdt",
        "sklearn_rf": "heat_demand_rf",
        "baseline_lag24h": "heat_demand_baseline_lag24h",
        "baseline_ma": "heat_demand_baseline_ma",
    }.get(model_type, "heat_demand_model")


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for rec in records:
        fj = rec.get("feature_json") or {}
        row = {
            "site_id": rec["site_id"],
            "feature_at": rec["feature_at"],
            "target_heat_demand": rec.get("target_heat_demand"),
            **{k: v for k, v in fj.items() if k not in ("feature_set_id",)},
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["feature_at"] = pd.to_datetime(df["feature_at"])
        df = df.sort_values(["feature_at", "site_id"]).reset_index(drop=True)
    return df


def build_feature_matrix(
    df: pd.DataFrame,
    feature_names: list[str],
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if df.empty:
        return pd.DataFrame(), pd.Series(dtype=float), df, warnings

    work = df.copy()
    work = work[work["target_heat_demand"].notna()]
    if work.empty:
        return pd.DataFrame(), pd.Series(dtype=float), work, ["target_heat_demand가 있는 행이 없습니다."]

    available = [f for f in feature_names if f in work.columns]
    missing = [f for f in feature_names if f not in work.columns]
    if missing:
        warnings.append(f"Feature Set에 정의됐으나 데이터에 없는 컬럼: {missing}")

    if not available:
        raise ValueError("학습 가능한 Feature 컬럼이 없습니다.")

    X = work[available].apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(work["target_heat_demand"], errors="coerce")
    meta = work[["site_id", "feature_at"]].copy()

    before = len(X)
    valid = X.notna().all(axis=1) & y.notna()
    X = X[valid].reset_index(drop=True)
    y = y[valid].reset_index(drop=True)
    meta = meta[valid].reset_index(drop=True)

    dropped = before - len(X)
    if dropped:
        warnings.append(f"결측 Feature/target으로 {dropped}행 제외")

    return X, y, meta, warnings


def time_based_split(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    validation_ratio: float = 0.2,
    validation_start_at: date | None = None,
    validation_end_at: date | None = None,
) -> TrainSplit:
    if len(X) < 2:
        raise ValueError("학습에 필요한 최소 2행 이상의 데이터가 필요합니다.")

    if validation_start_at is not None:
        val_mask = meta["feature_at"].dt.date >= validation_start_at
        if validation_end_at is not None:
            val_mask &= meta["feature_at"].dt.date <= validation_end_at
        train_mask = ~val_mask
    else:
        ratio = min(max(validation_ratio, 0.05), 0.5)
        split_idx = max(1, int(len(X) * (1 - ratio)))
        if split_idx >= len(X):
            split_idx = len(X) - 1
        train_mask = pd.Series([True] * split_idx + [False] * (len(X) - split_idx))
        val_mask = ~train_mask

    return TrainSplit(
        X_train=X[train_mask].reset_index(drop=True),
        y_train=y[train_mask].reset_index(drop=True),
        X_val=X[val_mask].reset_index(drop=True),
        y_val=y[val_mask].reset_index(drop=True),
        meta_train=meta[train_mask].reset_index(drop=True),
        meta_val=meta[val_mask].reset_index(drop=True),
    )


def train_model(
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    hyperparams: dict[str, Any] | None = None,
) -> Any:
    params = dict(hyperparams or {})
    params.pop("validation_ratio", None)

    if model_type == "baseline_lag24h":
        model = lag24h_baseline()
        model.fit(X_train, y_train)
        return model
    if model_type == "baseline_ma":
        model = moving_average_baseline()
        model.fit(X_train, y_train)
        return model
    if model_type == "lightgbm":
        try:
            return train_lightgbm(X_train, y_train, params)
        except (ImportError, OSError) as exc:
            raise ImportError("lightgbm unavailable") from exc
    if model_type == "sklearn_rf":
        return train_random_forest(X_train, y_train, params)
    return train_hist_gradient_boosting(X_train, y_train, params)


def predict(model: Any, X: pd.DataFrame) -> np.ndarray:
    if isinstance(model, FeatureColumnBaseline):
        return model.predict(X)
    return predict_model(model, X)


def run_training(
    records: list[dict[str, Any]],
    feature_names: list[str],
    algorithm: str | None = None,
    hyperparams: dict[str, Any] | None = None,
    validation_ratio: float | None = None,
    validation_start_at: date | None = None,
    validation_end_at: date | None = None,
) -> TrainResult:
    warnings: list[str] = []
    df = records_to_dataframe(records)
    X, y, meta, build_warnings = build_feature_matrix(df, feature_names)
    warnings.extend(build_warnings)

    if X.empty:
        raise ValueError("학습 데이터가 없습니다.")

    ratio = validation_ratio
    if ratio is None:
        ratio = float((hyperparams or {}).get("validation_ratio", 0.2))

    split = time_based_split(
        X, y, meta,
        validation_ratio=ratio,
        validation_start_at=validation_start_at,
        validation_end_at=validation_end_at,
    )

    if split.X_val.empty:
        raise ValueError("검증 데이터가 없습니다. 기간 또는 validation_ratio를 확인하세요.")

    model_type = resolve_model_type(algorithm)
    train_warnings: list[str] = []
    try:
        model = train_model(model_type, split.X_train, split.y_train, hyperparams)
    except (ImportError, OSError) as exc:
        if model_type == "lightgbm":
            train_warnings.append(f"LightGBM 사용 불가, sklearn_gbdt로 대체: {exc}")
            model_type = "sklearn_gbdt"
            model = train_model(model_type, split.X_train, split.y_train, hyperparams)
        else:
            raise

    train_pred = predict(model, split.X_train)
    val_pred = predict(model, split.X_val)

    train_metrics = compute_metrics(split.y_train.values, train_pred)
    metrics = compute_metrics(split.y_val.values, val_pred)
    metrics["train_count"] = float(len(split.X_train))
    metrics["validation_count"] = float(len(split.X_val))
    metrics["primary_metric"] = metrics["mape"]

    return TrainResult(
        model=model,
        model_type=model_type,
        metrics=metrics,
        train_metrics=train_metrics,
        feature_names=list(split.X_train.columns),
        train_count=len(split.X_train),
        validation_count=len(split.X_val),
        val_predictions=val_pred,
        y_val=split.y_val.values,
        val_meta=split.meta_val,
        warnings=warnings + train_warnings,
    )
