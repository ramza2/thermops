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


class StandardDatasetColumnInput(BaseModel):
    column_id: str | None = None
    column_name: str
    display_name: str | None = None
    data_type: str = "STRING"
    data_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    required: bool = False
    primary_key: bool = False
    unique: bool = False
    default_column_role: str | None = None
    role_required: bool = False
    description: str | None = None
    example_value: str | None = None
    sort_order: int | None = None


class StandardDatasetTypeCreate(BaseModel):
    dataset_type_id: str | None = None
    dataset_type_code: str
    dataset_type_name: str
    description: str | None = None
    domain: str | None = None
    category: str | None = None
    target_table: str
    status: str = "DRAFT"
    owner: str | None = None
    physical_table_yn: bool = True
    managed_table: bool = True
    build_supported: bool = False
    recipe_supported: bool = False
    mapping_supported: bool = False
    columns: list[StandardDatasetColumnInput] = []


class CreatePhysicalTableRequest(BaseModel):
    confirm: bool = True


class StandardDatasetTypeUpdate(BaseModel):
    dataset_type_name: str | None = None
    description: str | None = None
    domain: str | None = None
    category: str | None = None
    target_table: str | None = None
    owner: str | None = None
    build_supported: bool | None = None
    recipe_supported: bool | None = None
    mapping_supported: bool | None = None
    columns: list[StandardDatasetColumnInput] | None = None


class ValidateTargetTableRequest(BaseModel):
    target_table: str


class PipelineDefinitionCreate(BaseModel):
    template_id: str
    pipeline_name: str
    description: str | None = None
    node_config: dict[str, dict[str, Any]] = {}
    runtime_params: dict[str, Any] | None = None
    schedule_config: dict[str, Any] | None = None
    created_by: str | None = None


class PipelineDefinitionUpdate(BaseModel):
    pipeline_name: str | None = None
    description: str | None = None
    node_config: dict[str, dict[str, Any]] | None = None
    runtime_params: dict[str, Any] | None = None
    schedule_config: dict[str, Any] | None = None
    change_summary: str | None = None


class PipelineDefinitionValidateRequest(BaseModel):
    template_id: str | None = None
    node_config: dict[str, dict[str, Any]] | None = None


class PipelineDefinitionRunRequest(BaseModel):
    requested_by: str | None = None
    run_label: str | None = None
    runtime_params_override: dict[str, Any] | None = None
    dry_run: bool = False


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
