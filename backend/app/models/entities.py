from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text
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
    feature_set_id: Mapped[str | None] = mapped_column(String(50))
    base_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    base_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    feature_config_hash: Mapped[str | None] = mapped_column(String(128))
    record_count: Mapped[int | None] = mapped_column(Integer)
    feature_count: Mapped[int | None] = mapped_column(Integer)
    dataset_version_role: Mapped[str] = mapped_column(String(30), default="CANDIDATE")
    dataset_version_status: Mapped[str] = mapped_column(String(30), default="BUILD_SUCCESS")
    build_scope: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_training_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    is_serving_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[float | None] = mapped_column(Numeric(10, 4))
    coverage_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6))
    null_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6))
    build_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    build_finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_reason: Mapped[str | None] = mapped_column(Text)
    selection_policy_note: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
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


class FeatureLineage(Base):
    __tablename__ = "tb_feature_lineage"
    lineage_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(String(80))
    feature_build_job_id: Mapped[str | None] = mapped_column(String(80))
    feature_set_id: Mapped[str] = mapped_column(String(50))
    feature_name: Mapped[str] = mapped_column(String(100))
    registry_version: Mapped[str] = mapped_column(String(20), default="1.0")
    calc_method: Mapped[str] = mapped_column(String(20), default="CODE")
    calc_expression: Mapped[str | None] = mapped_column(Text)
    source_tables: Mapped[list | None] = mapped_column(JSONB)
    source_columns: Mapped[list | None] = mapped_column(JSONB)
    partition_keys: Mapped[list | None] = mapped_column(JSONB)
    time_key: Mapped[str | None] = mapped_column(String(50))
    lookback_hours: Mapped[int | None] = mapped_column(Integer)
    requires_shift: Mapped[bool | None] = mapped_column(Boolean)
    leakage_safe: Mapped[bool | None] = mapped_column(Boolean)
    build_start_at: Mapped[datetime | None] = mapped_column(DateTime)
    build_end_at: Mapped[datetime | None] = mapped_column(DateTime)
    site_filter: Mapped[str | None] = mapped_column(String(50))
    lineage_json: Mapped[dict | None] = mapped_column(JSONB)
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


