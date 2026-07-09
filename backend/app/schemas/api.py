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
    dataset_category: str = "CUSTOM"
    category: str | None = None
    business_domain: str | None = None
    tags: list[str] | str | None = None
    domain: str | None = None
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
    dataset_category: str | None = None
    category: str | None = None
    business_domain: str | None = None
    tags: list[str] | str | None = None
    domain: str | None = None
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
    dataset_version_id: str | None = None


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
    dataset_version_id: str | None = None
    entity_id: str | None = None
    forecast_provider_enabled: bool = False
    forecast_base_date: str | None = None
    forecast_base_time: str | None = None
    forecast_source_operation_id: str | None = None
    forecast_cache_policy: str = "USE_CACHE"
    weather_input_required: bool = False


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


class DatasetVersionArchiveRequest(BaseModel):
    reason: str | None = None


class DatasetVersionSelectionPreviewRequest(BaseModel):
    feature_set_id: str
    purpose: str = "TRAINING"
    explicit_dataset_version_id: str | None = None


class DatasetVersionCleanupPreviewRequest(BaseModel):
    feature_set_id: str | None = None
    roles: list[str] | None = None
    older_than_days: int | None = None
    dry_run: bool = True


class ApiConnectorOperationCreate(BaseModel):
    data_source_id: str
    operation_name: str
    operation_description: str | None = None
    http_method: str = "GET"
    endpoint_path: str
    request_content_type: str = "QUERY"
    response_format: str = "JSON"
    response_item_path: str | None = None
    result_array_mode: str = "AUTO"
    target_table: str | None = None
    standard_dataset_id: str | None = None
    metadata_json: dict[str, Any] | None = None


class ApiConnectorOperationUpdate(BaseModel):
    operation_name: str | None = None
    operation_description: str | None = None
    http_method: str | None = None
    endpoint_path: str | None = None
    request_content_type: str | None = None
    response_format: str | None = None
    response_item_path: str | None = None
    result_array_mode: str | None = None
    target_table: str | None = None
    standard_dataset_id: str | None = None
    active_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class ApiConnectorParamItem(BaseModel):
    param_id: str | None = None
    param_name: str
    display_name: str | None = None
    param_location: str = "QUERY"
    param_type: str = "STRING"
    required_yn: bool = False
    default_value: str | None = None
    example_value: str | None = None
    allowed_values_json: list[Any] | None = None
    value_source: str = "USER_INPUT"
    secret_key_ref: str | None = None
    encode_yn: bool = True
    sort_order: int = 0
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class ApiConnectorParamsReplace(BaseModel):
    params: list[ApiConnectorParamItem]


class ApiConnectorCredentialUpsert(BaseModel):
    credential_name: str | None = "default"
    credential_type: str = "API_KEY"
    key_location: str = "QUERY"
    key_name: str = "serviceKey"
    secret_value: str | None = None
    encoding_policy: str = "STORE_DECODED_ENCODE_ON_CALL"
    active_yn: bool = True


class ApiConnectorPaginationUpsert(BaseModel):
    pagination_type: str = "NONE"
    page_param_name: str | None = None
    size_param_name: str | None = None
    page_start: int = 1
    page_size: int = 100
    max_pages: int = 1
    total_count_path: str | None = None
    next_link_path: str | None = None
    stop_condition: str = "EMPTY_ITEMS"
    active_yn: bool = True


class ApiConnectorRuntimeParams(BaseModel):
    runtime_params: dict[str, Any] | None = None


class ApiConnectorLoadRunRequest(BaseModel):
    runtime_params: dict[str, Any] | None = None
    dry_run: bool = False


class ApiConnectorTransformConfigUpsert(BaseModel):
    transform_type: str = "NONE"
    transform_name: str | None = None
    source_system: str = "HEAT_DEMAND_API"
    external_code_group: str = "NODE"
    external_code_field: str = "ND_ID"
    external_name_field: str = "ND_KORN_NM"
    date_field: str = "BAS_YMD"
    date_format: str = "YYYYMMDD"
    hour_column_prefix: str = "HTDND_AMNT_"
    hour_column_suffix: str = "HR"
    hour_start: int = 1
    hour_end: int = 24
    value_output_field: str = "heat_demand"
    measured_at_output_field: str = "measured_at"
    entity_id_output_field: str = "entity_id"
    entity_code_output_field: str = "site_id"
    external_code_output_field: str = "external_node_id"
    external_name_output_field: str = "external_node_name"
    timestamp_policy: str = "HOUR_LABEL_AS_END"
    hour_24_policy: str = "NEXT_DAY_00"
    unmapped_policy: str = "FAIL_LOAD"
    null_value_policy: str = "SKIP_NULL"
    numeric_parse_policy: str = "ALLOW_COMMA"
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None
    station_code_field: str = "stnId"
    observed_at_field: str = "tm"
    value_field_mappings_json: dict[str, Any] | None = None
    special_day_name_field: str = "dateName"
    special_day_type_field: str | None = None
    default_special_day_type: str = "PUBLIC_HOLIDAY"
    public_holiday_field: str = "isHoliday"
    calendar_mode: str = "FULL_CALENDAR_WITH_OVERLAY"
    calendar_year: int | None = None
    calendar_month: int | None = None
    hour_generation_yn: bool = False
    station_unmapped_policy: str = "WARN_ONLY"
    store_raw_json: bool = True


