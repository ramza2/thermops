"""MLflow 실험 기록."""
from __future__ import annotations

import os
from typing import Any

import mlflow


def get_tracking_uri() -> str:
    return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def log_experiment(
    experiment_name: str,
    params: dict[str, Any],
    metrics: dict[str, float],
    model=None,
    tags: dict[str, str] | None = None,
) -> str:
    mlflow.set_tracking_uri(get_tracking_uri())
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run() as run:
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        if tags:
            mlflow.set_tags(tags)
        if model is not None:
            mlflow.sklearn.log_model(model, "model")
        return run.info.run_id