class ApiConnectorOperation(Base):
    __tablename__ = "tb_api_connector_operation"
    operation_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    data_source_id: Mapped[str] = mapped_column(String(50))
    operation_name: Mapped[str] = mapped_column(String(200))
    operation_description: Mapped[str | None] = mapped_column(Text)
    http_method: Mapped[str] = mapped_column(String(10), default="GET")
    endpoint_path: Mapped[str] = mapped_column(Text)
    full_url_preview: Mapped[str | None] = mapped_column(Text)
    request_content_type: Mapped[str] = mapped_column(String(50), default="QUERY")
    response_format: Mapped[str] = mapped_column(String(20), default="JSON")
    response_item_path: Mapped[str | None] = mapped_column(Text)
    result_array_mode: Mapped[str] = mapped_column(String(30), default="AUTO")
    target_table: Mapped[str | None] = mapped_column(String(100))
    standard_dataset_id: Mapped[str | None] = mapped_column(String(50))
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class ApiConnectorParam(Base):
    __tablename__ = "tb_api_connector_param"
    param_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50))
    param_name: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str | None] = mapped_column(String(200))
    param_location: Mapped[str] = mapped_column(String(20), default="QUERY")
    param_type: Mapped[str] = mapped_column(String(30), default="STRING")
    required_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[str | None] = mapped_column(Text)
    example_value: Mapped[str | None] = mapped_column(Text)
    allowed_values_json: Mapped[Any | None] = mapped_column(JSONB)
    value_source: Mapped[str] = mapped_column(String(30), default="USER_INPUT")
    secret_key_ref: Mapped[str | None] = mapped_column(String(100))
    encode_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class ApiConnectorCredential(Base):
    __tablename__ = "tb_api_connector_credential"
    credential_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    data_source_id: Mapped[str] = mapped_column(String(50))
    credential_name: Mapped[str] = mapped_column(String(200), default="default")
    credential_type: Mapped[str] = mapped_column(String(30), default="API_KEY")
    key_location: Mapped[str] = mapped_column(String(20), default="QUERY")
    key_name: Mapped[str] = mapped_column(String(100), default="serviceKey")
    secret_value_encrypted: Mapped[str | None] = mapped_column(Text)
    secret_value_masked: Mapped[str | None] = mapped_column(String(200))
    encoding_policy: Mapped[str] = mapped_column(String(30), default="STORE_DECODED_ENCODE_ON_CALL")
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class ApiConnectorPagination(Base):
    __tablename__ = "tb_api_connector_pagination"
    pagination_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50), unique=True)
    pagination_type: Mapped[str] = mapped_column(String(30), default="NONE")
    page_param_name: Mapped[str | None] = mapped_column(String(100))
    size_param_name: Mapped[str | None] = mapped_column(String(100))
    page_start: Mapped[int] = mapped_column(Integer, default=1)
    page_size: Mapped[int] = mapped_column(Integer, default=100)
    max_pages: Mapped[int] = mapped_column(Integer, default=1)
    total_count_path: Mapped[str | None] = mapped_column(Text)
    next_link_path: Mapped[str | None] = mapped_column(Text)
    stop_condition: Mapped[str] = mapped_column(String(50), default="EMPTY_ITEMS")
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiConnectorCallLog(Base):
    __tablename__ = "tb_api_connector_call_log"
    call_log_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50))
    data_source_id: Mapped[str] = mapped_column(String(50))
    called_at: Mapped[datetime] = mapped_column(DateTime)
    called_by: Mapped[str | None] = mapped_column(String(100))
    request_url_masked: Mapped[str | None] = mapped_column(Text)
    request_params_masked: Mapped[dict | None] = mapped_column(JSONB)
    http_status: Mapped[int | None] = mapped_column(Integer)
    success_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    response_format: Mapped[str | None] = mapped_column(String(20))
    response_item_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_response_snapshot_id: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class ApiConnectorResponseSnapshot(Base):
    __tablename__ = "tb_api_connector_response_snapshot"
    snapshot_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50))
    call_log_id: Mapped[str | None] = mapped_column(String(50))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    response_format: Mapped[str] = mapped_column(String(20), default="JSON")
    raw_response_text: Mapped[str | None] = mapped_column(Text)
    normalized_items_json: Mapped[Any | None] = mapped_column(JSONB)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    sample_only_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class ApiConnectorTransformConfig(Base):
    __tablename__ = "tb_api_connector_transform_config"
    transform_config_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50), unique=True)
    transform_type: Mapped[str] = mapped_column(String(50), default="NONE")
    transform_name: Mapped[str | None] = mapped_column(String(200))
    source_system: Mapped[str] = mapped_column(String(100), default="HEAT_DEMAND_API")
    external_code_group: Mapped[str] = mapped_column(String(100), default="NODE")
    external_code_field: Mapped[str] = mapped_column(String(100), default="ND_ID")
    external_name_field: Mapped[str] = mapped_column(String(100), default="ND_KORN_NM")
    date_field: Mapped[str] = mapped_column(String(100), default="BAS_YMD")
    date_format: Mapped[str] = mapped_column(String(50), default="YYYYMMDD")
    hour_column_prefix: Mapped[str] = mapped_column(String(100), default="HTDND_AMNT_")
    hour_column_suffix: Mapped[str] = mapped_column(String(50), default="HR")
    hour_start: Mapped[int] = mapped_column(Integer, default=1)
    hour_end: Mapped[int] = mapped_column(Integer, default=24)
    value_output_field: Mapped[str] = mapped_column(String(100), default="heat_demand")
    measured_at_output_field: Mapped[str] = mapped_column(String(100), default="measured_at")
    entity_id_output_field: Mapped[str] = mapped_column(String(100), default="entity_id")
    entity_code_output_field: Mapped[str] = mapped_column(String(100), default="site_id")
    external_code_output_field: Mapped[str] = mapped_column(String(100), default="external_node_id")
    external_name_output_field: Mapped[str] = mapped_column(String(100), default="external_node_name")
    timestamp_policy: Mapped[str] = mapped_column(String(50), default="HOUR_LABEL_AS_END")
    hour_24_policy: Mapped[str] = mapped_column(String(50), default="NEXT_DAY_00")
    unmapped_policy: Mapped[str] = mapped_column(String(50), default="FAIL_LOAD")
    null_value_policy: Mapped[str] = mapped_column(String(50), default="SKIP_NULL")
    numeric_parse_policy: Mapped[str] = mapped_column(String(50), default="ALLOW_COMMA")
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    station_code_field: Mapped[str] = mapped_column(String(100), default="stnId")
    observed_at_field: Mapped[str] = mapped_column(String(100), default="tm")
    value_field_mappings_json: Mapped[Any | None] = mapped_column(JSONB)
    special_day_name_field: Mapped[str] = mapped_column(String(100), default="dateName")
    special_day_type_field: Mapped[str | None] = mapped_column(String(100))
    default_special_day_type: Mapped[str] = mapped_column(String(50), default="PUBLIC_HOLIDAY")
    public_holiday_field: Mapped[str] = mapped_column(String(100), default="isHoliday")
    calendar_mode: Mapped[str] = mapped_column(String(50), default="FULL_CALENDAR_WITH_OVERLAY")
    calendar_year: Mapped[int | None] = mapped_column(Integer)
    calendar_month: Mapped[int | None] = mapped_column(Integer)
    hour_generation_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    station_unmapped_policy: Mapped[str] = mapped_column(String(50), default="WARN_ONLY")
    store_raw_json: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiConnectorLoadRun(Base):
    __tablename__ = "tb_api_connector_load_run"
    load_run_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50))
    data_source_id: Mapped[str] = mapped_column(String(50))
    target_table: Mapped[str | None] = mapped_column(String(100))
    standard_dataset_id: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    run_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    request_params_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    request_params_masked: Mapped[dict | None] = mapped_column(JSONB)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_snapshot_id: Mapped[str | None] = mapped_column(String(50))
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)


