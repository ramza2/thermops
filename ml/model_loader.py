"""MLflow 모델 로드."""
from __future__ import annotations

from typing import Any

import mlflow

from mlflow_utils import _configure_s3_env, get_tracking_uri


def resolve_model_uri(mlflow_model_uri: str | None, artifact_uri: str | None) -> str:
    uri = mlflow_model_uri or artifact_uri
    if not uri:
        raise ValueError("모델 URI가 없습니다.")
    return uri


def load_model(mlflow_model_uri: str | None, artifact_uri: str | None = None) -> Any:
    uri = resolve_model_uri(mlflow_model_uri, artifact_uri)
    mlflow.set_tracking_uri(get_tracking_uri())
    _configure_s3_env()
    try:
        return mlflow.pyfunc.load_model(uri)
    except Exception:
        return mlflow.sklearn.load_model(uri)
