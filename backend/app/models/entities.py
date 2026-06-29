from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utc_now


class Site(Base):
    __tablename__ = "tb_site"
    site_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    site_name: Mapped[str] = mapped_column(String(100))
    site_type: Mapped[str] = mapped_column(String(20))
    parent_site_id: Mapped[str | None] = mapped_column(String(50))
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")


class WeatherArea(Base):
    __tablename__ = "tb_weather_area"
    weather_area_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    area_name: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6))
    provider: Mapped[str | None] = mapped_column(String(50))


class SiteWeatherMapping(Base):
    __tablename__ = "tb_site_weather_mapping"
    mapping_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[str] = mapped_column(String(50))
    weather_area_id: Mapped[str] = mapped_column(String(50))
    priority_no: Mapped[int] = mapped_column(Integer, default=1)
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")


class Calendar(Base):
    __tablename__ = "tb_calendar"
    calendar_date: Mapped[date] = mapped_column(Date, primary_key=True)
    day_of_week: Mapped[int] = mapped_column(Integer)
    is_weekend: Mapped[str] = mapped_column(String(1))
    is_holiday: Mapped[str] = mapped_column(String(1))
    holiday_name: Mapped[str | None] = mapped_column(String(100))
    season: Mapped[str | None] = mapped_column(String(20))


class DatasetVersion(Base):
    __tablename__ = "tb_dataset_version"
    dataset_version_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_type: Mapped[str] = mapped_column(String(30))
    base_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    base_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    feature_config_hash: Mapped[str | None] = mapped_column(String(128))
    record_count: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class FeatureDataset(Base):
    __tablename__ = "tb_feature_dataset"
    feature_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(String(80))
    site_id: Mapped[str] = mapped_column(String(50))
    feature_at: Mapped[datetime] = mapped_column(DateTime)
    target_heat_demand: Mapped[float | None] = mapped_column(Numeric(18, 6))
    temp: Mapped[float | None] = mapped_column(Numeric(10, 3))
    humidity: Mapped[float | None] = mapped_column(Numeric(10, 3))
    lag_24h_demand: Mapped[float | None] = mapped_column(Numeric(18, 6))
    lag_168h_demand: Mapped[float | None] = mapped_column(Numeric(18, 6))
    rolling_24h_avg: Mapped[float | None] = mapped_column(Numeric(18, 6))
    feature_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DataSource(Base):
    __tablename__ = "tb_data_source"
    data_source_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(20))
    source_category: Mapped[str] = mapped_column(String(30))
    connection_ref: Mapped[str | None] = mapped_column(String(200))
    connection_info: Mapped[dict | None] = mapped_column(JSONB)
    load_cycle: Mapped[str | None] = mapped_column(String(20))
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    last_loaded_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DataMapping(Base):
    __tablename__ = "tb_data_mapping"
    mapping_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(50))
    mapping_name: Mapped[str] = mapped_column(String(100))
    target_table: Mapped[str] = mapped_column(String(100))
    columns: Mapped[list] = mapped_column(JSONB, default=list)
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class DataQualityRun(Base):
    __tablename__ = "tb_data_quality_run"
    run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(50))
    check_type: Mapped[str] = mapped_column(String(50))
    run_status: Mapped[str] = mapped_column(String(20))
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Feature(Base):
    __tablename__ = "tb_feature"
    feature_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    feature_name: Mapped[str] = mapped_column(String(100))
    feature_group: Mapped[str | None] = mapped_column(String(50))
    feature_type: Mapped[str] = mapped_column(String(20))
    calc_expression: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class FeatureSet(Base):
    __tablename__ = "tb_feature_set"
    feature_set_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    feature_set_name: Mapped[str] = mapped_column(String(100))
    target_domain: Mapped[str] = mapped_column(String(30))
    features: Mapped[list] = mapped_column(JSONB, default=list)
    apply_site_scope: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(500))
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class TrainingConfig(Base):
    __tablename__ = "tb_training_config"
    config_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    config_name: Mapped[str] = mapped_column(String(100))
    feature_set_id: Mapped[str | None] = mapped_column(String(50))
    algorithm: Mapped[str] = mapped_column(String(50))
    train_period_months: Mapped[int | None] = mapped_column(Integer)
    validation_period_months: Mapped[int | None] = mapped_column(Integer)
    hyperparams: Mapped[dict | None] = mapped_column(JSONB)
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class TrainingJob(Base):
    __tablename__ = "tb_training_job"
    job_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    config_id: Mapped[str | None] = mapped_column(String(50))
    pipeline_run_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    site_ids: Mapped[list | None] = mapped_column(JSONB)
    train_start_at: Mapped[date | None] = mapped_column(Date)
    train_end_at: Mapped[date | None] = mapped_column(Date)
    validation_start_at: Mapped[date | None] = mapped_column(Date)
    validation_end_at: Mapped[date | None] = mapped_column(Date)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(80))
    registered_model_name: Mapped[str | None] = mapped_column(String(100))
    registered_model_version: Mapped[str | None] = mapped_column(String(20))
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ModelExperiment(Base):
    __tablename__ = "tb_model_experiment"
    experiment_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(80))
    dataset_version_id: Mapped[str | None] = mapped_column(String(80))
    algorithm: Mapped[str] = mapped_column(String(50))
    parameter_json: Mapped[dict | None] = mapped_column(JSONB)
    metric_json: Mapped[dict | None] = mapped_column(JSONB)
    trained_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(50))


