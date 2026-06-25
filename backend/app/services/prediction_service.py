"""배치 예측 서비스 — Feature 로드, MLflow 모델 추론, 결과 저장."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import (
    FeatureDataset,
    FeatureSet,
    HeatDemandPrediction,
    ModelExperiment,
    ModelVersion,
    PipelineRun,
    PredictionJob,
)
from app.schemas.api import PredictionJobCreate


@dataclass
class PredictionJobParams:
    feature_set_id: str
    site_ids: list[str] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    prediction_horizon: str = "BATCH"
    model_version_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    overwrite_yn: bool = True


def _load_ml_modules():
    root = get_settings().project_root
    for candidate in (root / "ml", Path("/ml"), Path(__file__).resolve().parents[3] / "ml"):
        if candidate.exists():
            p = str(candidate.resolve())
            if p not in sys.path:
                sys.path.insert(0, p)
            break
    import model_loader  # noqa: WPS433
    import predict as predict_mod  # noqa: WPS433

    return predict_mod, model_loader


def _record_dict(row: FeatureDataset) -> dict[str, Any]:
    return {
        "site_id": row.site_id,
        "feature_at": row.feature_at,
        "target_heat_demand": float(row.target_heat_demand) if row.target_heat_demand is not None else None,
        "feature_json": row.feature_json or {},
        "lag_24h_demand": float(row.lag_24h_demand) if row.lag_24h_demand is not None else None,
        "rolling_24h_avg": float(row.rolling_24h_avg) if row.rolling_24h_avg is not None else None,
    }


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
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[dict[str, Any]]:
    clauses = [FeatureDataset.dataset_version_id == dataset_version_id]
    if site_ids:
        clauses.append(FeatureDataset.site_id.in_(site_ids))
    if start_at:
        clauses.append(FeatureDataset.feature_at >= start_at)
    if end_at:
        clauses.append(FeatureDataset.feature_at <= end_at)

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


async def _resolve_model_version(
    db: AsyncSession,
    params: PredictionJobParams,
) -> tuple[ModelVersion, list[str]]:
    warnings: list[str] = []
    mv: ModelVersion | None = None

    if params.model_version_id:
        mv = (
            await db.execute(
                select(ModelVersion).where(ModelVersion.model_version_id == params.model_version_id)
            )
        ).scalar_one_or_none()
        if not mv:
            raise ValueError(f"모델 버전을 찾을 수 없습니다: {params.model_version_id}")
        return mv, warnings

    if params.model_name and params.model_version:
        mv = (
            await db.execute(
                select(ModelVersion).where(
                    ModelVersion.model_name == params.model_name,
                    ModelVersion.version_no == params.model_version,
                )
            )
        ).scalar_one_or_none()
        if mv:
            return mv, warnings

    q = select(ModelVersion).where(ModelVersion.model_stage == "CHAMPION")
    if params.model_name:
        q = q.where(ModelVersion.model_name == params.model_name)
    mv = (await db.execute(q.order_by(ModelVersion.registered_at.desc()).limit(1))).scalar_one_or_none()
    if mv:
        return mv, warnings

    q = select(ModelVersion).where(ModelVersion.model_stage == "CANDIDATE")
    if params.model_name:
        q = q.where(ModelVersion.model_name == params.model_name)
    mv = (await db.execute(q.order_by(ModelVersion.registered_at.desc()).limit(1))).scalar_one_or_none()
    if mv:
        warnings.append(
            f"CHAMPION 모델이 없어 최신 CANDIDATE 모델을 사용합니다: {mv.model_name} v{mv.version_no}"
        )
        return mv, warnings

    raise ValueError("사용 가능한 모델 버전이 없습니다. 먼저 모델 학습을 실행하세요.")


async def _get_mlflow_run_id(db: AsyncSession, mv: ModelVersion) -> str | None:
    if not mv.experiment_id:
        return None
    exp = (
        await db.execute(
            select(ModelExperiment).where(ModelExperiment.experiment_id == mv.experiment_id)
        )
    ).scalar_one_or_none()
    return exp.mlflow_run_id if exp else None


def _run_prediction_sync(
    records: list[dict[str, Any]],
    feature_names: list[str],
    mlflow_model_uri: str | None,
    artifact_uri: str | None,
) -> tuple[Any, Any, list[str], int]:
    predict_mod, model_loader = _load_ml_modules()
    model = model_loader.load_model(mlflow_model_uri, artifact_uri)
    preds, meta, warnings, skipped = predict_mod.run_batch_predict(records, feature_names, model)
    return preds, meta, warnings, skipped


async def _upsert_predictions(
    db: AsyncSession,
    job_id: str,
    model_version_id: str,
    feature_set_id: str,
    preds,
    meta,
    overwrite_yn: bool,
) -> int:
    now = utc_now()
    rows: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(meta.iterrows()):
        target_at = row["feature_at"]
        if hasattr(target_at, "to_pydatetime"):
            target_at = target_at.to_pydatetime()
        site_id = str(row["site_id"])
        rows.append({
            "site_id": site_id,
            "target_at": target_at,
            "predicted_demand": float(preds[i]),
            "model_version_id": model_version_id,
        })

    if overwrite_yn and rows:
        for row in rows:
            await db.execute(
                delete(HeatDemandPrediction).where(
                    HeatDemandPrediction.site_id == row["site_id"],
                    HeatDemandPrediction.target_at == row["target_at"],
                    HeatDemandPrediction.model_version_id == model_version_id,
                )
            )

    for row in rows:
        db.add(
            HeatDemandPrediction(
                prediction_job_id=job_id,
                site_id=row["site_id"],
                target_at=row["target_at"],
                predicted_demand=row["predicted_demand"],
                model_version_id=model_version_id,
                feature_set_id=feature_set_id,
                created_at=now,
            )
        )

    return len(rows)


def params_from_schema(body: PredictionJobCreate) -> PredictionJobParams:
    start_at = body.start_at or body.target_start_at
    end_at = body.end_at or body.target_end_at
    if not start_at or not end_at:
        raise ValueError("start_at/target_start_at와 end_at/target_end_at가 필요합니다.")
    return PredictionJobParams(
        feature_set_id=body.feature_set_id,
        site_ids=body.site_ids,
        start_at=start_at,
        end_at=end_at,
        prediction_horizon=body.prediction_horizon,
        model_version_id=body.model_version_id,
        model_name=body.model_name,
        model_version=body.model_version,
        overwrite_yn=body.overwrite_yn,
    )


async def run_prediction_job(db: AsyncSession, params: PredictionJobParams) -> dict[str, Any]:
    started = utc_now()
    job_id = f"PRJ-{started.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
    run_id = f"LOCAL-RUN-{uuid4().hex[:6].upper()}"
    warnings: list[str] = []

    mv, select_warnings = await _resolve_model_version(db, params)
    warnings.extend(select_warnings)
    mlflow_run_id = await _get_mlflow_run_id(db, mv)

    pipeline = PipelineRun(
        pipeline_run_id=run_id,
        pipeline_id="batch_prediction_dag",
        pipeline_name="batch_prediction_dag",
        pipeline_type="PREDICTION",
        orchestrator="API",
        run_status="RUNNING",
        started_at=started,
        message="배치 예측 실행 중",
    )
    job = PredictionJob(
        prediction_job_id=job_id,
        pipeline_run_id=run_id,
        model_version_id=mv.model_version_id,
        prediction_horizon=params.prediction_horizon,
        target_start_at=params.start_at,
        target_end_at=params.end_at,
        site_ids=params.site_ids,
        job_status="RUNNING",
        started_at=started,
        created_at=started,
    )
    db.add(pipeline)
    db.add(job)
    await db.flush()

    try:
        fs = await _get_feature_set(db, params.feature_set_id)
        feature_names: list[str] = fs.features or []

        dataset_version_id = await _latest_dataset_version_id(db, params.feature_set_id)
        if not dataset_version_id:
            raise ValueError(
                f"Feature Set {params.feature_set_id}에 대한 Feature Dataset이 없습니다."
            )

        records = await _load_feature_records(
            db,
            dataset_version_id,
            params.site_ids,
            params.start_at,
            params.end_at,
        )
        input_count = len(records)
        if not records:
            raise ValueError("예측 조건에 맞는 Feature Dataset 행이 없습니다.")

        preds, meta, pred_warnings, skipped = await asyncio.to_thread(
            _run_prediction_sync,
            records,
            feature_names,
            mv.mlflow_model_uri,
            mv.artifact_uri,
        )
        warnings.extend(pred_warnings)

        predicted_count = await _upsert_predictions(
            db,
            job_id,
            mv.model_version_id,
            params.feature_set_id,
            preds,
            meta,
            params.overwrite_yn,
        )

        site_count = int(meta["site_id"].nunique()) if not meta.empty else 0
        result_summary = {
            "model_name": mv.model_name,
            "model_version_id": mv.model_version_id,
            "version_no": mv.version_no,
            "model_stage": mv.model_stage,
            "mlflow_run_id": mlflow_run_id,
            "mlflow_model_uri": mv.mlflow_model_uri,
            "artifact_uri": mv.artifact_uri,
            "feature_set_id": params.feature_set_id,
            "dataset_version_id": dataset_version_id,
            "target_start_at": params.start_at.isoformat(),
            "target_end_at": params.end_at.isoformat(),
            "site_count": site_count,
            "input_count": input_count,
            "predicted_count": predicted_count,
            "skipped_count": skipped,
            "feature_count": len(feature_names),
            "warnings": warnings,
        }

        finished = utc_now()
        job.job_status = "SUCCESS"
        job.finished_at = finished
        job.result_summary = result_summary
        pipeline.run_status = "SUCCESS"
        pipeline.finished_at = finished
        pipeline.message = f"배치 예측 완료 ({predicted_count}건)"
        await db.flush()

        return {
            "job_id": job_id,
            "pipeline_run_id": run_id,
            "status": "SUCCESS",
            "predicted_count": predicted_count,
            "model_version_id": mv.model_version_id,
            "model_name": mv.model_name,
            "model_version": mv.version_no,
            "result_summary": result_summary,
            "warnings": warnings,
        }
    except Exception as exc:  # noqa: BLE001
        finished = utc_now()
        job.job_status = "FAILED"
        job.finished_at = finished
        job.error_message = str(exc)
        job.result_summary = {"warnings": warnings}
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


async def get_prediction_job(db: AsyncSession, job_id: str) -> dict[str, Any] | None:
    j = (
        await db.execute(select(PredictionJob).where(PredictionJob.prediction_job_id == job_id))
    ).scalar_one_or_none()
    if not j:
        return None
    return _job_dict(j)


def _job_dict(j: PredictionJob) -> dict[str, Any]:
    summary = j.result_summary or {}
    return {
        "job_id": j.prediction_job_id,
        "status": j.job_status,
        "model_version_id": j.model_version_id,
        "prediction_horizon": j.prediction_horizon,
        "target_start_at": j.target_start_at.isoformat(),
        "target_end_at": j.target_end_at.isoformat(),
        "site_ids": j.site_ids,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "created_at": j.created_at.isoformat(),
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        "error_message": j.error_message,
        "predicted_count": summary.get("predicted_count"),
        "result_summary": summary,
    }