class ApiConnectorWritePolicy(Base):
    __tablename__ = "tb_api_connector_write_policy"
    write_policy_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(50))
    target_table: Mapped[str] = mapped_column(String(100))
    write_mode: Mapped[str] = mapped_column(String(30), default="INSERT_ONLY")
    conflict_key_columns_json: Mapped[Any | None] = mapped_column(JSONB)
    update_columns_json: Mapped[Any | None] = mapped_column(JSONB)
    exclude_update_columns_json: Mapped[Any | None] = mapped_column(JSONB)
    compare_columns_json: Mapped[Any | None] = mapped_column(JSONB)
    null_update_policy: Mapped[str] = mapped_column(String(30), default="KEEP_EXISTING")
    duplicate_within_batch_policy: Mapped[str] = mapped_column(String(30), default="KEEP_LAST")
    no_conflict_key_policy: Mapped[str] = mapped_column(String(30), default="WARN_INSERT_ONLY")
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class ApiConnectorLoadDedupSummary(Base):
    __tablename__ = "tb_api_connector_load_dedup_summary"
    summary_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    load_run_id: Mapped[str | None] = mapped_column(String(50))
    schedule_run_id: Mapped[str | None] = mapped_column(String(50))
    operation_id: Mapped[str] = mapped_column(String(50))
    target_table: Mapped[str | None] = mapped_column(String(100))
    write_mode: Mapped[str] = mapped_column(String(30), default="INSERT_ONLY")
    input_row_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_input_row_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_within_batch_count: Mapped[int] = mapped_column(Integer, default=0)
    existing_match_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_key_columns_json: Mapped[Any | None] = mapped_column(JSONB)
    sample_conflicts_json: Mapped[Any | None] = mapped_column(JSONB)
    warnings_json: Mapped[Any | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


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


class FeatureColumnRole(Base):
    __tablename__ = "tb_feature_column_role"
    role_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    mapping_id: Mapped[str | None] = mapped_column(String(50))
    data_source_id: Mapped[str | None] = mapped_column(String(50))
    source_table: Mapped[str | None] = mapped_column(String(100))
    target_table: Mapped[str | None] = mapped_column(String(100))
    source_column: Mapped[str] = mapped_column(String(100))
    target_column: Mapped[str | None] = mapped_column(String(100))
    data_type: Mapped[str | None] = mapped_column(String(50))
    column_role: Mapped[str] = mapped_column(String(50))
    inferred_role: Mapped[str | None] = mapped_column(String(50))
    inference_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    role_source: Mapped[str] = mapped_column(String(20), default="MANUAL")
    description: Mapped[str | None] = mapped_column(Text)
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class StandardDatasetType(Base):
    __tablename__ = "tb_standard_dataset_type"
    dataset_type_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    dataset_type_code: Mapped[str] = mapped_column(String(80))
    dataset_type_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str | None] = mapped_column(String(80))
    business_domain: Mapped[str | None] = mapped_column(String(100))
    tags_json: Mapped[Any | None] = mapped_column(JSONB)
    target_table: Mapped[str] = mapped_column(String(120))
    physical_table_yn: Mapped[str] = mapped_column(String(1), default="Y")
    physical_table_exists_yn: Mapped[str] = mapped_column(String(1), default="Y")
    physical_table_schema: Mapped[str] = mapped_column(String(63), default="public")
    managed_table_yn: Mapped[str] = mapped_column(String(1), default="N")
    table_create_status: Mapped[str] = mapped_column(String(30), default="NOT_CREATED")
    table_create_sql_preview: Mapped[str | None] = mapped_column(Text)
    table_create_error: Mapped[str | None] = mapped_column(Text)
    physical_table_created_at: Mapped[datetime | None] = mapped_column(DateTime)
    physical_table_created_by: Mapped[str | None] = mapped_column(String(100))
    build_supported_yn: Mapped[str] = mapped_column(String(1), default="N")
    recipe_supported_yn: Mapped[str] = mapped_column(String(1), default="N")
    mapping_supported_yn: Mapped[str] = mapped_column(String(1), default="Y")
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    owner: Mapped[str | None] = mapped_column(String(100))
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archive_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class StandardDatasetColumn(Base):
    __tablename__ = "tb_standard_dataset_column"
    column_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    dataset_type_id: Mapped[str] = mapped_column(String(50))
    column_name: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str | None] = mapped_column(String(200))
    data_type: Mapped[str] = mapped_column(String(80))
    data_length: Mapped[int | None] = mapped_column(Integer)
    numeric_precision: Mapped[int | None] = mapped_column(Integer)
    numeric_scale: Mapped[int | None] = mapped_column(Integer)
    nullable_yn: Mapped[str] = mapped_column(String(1), default="Y")
    required_yn: Mapped[str] = mapped_column(String(1), default="N")
    primary_key_yn: Mapped[str] = mapped_column(String(1), default="N")
    unique_yn: Mapped[str] = mapped_column(String(1), default="N")
    default_column_role: Mapped[str | None] = mapped_column(String(50))
    role_required_yn: Mapped[str] = mapped_column(String(1), default="N")
    description: Mapped[str | None] = mapped_column(Text)
    example_value: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class StandardDatasetTableCreateLog(Base):
    __tablename__ = "tb_standard_dataset_table_create_log"
    log_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    dataset_type_id: Mapped[str] = mapped_column(String(50))
    action_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    sql_preview: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class FeatureRecipe(Base):
    __tablename__ = "tb_feature_recipe"
    recipe_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    feature_name: Mapped[str | None] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(50))
    task_type: Mapped[str | None] = mapped_column(String(50))
    calc_mode: Mapped[str] = mapped_column(String(20), default="TEMPLATE")
    recipe_type: Mapped[str] = mapped_column(String(50))
    mapping_id: Mapped[str | None] = mapped_column(String(50))
    data_source_id: Mapped[str | None] = mapped_column(String(50))
    source_table: Mapped[str | None] = mapped_column(String(100))
    target_table: Mapped[str | None] = mapped_column(String(100))
    source_columns: Mapped[list] = mapped_column(JSONB, default=list)
    entity_keys: Mapped[list | None] = mapped_column(JSONB)
    time_key: Mapped[str | None] = mapped_column(String(100))
    target_column: Mapped[str | None] = mapped_column(String(100))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_feature_names: Mapped[list | None] = mapped_column(JSONB)
    output_data_type: Mapped[str | None] = mapped_column(String(50))
    unit: Mapped[str | None] = mapped_column(String(50))
    null_handling: Mapped[str | None] = mapped_column(String(50))
    leakage_policy: Mapped[str | None] = mapped_column(String(50))
    validation_summary: Mapped[dict | None] = mapped_column(JSONB)
    preview_summary: Mapped[dict | None] = mapped_column(JSONB)
    lineage_preview: Mapped[dict | None] = mapped_column(JSONB)
    quality_preview: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, default=1)
    owner: Mapped[str | None] = mapped_column(String(100))
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class FeatureRecipeVersion(Base):
    __tablename__ = "tb_feature_recipe_version"
    version_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    recipe_id: Mapped[str] = mapped_column(String(50))
    version_no: Mapped[int] = mapped_column(Integer)
    recipe_snapshot: Mapped[dict] = mapped_column(JSONB)
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


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