class ApiConnectorTransformPreviewRequest(BaseModel):
    raw_items: list[dict[str, Any]] | None = None
    runtime_params: dict[str, Any] | None = None


class ApiConnectorWritePolicyUpsert(BaseModel):
    write_mode: str = "INSERT_ONLY"
    conflict_key_columns_json: list[str] | None = None
    update_columns_json: list[str] | None = None
    exclude_update_columns_json: list[str] | None = None
    compare_columns_json: list[str] | None = None
    null_update_policy: str = "KEEP_EXISTING"
    duplicate_within_batch_policy: str = "KEEP_LAST"
    no_conflict_key_policy: str = "WARN_INSERT_ONLY"
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class PredictionEntityCreate(BaseModel):
    entity_code: str
    entity_name: str
    entity_type: str = "SITE"
    business_domain: str | None = None
    description: str | None = None
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class PredictionEntityUpdate(BaseModel):
    entity_code: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    business_domain: str | None = None
    description: str | None = None
    active_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class PredictionEntityLocationCreate(BaseModel):
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_source: str = "MANUAL"
    valid_from: date | None = None
    valid_to: date | None = None
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class PredictionEntityLocationUpdate(BaseModel):
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_source: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    active_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class WeatherForecastGridUpsert(BaseModel):
    grid_system: str = "KMA_DFS"
    nx: int
    ny: int
    grid_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class WeatherObservationStationUpsert(BaseModel):
    station_code: str
    station_name: str
    station_type: str = "ASOS"
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class WeatherMappingCreate(BaseModel):
    forecast_grid_id: str | None = None
    station_id: str | None = None
    mapping_type: str = "BOTH"
    mapping_method: str = "MANUAL"
    distance_km: float | None = None
    priority: int = 1
    valid_from: date | None = None
    valid_to: date | None = None
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class WeatherMappingUpdate(BaseModel):
    forecast_grid_id: str | None = None
    station_id: str | None = None
    mapping_type: str | None = None
    mapping_method: str | None = None
    distance_km: float | None = None
    priority: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    active_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class LatLonToGridRequest(BaseModel):
    latitude: float
    longitude: float


class ExternalCodeMappingCreate(BaseModel):
    source_system: str
    source_operation_id: str | None = None
    external_code_group: str
    external_code: str
    external_code_name: str | None = None
    external_code_description: str | None = None
    target_type: str
    target_id: str
    target_display_name: str | None = None
    mapping_status: str = "ACTIVE"
    mapping_method: str = "MANUAL"
    confidence_score: float | None = None
    priority: int = 1
    valid_from: date | None = None
    valid_to: date | None = None
    active_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class ExternalCodeMappingUpdate(BaseModel):
    source_system: str | None = None
    source_operation_id: str | None = None
    external_code_group: str | None = None
    external_code: str | None = None
    external_code_name: str | None = None
    external_code_description: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    target_display_name: str | None = None
    mapping_status: str | None = None
    mapping_method: str | None = None
    confidence_score: float | None = None
    priority: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    active_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class ExternalCodeResolveRequest(BaseModel):
    source_system: str
    external_code_group: str
    external_code: str
    target_type: str | None = None
    at_date: date | None = None


class ExternalCodeResolveBatchRequest(BaseModel):
    items: list[ExternalCodeResolveRequest]


class UnmappedAssignRequest(BaseModel):
    target_type: str
    target_id: str
    target_display_name: str | None = None
    mapping_method: str = "MANUAL"
    priority: int = 1
    valid_from: date | None = None
    valid_to: date | None = None
    external_code_name: str | None = None
    metadata_json: dict[str, Any] | None = None


class UnmappedIgnoreRequest(BaseModel):
    ignored_reason: str | None = None


class ArchiveMappingRequest(BaseModel):
    archived_reason: str | None = None


# Forecast Provider (R10-S5)
class ForecastProviderConfigUpdate(BaseModel):
    provider_name: str | None = None
    provider_type: str | None = None
    source_operation_id: str | None = None
    default_num_of_rows: int | None = None
    default_data_type: str | None = None
    base_time_policy: str | None = None
    delay_minutes: int | None = None
    active_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class ForecastResolveBaseTimeRequest(BaseModel):
    base_date: str | None = None
    base_time: str | None = None


class ForecastPreviewInputRequest(BaseModel):
    entity_id: str
    base_date: str | None = None
    base_time: str | None = None
    cache_policy: str = "REFRESH"
    target_start_at: datetime | None = None
    target_end_at: datetime | None = None
    source_operation_id: str | None = None


class ForecastRequestPreviewRequest(BaseModel):
    entity_id: str
    base_date: str | None = None
    base_time: str | None = None
    source_operation_id: str | None = None


