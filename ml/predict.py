"""배치 예측 — Feature Matrix 생성 및 추론."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from train import predict as train_predict, records_to_dataframe


def build_prediction_matrix(
    df: pd.DataFrame,
    feature_names: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], int]:
    warnings: list[str] = []
    if df.empty:
        return pd.DataFrame(), df, ["입력 Feature 데이터가 없습니다."], 0

    work = df.copy()
    available = [f for f in feature_names if f in work.columns]
    missing = [f for f in feature_names if f not in work.columns]
    if missing:
        warnings.append(f"Feature Set에 정의됐으나 데이터에 없는 컬럼: {missing}")

    if not available:
        raise ValueError("예측 가능한 Feature 컬럼이 없습니다.")

    meta_cols = ["site_id", "feature_at"]
    if "target_heat_demand" in work.columns:
        meta_cols.append("target_heat_demand")

    X = work[available].apply(pd.to_numeric, errors="coerce")
    meta = work[meta_cols].copy()

    before = len(X)
    valid = X.notna().all(axis=1)
    skipped = int(before - valid.sum())
    X = X[valid].reset_index(drop=True)
    meta = meta[valid].reset_index(drop=True)

    if skipped:
        warnings.append(f"결측 Feature로 {skipped}행 제외")

    return X, meta, warnings, skipped


def run_batch_predict(
    records: list[dict[str, Any]],
    feature_names: list[str],
    model: Any,
) -> tuple[np.ndarray, pd.DataFrame, list[str], int]:
    df = records_to_dataframe(records)
    X, meta, warnings, skipped = build_prediction_matrix(df, feature_names)
    if X.empty:
        raise ValueError("예측 입력 행이 없습니다.")

    if hasattr(model, "predict"):
        preds = np.asarray(model.predict(X))
    else:
        preds = np.asarray(train_predict(model, X))

    clipped = int(np.sum(preds < 0))
    if clipped:
        warnings.append(f"예측값 0 미만 {clipped}건을 0으로 보정")
    preds = np.clip(preds, 0, None)

    return preds, meta, warnings, skipped