class ModelVersion(Base):
    __tablename__ = "tb_model_version"
    model_version_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100))
    version_no: Mapped[str] = mapped_column(String(20))
    experiment_id: Mapped[str | None] = mapped_column(String(80))
    mlflow_model_uri: Mapped[str | None] = mapped_column(String(500))
    artifact_uri: Mapped[str | None] = mapped_column(String(500))
    model_stage: Mapped[str] = mapped_column(String(20))
    metric_summary_json: Mapped[dict | None] = mapped_column(JSONB)
    registered_at: Mapped[datetime] = mapped_column(DateTime)


class PredictionJob(Base):
    __tablename__ = "tb_prediction_job"
    prediction_job_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    pipeline_run_id: Mapped[str | None] = mapped_column(String(80))
    model_version_id: Mapped[str] = mapped_column(String(80))
    prediction_horizon: Mapped[str] = mapped_column(String(20))
    target_start_at: Mapped[datetime] = mapped_column(DateTime)
    target_end_at: Mapped[datetime] = mapped_column(DateTime)
    site_ids: Mapped[list | None] = mapped_column(JSONB)
    job_status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class HeatDemandPrediction(Base):
    __tablename__ = "tb_heat_demand_prediction"
    prediction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prediction_job_id: Mapped[str] = mapped_column(String(80))
    site_id: Mapped[str] = mapped_column(String(50))
    target_at: Mapped[datetime] = mapped_column(DateTime)
    predicted_demand: Mapped[float] = mapped_column(Numeric(18, 6))
    lower_bound: Mapped[float | None] = mapped_column(Numeric(18, 6))
    upper_bound: Mapped[float | None] = mapped_column(Numeric(18, 6))
    model_version_id: Mapped[str] = mapped_column(String(80))
    feature_set_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)


class PredictionActualMatch(Base):
    __tablename__ = "tb_prediction_actual_match"
    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(BigInteger)
    site_id: Mapped[str] = mapped_column(String(50))
    target_at: Mapped[datetime] = mapped_column(DateTime)
    model_version_id: Mapped[str] = mapped_column(String(80))
    prediction_job_id: Mapped[str | None] = mapped_column(String(80))
    predicted_demand: Mapped[float] = mapped_column(Numeric(18, 6))
    actual_demand: Mapped[float] = mapped_column(Numeric(18, 6))
    error: Mapped[float | None] = mapped_column(Numeric(18, 6))
    abs_error: Mapped[float | None] = mapped_column(Numeric(18, 6))
    squared_error: Mapped[float | None] = mapped_column(Numeric(18, 6))
    ape: Mapped[float | None] = mapped_column(Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class HeatDemandActual(Base):
    __tablename__ = "tb_heat_demand_actual"
    actual_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[str] = mapped_column(String(50))
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    heat_demand: Mapped[float] = mapped_column(Numeric(18, 6))
    supply_temp: Mapped[float | None] = mapped_column(Numeric(10, 3))
    return_temp: Mapped[float | None] = mapped_column(Numeric(10, 3))
    flow_rate: Mapped[float | None] = mapped_column(Numeric(18, 6))
    quality_flag: Mapped[str | None] = mapped_column(String(20))
    source_system: Mapped[str | None] = mapped_column(String(100))
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime)


