from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.services.connectors.registry import SUPPORTED_SOURCE_TYPES

SUPPORTED_DATA_SOURCE_TYPES = set(SUPPORTED_SOURCE_TYPES)


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

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        key = (v or "").upper()
        if key not in SUPPORTED_DATA_SOURCE_TYPES:
            raise ValueError(f"source_type은 {sorted(SUPPORTED_DATA_SOURCE_TYPES)} 중 하나여야 합니다.")
        return key


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


class FeatureSetLegacyReplaceRequest(BaseModel):
    dry_run: bool = True


class FeatureColumnRoleColumnInput(BaseModel):
    source_column: str
    target_column: str | None = None
    data_type: str | None = None
    cardinality: int | None = None


class FeatureColumnRoleItemInput(BaseModel):
    source_column: str
    target_column: str | None = None
    data_type: str | None = None
    column_role: str
    description: str | None = None


class FeatureColumnRoleInferRequest(BaseModel):
    mapping_id: str | None = None
    columns: list[FeatureColumnRoleColumnInput]
    target_table: str | None = None
    source_table: str | None = None


class FeatureColumnRoleValidateRequest(BaseModel):
    mapping_id: str | None = None
    roles: list[FeatureColumnRoleItemInput]
    mapping_columns: list[FeatureColumnRoleColumnInput] | None = None


class FeatureColumnRoleBulkUpdateRequest(BaseModel):
    mapping_id: str
    roles: list[FeatureColumnRoleItemInput]


class FeatureRecipeValidateRequest(BaseModel):
    mapping_id: str | None = None
    recipe_type: str
    source_columns: list[str]
    entity_keys: list[str] | None = None
    time_key: str | None = None
    target_column: str | None = None
    params: dict[str, Any] | None = None
    output_feature_name: str | None = None
    cardinality: int | None = None


class FeatureRecipePreviewRequest(FeatureRecipeValidateRequest):
    sample_size: int = 100
    start_at: str | None = None
    end_at: str | None = None


class FeatureRecipeCreateRequest(FeatureRecipeValidateRequest):
    display_name: str | None = None
    description: str | None = None
    domain: str | None = None
    task_type: str | None = None
    owner: str | None = None
    output_data_type: str | None = None
    unit: str | None = None
    null_handling: str | None = None
    leakage_policy: str | None = None


class FeatureRecipeUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    domain: str | None = None
    task_type: str | None = None
    owner: str | None = None
    mapping_id: str | None = None
    source_columns: list[str] | None = None
    entity_keys: list[str] | None = None
    time_key: str | None = None
    target_column: str | None = None
    params: dict[str, Any] | None = None
    output_feature_name: str | None = None
    output_data_type: str | None = None
    unit: str | None = None
    null_handling: str | None = None
    leakage_policy: str | None = None


class FeatureRecipePreviewSavedRequest(BaseModel):
    sample_size: int = 100


class FeatureRecipeComparePreviewBuildRequest(BaseModel):
    dataset_version_id: str | None = None
    feature_set_id: str | None = None
    sample_size: int = Field(default=20, ge=1, le=100)


class FeatureSetAddRecipeFeatureRequest(BaseModel):
    recipe_id: str
    feature_name: str | None = None


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


class SystemConfigUpdate(BaseModel):
    config_value: str


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


class PipelineRunStatusUpdate(BaseModel):
    status: str
    step_name: str | None = None
    message: str | None = None
    result_summary: dict[str, Any] | None = None


# Drift
class DriftCheckCreate(BaseModel):
    model_version_id: str | None = None
    feature_set_id: str | None = None
    dataset_version_id: str | None = None
    site_ids: list[str] | None = None
    baseline_start_at: datetime | None = None
    baseline_end_at: datetime | None = None
    current_start_at: datetime | None = None
    current_end_at: datetime | None = None
    force_candidate: bool = False


class FeatureQualityRunCreate(BaseModel):
    feature_set_id: str
    dataset_version_id: str | None = None
