"""Feature Recipe Template Catalog 및 Validate (실행/저장 없음)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.feature_column_role_service import (
    COLUMN_ROLE_CODES,
    list_column_roles,
    summarize_role_coverage,
)
from app.services.feature_registration_service import (
    classify_feature_name,
    is_legacy_alias,
    load_catalog_feature_names,
)

RECIPE_TYPE_CODES = frozenset({
    "RAW_COLUMN",
    "DATE_PART",
    "LAG",
    "ROLLING_MEAN",
    "ROLLING_SUM",
    "DIFF",
    "RATIO",
    "BINNING",
    "FILL_NULL",
    "CATEGORY_ENCODING",
})

GRANULARITY_OPTIONS = ["1min", "5min", "10min", "30min", "1h", "1d", "1w"]
GRANULARITY_SUFFIX = {
    "1min": "min",
    "5min": "min",
    "10min": "min",
    "30min": "min",
    "1h": "h",
    "1d": "d",
    "1w": "w",
}

DATE_PART_OPTIONS = ["hour", "day_of_week", "month", "day", "is_weekend", "week_of_year"]
STANDARD_DATE_PART_CANONICAL_NAMES = frozenset({"hour", "day_of_week", "month", "is_weekend"})
PREVIEW_SUPPORTED_RECIPE_TYPES = frozenset({
    "RAW_COLUMN",
    "DATE_PART",
    "LAG",
    "ROLLING_MEAN",
    "ROLLING_SUM",
})
TIME_SERIES_PREVIEW_TYPES = frozenset({"LAG", "ROLLING_MEAN", "ROLLING_SUM"})
FILL_NULL_STRATEGIES = ["ZERO", "MEAN", "MEDIAN", "MODE", "PREVIOUS", "CONSTANT"]
BINNING_STRATEGIES = ["equal_width", "quantile", "custom"]

NUMERIC_SOURCE_ROLES = frozenset({"NUMERIC_INPUT", "MEASURE", "TARGET"})
RAW_SOURCE_ROLES = frozenset({
    "NUMERIC_INPUT", "CATEGORICAL_INPUT", "BOOLEAN_INPUT", "MEASURE", "DATETIME",
})
RATIO_SOURCE_ROLES = frozenset({"NUMERIC_INPUT", "MEASURE"})


def _granularity_suffix(granularity: str) -> str:
    return GRANULARITY_SUFFIX.get(granularity, granularity.replace("1", ""))


def _param_schema_lag() -> dict[str, Any]:
    return {
        "offset_steps": {
            "type": "integer",
            "required": True,
            "min": 1,
            "default": 24,
            "presets": [1, 3, 6, 12, 24, 168],
        },
        "granularity": {
            "type": "string",
            "required": True,
            "default": "1h",
            "options": GRANULARITY_OPTIONS,
        },
        "include_current_row": {
            "type": "boolean",
            "required": False,
            "default": False,
        },
    }


def _param_schema_rolling() -> dict[str, Any]:
    return {
        "window_steps": {
            "type": "integer",
            "required": True,
            "min": 1,
            "default": 24,
            "presets": [3, 6, 12, 24, 168],
        },
        "granularity": {
            "type": "string",
            "required": True,
            "default": "1h",
            "options": GRANULARITY_OPTIONS,
        },
        "min_periods": {
            "type": "integer",
            "required": False,
            "min": 1,
            "default": 1,
        },
        "include_current_row": {
            "type": "boolean",
            "required": False,
            "default": False,
        },
    }


@dataclass(frozen=True)
class TemplateSpec:
    recipe_type: str
    display_name: str
    description: str
    category: str
    status: str
    required_roles: list[str]
    optional_roles: list[str] = field(default_factory=list)
    required_input_count: int = 1
    output_data_type: str = "NUMERIC"
    param_schema: dict[str, Any] = field(default_factory=dict)
    default_params: dict[str, Any] = field(default_factory=dict)
    output_name_rule: str = ""
    leakage_policy: str = "NONE"
    supported_granularity: list[str] = field(default_factory=list)
    enabled_by_default: bool = True
    examples: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_type": self.recipe_type,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "status": self.status,
            "required_roles": self.required_roles,
            "optional_roles": self.optional_roles,
            "required_input_count": self.required_input_count,
            "output_data_type": self.output_data_type,
            "param_schema": self.param_schema,
            "default_params": self.default_params,
            "output_name_rule": self.output_name_rule,
            "leakage_policy": self.leakage_policy,
            "supported_granularity": self.supported_granularity,
            "enabled_by_default": self.enabled_by_default,
            "examples": self.examples,
            "warnings": self.warnings,
        }


ALL_RECIPE_TEMPLATES: dict[str, TemplateSpec] = {
    "RAW_COLUMN": TemplateSpec(
        recipe_type="RAW_COLUMN",
        display_name="원본 컬럼",
        description="원본 컬럼 값을 Feature로 사용합니다.",
        category="RAW",
        status="ACTIVE",
        required_roles=[],
        optional_roles=["NUMERIC_INPUT", "CATEGORICAL_INPUT", "BOOLEAN_INPUT", "MEASURE", "DATETIME"],
        required_input_count=1,
        output_data_type="INHERITED",
        param_schema={},
        output_name_rule="{source_column}",
        leakage_policy="NONE",
        examples=[{"source_column": "temperature", "output_feature_name": "temperature"}],
    ),
    "DATE_PART": TemplateSpec(
        recipe_type="DATE_PART",
        display_name="날짜/시간 파생",
        description="TIME_KEY 또는 DATETIME 컬럼에서 hour, day_of_week 등을 생성합니다.",
        category="DATETIME",
        status="ACTIVE",
        required_roles=[],
        optional_roles=["TIME_KEY", "DATETIME"],
        required_input_count=1,
        output_data_type="NUMERIC",
        param_schema={
            "parts": {
                "type": "array",
                "required": True,
                "min_items": 1,
                "max_items": len(DATE_PART_OPTIONS),
                "item_options": DATE_PART_OPTIONS,
                "default": ["hour"],
            },
        },
        default_params={"parts": ["hour"]},
        output_name_rule="{time_key}_{part}",
        leakage_policy="LOW",
        examples=[
            {
                "source_column": "measured_at",
                "params": {"parts": ["hour"]},
                "output_feature_name": "hour",
            },
        ],
        warnings=["R3 Preview에서 parts 복수 선택을 지원합니다."],
    ),
    "LAG": TemplateSpec(
        recipe_type="LAG",
        display_name="과거값 Lag",
        description="entity+time 기준 n step 이전 값을 생성합니다.",
        category="TIME_SERIES",
        status="ACTIVE",
        required_roles=["ENTITY_KEY", "TIME_KEY"],
        optional_roles=["NUMERIC_INPUT", "MEASURE", "TARGET"],
        required_input_count=1,
        param_schema=_param_schema_lag(),
        default_params={"offset_steps": 24, "granularity": "1h", "include_current_row": False},
        output_name_rule="{source_column}_lag_{offset_steps}{granularity_suffix}",
        leakage_policy="SHIFT_REQUIRED",
        supported_granularity=GRANULARITY_OPTIONS,
        examples=[
            {
                "source_column": "heat_demand",
                "params": {"offset_steps": 24, "granularity": "1h"},
                "output_feature_name": "heat_demand_lag_24h",
            },
        ],
    ),
    "ROLLING_MEAN": TemplateSpec(
        recipe_type="ROLLING_MEAN",
        display_name="이동 평균",
        description="최근 n step 이동 평균을 생성합니다.",
        category="AGGREGATION",
        status="ACTIVE",
        required_roles=["ENTITY_KEY", "TIME_KEY"],
        optional_roles=["NUMERIC_INPUT", "MEASURE", "TARGET"],
        required_input_count=1,
        param_schema=_param_schema_rolling(),
        default_params={"window_steps": 24, "granularity": "1h", "min_periods": 1, "include_current_row": False},
        output_name_rule="{source_column}_ma_{window_steps}{granularity_suffix}",
        leakage_policy="WINDOW_INCLUDES_CURRENT_RISK",
        supported_granularity=GRANULARITY_OPTIONS,
        examples=[
            {
                "source_column": "heat_demand",
                "params": {"window_steps": 24, "granularity": "1h"},
                "output_feature_name": "heat_demand_ma_24h",
            },
        ],
    ),
    "ROLLING_SUM": TemplateSpec(
        recipe_type="ROLLING_SUM",
        display_name="이동 합계",
        description="최근 n step 이동 합계를 생성합니다.",
        category="AGGREGATION",
        status="ACTIVE",
        required_roles=["ENTITY_KEY", "TIME_KEY"],
        optional_roles=["NUMERIC_INPUT", "MEASURE", "TARGET"],
        required_input_count=1,
        param_schema=_param_schema_rolling(),
        default_params={"window_steps": 24, "granularity": "1h", "min_periods": 1, "include_current_row": False},
        output_name_rule="{source_column}_sum_{window_steps}{granularity_suffix}",
        leakage_policy="WINDOW_INCLUDES_CURRENT_RISK",
        supported_granularity=GRANULARITY_OPTIONS,
    ),
    "DIFF": TemplateSpec(
        recipe_type="DIFF",
        display_name="차분",
        description="현재값과 n step 이전값의 차이를 생성합니다.",
        category="TIME_SERIES",
        status="ACTIVE",
        required_roles=["ENTITY_KEY", "TIME_KEY"],
        optional_roles=["NUMERIC_INPUT", "MEASURE", "TARGET"],
        required_input_count=1,
        param_schema={
            "offset_steps": _param_schema_lag()["offset_steps"],
            "granularity": _param_schema_lag()["granularity"],
        },
        default_params={"offset_steps": 24, "granularity": "1h"},
        output_name_rule="{source_column}_diff_{offset_steps}{granularity_suffix}",
        leakage_policy="SHIFT_REQUIRED",
        supported_granularity=GRANULARITY_OPTIONS,
        examples=[
            {
                "source_column": "temperature",
                "params": {"offset_steps": 24, "granularity": "1h"},
                "output_feature_name": "temperature_diff_24h",
            },
        ],
    ),
    "RATIO": TemplateSpec(
        recipe_type="RATIO",
        display_name="비율",
        description="두 수치 컬럼의 비율(column_a / column_b)을 생성합니다.",
        category="RATIO",
        status="ACTIVE",
        required_roles=[],
        optional_roles=["NUMERIC_INPUT", "MEASURE"],
        required_input_count=2,
        param_schema={
            "epsilon": {
                "type": "number",
                "required": False,
                "default": 1e-9,
                "min": 0,
            },
        },
        default_params={"epsilon": 1e-9},
        output_name_rule="{column_a}_over_{column_b}",
        leakage_policy="LOW",
        examples=[
            {
                "source_columns": ["heat_demand", "supply_temp"],
                "output_feature_name": "heat_demand_over_supply_temp",
            },
        ],
    ),
    "BINNING": TemplateSpec(
        recipe_type="BINNING",
        display_name="구간화",
        description="수치 컬럼을 구간(bin)으로 변환합니다.",
        category="TRANSFORM",
        status="ACTIVE",
        required_roles=[],
        optional_roles=["NUMERIC_INPUT", "MEASURE"],
        required_input_count=1,
        output_data_type="CATEGORICAL",
        param_schema={
            "strategy": {
                "type": "string",
                "required": True,
                "default": "equal_width",
                "options": BINNING_STRATEGIES,
            },
            "n_bins": {
                "type": "integer",
                "required": False,
                "min": 2,
                "default": 5,
            },
            "bins": {
                "type": "array",
                "required": False,
                "item_type": "number",
                "sorted_required": True,
            },
        },
        default_params={"strategy": "equal_width", "n_bins": 5},
        output_name_rule="{source_column}_bin",
        leakage_policy="LOW",
    ),
    "FILL_NULL": TemplateSpec(
        recipe_type="FILL_NULL",
        display_name="결측 처리",
        description="결측값을 지정 전략으로 채운 Feature를 생성합니다.",
        category="TRANSFORM",
        status="ACTIVE",
        required_roles=[],
        optional_roles=["NUMERIC_INPUT", "MEASURE", "CATEGORICAL_INPUT", "BOOLEAN_INPUT"],
        required_input_count=1,
        param_schema={
            "strategy": {
                "type": "string",
                "required": True,
                "default": "PREVIOUS",
                "options": FILL_NULL_STRATEGIES,
            },
            "constant_value": {
                "type": "number",
                "required": False,
            },
        },
        default_params={"strategy": "PREVIOUS"},
        output_name_rule="{source_column}_filled",
        leakage_policy="NONE",
    ),
    "CATEGORY_ENCODING": TemplateSpec(
        recipe_type="CATEGORY_ENCODING",
        display_name="범주 인코딩",
        description="범주형 컬럼을 인코딩합니다. (실험적)",
        category="CATEGORICAL",
        status="EXPERIMENTAL",
        required_roles=[],
        optional_roles=["CATEGORICAL_INPUT", "BOOLEAN_INPUT"],
        required_input_count=1,
        output_data_type="NUMERIC",
        param_schema={
            "method": {
                "type": "string",
                "required": True,
                "default": "LABEL",
                "options": ["LABEL", "ONE_HOT"],
            },
        },
        default_params={"method": "LABEL"},
        output_name_rule="{source_column}_{method}_enc",
        leakage_policy="LOW",
        warnings=["cardinality 정보가 없으면 경고가 발생할 수 있습니다."],
    ),
}


def get_template_spec(recipe_type: str) -> TemplateSpec | None:
    return ALL_RECIPE_TEMPLATES.get(recipe_type)


def list_template_specs() -> list[TemplateSpec]:
    return [ALL_RECIPE_TEMPLATES[k] for k in sorted(ALL_RECIPE_TEMPLATES)]


def _role_summary_from_items(role_items: list[dict[str, Any]]) -> dict[str, Any]:
    role_values = [
        {
            "source_column": i.get("source_column"),
            "target_column": i.get("target_column"),
            "column_role": i.get("column_role"),
        }
        for i in role_items
        if i.get("column_role")
    ]
    return summarize_role_coverage(role_values)


def _column_role_map(role_items: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in role_items:
        role = item.get("column_role")
        if not role:
            continue
        src = str(item.get("source_column") or "").strip()
        tgt = str(item.get("target_column") or "").strip()
        if src:
            mapping[src] = role
        if tgt and tgt not in mapping:
            mapping[tgt] = role
    return mapping


def _missing_roles(required: list[str], summary: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for role in required:
        if role == "ENTITY_KEY" and summary.get("entity_key_count", 0) < 1:
            missing.append(role)
        elif role == "TIME_KEY" and summary.get("time_key_count", 0) != 1:
            missing.append(role)
        elif role == "TARGET" and summary.get("target_count", 0) < 1:
            missing.append(role)
        elif role == "NUMERIC_INPUT" and summary.get("numeric_input_count", 0) < 1:
            missing.append(role)
        elif role == "CATEGORICAL_INPUT" and summary.get("categorical_input_count", 0) < 1:
            missing.append(role)
    return missing


def evaluate_template_availability(
    template: TemplateSpec,
    role_summary: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    missing_roles = _missing_roles(template.required_roles, role_summary)

    available = True
    if template.status == "PLANNED":
        available = False
        warnings.append("PLANNED 상태 템플릿은 아직 사용할 수 없습니다.")

    if missing_roles:
        available = False

    recipe_type = template.recipe_type
    if recipe_type in ("LAG", "ROLLING_MEAN", "ROLLING_SUM", "DIFF"):
        if not role_summary.get("recipe_readiness", {}).get("time_series", {}).get("ready"):
            available = False
            if "TIME_SERIES" not in str(missing_roles):
                warnings.append("ENTITY_KEY, TIME_KEY(1개), 수치 입력이 필요합니다.")
    elif recipe_type == "RATIO":
        numeric = role_summary.get("numeric_input_count", 0) + role_summary.get("measure_count", 0)
        if numeric < 2:
            available = False
            warnings.append("수치 입력 컬럼이 2개 이상 필요합니다.")
    elif recipe_type == "DATE_PART":
        if not role_summary.get("recipe_readiness", {}).get("date_part", {}).get("ready"):
            available = False
            warnings.append("TIME_KEY 또는 DATETIME 컬럼이 필요합니다.")
    elif recipe_type == "CATEGORY_ENCODING":
        if not role_summary.get("recipe_readiness", {}).get("encoding", {}).get("ready"):
            available = False
            warnings.append("범주 입력 컬럼이 필요합니다.")
        if template.status == "EXPERIMENTAL":
            warnings.append("EXPERIMENTAL 템플릿입니다.")
    elif recipe_type == "RAW_COLUMN":
        if role_summary.get("feature_candidate_count", 0) < 1:
            available = False
            warnings.append("Feature 후보 컬럼(NUMERIC/CATEGORICAL/BOOLEAN/MEASURE/DATETIME)이 필요합니다.")
    elif recipe_type in ("BINNING", "FILL_NULL"):
        numeric = role_summary.get("numeric_input_count", 0) + role_summary.get("measure_count", 0)
        if recipe_type == "BINNING" and numeric < 1:
            available = False
            warnings.append("수치 입력 또는 측정값 컬럼이 필요합니다.")

    return {
        "available": available,
        "missing_roles": missing_roles,
        "warnings": warnings,
    }


def get_template_catalog(
    *,
    role_summary: dict[str, Any] | None = None,
    category: str | None = None,
    status: str | None = None,
    include_availability: bool = True,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    available_count = 0
    active_count = 0

    for spec in list_template_specs():
        if category and spec.category != category:
            continue
        if status and spec.status != status:
            continue

        item = spec.to_dict()
        if spec.status == "ACTIVE":
            active_count += 1

        if include_availability and role_summary is not None:
            avail = evaluate_template_availability(spec, role_summary)
            item["available"] = avail["available"]
            item["availability"] = avail
            if avail["available"]:
                available_count += 1
        else:
            item["available"] = None
            item["availability"] = None

        items.append(item)

    return {
        "items": items,
        "summary": {
            "total_count": len(items),
            "available_count": available_count if role_summary is not None else None,
            "active_count": active_count,
        },
    }


def _err(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _merge_params(spec: TemplateSpec, params: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(spec.default_params)
    if params:
        merged.update(params)
    return merged


def _validate_params(spec: TemplateSpec, params: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    schema = spec.param_schema

    for key, rule in schema.items():
        required = rule.get("required", False)
        if required and key not in params:
            errors.append(_err("MISSING_PARAM", f"필수 파라미터 '{key}'가 없습니다."))
            continue
        if key not in params:
            continue
        val = params[key]
        ptype = rule.get("type")
        if ptype == "integer":
            if not isinstance(val, int) or isinstance(val, bool):
                errors.append(_err("INVALID_PARAM", f"{key}는 정수여야 합니다."))
            elif rule.get("min") is not None and val < rule["min"]:
                errors.append(_err("INVALID_PARAM", f"{key}는 {rule['min']} 이상이어야 합니다."))
        elif ptype == "number":
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                errors.append(_err("INVALID_PARAM", f"{key}는 숫자여야 합니다."))
        elif ptype == "string":
            if not isinstance(val, str):
                errors.append(_err("INVALID_PARAM", f"{key}는 문자열이어야 합니다."))
            elif rule.get("options") and val not in rule["options"]:
                errors.append(_err("INVALID_PARAM", f"{key} 값 '{val}'는 지원되지 않습니다."))
        elif ptype == "boolean":
            if not isinstance(val, bool):
                errors.append(_err("INVALID_PARAM", f"{key}는 boolean이어야 합니다."))
        elif ptype == "array":
            if not isinstance(val, list):
                errors.append(_err("INVALID_PARAM", f"{key}는 배열이어야 합니다."))
            else:
                min_items = rule.get("min_items")
                max_items = rule.get("max_items")
                if min_items and len(val) < min_items:
                    errors.append(_err("INVALID_PARAM", f"{key}는 최소 {min_items}개 항목이 필요합니다."))
                if max_items and len(val) > max_items:
                    errors.append(_err("INVALID_PARAM", f"{key}는 최대 {max_items}개까지 허용됩니다."))
                item_options = rule.get("item_options")
                if item_options:
                    for part in val:
                        if part not in item_options:
                            errors.append(_err("INVALID_PARAM", f"지원하지 않는 part: {part}"))
                if rule.get("sorted_required") and val:
                    nums = [float(x) for x in val]
                    if nums != sorted(nums):
                        errors.append(_err("INVALID_PARAM", "bins는 오름차순이어야 합니다."))

    if spec.recipe_type == "BINNING":
        strategy = params.get("strategy", "equal_width")
        if strategy == "custom" and not params.get("bins"):
            errors.append(_err("MISSING_PARAM", "strategy=custom일 때 bins가 필요합니다."))
        if strategy != "custom" and not params.get("n_bins") and not params.get("bins"):
            errors.append(_err("MISSING_PARAM", "n_bins 또는 bins가 필요합니다."))

    if spec.recipe_type == "FILL_NULL":
        if params.get("strategy") == "CONSTANT" and "constant_value" not in params:
            errors.append(_err("MISSING_PARAM", "strategy=CONSTANT일 때 constant_value가 필요합니다."))

    return errors


def _sanitize_feature_name(name: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip())
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text or "feature"


def _date_part_feature_name(part: str, time_col: str) -> str:
    if part in STANDARD_DATE_PART_CANONICAL_NAMES:
        return part
    base = _sanitize_feature_name(time_col)
    return f"{base}_{part}"


def generate_date_part_feature_names(recipe: dict[str, Any], spec: TemplateSpec) -> list[str]:
    params = recipe.get("params") or {}
    source_columns = list(recipe.get("source_columns") or [])
    time_col = recipe.get("time_key") or (source_columns[0] if source_columns else "time")
    parts = params.get("parts") or spec.default_params.get("parts") or ["hour"]
    if isinstance(parts, str):
        parts = [parts]
    return [_date_part_feature_name(str(part), str(time_col)) for part in parts]


def generate_output_feature_name(recipe: dict[str, Any], spec: TemplateSpec) -> str | list[str]:
    recipe_type = spec.recipe_type
    params = recipe.get("params") or {}
    source_columns = list(recipe.get("source_columns") or [])

    if recipe_type == "RAW_COLUMN":
        col = source_columns[0] if source_columns else "column"
        return _sanitize_feature_name(col)

    if recipe_type == "DATE_PART":
        names = generate_date_part_feature_names(recipe, spec)
        return names[0] if len(names) == 1 else names

    col = _sanitize_feature_name(source_columns[0]) if source_columns else "value"
    gran = params.get("granularity", "1h")
    suffix = _granularity_suffix(str(gran))

    if recipe_type == "LAG":
        offset = params.get("offset_steps", 24)
        return f"{col}_lag_{offset}{suffix}"

    if recipe_type == "ROLLING_MEAN":
        window = params.get("window_steps", 24)
        return f"{col}_ma_{window}{suffix}"

    if recipe_type == "ROLLING_SUM":
        window = params.get("window_steps", 24)
        return f"{col}_sum_{window}{suffix}"

    if recipe_type == "DIFF":
        offset = params.get("offset_steps", 24)
        return f"{col}_diff_{offset}{suffix}"

    if recipe_type == "RATIO":
        if len(source_columns) >= 2:
            a = _sanitize_feature_name(source_columns[0])
            b = _sanitize_feature_name(source_columns[1])
            return f"{a}_over_{b}"
        return f"{col}_ratio"

    if recipe_type == "BINNING":
        return f"{col}_bin"

    if recipe_type == "FILL_NULL":
        return f"{col}_filled"

    if recipe_type == "CATEGORY_ENCODING":
        method = str(params.get("method", "LABEL")).lower()
        return f"{col}_{method}_enc"

    return col


def _resolve_column_role(col: str, role_map: dict[str, str]) -> str | None:
    return role_map.get(col)


async def validate_recipe_definition(
    db: AsyncSession,
    recipe: dict[str, Any],
    *,
    mapping_columns: list[dict[str, Any]] | None = None,
    role_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    infos: list[str] = []

    recipe_type = str(recipe.get("recipe_type") or "").strip()
    spec = get_template_spec(recipe_type)
    if not spec:
        errors.append(_err("UNKNOWN_RECIPE_TYPE", f"지원하지 않는 recipe_type: {recipe_type}"))
        return _validation_result(False, recipe_type, errors, warnings, infos, None, spec)

    if spec.status == "PLANNED":
        errors.append(_err("TEMPLATE_NOT_AVAILABLE", f"{recipe_type}는 PLANNED 상태로 validate할 수 없습니다."))

    source_columns = [str(c).strip() for c in (recipe.get("source_columns") or []) if str(c).strip()]
    if not source_columns:
        errors.append(_err("MISSING_SOURCE_COLUMNS", "source_columns가 비어 있습니다."))
    elif len(source_columns) != spec.required_input_count:
        errors.append(
            _err(
                "INVALID_SOURCE_COUNT",
                f"{recipe_type}는 source_columns {spec.required_input_count}개가 필요합니다.",
            )
        )

    known_cols: set[str] = set()
    if mapping_columns:
        for col in mapping_columns:
            if col.get("source_column"):
                known_cols.add(str(col["source_column"]))
            if col.get("target_column"):
                known_cols.add(str(col["target_column"]))

    for col in source_columns:
        if known_cols and col not in known_cols:
            if recipe_type in PREVIEW_SUPPORTED_RECIPE_TYPES:
                errors.append(_err("UNKNOWN_SOURCE_COLUMN", f"매핑에 없는 source_column: {col}"))
            else:
                warnings.append(f"매핑 컬럼 목록에 없는 source_column: {col}")

    role_map = _column_role_map(role_items or [])
    role_summary = _role_summary_from_items(role_items or []) if role_items else {}

    if role_items:
        avail = evaluate_template_availability(spec, role_summary)
        if not avail["available"]:
            for role in avail["missing_roles"]:
                if role == "TIME_KEY":
                    errors.append(_err("MISSING_TIME_KEY", f"{recipe_type} 템플릿에는 TIME_KEY 역할 컬럼이 필요합니다."))
                elif role == "ENTITY_KEY":
                    errors.append(_err("MISSING_ENTITY_KEY", f"{recipe_type} 템플릿에는 ENTITY_KEY가 필요합니다."))
                else:
                    errors.append(_err("MISSING_ROLE", f"필수 역할 {role}이(가) 부족합니다."))
            for w in avail["warnings"]:
                if w not in warnings:
                    warnings.append(w)

    params = _merge_params(spec, recipe.get("params"))
    errors.extend(_validate_params(spec, params))

    if recipe_type in ("ROLLING_MEAN", "ROLLING_SUM"):
        window = int(params.get("window_steps", 24))
        min_periods = params.get("min_periods")
        if min_periods is not None:
            if not isinstance(min_periods, int) or isinstance(min_periods, bool):
                errors.append(_err("INVALID_PARAM", "min_periods는 정수여야 합니다."))
            elif min_periods <= 0:
                errors.append(_err("INVALID_PARAM", "min_periods는 1 이상이어야 합니다."))
            elif min_periods > window:
                errors.append(_err("INVALID_PARAM", "min_periods는 window_steps 이하여야 합니다."))

    if recipe_type in ("LAG", "ROLLING_MEAN", "ROLLING_SUM", "DIFF"):
        steps = params.get("offset_steps") if recipe_type == "LAG" else params.get("window_steps")
        if recipe_type == "DIFF":
            steps = params.get("offset_steps")
        if isinstance(steps, int) and steps >= 10000:
            warnings.append(f"{steps} step은 매우 큽니다. Preview 이력·성능에 주의하세요.")

    if recipe_type in TIME_SERIES_PREVIEW_TYPES and role_items:
        if not recipe.get("entity_keys") and role_summary.get("entity_key_count", 0) < 1:
            errors.append(_err("MISSING_ENTITY_KEY", f"{recipe_type} Preview에는 ENTITY_KEY가 필요합니다."))
        if not recipe.get("time_key") and role_summary.get("time_key_count", 0) != 1:
            errors.append(_err("MISSING_TIME_KEY", f"{recipe_type} Preview에는 TIME_KEY가 1개 필요합니다."))

    if recipe_type == "LAG" and params.get("include_current_row"):
        warnings.append("LAG에서 include_current_row=true는 무시되며 shift가 적용됩니다.")
        params["include_current_row"] = False

    for col in source_columns:
        role = _resolve_column_role(col, role_map)
        if recipe_type == "RAW_COLUMN":
            if role in ("EXCLUDE", "ID", "TEXT"):
                errors.append(_err("INVALID_SOURCE_ROLE", f"{col} 역할({role})은 RAW_COLUMN에 적합하지 않습니다."))
            elif role in ("ENTITY_KEY", "TIME_KEY", "JOIN_KEY"):
                warnings.append(f"{col}은(는) {role}이지만 RAW_COLUMN으로 사용할 수 있습니다.")
        elif recipe_type in ("LAG", "ROLLING_MEAN", "ROLLING_SUM", "DIFF"):
            if role and role not in NUMERIC_SOURCE_ROLES:
                errors.append(_err("INVALID_SOURCE_ROLE", f"{col} 역할({role})은 시계열 연산에 사용할 수 없습니다."))
        elif recipe_type == "RATIO":
            if role and role not in RATIO_SOURCE_ROLES:
                errors.append(_err("INVALID_SOURCE_ROLE", f"{col} 역할({role})은 RATIO에 사용할 수 없습니다."))
        elif recipe_type == "BINNING":
            if role and role not in ("NUMERIC_INPUT", "MEASURE"):
                errors.append(_err("INVALID_SOURCE_ROLE", f"{col} 역할({role})은 BINNING에 사용할 수 없습니다."))
        elif recipe_type == "CATEGORY_ENCODING":
            if role and role not in ("CATEGORICAL_INPUT", "BOOLEAN_INPUT"):
                warnings.append(f"{col} 역할({role}) — CATEGORICAL_INPUT 권장")
            if not recipe.get("cardinality"):
                warnings.append("cardinality 정보가 없어 인코딩 품질을 사전에 평가하기 어렵습니다.")

    target_column = recipe.get("target_column")
    if recipe_type in ("ROLLING_MEAN", "ROLLING_SUM") and params.get("include_current_row"):
        if target_column and source_columns and target_column in source_columns:
            warnings.append(
                "include_current_row=true이고 source가 TARGET과 동일하면 누수 위험이 있습니다."
            )

    if recipe_type == "LAG":
        infos.append("LAG 템플릿은 현재 행을 사용하지 않으므로 누수 위험이 낮습니다.")

    recipe_for_name = {**recipe, "params": params}
    explicit_output = recipe.get("output_feature_name")
    reusable_existing_features: list[dict[str, str]] = []
    duplicate_policy = "STRICT"

    if recipe_type == "DATE_PART":
        duplicate_policy = "STANDARD_DATE_PART_REUSE"
        parts = params.get("parts") or ["hour"]
        if isinstance(parts, str):
            parts = [parts]
        generated_names = generate_date_part_feature_names(recipe_for_name, spec)
        if explicit_output:
            if len(parts) > 1:
                errors.append(
                    _err(
                        "INVALID_OUTPUT_NAME",
                        "parts가 2개 이상일 때 output_feature_name 단일 문자열은 사용할 수 없습니다.",
                    )
                )
            output_names = [_sanitize_feature_name(str(explicit_output))]
        else:
            output_names = generated_names
    else:
        generated = generate_output_feature_name(recipe_for_name, spec)
        generated_names = generated if isinstance(generated, list) else [generated]
        output_names = [_sanitize_feature_name(str(explicit_output or generated_names[0]))]

    catalog_names = await load_catalog_feature_names(db)
    for name in output_names:
        if is_legacy_alias(name):
            errors.append(_err("LEGACY_FEATURE_NAME", f"{name}는 레거시 별칭입니다. 공식명을 사용하세요."))
            continue

        in_catalog = name in catalog_names
        name_check = classify_feature_name(name, catalog_registered=in_catalog)
        exists = in_catalog or name_check["status"] in (
            "DUPLICATE",
            "COMPUTABLE",
            "REGISTERED_IN_REGISTRY",
        )
        is_standard_date_part = recipe_type == "DATE_PART" and name in STANDARD_DATE_PART_CANONICAL_NAMES

        if is_standard_date_part and exists:
            reusable_existing_features.append(
                {
                    "feature_name": name,
                    "reason": "STANDARD_DATE_PART_ALREADY_EXISTS",
                }
            )
            infos.append(
                f"동일한 표준 DATE_PART Feature '{name}'가 이미 등록되어 있어 기존 Feature를 재사용할 수 있습니다."
            )
            continue

        if exists:
            errors.append(
                _err("DUPLICATE_FEATURE_NAME", f"Feature명 '{name}'은(는) 이미 카탈로그에 등록되어 있습니다.")
            )

    output_name = output_names[0] if output_names else ""
    valid = len(errors) == 0

    lineage_preview = {
        "calc_method": "TEMPLATE",
        "recipe_type": recipe_type,
        "source_columns": source_columns,
        "entity_keys": recipe.get("entity_keys") or [],
        "time_key": recipe.get("time_key"),
        "target_column": target_column,
        "params": params,
    }

    template_dict = spec.to_dict() if spec else None

    return _validation_result(
        valid,
        recipe_type,
        errors,
        warnings,
        infos,
        {
            "generated_feature_name": generated_names[0] if generated_names else output_name,
            "output_feature_name": output_name,
            "generated_feature_names": generated_names,
            "output_feature_names": output_names,
            "duplicate_policy": duplicate_policy,
            "reusable_existing_feature": bool(reusable_existing_features),
            "reusable_existing_features": reusable_existing_features,
            "lineage_preview": lineage_preview,
            "template": template_dict,
        },
        spec,
    )


def _validation_result(
    valid: bool,
    recipe_type: str,
    errors: list[dict[str, str]],
    warnings: list[str],
    infos: list[str],
    extra: dict[str, Any] | None,
    spec: TemplateSpec | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "valid": valid,
        "recipe_type": recipe_type,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }
    if extra:
        result.update(extra)
    elif spec:
        result["template"] = spec.to_dict()
    return result


async def get_catalog_for_mapping(
    db: AsyncSession,
    mapping_id: str,
    *,
    category: str | None = None,
    status: str | None = None,
    include_availability: bool = True,
) -> dict[str, Any]:
    role_data = await list_column_roles(db, mapping_id=mapping_id, include_inferred=False)
    role_summary = role_data.get("summary") or {}
    return get_template_catalog(
        role_summary=role_summary if include_availability else None,
        category=category,
        status=status,
        include_availability=include_availability,
    )
