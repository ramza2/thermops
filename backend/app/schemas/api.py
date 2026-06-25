from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# Common
class CodeItem(BaseModel):
    code_group: str
    code: str
    code_name: str


class SiteItem(BaseModel):
    site_id: str
    site_name: str
    site_type: str
    active_yn: str = "Y"


# Data Source
class DataSourceCreate(BaseModel):
    source_name: str
    source_type: str
    data_domain: str
    connection_info: dict[str, Any]
    active_yn: bool = True


class DataSourceUpdate(BaseModel):
    source_name: str | None = None
    source_type: str | None = None
    connection_info: dict[str, Any] | None = None
    active_yn: bool | None = None


# Mapping
class MappingColumn(BaseModel):
    source_column: str
    target_column: str
    transform_rule: str | None = None
    required_yn: bool = False


class MappingCreate(BaseModel):
    source_id: str
    mapping_name: str
    target_table: str
    columns: list[MappingColumn]


class MappingUpdate(BaseModel):
    mapping_name: str | None = None
    target_table: str | None = None
    columns: list[MappingColumn] | None = None


# Feature
class FeatureCreate(BaseModel):
    feature_name: str
    feature_group: str | None = None
    feature_type: str
    calc_expression: str | None = None
    description: str | None = None


class FeatureSetCreate(BaseModel):
    feature_set_name: str
    target_domain: str
    features: list[str]
    apply_site_scope: str = "ALL"
    description: str | None = None


# Training
class TrainingConfigCreate(BaseModel):
    config_name: str
    feature_set_id: str
    algorithm: str
    train_period_months: int = 24
    validation_period_months: int = 3
    hyperparams: dict[str, Any] | None = None


class TrainingJobCreate(BaseModel):
    config_id: str
    site_ids: list[str] | None = None
    train_start_at: date | None = None
    train_end_at: date | None = None
    validation_start_at: date | None = None
    validation_end_at: date | None = None
    register_model_yn: bool = True
    triggered_by: str | None = None


# Prediction
class PredictionJobCreate(BaseModel):
    feature_set_id: str
    site_ids: list[str] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    target_start_at: datetime | None = None
    target_end_at: datetime | None = None
    prediction_horizon: str = "BATCH"
    model_version_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    overwrite_yn: bool = True


class PredictionEvaluateRequest(BaseModel):
    model_version_id: str | None = None
    prediction_job_id: str | None = None
    site_ids: list[str] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


# Model
class ChampionRequest(BaseModel):
    reason: str | None = None
    approved_by: str | None = None


class ModelStatusUpdate(BaseModel):
    model_stage: str


# Pipeline
class PipelineTrigger(BaseModel):
    business_date: str | None = None
    parameters: dict[str, Any] | None = None


# Drift
class DriftCheckCreate(BaseModel):
    model_version_id: str | None = None
    dataset_version_id: str | None = None