class ForecastTestCallRequest(BaseModel):
    entity_id: str
    base_date: str | None = None
    base_time: str | None = None
    cache_policy: str = "REFRESH"
    source_operation_id: str | None = None


# Data Load Scheduler (R10-S6)
class DataLoadScheduleCreate(BaseModel):
    schedule_name: str
    operation_id: str
    schedule_description: str | None = None
    schedule_type: str = "MANUAL"
    cron_expression: str | None = None
    timezone: str = "Asia/Seoul"
    start_at: datetime | None = None
    end_at: datetime | None = None
    active_yn: bool = True
    run_policy: str = "LOAD_RUN"
    load_window_type: str = "NONE"
    window_offset_minutes: int | None = None
    runtime_params_template: dict[str, Any] | None = None
    max_pages_override: int | None = None
    retry_enabled_yn: bool = False
    max_retry_count: int = 0
    retry_interval_minutes: int = 10
    on_failure_policy: str = "STOP"
    metadata_json: dict[str, Any] | None = None


class DataLoadScheduleUpdate(BaseModel):
    schedule_name: str | None = None
    schedule_description: str | None = None
    operation_id: str | None = None
    schedule_type: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    active_yn: bool | None = None
    run_policy: str | None = None
    load_window_type: str | None = None
    window_offset_minutes: int | None = None
    runtime_params_template: dict[str, Any] | None = None
    max_pages_override: int | None = None
    retry_enabled_yn: bool | None = None
    max_retry_count: int | None = None
    retry_interval_minutes: int | None = None
    on_failure_policy: str | None = None
    metadata_json: dict[str, Any] | None = None


class DataLoadSchedulePreviewNextRunRequest(BaseModel):
    schedule_id: str | None = None
    schedule_type: str | None = None
    timezone: str | None = None
    start_at: datetime | None = None


class DataLoadScheduleRenderParamsRequest(BaseModel):
    schedule_id: str | None = None
    runtime_params_template: dict[str, Any] | None = None
    load_window_type: str | None = None
    window_offset_minutes: int | None = None
    manual_params: dict[str, Any] | None = None


class DataLoadScheduleRunNowRequest(BaseModel):
    manual_params: dict[str, Any] | None = None


class DataLoadScheduleArchiveRequest(BaseModel):
    archived_reason: str | None = None


# Notifications (R10-S9)
class NotificationChannelCreate(BaseModel):
    channel_name: str
    channel_type: str = "MOCK"
    enabled_yn: bool = True
    config_json: dict[str, Any] | None = None
    secret_value: str | None = None
    mask_policy_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None


class NotificationChannelUpdate(BaseModel):
    channel_name: str | None = None
    channel_type: str | None = None
    enabled_yn: bool | None = None
    config_json: dict[str, Any] | None = None
    secret_value: str | None = None
    mask_policy_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None


class NotificationRecipientCreate(BaseModel):
    recipient_name: str
    recipient_type: str = "CUSTOM"
    address: str | None = None
    enabled_yn: bool = True
    metadata_json: dict[str, Any] | None = None


class NotificationRecipientUpdate(BaseModel):
    recipient_name: str | None = None
    recipient_type: str | None = None
    address: str | None = None
    enabled_yn: bool | None = None
    metadata_json: dict[str, Any] | None = None


class AlertRuleCreate(BaseModel):
    rule_name: str
    rule_description: str | None = None
    enabled_yn: bool = True
    event_source: str
    event_type: str
    min_severity: str = "WARNING"
    condition_json: dict[str, Any] | None = None
    dedup_window_minutes: int = 30
    suppress_yn: bool = False
    create_incident_yn: bool = True
    channel_ids_json: list[str] | None = None
    recipient_ids_json: list[str] | None = None
    message_template: str | None = None
    metadata_json: dict[str, Any] | None = None


class AlertRuleUpdate(BaseModel):
    rule_name: str | None = None
    rule_description: str | None = None
    enabled_yn: bool | None = None
    event_source: str | None = None
    event_type: str | None = None
    min_severity: str | None = None
    condition_json: dict[str, Any] | None = None
    dedup_window_minutes: int | None = None
    suppress_yn: bool | None = None
    create_incident_yn: bool | None = None
    channel_ids_json: list[str] | None = None
    recipient_ids_json: list[str] | None = None
    message_template: str | None = None
    metadata_json: dict[str, Any] | None = None


class AlertRuleTestMatchRequest(BaseModel):
    severity: str = "ERROR"
    event_payload_json: dict[str, Any] | None = None


class NotificationEventTestRequest(BaseModel):
    event_source: str
    event_type: str
    severity: str = "WARNING"
    title: str
    message: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    correlation_id: str | None = None
    dedup_key: str | None = None
    event_payload_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None


class IncidentAcknowledgeRequest(BaseModel):
    acknowledged_by: str | None = None


class IncidentResolveRequest(BaseModel):
    resolved_by: str | None = None
    resolution_note: str | None = None
