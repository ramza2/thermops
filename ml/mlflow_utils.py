"""MLflow 실험 기록."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import mlflow


def get_tracking_uri() -> str:
    return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def _configure_s3_env() -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"))
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"))
    os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000"))
    os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")


def log_experiment(
    experiment_name: str,
    params: dict[str, Any],
    metrics: dict[str, float],
    model=None,
    tags: dict[str, str] | None = None,
) -> str:
    mlflow.set_tracking_uri(get_tracking_uri())
    _configure_s3_env()
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run() as run:
        mlflow.log_params({k: str(v) for k, v in params.items()})
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})
        if tags:
            mlflow.set_tags(tags)
        if model is not None:
            try:
                mlflow.sklearn.log_model(model, "model")
            except Exception:
                pass
        return run.info.run_id


def _log_json_artifact(data: dict[str, Any], artifact_path: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        path = f.name
    try:
        mlflow.log_artifact(path, artifact_path=artifact_path)
    finally:
        os.unlink(path)


def log_training_run(
    experiment_name: str,
    params: dict[str, Any],
    metrics: dict[str, float],
    model: Any,
    feature_names: list[str],
    model_type: str,
    tags: dict[str, str] | None = None,
) -> tuple[str, str]:
    """MLflow run 생성 후 run_id, artifact_uri 반환."""
    mlflow.set_tracking_uri(get_tracking_uri())
    _configure_s3_env()
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run() as run:
        run_id = run.info.run_id
        mlflow.log_params({k: str(v) for k, v in params.items()})
        log_metrics = {k: float(v) for k, v in metrics.items() if v is not None and k != "primary_metric"}
        mlflow.log_metrics(log_metrics)
        if tags:
            mlflow.set_tags(tags)

        try:
            _log_json_artifact(
                {"features": feature_names, "model_type": model_type},
                artifact_path="metadata",
            )
            _log_json_artifact(log_metrics, artifact_path="metadata")
        except Exception:
            pass

        if model is not None:
            try:
                if model_type == "lightgbm":
                    try:
                        mlflow.lightgbm.log_model(model, "model")
                    except Exception:
                        mlflow.sklearn.log_model(model, "model")
                elif model_type == "catboost":
                    try:
                        mlflow.catboost.log_model(model, "model")
                    except Exception:
                        mlflow.sklearn.log_model(model, "model")
                elif model_type == "two_stage_catboost":
                    mlflow.sklearn.log_model(model, "model")
                else:
                    mlflow.sklearn.log_model(model, "model")
            except Exception:
                pass

        artifact_uri = f"runs:/{run_id}/model"
        return run_id, artifact_uri
