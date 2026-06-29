"""파이프라인 Task callable — DAG 파일에서 공유."""
from __future__ import annotations

from common import call_backend_api, extract_conf, update_pipeline_status


def _parse_dt(value: str | None, end: bool = False) -> str | None:
    if not value:
        return None
    if "T" not in value:
        return f"{value}T23:59:59" if end else f"{value}T00:00:00"
    return value


def _is_final_step(context: dict) -> bool:
    ti = context.get("task_instance")
    if not ti:
        return True
    if ti.dag_id == "thermops_full_pipeline_dag":
        return ti.task_id == "prediction_evaluation"
    return True


def _complete_step(
    context: dict,
    pipeline_run_id: str | None,
    step_name: str,
    message: str,
    summary: dict,
) -> None:
    status = "SUCCESS" if _is_final_step(context) else "RUNNING"
    update_pipeline_status(pipeline_run_id, status, step_name, message, summary)


def mark_pipeline_running(**context):
    conf = extract_conf(context)
    update_pipeline_status(conf.get("pipeline_run_id"), "RUNNING", "full_pipeline", "전체 파이프라인 시작")


def run_ingestion(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    source_id = conf.get("source_id")
    if not source_id:
        raise ValueError("data_ingestion_dag conf에 source_id가 필요합니다.")
    weather_source_id = conf.get("weather_source_id")

    update_pipeline_status(pipeline_run_id, "RUNNING", "data_ingestion", "데이터 적재 시작")
    results = []

    def _ingest_params(sid: str) -> dict:
        params: dict = {"source_id": sid, "load_mode": conf.get("load_mode", "UPSERT")}
        if conf.get("start_at"):
            params["start_at"] = conf.get("start_at")
        if conf.get("end_at"):
            params["end_at"] = conf.get("end_at")
        if conf.get("limit") is not None:
            params["limit"] = conf.get("limit")
        if conf.get("mapping_id"):
            params["mapping_id"] = conf.get("mapping_id")
        if conf.get("data_domain"):
            params["data_domain"] = conf.get("data_domain")
        return params

    heat = call_backend_api("POST", "/ingestion-jobs", params=_ingest_params(source_id))
    results.append({"source_id": source_id, **heat})
    if weather_source_id:
        weather = call_backend_api("POST", "/ingestion-jobs", params=_ingest_params(weather_source_id))
        results.append({"source_id": weather_source_id, **weather})

    summary = {
        "inserted_count": sum(r.get("inserted_count") or 0 for r in results),
        "updated_count": sum(r.get("updated_count") or 0 for r in results),
        "failed_count": sum(r.get("failed_count") or 0 for r in results),
        "skipped_count": sum(r.get("skipped_count") or 0 for r in results),
        "jobs": results,
    }
    _complete_step(context, pipeline_run_id, "data_ingestion", "데이터 적재 완료", summary)
    return summary


def run_quality_check(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    params = {"data_domain": conf.get("data_domain", "HEAT_DEMAND")}
    if conf.get("source_id"):
        params["source_id"] = conf["source_id"]
    if conf.get("site_id"):
        params["site_id"] = conf["site_id"]
    if conf.get("weather_area_id"):
        params["weather_area_id"] = conf["weather_area_id"]
    if conf.get("start_at"):
        params["start_at"] = conf["start_at"]
    if conf.get("end_at"):
        params["end_at"] = conf["end_at"]

    update_pipeline_status(pipeline_run_id, "RUNNING", "data_quality", "품질 점검 시작")
    result = call_backend_api("POST", "/data-quality/checks", params=params)
    summary = dict(result.get("result_summary") or {})
    summary.update({"run_id": result.get("run_id"), "status": result.get("status")})
    if result.get("status") != "SUCCESS":
        update_pipeline_status(
            pipeline_run_id,
            "FAILED",
            "data_quality",
            "품질 점검 실패",
            summary,
        )
        raise RuntimeError(summary.get("error_message") or "data quality check failed")
    _complete_step(context, pipeline_run_id, "data_quality", "품질 점검 완료", summary)
    return summary


def run_feature_build(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    params = {"feature_set_id": conf.get("feature_set_id", "FS-TPL-LAG-ROLL")}
    if conf.get("site_id"):
        params["site_id"] = conf["site_id"]
    if conf.get("start_at"):
        params["start_at"] = conf["start_at"]
    if conf.get("end_at"):
        params["end_at"] = conf["end_at"]

    update_pipeline_status(pipeline_run_id, "RUNNING", "feature_build", "Feature 생성 시작")
    result = call_backend_api("POST", "/feature-build-jobs", params=params)
    summary = {
        "job_id": result.get("job_id"),
        "status": result.get("status"),
        "generated_count": result.get("inserted_count"),
        "feature_count": len((result.get("result_summary") or {}).get("feature_names") or []),
        "warnings": result.get("warnings") or [],
        "dataset_version_id": result.get("dataset_version_id"),
    }
    if result.get("status") != "SUCCESS":
        update_pipeline_status(pipeline_run_id, "FAILED", "feature_build", "Feature 생성 실패", summary)
        raise RuntimeError(result.get("error_message") or "feature build failed")
    _complete_step(context, pipeline_run_id, "feature_build", "Feature 생성 완료", summary)
    return summary


def run_model_training(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    body = {
        "config_id": conf.get("config_id", "TRC-TPL-LAG-ROLL"),
        "register_model_yn": conf.get("register_model_yn", True),
    }
    if conf.get("site_ids"):
        body["site_ids"] = conf["site_ids"]

    update_pipeline_status(pipeline_run_id, "RUNNING", "model_training", "모델 학습 시작")
    result = call_backend_api("POST", "/training-jobs", json_body=body)
    summary = {
        "job_id": result.get("job_id"),
        "status": result.get("status"),
        "model_version_id": result.get("model_version_id"),
        "mlflow_run_id": result.get("mlflow_run_id"),
        "metrics": result.get("metrics") or {},
    }
    if result.get("status") != "SUCCESS":
        update_pipeline_status(pipeline_run_id, "FAILED", "model_training", "모델 학습 실패", summary)
        raise RuntimeError(result.get("error_message") or "model training failed")
    _complete_step(context, pipeline_run_id, "model_training", "모델 학습 완료", summary)
    return summary


def run_batch_prediction(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    ti = context.get("ti")

    model_version_id = conf.get("model_version_id")
    if not model_version_id and ti:
        train_result = ti.xcom_pull(task_ids="model_training")
        if isinstance(train_result, dict):
            model_version_id = train_result.get("model_version_id")

    body: dict = {
        "feature_set_id": conf.get("feature_set_id", "FS-TPL-LAG-ROLL"),
        "overwrite_yn": conf.get("overwrite_yn", True),
    }
    if model_version_id:
        body["model_version_id"] = model_version_id
    if conf.get("model_name"):
        body["model_name"] = conf["model_name"]
    if conf.get("site_ids"):
        body["site_ids"] = conf["site_ids"]
    start_at = _parse_dt(conf.get("start_at"))
    end_at = _parse_dt(conf.get("end_at"), end=True)
    if start_at:
        body["start_at"] = start_at
    if end_at:
        body["end_at"] = end_at

    update_pipeline_status(pipeline_run_id, "RUNNING", "batch_prediction", "배치 예측 시작")
    result = call_backend_api("POST", "/prediction-jobs", json_body=body)
    summary = {
        "prediction_job_id": result.get("prediction_job_id") or result.get("job_id"),
        "status": result.get("status"),
        "predicted_count": result.get("predicted_count"),
        "skipped_count": result.get("skipped_count"),
        "model_version_id": result.get("model_version_id"),
        "warnings": result.get("warnings") or [],
    }
    if result.get("status") != "SUCCESS":
        update_pipeline_status(pipeline_run_id, "FAILED", "batch_prediction", "배치 예측 실패", summary)
        raise RuntimeError(result.get("error_message") or "batch prediction failed")
    _complete_step(context, pipeline_run_id, "batch_prediction", "배치 예측 완료", summary)
    return summary


def run_monitoring(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    ti = context.get("ti")

    prediction_job_id = conf.get("prediction_job_id")
    model_version_id = conf.get("model_version_id")
    if ti:
        pred_result = ti.xcom_pull(task_ids="batch_prediction")
        if isinstance(pred_result, dict):
            prediction_job_id = prediction_job_id or pred_result.get("prediction_job_id")
            model_version_id = model_version_id or pred_result.get("model_version_id")

    body: dict = {}
    if model_version_id:
        body["model_version_id"] = model_version_id
    if prediction_job_id:
        body["prediction_job_id"] = prediction_job_id
    if conf.get("site_ids"):
        body["site_ids"] = conf["site_ids"]
    start_at = _parse_dt(conf.get("start_at"))
    end_at = _parse_dt(conf.get("end_at"), end=True)
    if start_at:
        body["start_at"] = start_at
    if end_at:
        body["end_at"] = end_at

    update_pipeline_status(pipeline_run_id, "RUNNING", "prediction_evaluation", "예측 평가 시작")
    result = call_backend_api("POST", "/predictions/evaluate", json_body=body)
    metrics = result.get("metrics") or {}
    summary = {
        "status": result.get("status"),
        "matched_count": result.get("matched_count"),
        "prediction_job_id": prediction_job_id,
        "model_version_id": model_version_id,
        "mape": metrics.get("mape"),
        "mae": metrics.get("mae"),
        "rmse": metrics.get("rmse"),
        "r2": metrics.get("r2"),
    }
    if result.get("status") != "SUCCESS":
        update_pipeline_status(pipeline_run_id, "FAILED", "prediction_evaluation", "예측 평가 실패", summary)
        raise RuntimeError(result.get("error_message") or "prediction evaluation failed")
    _complete_step(context, pipeline_run_id, "prediction_evaluation", "예측 평가 완료", summary)
    return summary


def run_drift_detection(**context):
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")

    body: dict = {}
    if conf.get("model_version_id"):
        body["model_version_id"] = conf["model_version_id"]
    if conf.get("feature_set_id"):
        body["feature_set_id"] = conf["feature_set_id"]
    if conf.get("site_ids"):
        body["site_ids"] = conf["site_ids"]
    start_at = _parse_dt(conf.get("baseline_start_at"))
    end_at = _parse_dt(conf.get("baseline_end_at"), end=True)
    if start_at:
        body["baseline_start_at"] = start_at
    if end_at:
        body["baseline_end_at"] = end_at
    start_at = _parse_dt(conf.get("current_start_at"))
    end_at = _parse_dt(conf.get("current_end_at"), end=True)
    if start_at:
        body["current_start_at"] = start_at
    if end_at:
        body["current_end_at"] = end_at
    if conf.get("force_candidate"):
        body["force_candidate"] = conf["force_candidate"]

    update_pipeline_status(pipeline_run_id, "RUNNING", "drift_detection", "Drift 감지 시작")
    result = call_backend_api("POST", "/drift-checks", json_body=body)
    summary = {
        "status": result.get("status"),
        "overall_drift_status": result.get("overall_drift_status"),
        "drift_report_id": result.get("drift_report_id"),
        "created_retraining_candidates": result.get("created_retraining_candidates"),
        "retraining_candidate_id": result.get("retraining_candidate_id"),
        "metric_summary": result.get("metric_summary"),
    }
    if result.get("status") != "SUCCESS":
        update_pipeline_status(pipeline_run_id, "FAILED", "drift_detection", "Drift 감지 실패", summary)
        raise RuntimeError("drift detection failed")
    _complete_step(context, pipeline_run_id, "drift_detection", "Drift 감지 완료", summary)
    return summary


def validate_retraining_candidate(**context):
    conf = extract_conf(context)
    candidate_id = conf.get("candidate_id")
    if not candidate_id:
        raise RuntimeError("retraining_dag conf에 candidate_id가 필요합니다.")

    result = call_backend_api("GET", f"/retraining-candidates/{candidate_id}")
    source_type = result.get("source_type")
    status = result.get("status")
    if source_type != "COMPUTED":
        raise RuntimeError(f"COMPUTED 후보만 재학습할 수 있습니다. (source_type={source_type})")
    if status not in ("APPROVED", "TRAINING"):
        raise RuntimeError(f"승인 또는 학습 중 상태만 실행 가능합니다. (status={status})")
    return {
        "candidate_id": candidate_id,
        "status": status,
        "source_type": source_type,
    }


def run_retraining(**context):
    conf = extract_conf(context)
    candidate_id = conf.get("candidate_id")
    if not candidate_id:
        raise RuntimeError("retraining_dag conf에 candidate_id가 필요합니다.")

    result = call_backend_api("POST", f"/retraining-candidates/{candidate_id}/train-sync-internal", json_body={})
    if result.get("status") != "SUCCESS":
        raise RuntimeError(result.get("candidate", {}).get("error_message") or "retraining failed")
    return result


def finalize_retraining_candidate(**context):
    conf = extract_conf(context)
    candidate_id = conf.get("candidate_id")
    if not candidate_id:
        raise RuntimeError("retraining_dag conf에 candidate_id가 필요합니다.")

    result = call_backend_api("GET", f"/retraining-candidates/{candidate_id}", params={"sync_airflow": "true"})
    if result.get("status") != "TRAINED":
        raise RuntimeError(f"재학습 후보가 TRAINED가 아닙니다. (status={result.get('status')})")
    return {
        "candidate_id": candidate_id,
        "status": result.get("status"),
        "training_job_id": result.get("training_job_id"),
        "new_model_version_id": result.get("new_model_version_id"),
        "mlflow_run_id": result.get("mlflow_run_id"),
    }
