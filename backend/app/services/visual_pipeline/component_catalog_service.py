"""R11-S1 Visual Pipeline component catalog (code-based, no DB).

Provides component contracts, port types, config_schema hints, and connection rules
for Visual Pipeline Studio. Does not perform graph validation, compile, or R10 writes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.visual_pipeline.schemas import (
    CardinalityRuleDict,
    ComponentContractDict,
    ConnectionRuleDict,
)

COMPONENT_CONTRACT_VERSION = "R11-S1-V1"

PORT_DATA_TYPES_MVP = (
    "RAW_ROWS",
    "TRANSFORMED_ROWS",
    "LOAD_RESULT",
    "SCHEDULE_CONFIG",
    "SCHEDULE_TRIGGER",
)

PORT_DATA_TYPES_FUTURE = (
    "ERROR_EVENT",
    "DATA_QUALITY_RESULT",
    "FEATURE_DATASET",
    "MODEL_VERSION",
    "PREDICTION_RESULT",
)

ACTIVE_COMPONENT_TYPES = (
    "VP_REST_API_SOURCE",
    "VP_TRANSFORM",
    "VP_UPSERT_LOAD",
    "VP_CRON_SCHEDULE",
)

DISABLED_COMPONENT_TYPES = (
    "VP_NOTIFICATION",
    "VP_DATA_QUALITY",
    "VP_FEATURE_BUILD",
    "VP_MODEL_TRAINING",
    "VP_BATCH_PREDICTION",
    "VP_FORECAST_PROVIDER",
    "VP_DB_SOURCE",
    "VP_CSV_SOURCE",
)


def _field(
    name: str,
    *,
    field_type: str,
    required: bool = False,
    default: Any = None,
    values: list[str] | None = None,
    ui_component: str | None = None,
    option_source: dict[str, Any] | None = None,
    required_if: str | None = None,
    description: str | None = None,
    secret: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": name,
        "type": field_type,
        "required": required,
    }
    if default is not None:
        item["default"] = default
    if values is not None:
        item["values"] = values
    if ui_component:
        item["ui_component"] = ui_component
    if option_source:
        item["option_source"] = option_source
    if required_if:
        item["required_if"] = required_if
    if description:
        item["description"] = description
    if secret:
        item["secret"] = True
        item["store_in_graph"] = False
    return item


def _port(
    port_id: str,
    data_type: str,
    *,
    required: bool = True,
    accepted_data_types: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "port_id": port_id,
        "data_type": data_type,
        "required": required,
    }
    if accepted_data_types:
        item["accepted_data_types"] = accepted_data_types
    if description:
        item["description"] = description
    return item


def _disabled(
    component_type: str,
    display_name: str,
    category: str,
    disabled_reason: str,
    description: str,
) -> ComponentContractDict:
    return {
        "component_type": component_type,
        "display_name": display_name,
        "category": category,
        "status": "DISABLED",
        "version": "1.0",
        "description": description,
        "disabled_reason": disabled_reason,
        "input_ports": [],
        "output_ports": [],
        "config_schema": [],
        "validation_rules": [],
        "compile_role": None,
        "execution_adapter": None,
        "ui_hints": {"coming_soon": True},
        "allowed_targets": [],
    }


_CATALOG: list[ComponentContractDict] = [
    {
        "component_type": "VP_REST_API_SOURCE",
        "display_name": "REST API Source",
        "category": "DATA_INPUT",
        "status": "ACTIVE",
        "version": "1.0",
        "description": "REST API Connector operation을 통해 원천 rows를 생성한다.",
        "disabled_reason": None,
        "input_ports": [
            _port(
                "trigger",
                "SCHEDULE_TRIGGER",
                required=False,
                description="CRON schedule trigger 입력 (선택)",
            ),
        ],
        "output_ports": [
            _port("raw_rows", "RAW_ROWS", required=True),
        ],
        "config_schema": [
            _field(
                "data_source_id",
                field_type="string",
                required=True,
                ui_component="select",
                option_source={"type": "api", "endpoint": "/api/v1/data-sources"},
                description="데이터 소스 ID",
            ),
            _field("operation_name", field_type="string", required=True, ui_component="text"),
            _field(
                "endpoint_path",
                field_type="string",
                required=True,
                ui_component="text",
                description="API endpoint path (R10 tb_api_connector_operation.endpoint_path)",
            ),
            _field(
                "http_method",
                field_type="enum",
                required=True,
                values=["GET", "POST"],
                default="GET",
                ui_component="select",
            ),
            _field(
                "request_params",
                field_type="object",
                required=False,
                ui_component="key_value_editor",
                description="요청 파라미터 정의 (compile 시 tb_api_connector_param)",
            ),
            _field(
                "pagination",
                field_type="object",
                required=False,
                ui_component="object_editor",
                description="페이징 설정 (compile 시 tb_api_connector_pagination)",
            ),
            _field("response_item_path", field_type="string", required=False, ui_component="text"),
            _field(
                "credential_ref",
                field_type="reference",
                required=False,
                ui_component="select",
                description="credential_id 또는 data_source credential 참조. secret 원문 저장 금지",
                secret=True,
            ),
        ],
        "validation_rules": [
            "data_source_id must exist",
            "endpoint_path is required",
            "http_method must be GET or POST",
            "secret fields must not be stored in graph",
            "credential values must not appear in compiled_target_json",
        ],
        "compile_role": "OPERATION_BASE",
        "execution_adapter": "api_connector_operation",
        "ui_hints": {
            "palette_group": "활성",
            "icon": "api",
            "option_source_operations": "/api/v1/api-connectors/operations",
        },
        "allowed_targets": [],
    },
    {
        "component_type": "VP_TRANSFORM",
        "display_name": "Transform",
        "category": "TRANSFORM",
        "status": "ACTIVE",
        "version": "1.0",
        "description": "API raw rows를 표준 적재 rows로 변환한다.",
        "disabled_reason": None,
        "input_ports": [
            _port("input_rows", "RAW_ROWS", required=True),
        ],
        "output_ports": [
            _port("transformed_rows", "TRANSFORMED_ROWS", required=True),
        ],
        "config_schema": [
            _field(
                "transform_type",
                field_type="enum",
                required=True,
                values=[
                    "NONE",
                    "WIDE_HOUR_TO_LONG",
                    "ASOS_HOURLY_TO_CANONICAL",
                    "CALENDAR_SPECIAL_DAY_TO_DATE",
                    "CALENDAR_DATE_TO_HOUR",
                ],
                ui_component="select",
            ),
            _field("mapping_config", field_type="object", required=False, ui_component="object_editor"),
            _field("unmapped_policy", field_type="enum", required=False, ui_component="select"),
            _field("hour_policy", field_type="object", required=False, ui_component="object_editor"),
            _field("target_schema_preview", field_type="object", required=False, ui_component="readonly_json"),
        ],
        "validation_rules": [
            "transform_type must be supported",
            "input data_type must be RAW_ROWS",
            "output data_type is TRANSFORMED_ROWS",
            "transform-specific required fields are validated in R11-S4",
        ],
        "compile_role": "TRANSFORM_CONFIG",
        "execution_adapter": "connector_transform_config",
        "ui_hints": {"palette_group": "활성", "icon": "transform"},
        "allowed_targets": [],
    },
    {
        "component_type": "VP_UPSERT_LOAD",
        "display_name": "Upsert Load",
        "category": "LOAD",
        "status": "ACTIVE",
        "version": "1.0",
        "description": "rows를 target table에 INSERT_ONLY / DEDUPLICATE / UPSERT로 적재한다.",
        "disabled_reason": None,
        "input_ports": [
            _port(
                "input_rows",
                "TRANSFORMED_ROWS",
                required=True,
                accepted_data_types=["RAW_ROWS", "TRANSFORMED_ROWS"],
                description="Transform 결과 또는 Source raw rows",
            ),
        ],
        "output_ports": [
            _port("load_result", "LOAD_RESULT", required=True),
        ],
        "config_schema": [
            _field(
                "standard_dataset_id",
                field_type="string",
                required=False,
                ui_component="select",
                option_source={"type": "api", "endpoint": "/api/v1/standard-datasets"},
            ),
            _field("target_table", field_type="string", required=True, ui_component="text"),
            _field(
                "write_mode",
                field_type="enum",
                required=True,
                values=["INSERT_ONLY", "DEDUPLICATE", "UPSERT"],
                default="INSERT_ONLY",
                ui_component="select",
            ),
            _field(
                "conflict_key_columns_json",
                field_type="array[string]",
                required=False,
                required_if="write_mode in [DEDUPLICATE, UPSERT]",
                ui_component="string_list",
                description="R10 tb_api_connector_write_policy.conflict_key_columns_json",
            ),
            _field(
                "duplicate_within_batch_policy",
                field_type="enum",
                required=False,
                values=["KEEP_FIRST", "KEEP_LAST", "ERROR"],
                default="KEEP_LAST",
                ui_component="select",
            ),
            _field(
                "null_update_policy",
                field_type="enum",
                required=False,
                values=["KEEP_EXISTING", "OVERWRITE_WITH_NULL"],
                default="KEEP_EXISTING",
                ui_component="select",
            ),
            _field(
                "save_dedup_summary_yn",
                field_type="boolean",
                required=False,
                default=True,
                ui_component="checkbox",
            ),
        ],
        "validation_rules": [
            "target_table is required",
            "write_mode must be INSERT_ONLY, DEDUPLICATE, or UPSERT",
            "conflict_key_columns_json required for DEDUPLICATE/UPSERT",
            "conflict_key_columns_json must not be empty for DEDUPLICATE/UPSERT",
            "secret fields are not allowed",
        ],
        "compile_role": "WRITE_POLICY",
        "execution_adapter": "api_connector_load_write_policy",
        "ui_hints": {"palette_group": "활성", "icon": "load"},
        "allowed_targets": [],
    },
    {
        "component_type": "VP_CRON_SCHEDULE",
        "display_name": "CRON Schedule",
        "category": "SCHEDULE",
        "status": "ACTIVE",
        "version": "1.0",
        "description": "compiled operation을 CRON 일정으로 실행한다. MVP schedule_type은 CRON만 지원한다.",
        "disabled_reason": None,
        "input_ports": [],
        "output_ports": [
            _port("schedule_config", "SCHEDULE_CONFIG", required=True),
        ],
        "config_schema": [
            _field(
                "schedule_type",
                field_type="enum",
                required=True,
                values=["CRON"],
                default="CRON",
                ui_component="select",
                description="MVP에서는 CRON만 허용",
            ),
            _field("cron_expression", field_type="string", required=True, ui_component="text"),
            _field(
                "timezone",
                field_type="string",
                required=True,
                default="Asia/Seoul",
                ui_component="text",
            ),
            _field("start_at", field_type="datetime", required=False, ui_component="datetime"),
            _field("end_at", field_type="datetime", required=False, ui_component="datetime"),
            _field("active_yn", field_type="boolean", required=False, default=False, ui_component="checkbox"),
            _field(
                "retry_enabled_yn",
                field_type="boolean",
                required=False,
                default=False,
                ui_component="checkbox",
            ),
            _field("max_retry_count", field_type="integer", required=False, default=0, ui_component="number"),
            _field(
                "retry_interval_minutes",
                field_type="integer",
                required=False,
                default=10,
                ui_component="number",
            ),
        ],
        "validation_rules": [
            "cron_expression is required",
            "timezone is required",
            "schedule_type must be CRON in MVP",
            "cron_expression is validated by cron_schedule_service in R11-S4/S5",
        ],
        "compile_role": "DATA_LOAD_SCHEDULE",
        "execution_adapter": "data_load_scheduler",
        "ui_hints": {
            "palette_group": "활성",
            "icon": "schedule",
            "cron_validate_endpoint": "/api/v1/data-load-schedules/cron/validate",
            "cron_preview_endpoint": "/api/v1/data-load-schedules/cron/preview",
        },
        "allowed_targets": [],
    },
    _disabled(
        "VP_NOTIFICATION",
        "Notification",
        "OPERATION",
        "Alert Rule 연결은 R11-S6 이후 검토",
        "적재 실패/경고 알림 규칙 연결 (후순위)",
    ),
    _disabled(
        "VP_DATA_QUALITY",
        "Data Quality Check",
        "QUALITY",
        "Connector load 경로와 직접 연동 범위가 S1에 없음",
        "데이터 품질 점검 노드 (후순위)",
    ),
    _disabled(
        "VP_FEATURE_BUILD",
        "Feature Build",
        "FEATURE",
        "2차 MVP",
        "Feature Recipe Build 노드 (후순위)",
    ),
    _disabled(
        "VP_MODEL_TRAINING",
        "Model Training",
        "MODEL",
        "2차 MVP",
        "모델 학습 노드 (후순위)",
    ),
    _disabled(
        "VP_BATCH_PREDICTION",
        "Batch Prediction",
        "PREDICTION",
        "2차 MVP",
        "배치 예측 노드 (후순위)",
    ),
    _disabled(
        "VP_FORECAST_PROVIDER",
        "Forecast Provider",
        "DATA_INPUT",
        "R10-S5 on-demand forecast와 별도 축",
        "단기예보 on-demand 입력 (후순위)",
    ),
    _disabled(
        "VP_DB_SOURCE",
        "DB Source",
        "DATA_INPUT",
        "1차 MVP 제외",
        "DB 소스 노드 (후순위)",
    ),
    _disabled(
        "VP_CSV_SOURCE",
        "CSV Upload",
        "DATA_INPUT",
        "1차 MVP 제외",
        "CSV 업로드 소스 노드 (후순위)",
    ),
]

_CONNECTION_RULES: list[ConnectionRuleDict] = [
    {
        "rule_id": "ALLOW_SOURCE_TO_TRANSFORM",
        "from_component_type": "VP_REST_API_SOURCE",
        "from_port_id": "raw_rows",
        "to_component_type": "VP_TRANSFORM",
        "to_port_id": "input_rows",
        "allowed": True,
        "reason": "API raw rows를 transform으로 전달",
    },
    {
        "rule_id": "ALLOW_TRANSFORM_TO_LOAD",
        "from_component_type": "VP_TRANSFORM",
        "from_port_id": "transformed_rows",
        "to_component_type": "VP_UPSERT_LOAD",
        "to_port_id": "input_rows",
        "allowed": True,
        "reason": "transform 결과를 load로 전달",
    },
    {
        "rule_id": "ALLOW_SOURCE_TO_LOAD",
        "from_component_type": "VP_REST_API_SOURCE",
        "from_port_id": "raw_rows",
        "to_component_type": "VP_UPSERT_LOAD",
        "to_port_id": "input_rows",
        "allowed": True,
        "reason": "transform 없이 직접 load 가능",
    },
    {
        "rule_id": "ALLOW_CRON_TO_SOURCE_TRIGGER",
        "from_component_type": "VP_CRON_SCHEDULE",
        "from_port_id": "schedule_config",
        "to_component_type": "VP_REST_API_SOURCE",
        "to_port_id": "trigger",
        "allowed": True,
        "reason": "CRON이 operation 실행을 trigger함",
    },
    {
        "rule_id": "DENY_LOAD_TO_CRON",
        "from_component_type": "VP_UPSERT_LOAD",
        "from_port_id": "load_result",
        "to_component_type": "VP_CRON_SCHEDULE",
        "to_port_id": "input",
        "allowed": False,
        "reason": "schedule은 실행 결과를 입력으로 받지 않음",
    },
    {
        "rule_id": "DENY_NOTIFICATION_TO_TRANSFORM",
        "from_component_type": "VP_NOTIFICATION",
        "from_port_id": "event",
        "to_component_type": "VP_TRANSFORM",
        "to_port_id": "input_rows",
        "allowed": False,
        "reason": "Notification은 데이터 입력이 아님",
    },
    {
        "rule_id": "DENY_FEATURE_TO_LOAD",
        "from_component_type": "VP_FEATURE_BUILD",
        "from_port_id": "feature_dataset",
        "to_component_type": "VP_UPSERT_LOAD",
        "to_port_id": "input_rows",
        "allowed": False,
        "reason": "Feature pipeline은 1차 MVP 제외",
    },
]

_CARDINALITY_RULES: list[CardinalityRuleDict] = [
    {
        "component_type": "VP_REST_API_SOURCE",
        "min_count": 1,
        "max_count": 1,
        "required": True,
        "note": "1 graph = 1 operation group",
    },
    {
        "component_type": "VP_UPSERT_LOAD",
        "min_count": 1,
        "max_count": 1,
        "required": True,
        "note": "1 graph = 1 operation group",
    },
    {
        "component_type": "VP_TRANSFORM",
        "min_count": 0,
        "max_count": 1,
        "required": False,
        "note": "transform 생략 가능",
    },
    {
        "component_type": "VP_CRON_SCHEDULE",
        "min_count": 0,
        "max_count": 1,
        "required": False,
        "note": "schedule 생략 시 수동 run-now만 가능 (S6)",
    },
]


def normalize_component_type(component_type: str) -> str:
    return str(component_type or "").strip().upper()


def _index() -> dict[str, ComponentContractDict]:
    return {c["component_type"]: c for c in _CATALOG}


def _with_allowed_targets(component: ComponentContractDict) -> ComponentContractDict:
    """Attach allowed_targets derived from connection rules for ACTIVE sources."""
    item = deepcopy(component)
    ctype = item["component_type"]
    targets: list[dict[str, Any]] = []
    for rule in _CONNECTION_RULES:
        if rule["from_component_type"] == ctype and rule["allowed"]:
            targets.append(
                {
                    "to_component_type": rule["to_component_type"],
                    "from_port_id": rule["from_port_id"],
                    "to_port_id": rule["to_port_id"],
                    "rule_id": rule["rule_id"],
                }
            )
    item["allowed_targets"] = targets
    return item


def list_components(
    *,
    status: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    status_f = status.strip().upper() if status else None
    category_f = category.strip().upper() if category else None
    items: list[ComponentContractDict] = []
    for raw in _CATALOG:
        if status_f and raw.get("status") != status_f:
            continue
        if category_f and raw.get("category") != category_f:
            continue
        items.append(_with_allowed_targets(raw))
    return {
        "items": items,
        "total": len(items),
        "contract_version": COMPONENT_CONTRACT_VERSION,
        "port_data_types_mvp": list(PORT_DATA_TYPES_MVP),
        "port_data_types_future": list(PORT_DATA_TYPES_FUTURE),
    }


def get_component(component_type: str) -> ComponentContractDict:
    key = normalize_component_type(component_type)
    found = _index().get(key)
    if not found:
        raise LookupError("COMPONENT_NOT_FOUND")
    return _with_allowed_targets(found)


def list_connection_rules() -> dict[str, Any]:
    return {
        "items": deepcopy(_CONNECTION_RULES),
        "total": len(_CONNECTION_RULES),
        "cardinality_rules": deepcopy(_CARDINALITY_RULES),
        "mvp_note": "1 graph = 1 operation group. Actual graph validation is R11-S4.",
        "contract_version": COMPONENT_CONTRACT_VERSION,
    }


def list_active_component_types() -> list[str]:
    return list(ACTIVE_COMPONENT_TYPES)


def list_disabled_component_types() -> list[str]:
    return list(DISABLED_COMPONENT_TYPES)