class ForecastProviderConfig(Base):
    __tablename__ = "tb_forecast_provider_config"
    provider_config_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(200))
    provider_type: Mapped[str] = mapped_column(String(50), default="KMA_SHORT_FORECAST")
    source_operation_id: Mapped[str | None] = mapped_column(String(50))
    default_num_of_rows: Mapped[int] = mapped_column(Integer, default=1000)
    default_data_type: Mapped[str] = mapped_column(String(20), default="JSON")
    base_time_policy: Mapped[str] = mapped_column(String(50), default="LATEST_AVAILABLE")
    delay_minutes: Mapped[int] = mapped_column(Integer, default=60)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class ForecastInputSnapshot(Base):
    __tablename__ = "tb_forecast_input_snapshot"
    snapshot_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    prediction_job_id: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(50))
    nx: Mapped[int] = mapped_column(Integer)
    ny: Mapped[int] = mapped_column(Integer)
    source_system: Mapped[str] = mapped_column(String(100), default="KMA_SHORT_FORECAST_API")
    source_operation_id: Mapped[str | None] = mapped_column(String(50))
    request_base_date: Mapped[str | None] = mapped_column(String(8))
    request_base_time: Mapped[str | None] = mapped_column(String(4))
    forecast_base_at: Mapped[datetime | None] = mapped_column(DateTime)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    cache_key: Mapped[str] = mapped_column(String(300))
    request_params_masked: Mapped[dict | None] = mapped_column(JSONB)
    raw_response_snapshot_id: Mapped[str | None] = mapped_column(String(50))
    raw_response_json: Mapped[Any | None] = mapped_column(JSONB)
    normalized_rows_json: Mapped[Any | None] = mapped_column(JSONB)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    success_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class PredictionWeatherInput(Base):
    __tablename__ = "tb_prediction_weather_input"
    weather_input_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    prediction_job_id: Mapped[str] = mapped_column(String(80))
    snapshot_id: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(50))
    forecast_base_at: Mapped[datetime | None] = mapped_column(DateTime)
    forecast_target_at: Mapped[datetime] = mapped_column(DateTime)
    forecast_horizon_hours: Mapped[int | None] = mapped_column(Integer)
    nx: Mapped[int | None] = mapped_column(Integer)
    ny: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Numeric(10, 2))
    humidity: Mapped[float | None] = mapped_column(Numeric(10, 2))
    wind_speed: Mapped[float | None] = mapped_column(Numeric(10, 2))
    precipitation: Mapped[float | None] = mapped_column(Numeric(10, 2))
    precipitation_probability: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sky_condition: Mapped[str | None] = mapped_column(String(50))
    precipitation_type: Mapped[str | None] = mapped_column(String(50))
    raw_category_values_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DataLoadSchedule(Base):
    __tablename__ = "tb_data_load_schedule"
    schedule_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    schedule_name: Mapped[str] = mapped_column(String(200))
    schedule_description: Mapped[str | None] = mapped_column(Text)
    operation_id: Mapped[str] = mapped_column(String(50))
    data_source_id: Mapped[str | None] = mapped_column(String(50))
    schedule_type: Mapped[str] = mapped_column(String(30), default="MANUAL")
    cron_expression: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Seoul")
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    run_policy: Mapped[str] = mapped_column(String(30), default="LOAD_RUN")
    load_window_type: Mapped[str] = mapped_column(String(30), default="NONE")
    window_offset_minutes: Mapped[int | None] = mapped_column(Integer)
    runtime_params_template: Mapped[dict | None] = mapped_column(JSONB)
    max_pages_override: Mapped[int | None] = mapped_column(Integer)
    retry_enabled_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    max_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_interval_minutes: Mapped[int] = mapped_column(Integer, default=10)
    on_failure_policy: Mapped[str] = mapped_column(String(30), default="STOP")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_status: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class DataLoadScheduleRun(Base):
    __tablename__ = "tb_data_load_schedule_run"
    schedule_run_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String(50))
    operation_id: Mapped[str] = mapped_column(String(50))
    api_load_run_id: Mapped[str | None] = mapped_column(String(50))
    run_source: Mapped[str] = mapped_column(String(30), default="SCHEDULED_LOAD")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    run_status: Mapped[str] = mapped_column(String(30), default="RUNNING")
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    parent_schedule_run_id: Mapped[str | None] = mapped_column(String(50))
    runtime_params_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    runtime_params_masked: Mapped[dict | None] = mapped_column(JSONB)
    request_summary: Mapped[dict | None] = mapped_column(JSONB)
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class DataLoadScheduleEvent(Base):
    __tablename__ = "tb_data_load_schedule_event"
    event_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String(50))
    schedule_run_id: Mapped[str | None] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(50))
    event_message: Mapped[str | None] = mapped_column(Text)
    event_payload_json: Mapped[dict | None] = mapped_column(JSONB)
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
    training_job_id: Mapped[str | None] = mapped_column(String(80))
    new_model_version_id: Mapped[str | None] = mapped_column(String(80))
    mlflow_run_id: Mapped[str | None] = mapped_column(String(80))
    trained_at: Mapped[datetime | None] = mapped_column(DateTime)
    train_result_summary: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    retraining_dag_run_id: Mapped[str | None] = mapped_column(String(120))
    retraining_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    retraining_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    retraining_finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    execution_mode: Mapped[str | None] = mapped_column(String(20))
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