class WeatherObservation(Base):
    __tablename__ = "tb_weather_observation"
    weather_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    weather_area_id: Mapped[str] = mapped_column(String(50))
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    data_type: Mapped[str] = mapped_column(String(20))
    temperature: Mapped[float | None] = mapped_column(Numeric(10, 3))
    humidity: Mapped[float | None] = mapped_column(Numeric(10, 3))
    wind_speed: Mapped[float | None] = mapped_column(Numeric(10, 3))
    rainfall: Mapped[float | None] = mapped_column(Numeric(10, 3))
    apparent_temp: Mapped[float | None] = mapped_column(Numeric(10, 3))
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime)


class ModelPerformanceMetric(Base):
    __tablename__ = "tb_model_performance_metric"
    metric_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    site_id: Mapped[str] = mapped_column(String(50))
    model_version_id: Mapped[str] = mapped_column(String(80))
    eval_start_at: Mapped[datetime] = mapped_column(DateTime)
    eval_end_at: Mapped[datetime] = mapped_column(DateTime)
    mae: Mapped[float | None] = mapped_column(Numeric(18, 6))
    rmse: Mapped[float | None] = mapped_column(Numeric(18, 6))
    mape: Mapped[float | None] = mapped_column(Numeric(18, 6))
    sample_count: Mapped[int | None] = mapped_column(Integer)
    metric_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, insert_default=utc_now)


class DriftReport(Base):
    __tablename__ = "tb_drift_report"
    drift_report_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    dataset_version_id: Mapped[str | None] = mapped_column(String(80))
    model_version_id: Mapped[str | None] = mapped_column(String(80))
    feature_set_id: Mapped[str | None] = mapped_column(String(50))
    site_id: Mapped[str | None] = mapped_column(String(50))
    base_period: Mapped[str | None] = mapped_column(String(100))
    current_period: Mapped[str | None] = mapped_column(String(100))
    baseline_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    baseline_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    current_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    current_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    drift_type: Mapped[str | None] = mapped_column(String(20))
    drift_status: Mapped[str] = mapped_column(String(20))
    drift_score: Mapped[float | None] = mapped_column(Numeric(10, 6))
    drift_score_json: Mapped[dict | None] = mapped_column(JSONB)
    recommendation: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(20))
    report_uri: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class RetrainingCandidate(Base):
    __tablename__ = "tb_retraining_candidate"
    candidate_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    reason: Mapped[str] = mapped_column(String(500))
    reason_summary: Mapped[str | None] = mapped_column(String(500))
    model_name: Mapped[str | None] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(20))
    model_version_id: Mapped[str | None] = mapped_column(String(80))
    feature_set_id: Mapped[str | None] = mapped_column(String(50))
    site_id: Mapped[str | None] = mapped_column(String(50))
    reason_type: Mapped[str | None] = mapped_column(String(50))
    severity: Mapped[str | None] = mapped_column(String(20))
    risk_level: Mapped[str | None] = mapped_column(String(20))
    drift_report_id: Mapped[str | None] = mapped_column(String(80))
    metric_snapshot_json: Mapped[dict | None] = mapped_column(JSONB)
    source_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PipelineRun(Base):
    __tablename__ = "tb_pipeline_run"
    pipeline_run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(50))
    pipeline_name: Mapped[str | None] = mapped_column(String(100))
    pipeline_type: Mapped[str] = mapped_column(String(30))
    orchestrator: Mapped[str] = mapped_column(String(30))
    orchestrator_run_id: Mapped[str | None] = mapped_column(String(120))
    run_status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    message: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[dict | None] = mapped_column(JSONB)


class CommonCode(Base):
    __tablename__ = "tb_common_code"
    code_group: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    code_name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int | None] = mapped_column(Integer)
    active_yn: Mapped[str] = mapped_column(String(1))
    description: Mapped[str | None] = mapped_column(String(500))


class SystemConfig(Base):
    __tablename__ = "tb_system_config"
    config_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    config_name: Mapped[str | None] = mapped_column(String(200))
    config_value: Mapped[str | None] = mapped_column(Text)
    config_type: Mapped[str | None] = mapped_column(String(20))
    scope: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(500))
    editable_yn: Mapped[str] = mapped_column(String(1), default="Y")
    updated_by: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
