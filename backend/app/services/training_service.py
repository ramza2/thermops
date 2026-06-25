"""모델 학습 서비스 — Feature Dataset 로드, 학습, MLflow·DB 반영."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import (
    FeatureDataset,
    FeatureSet,
    ModelExperiment,
    ModelPerformanceMetric,
    ModelVersion,
    PipelineRun,
    TrainingConfig,
    TrainingJob,
)
from app.schemas.api import TrainingJobCreate


ML_EXPERIMENT_NAME = "THERMOps_Heat_Demand_Forecasting"


@dataclass
class TrainingJobParams:
    config_id: str
    site_ids: list[str] | None = None
    train_start_at: date | None = None
    train_end_at: date | None = None
    validation_start_at: date | None = None
    validation_end_at: date | None = None
    register_model_yn: bool = True
    triggered_by: str | None = None


def _load_ml_modules():
    root = get_settings().project_root
    for candidate in (root / "ml", Path("/ml"), Path(__file__).resolve().parents[3] / "ml"):
        if candidate.exists():
            p = str(candidate.resolve())
            if p not in sys.path:
                sys.path.insert(0, p)
            break
    import mlflow_utils  # noqa: WPS433
    import train as train_mod  # noqa: WPS433

    return train_mod, mlflow_utils


def _record_dict(row: FeatureDataset) -> dict[str, Any]:
    return {
        "site_id": row.site_id,
        "feature_at": row.feature_at,
        "target_heat_demand": float(row.target_heat_demand) if row.target_heat_demand is not None else None,
        "feature_json": row.feature_json or {},
        "lag_24h_demand": float(row.lag_24h_demand) if row.lag_24h_demand is not None else None,
        "rolling_24h_avg": float(row.rolling_24h_avg) if row.rolling_24h_avg is not None else None,
    }


async def _get_config(db: AsyncSession, config_id: str) -> TrainingConfig:
    cfg = (
        await db.execute(select(TrainingConfig).where(TrainingConfig.config_id == config_id))
    ).scalar_one_or_none()
    if not cfg:
        raise ValueError(f"학습 설정을 찾을 수 없습니다: {config_id}")
    return cfg


async def _get_feature_set(db: AsyncSession, feature_set_id: str) -> FeatureSet:
    fs = (
        await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))
    ).scalar_one_or_none()
    if not fs:
        raise ValueError(f"Feature Set을 찾을 수 없습니다: {feature_set_id}")
    return fs


async def _latest_dataset_version_id(db: AsyncSession, feature_set_id: str) -> str | None:
    row = (
        await db.execute(
            select(FeatureDataset.dataset_version_id)
            .where(FeatureDataset.feature_json["feature_set_id"].astext == feature_set_id)
            .group_by(FeatureDataset.dataset_version_id)
            .order_by(func.max(FeatureDataset.created_at).desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def _load_feature_records(
    db: AsyncSession,
    dataset_version_id: str,
    site_ids: list[str] | None,
    train_start_at: date | None,
    train_end_at: date | None,
) -> list[dict[str, Any]]:
    clauses = [FeatureDataset.dataset_version_id == dataset_version_id]
    if site_ids:
        clauses.append(FeatureDataset.site_id.in_(site_ids))
    if train_start_at:
        clauses.append(FeatureDataset.feature_at >= datetime.combine(train_start_at, time.min))
    if train_end_at:
        clauses.append(FeatureDataset.feature_at <= datetime.combine(train_end_at, time.max))

    rows = (
        await db.execute(
            select(FeatureDataset)
            .where(and_(*clauses))
            .order_by(FeatureDataset.feature_at, FeatureDataset.site_id)
        )
    ).scalars().all()

    records = []
    for row in rows:
        rec = _record_dict(row)
        fj = rec["feature_json"]
        if rec.get("lag_24h_demand") is not None and "demand_lag_24h" not in fj:
            fj["demand_lag_24h"] = rec["lag_24h_demand"]
        if rec.get("rolling_24h_avg") is not None and "demand_ma_24h" not in fj:
            fj["demand_ma_24h"] = rec["rolling_24h_avg"]
        records.append(rec)
    return records


async def _next_version_no(db: AsyncSession, model_name: str) -> str:
    rows = (
        await db.execute(select(ModelVersion.version_no).where(ModelVersion.model_name == model_name))
    ).scalars().all()
    nums = []
    for v in rows:
        try:
            nums.append(int(str(v).lstrip("v")))
        except ValueError:
            continue
    return str(max(nums, default=0) + 1)


def _run_training_sync(
    records: list[dict[str, Any]],
    feature_names: list[str],
    algorithm: str,
    hyperparams: dict[str, Any] | None,
    feature_set_id: str,
    validation_start_at: date | None,
    validation_end_at: date | None,
) -> Any:
    train_mod, mlflow_utils = _load_ml_modules()
    ratio = None
    if hyperparams and "validation_ratio" in hyperparams:
        ratio = float(hyperparams["validation_ratio"])

    result = train_mod.run_training(
        records=records,
        feature_names=feature_names,
        algorithm=algorithm,
        hyperparams=hyperparams,
        validation_ratio=ratio,
        validation_start_at=validation_start_at,
        validation_end_at=validation_end_at,
    )

    model_name = train_mod.model_name_for_type(result.model_type)
    params = {
        "model_type": result.model_type,
        "feature_count": len(result.feature_names),
        "train_count": result.train_count,
        "validation_count": result.validation_count,
        "algorithm": algorithm,
        "feature_set_id": feature_set_id,
        "validation_ratio": ratio if ratio is not None else 0.2,
    }
    if hyperparams:
        params.update({k: v for k, v in hyperparams.items() if k != "validation_ratio"})

    mlflow_warnings: list[str] = []
    run_id = None
    artifact_uri = None
    try:
        run_id, artifact_uri = mlflow_utils.log_training_run(
            experiment_name=ML_EXPERIMENT_NAME,
            params=params,
            metrics=result.metrics,
            model=result.model,
            feature_names=result.feature_names,
            model_type=result.model_type,
            tags={"model_name": model_name},
        )
    except Exception as exc:  # noqa: BLE001
        mlflow_warnings.append(f"MLflow 기록 실패: {exc}")

    return result, model_name, run_id, artifact_uri, mlflow_warnings


def _per_site_metrics(y_true, y_pred, meta) -> list[dict[str, Any]]:
    from evaluation import compute_metrics  # noqa: WPS433
    import pandas as pd

    frame = meta.copy()
    frame["y_true"] = y_true
    frame["y_pred"] = y_pred
    out = []
    for site_id, grp in frame.groupby("site_id"):
        metrics = compute_metrics(grp["y_true"].values, grp["y_pred"].values)
        eval_start = grp["feature_at"].min()
        eval_end = grp["feature_at"].max()
        out.append({
            "site_id": site_id,
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "mape": metrics["mape"],
            "r2": metrics["r2"],
            "sample_count": len(grp),
            "eval_start_at": eval_start.to_pydatetime() if hasattr(eval_start, "to_pydatetime") else eval_start,
            "eval_end_at": eval_end.to_pydatetime() if hasattr(eval_end, "to_pydatetime") else eval_end,
        })
    return out


async def run_training_job(db: AsyncSession, params: TrainingJobParams) -> dict[str, Any]:
    started = utc_now()
    job_id = f"TRJ-{started.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
    run_id = f"LOCAL-RUN-{uuid4().hex[:6].upper()}"

    pipeline = PipelineRun(
        pipeline_run_id=run_id,
        pipeline_id="model_training_dag",
        pipeline_name="model_training_dag",
        pipeline_type="TRAINING",
        orchestrator="API",
        run_status="RUNNING",
        started_at=started,
        message="모델 학습 실행 중",
    )
    job = TrainingJob(
        job_id=job_id,
        config_id=params.config_id,
        pipeline_run_id=run_id,
        status="RUNNING",
        site_ids=params.site_ids,
        train_start_at=params.train_start_at,
        train_end_at=params.train_end_at,
        validation_start_at=params.validation_start_at,
        validation_end_at=params.validation_end_at,
        started_at=started,
        created_at=started,
    )
    db.add(pipeline)
    db.add(job)
    await db.flush()

    warnings: list[str] = []
    try:
        cfg = await _get_config(db, params.config_id)
        fs = await _get_feature_set(db, cfg.feature_set_id)
        feature_names: list[str] = fs.features or []

        dataset_version_id = await _latest_dataset_version_id(db, cfg.feature_set_id)
        if not dataset_version_id:
            raise ValueError(
                f"Feature Set {cfg.feature_set_id}에 대한 Feature Dataset이 없습니다. "
                "먼저 Feature 생성을 실행하세요."
            )

        records = await _load_feature_records(
            db,
            dataset_version_id,
            params.site_ids,
            params.train_start_at,
            params.train_end_at,
        )
        if not records:
            raise ValueError("학습 조건에 맞는 Feature Dataset 행이 없습니다.")

        result, model_name, mlflow_run_id, artifact_uri, mlflow_warnings = await asyncio.to_thread(
            _run_training_sync,
            records,
            feature_names,
            cfg.algorithm,
            cfg.hyperparams,
            cfg.feature_set_id,
            params.validation_start_at,
            params.validation_end_at,
        )
        warnings.extend(result.warnings)
        warnings.extend(mlflow_warnings)

        version_no = await _next_version_no(db, model_name)
        model_version_id = f"MV-{model_name}-{version_no}"[:80]
        experiment_id = f"EXP-{uuid4().hex[:8].upper()}"

        metric_summary = {
            "mae": result.metrics["mae"],
            "rmse": result.metrics["rmse"],
            "mape": result.metrics["mape"],
            "r2": result.metrics["r2"],
            "train_count": result.train_count,
            "validation_count": result.validation_count,
            "primary_metric": result.metrics["mape"],
        }

        experiment = ModelExperiment(
            experiment_id=experiment_id,
            mlflow_run_id=mlflow_run_id,
            dataset_version_id=dataset_version_id,
            algorithm=result.model_type,
            parameter_json={
                "config_id": params.config_id,
                "feature_set_id": cfg.feature_set_id,
                "hyperparams": cfg.hyperparams,
                "feature_names": result.feature_names,
            },
            metric_json=metric_summary,
            trained_at=utc_now(),
            created_by=params.triggered_by or "training_api",
        )
        db.add(experiment)

        model_version = ModelVersion(
            model_version_id=model_version_id,
            model_name=model_name,
            version_no=version_no,
            experiment_id=experiment_id,
            mlflow_model_uri=artifact_uri or (f"runs:/{mlflow_run_id}/model" if mlflow_run_id else None),
            artifact_uri=artifact_uri,
            model_stage="CANDIDATE",
            metric_summary_json=metric_summary,
            registered_at=utc_now(),
        )
        db.add(model_version)
        await db.flush()

        for site_row in _per_site_metrics(result.y_val, result.val_predictions, result.val_meta):
            db.add(
                ModelPerformanceMetric(
                    site_id=site_row["site_id"],
                    model_version_id=model_version_id,
                    eval_start_at=site_row["eval_start_at"],
                    eval_end_at=site_row["eval_end_at"],
                    mae=site_row["mae"],
                    rmse=site_row["rmse"],
                    mape=site_row["mape"],
                    sample_count=site_row["sample_count"],
                    metric_json={"eval_type": "TRAINING_VALIDATION"},
                )
            )

        finished = utc_now()
        job.status = "SUCCESS"
        job.ended_at = finished
        job.mlflow_run_id = mlflow_run_id
        job.registered_model_name = model_name
        job.registered_model_version = version_no
        job.metrics = metric_summary
        pipeline.run_status = "SUCCESS"
        pipeline.finished_at = finished
        pipeline.message = "모델 학습 완료"

        await db.flush()

        return {
            "job_id": job_id,
            "pipeline_run_id": run_id,
            "status": "SUCCESS",
            "model_version_id": model_version_id,
            "model_name": model_name,
            "model_version": version_no,
            "mlflow_run_id": mlflow_run_id,
            "artifact_uri": artifact_uri,
            "metrics": metric_summary,
            "dataset_version_id": dataset_version_id,
            "feature_set_id": cfg.feature_set_id,
            "warnings": warnings,
        }
    except Exception as exc:  # noqa: BLE001
        finished = utc_now()
        job.status = "FAILED"
        job.ended_at = finished
        job.metrics = {"error": str(exc)}
        pipeline.run_status = "FAILED"
        pipeline.finished_at = finished
        pipeline.message = str(exc)[:500]
        await db.flush()
        return {
            "job_id": job_id,
            "pipeline_run_id": run_id,
            "status": "FAILED",
            "error_message": str(exc),
            "warnings": warnings,
        }


async def get_training_job(db: AsyncSession, job_id: str) -> dict[str, Any] | None:
    j = (await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))).scalar_one_or_none()
    if not j:
        return None
    return _job_dict(j)


def _job_dict(j: TrainingJob) -> dict[str, Any]:
    data = {
        "job_id": j.job_id,
        "config_id": j.config_id,
        "status": j.status,
        "pipeline_run_id": j.pipeline_run_id,
        "site_ids": j.site_ids,
        "mlflow_run_id": j.mlflow_run_id,
        "registered_model_name": j.registered_model_name,
        "registered_model_version": j.registered_model_version,
        "metrics": j.metrics,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "ended_at": j.ended_at.isoformat() if j.ended_at else None,
        "train_start_at": j.train_start_at.isoformat() if j.train_start_at else None,
        "train_end_at": j.train_end_at.isoformat() if j.train_end_at else None,
        "validation_start_at": j.validation_start_at.isoformat() if j.validation_start_at else None,
        "validation_end_at": j.validation_end_at.isoformat() if j.validation_end_at else None,
    }
    if j.metrics and isinstance(j.metrics, dict):
        if j.registered_model_name and j.registered_model_version:
            data["model_version_id"] = f"MV-{j.registered_model_name}-{j.registered_model_version}"[:80]
    return data


def params_from_schema(body: TrainingJobCreate) -> TrainingJobParams:
    return TrainingJobParams(
        config_id=body.config_id,
        site_ids=body.site_ids,
        train_start_at=body.train_start_at,
        train_end_at=body.train_end_at,
        validation_start_at=body.validation_start_at,
        validation_end_at=body.validation_end_at,
        register_model_yn=body.register_model_yn,
        triggered_by=body.triggered_by,
    )