class PipelineTemplate(Base):
    __tablename__ = "tb_pipeline_template"
    template_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    template_code: Mapped[str] = mapped_column(String(80))
    template_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    pipeline_type: Mapped[str] = mapped_column(String(80))
    airflow_dag_id: Mapped[str | None] = mapped_column(String(200))
    template_version: Mapped[str] = mapped_column(String(30), default="1.0")
    node_schema_json: Mapped[dict] = mapped_column(JSONB)
    edge_schema_json: Mapped[dict] = mapped_column(JSONB)
    default_config_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PipelineDefinition(Base):
    __tablename__ = "tb_pipeline_definition"
    pipeline_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(50))
    pipeline_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    pipeline_type: Mapped[str] = mapped_column(String(80))
    airflow_dag_id: Mapped[str | None] = mapped_column(String(200))
    node_config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    edge_config_json: Mapped[dict | None] = mapped_column(JSONB)
    runtime_params_json: Mapped[dict | None] = mapped_column(JSONB)
    schedule_config_json: Mapped[dict | None] = mapped_column(JSONB)
    validation_result_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_id: Mapped[str | None] = mapped_column(String(80))
    active_yn: Mapped[str] = mapped_column(String(1), default="Y")
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PipelineDefinitionVersion(Base):
    __tablename__ = "tb_pipeline_definition_version"
    version_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(50))
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSONB)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class PipelineRunLink(Base):
    __tablename__ = "tb_pipeline_run_link"
    link_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(50))
    template_id: Mapped[str] = mapped_column(String(50))
    pipeline_run_id: Mapped[str] = mapped_column(String(80))
    airflow_dag_id: Mapped[str | None] = mapped_column(String(200))
    airflow_run_id: Mapped[str | None] = mapped_column(String(250))
    run_source: Mapped[str] = mapped_column(String(50), default="PIPELINE_DEFINITION")
    run_status: Mapped[str] = mapped_column(String(50), default="REQUESTED")
    runtime_params_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    node_config_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    validation_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    trigger_response_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(100))
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PredictionEntity(Base):
    __tablename__ = "tb_prediction_entity"
    entity_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    entity_code: Mapped[str] = mapped_column(String(100), unique=True)
    entity_name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(50), default="SITE")
    business_domain: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PredictionEntityLocation(Base):
    __tablename__ = "tb_prediction_entity_location"
    location_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(12, 8))
    longitude: Mapped[float | None] = mapped_column(Numeric(12, 8))
    location_source: Mapped[str | None] = mapped_column(String(50))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class WeatherForecastGrid(Base):
    __tablename__ = "tb_weather_forecast_grid"
    forecast_grid_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    grid_system: Mapped[str] = mapped_column(String(50), default="KMA_DFS")
    nx: Mapped[int] = mapped_column(Integer)
    ny: Mapped[int] = mapped_column(Integer)
    grid_name: Mapped[str | None] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Numeric(12, 8))
    longitude: Mapped[float | None] = mapped_column(Numeric(12, 8))
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class WeatherObservationStation(Base):
    __tablename__ = "tb_weather_observation_station"
    station_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    station_code: Mapped[str] = mapped_column(String(50), unique=True)
    station_name: Mapped[str] = mapped_column(String(200))
    station_type: Mapped[str] = mapped_column(String(30), default="ASOS")
    latitude: Mapped[float | None] = mapped_column(Numeric(12, 8))
    longitude: Mapped[float | None] = mapped_column(Numeric(12, 8))
    address: Mapped[str | None] = mapped_column(Text)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PredictionEntityWeatherMapping(Base):
    __tablename__ = "tb_prediction_entity_weather_mapping"
    mapping_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(50))
    forecast_grid_id: Mapped[str | None] = mapped_column(String(50))
    station_id: Mapped[str | None] = mapped_column(String(50))
    mapping_type: Mapped[str] = mapped_column(String(30), default="BOTH")
    mapping_method: Mapped[str | None] = mapped_column(String(50))
    distance_km: Mapped[float | None] = mapped_column(Numeric(10, 3))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class ExternalCodeMapping(Base):
    __tablename__ = "tb_external_code_mapping"
    mapping_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(100))
    source_operation_id: Mapped[str | None] = mapped_column(String(50))
    external_code_group: Mapped[str] = mapped_column(String(100))
    external_code: Mapped[str] = mapped_column(String(200))
    external_code_name: Mapped[str | None] = mapped_column(String(300))
    external_code_description: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(100))
    target_display_name: Mapped[str | None] = mapped_column(String(300))
    mapping_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    mapping_method: Mapped[str] = mapped_column(String(50), default="MANUAL")
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    active_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    archived_reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class UnmappedExternalCode(Base):
    __tablename__ = "tb_unmapped_external_code"
    unmapped_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(100))
    source_operation_id: Mapped[str | None] = mapped_column(String(50))
    external_code_group: Mapped[str] = mapped_column(String(100))
    external_code: Mapped[str] = mapped_column(String(200))
    external_code_name: Mapped[str | None] = mapped_column(String(300))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    seen_count: Mapped[int] = mapped_column(Integer, default=1)
    sample_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    suggested_target_type: Mapped[str | None] = mapped_column(String(50))
    suggested_target_id: Mapped[str | None] = mapped_column(String(100))
    suggested_target_name: Mapped[str | None] = mapped_column(String(300))
    review_status: Mapped[str] = mapped_column(String(30), default="NEW")
    ignored_reason: Mapped[str | None] = mapped_column(Text)
    resolved_mapping_id: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


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


class NotificationChannel(Base):
    __tablename__ = "tb_notification_channel"
    channel_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    channel_name: Mapped[str] = mapped_column(String(200))
    channel_type: Mapped[str] = mapped_column(String(50))
    enabled_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict | None] = mapped_column(JSONB)
    secret_config_encrypted: Mapped[str | None] = mapped_column(Text)
    mask_policy_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class NotificationRecipient(Base):
    __tablename__ = "tb_notification_recipient"
    recipient_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    recipient_name: Mapped[str] = mapped_column(String(200))
    recipient_type: Mapped[str] = mapped_column(String(50))
    address_masked: Mapped[str | None] = mapped_column(String(300))
    address_encrypted: Mapped[str | None] = mapped_column(Text)
    enabled_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class AlertRule(Base):
    __tablename__ = "tb_alert_rule"
    alert_rule_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(200))
    rule_description: Mapped[str | None] = mapped_column(Text)
    enabled_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    event_source: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(80))
    min_severity: Mapped[str] = mapped_column(String(30), default="WARNING")
    condition_json: Mapped[dict | None] = mapped_column(JSONB)
    dedup_window_minutes: Mapped[int] = mapped_column(Integer, default=30)
    suppress_yn: Mapped[bool] = mapped_column(Boolean, default=False)
    create_incident_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    channel_ids_json: Mapped[Any | None] = mapped_column(JSONB)
    recipient_ids_json: Mapped[Any | None] = mapped_column(JSONB)
    message_template: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class NotificationEvent(Base):
    __tablename__ = "tb_notification_event"
    event_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_source: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    dedup_key: Mapped[str | None] = mapped_column(String(300))
    event_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    masked_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class Incident(Base):
    __tablename__ = "tb_incident"
    incident_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(50))
    alert_rule_id: Mapped[str | None] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    dedup_key: Mapped[str | None] = mapped_column(String(300))
    first_occurred_at: Mapped[datetime] = mapped_column(DateTime)
    last_occurred_at: Mapped[datetime] = mapped_column(DateTime)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    acknowledged_by: Mapped[str | None] = mapped_column(String(100))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String(100))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class RunDueWorkerInstance(Base):
    __tablename__ = "tb_run_due_worker_instance"
    worker_instance_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    worker_name: Mapped[str] = mapped_column(String(200))
    worker_mode: Mapped[str] = mapped_column(String(30))
    host_name: Mapped[str | None] = mapped_column(String(200))
    process_id: Mapped[int | None] = mapped_column(Integer)
    enabled_yn: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="STARTING")
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_run_status: Mapped[str | None] = mapped_column(String(30))
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    total_run_count: Mapped[int] = mapped_column(Integer, default=0)
    total_success_count: Mapped[int] = mapped_column(Integer, default=0)
    total_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class RunDueWorkerRun(Base):
    __tablename__ = "tb_run_due_worker_run"
    worker_run_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    worker_instance_id: Mapped[str | None] = mapped_column(String(100))
    worker_name: Mapped[str | None] = mapped_column(String(200))
    run_mode: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    run_status: Mapped[str] = mapped_column(String(30), default="RUNNING")
    due_schedule_count: Mapped[int] = mapped_column(Integer, default=0)
    executed_schedule_count: Mapped[int] = mapped_column(Integer, default=0)
    success_schedule_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_schedule_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_schedule_count: Mapped[int] = mapped_column(Integer, default=0)
    run_due_result_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class RunDueWorkerLock(Base):
    __tablename__ = "tb_run_due_worker_lock"
    lock_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_instance_id: Mapped[str] = mapped_column(String(100))
    acquired_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class NotificationDelivery(Base):
    __tablename__ = "tb_notification_delivery"
    delivery_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(50))
    incident_id: Mapped[str | None] = mapped_column(String(50))
    alert_rule_id: Mapped[str | None] = mapped_column(String(50))
    channel_id: Mapped[str | None] = mapped_column(String(50))
    recipient_id: Mapped[str | None] = mapped_column(String(50))
    delivery_status: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str | None] = mapped_column(Text)
    destination_masked: Mapped[str | None] = mapped_column(String(300))
    request_payload_masked: Mapped[dict | None] = mapped_column(JSONB)
    response_payload_masked: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
