"""Pipeline Template / Definition Builder (Phase R8)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    DataMapping,
    DataSource,
    FeatureSet,
    PipelineDefinition,
    PipelineDefinitionVersion,
    PipelineTemplate,
    StandardDatasetType,
    TrainingConfig,
)
from app.services.pipeline_service import PIPELINE_IDS

REQUIRED_FIELDS: dict[str, list[str]] = {
    "DATA_SOURCE": ["data_source_id"],
    "DATA_MAPPING": ["mapping_id"],
    "STANDARD_DATASET": ["dataset_type_id"],
    "FEATURE_SET": ["feature_set_id"],
    "FEATURE_BUILD": ["feature_set_id"],
    "MODEL_SELECTION": ["model_name"],
    "BATCH_PREDICTION": ["predict_start_date", "predict_end_date"],
    "MODEL_TRAINING": [],
    "DATA_QUALITY": [],
    "FEATURE_QUALITY": [],
    "PERFORMANCE_EVAL": [],
    "DRIFT_CHECK": [],
    "MONITORING": [],
    "RETRAINING_CANDIDATE": [],
    "APPROVAL": [],
    "MODEL_REGISTRY": [],
}

STATIC_OPTIONS: dict[str, list[dict[str, str]]] = {
    "algorithm": [
        {"value": "catboost", "label": "CatBoost"},
        {"value": "two_stage_catboost", "label": "2-Stage CatBoost"},
        {"value": "lightgbm", "label": "LightGBM"},
    ],
    "metric": [
        {"value": "MAPE", "label": "MAPE"},
        {"value": "RMSE", "label": "RMSE"},
        {"value": "MAE", "label": "MAE"},
    ],
    "registry_stage": [
        {"value": "CHAMPION", "label": "Champion"},
        {"value": "CANDIDATE", "label": "Candidate"},
    ],
    "quality_rule_set": [
        {"value": "DEFAULT", "label": "기본 규칙"},
        {"value": "STRICT", "label": "엄격"},
    ],
}


def _template_nodes(template: PipelineTemplate) -> list[dict[str, Any]]:
    schema = template.node_schema_json or {}
    nodes = schema.get("nodes") if isinstance(schema, dict) else schema
    return list(nodes or [])


def _template_edges(template: PipelineTemplate) -> list[dict[str, Any]]:
    schema = template.edge_schema_json or {}
    edges = schema.get("edges") if isinstance(schema, dict) else schema
    return list(edges or [])


def _template_dict(row: PipelineTemplate, *, flow: dict | None = None) -> dict[str, Any]:
    item = {
        "template_id": row.template_id,
        "template_code": row.template_code,
        "template_name": row.template_name,
        "description": row.description,
        "pipeline_type": row.pipeline_type,
        "airflow_dag_id": row.airflow_dag_id,
        "template_version": row.template_version,
        "status": row.status,
        "active": row.active_yn == "Y",
        "node_schema": row.node_schema_json,
        "edge_schema": row.edge_schema_json,
        "default_config": row.default_config_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if flow:
        item["flow"] = flow
    return item


def _definition_dict(
    row: PipelineDefinition,
    template: PipelineTemplate | None = None,
    *,
    flow: dict | None = None,
) -> dict[str, Any]:
    item = {
        "pipeline_id": row.pipeline_id,
        "template_id": row.template_id,
        "pipeline_name": row.pipeline_name,
        "description": row.description,
        "pipeline_type": row.pipeline_type,
        "airflow_dag_id": row.airflow_dag_id,
        "node_config": row.node_config_json or {},
        "edge_config": row.edge_config_json,
        "runtime_params": row.runtime_params_json,
        "schedule_config": row.schedule_config_json,
        "validation_result": row.validation_result_json,
        "status": row.status,
        "last_validated_at": row.last_validated_at.isoformat() if row.last_validated_at else None,
        "last_run_id": row.last_run_id,
        "active": row.active_yn == "Y",
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if template:
        item["template_code"] = template.template_code
        item["template_name"] = template.template_name
    if flow:
        item["flow"] = flow
    return item


def _node_config_complete(component_type: str, config: dict[str, Any]) -> bool:
    fields = REQUIRED_FIELDS.get(component_type, [])
    if not fields:
        return bool(config)
    return all(config.get(f) not in (None, "", []) for f in fields)


def _merge_node_config(
    template: PipelineTemplate,
    node_config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = deepcopy((template.default_config_json or {}).get("node_config") or {})
    merged.update(node_config or {})
    return merged


def build_flow_view(
    template: PipelineTemplate,
    node_config: dict[str, Any] | None,
    *,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = _merge_node_config(template, node_config)
    errors_by_node: dict[str, list[str]] = {}
    warnings_by_node: dict[str, list[str]] = {}
    if validation:
        for err in validation.get("errors") or []:
            if isinstance(err, dict) and err.get("node_id"):
                errors_by_node.setdefault(err["node_id"], []).append(err.get("message", ""))
        for warn in validation.get("warnings") or []:
            if isinstance(warn, dict) and warn.get("node_id"):
                warnings_by_node.setdefault(warn["node_id"], []).append(warn.get("message", ""))

    nodes_out: list[dict[str, Any]] = []
    for node in _template_nodes(template):
        nid = node["node_id"]
        cfg = merged.get(nid) or {}
        required = bool(node.get("required"))
        complete = _node_config_complete(node.get("component_type", ""), cfg)
        err_count = len(errors_by_node.get(nid, []))
        warn_count = len(warnings_by_node.get(nid, []))
        if err_count:
            state = "error"
        elif warn_count:
            state = "warning"
        elif complete:
            state = "configured"
        elif required:
            state = "required"
        else:
            state = "optional"
        nodes_out.append({
            **node,
            "config": cfg,
            "config_state": state,
            "error_count": err_count,
            "warning_count": warn_count,
        })
    return {
        "nodes": nodes_out,
        "edges": _template_edges(template),
    }


async def list_pipeline_templates(
    db: AsyncSession,
    *,
    status: str | None = None,
    pipeline_type: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    q = select(PipelineTemplate)
    if active_only:
        q = q.where(PipelineTemplate.active_yn == "Y")
    if status:
        q = q.where(PipelineTemplate.status == status.upper())
    if pipeline_type:
        q = q.where(PipelineTemplate.pipeline_type == pipeline_type.upper())
    rows = (await db.execute(q.order_by(PipelineTemplate.template_name))).scalars().all()
    return [_template_dict(r) for r in rows]


async def get_pipeline_template(db: AsyncSession, template_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == template_id))
    ).scalar_one_or_none()
    if not row:
        raise LookupError("TEMPLATE_NOT_FOUND")
    flow = build_flow_view(row, _merge_node_config(row, {}))
    return _template_dict(row, flow=flow)


async def list_pipeline_definitions(
    db: AsyncSession,
    *,
    status: str | None = None,
    pipeline_type: str | None = None,
    template_id: str | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    q = select(PipelineDefinition, PipelineTemplate).join(
        PipelineTemplate, PipelineDefinition.template_id == PipelineTemplate.template_id
    )
    if active_only:
        q = q.where(PipelineDefinition.active_yn == "Y")
    if status:
        q = q.where(PipelineDefinition.status == status.upper())
    if pipeline_type:
        q = q.where(PipelineDefinition.pipeline_type == pipeline_type.upper())
    if template_id:
        q = q.where(PipelineDefinition.template_id == template_id)
    rows = (await db.execute(q.order_by(PipelineDefinition.updated_at.desc()))).all()
    items: list[dict[str, Any]] = []
    for defn, tmpl in rows:
        items.append(_definition_dict(defn, tmpl))
    return items


async def get_pipeline_definition(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    row = (
        await db.execute(
            select(PipelineDefinition, PipelineTemplate)
            .join(PipelineTemplate, PipelineDefinition.template_id == PipelineTemplate.template_id)
            .where(PipelineDefinition.pipeline_id == pipeline_id)
        )
    ).first()
    if not row:
        raise LookupError("PIPELINE_NOT_FOUND")
    defn, tmpl = row
    validation = defn.validation_result_json
    flow = build_flow_view(tmpl, defn.node_config_json, validation=validation)
    return _definition_dict(defn, tmpl, flow=flow)


async def _next_version_no(db: AsyncSession, pipeline_id: str) -> int:
    current = (
        await db.execute(
            select(func.max(PipelineDefinitionVersion.version_no)).where(
                PipelineDefinitionVersion.pipeline_id == pipeline_id
            )
        )
    ).scalar()
    return int(current or 0) + 1


async def _save_version(
    db: AsyncSession,
    defn: PipelineDefinition,
    *,
    change_summary: str | None = None,
) -> None:
    version_no = await _next_version_no(db, defn.pipeline_id)
    db.add(PipelineDefinitionVersion(
        version_id=f"PDV-{uuid4().hex[:8].upper()}",
        pipeline_id=defn.pipeline_id,
        version_no=version_no,
        snapshot_json={
            "pipeline_name": defn.pipeline_name,
            "description": defn.description,
            "node_config": defn.node_config_json,
            "schedule_config": defn.schedule_config_json,
            "status": defn.status,
        },
        change_summary=change_summary,
        created_at=utc_now(),
    ))


async def create_pipeline_definition(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    template = (
        await db.execute(
            select(PipelineTemplate).where(PipelineTemplate.template_id == payload["template_id"])
        )
    ).scalar_one_or_none()
    if not template:
        raise LookupError("TEMPLATE_NOT_FOUND")
    if template.status == "PLANNED":
        raise ValueError("PLANNED 템플릿으로는 Pipeline Definition을 생성할 수 없습니다.")

    pipeline_id = f"PIPE-{uuid4().hex[:6].upper()}"
    node_config = _merge_node_config(template, payload.get("node_config"))
    defn = PipelineDefinition(
        pipeline_id=pipeline_id,
        template_id=template.template_id,
        pipeline_name=payload["pipeline_name"],
        description=payload.get("description"),
        pipeline_type=template.pipeline_type,
        airflow_dag_id=template.airflow_dag_id,
        node_config_json=node_config,
        edge_config_json=template.edge_schema_json,
        runtime_params_json=payload.get("runtime_params"),
        schedule_config_json=payload.get("schedule_config") or {"enabled": False, "schedule_type": "MANUAL"},
        status="DRAFT",
        active_yn="Y",
        created_by=payload.get("created_by"),
        created_at=utc_now(),
    )
    db.add(defn)
    await db.flush()
    await _save_version(db, defn, change_summary="initial create")
    return await get_pipeline_definition(db, pipeline_id)


async def update_pipeline_definition(
    db: AsyncSession,
    pipeline_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    defn = (
        await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id))
    ).scalar_one_or_none()
    if not defn:
        raise LookupError("PIPELINE_NOT_FOUND")
    if defn.status == "ARCHIVED":
        raise ValueError("ARCHIVED Pipeline은 수정할 수 없습니다.")

    if payload.get("pipeline_name"):
        defn.pipeline_name = payload["pipeline_name"]
    if "description" in payload:
        defn.description = payload["description"]
    if payload.get("node_config") is not None:
        template = (
            await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == defn.template_id))
        ).scalar_one_or_none()
        defn.node_config_json = _merge_node_config(template, payload["node_config"]) if template else payload["node_config"]
    if payload.get("schedule_config") is not None:
        defn.schedule_config_json = payload["schedule_config"]
    if payload.get("runtime_params") is not None:
        defn.runtime_params_json = payload["runtime_params"]
    defn.updated_at = utc_now()
    if defn.status == "ACTIVE":
        defn.status = "DRAFT"
    await db.flush()
    await _save_version(db, defn, change_summary=payload.get("change_summary") or "update")
    return await get_pipeline_definition(db, pipeline_id)


async def validate_pipeline_definition(
    db: AsyncSession,
    *,
    pipeline_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if pipeline_id:
        defn_row = (
            await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id))
        ).scalar_one_or_none()
        if not defn_row:
            raise LookupError("PIPELINE_NOT_FOUND")
        template = (
            await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == defn_row.template_id))
        ).scalar_one_or_none()
        node_config = defn_row.node_config_json or {}
        airflow_dag_id = defn_row.airflow_dag_id
        template_status = template.status if template else None
    else:
        if not payload:
            raise ValueError("pipeline_id 또는 payload가 필요합니다.")
        template = (
            await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == payload["template_id"]))
        ).scalar_one_or_none()
        if not template:
            raise LookupError("TEMPLATE_NOT_FOUND")
        node_config = _merge_node_config(template, payload.get("node_config"))
        airflow_dag_id = template.airflow_dag_id
        template_status = template.status
        defn_row = None

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    required_missing: list[str] = []

    if template_status == "PLANNED":
        errors.append({
            "code": "PLANNED_NODE_INCLUDED",
            "message": "PLANNED 템플릿은 ACTIVE Pipeline으로 사용할 수 없습니다.",
        })

    if not airflow_dag_id or airflow_dag_id not in PIPELINE_IDS:
        errors.append({
            "code": "AIRFLOW_DAG_NOT_MAPPED",
            "message": f"Airflow DAG 매핑이 없습니다: {airflow_dag_id}",
        })

    if not template:
        raise LookupError("TEMPLATE_NOT_FOUND")

    for node in _template_nodes(template):
        nid = node["node_id"]
        ctype = node.get("component_type", "")
        cfg = node_config.get(nid) or {}
        required = bool(node.get("required"))
        complete = _node_config_complete(ctype, cfg)

        if required and not complete:
            required_missing.append(nid)
            errors.append({
                "node_id": nid,
                "code": "REQUIRED_NODE_CONFIG_MISSING",
                "message": f"필수 노드 '{node.get('label', nid)}' 설정이 누락되었습니다.",
            })
        elif not required and not complete:
            warnings.append({
                "node_id": nid,
                "code": "OPTIONAL_NODE_NOT_CONFIGURED",
                "message": f"선택 노드 '{node.get('label', nid)}'가 설정되지 않았습니다.",
            })

        await _validate_node_refs(db, nid, ctype, cfg, errors, warnings)

    if node_config.get("MODEL_TRAINING") and node_config.get("MODEL_SELECTION"):
        mt = node_config.get("MODEL_TRAINING") or {}
        ms = node_config.get("MODEL_SELECTION") or {}
        if mt.get("config_id") and ms.get("model_name"):
            warnings.append({
                "code": "MODEL_TRAINING_AND_SELECTION_BOTH_SET",
                "message": "모델 학습과 모델 선택이 모두 설정되었습니다. 실행 정책을 확인하세요.",
            })

    runtime_preview = build_airflow_runtime_params(template, node_config, pipeline_id=pipeline_id or "preview")

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "required_missing_nodes": required_missing,
        "runtime_params_preview": runtime_preview,
    }

    if defn_row:
        defn_row.validation_result_json = result
        defn_row.last_validated_at = utc_now()
        defn_row.runtime_params_json = runtime_preview
        defn_row.status = "VALIDATED" if result["valid"] else "DRAFT"
        defn_row.updated_at = utc_now()
        await db.flush()

    return result


async def _validate_node_refs(
    db: AsyncSession,
    node_id: str,
    component_type: str,
    cfg: dict[str, Any],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if component_type == "DATA_SOURCE" and cfg.get("data_source_id"):
        src = (
            await db.execute(
                select(DataSource).where(DataSource.data_source_id == cfg["data_source_id"])
            )
        ).scalar_one_or_none()
        if not src:
            errors.append({
                "node_id": node_id,
                "code": "DATA_SOURCE_NOT_FOUND",
                "message": f"데이터소스를 찾을 수 없습니다: {cfg['data_source_id']}",
            })
        if cfg.get("mapping_id"):
            m = (
                await db.execute(select(DataMapping).where(DataMapping.mapping_id == cfg["mapping_id"]))
            ).scalar_one_or_none()
            if not m:
                errors.append({
                    "node_id": node_id,
                    "code": "MAPPING_NOT_FOUND",
                    "message": f"매핑을 찾을 수 없습니다: {cfg['mapping_id']}",
                })

    if component_type in ("DATA_MAPPING",) and cfg.get("mapping_id"):
        m = (
            await db.execute(select(DataMapping).where(DataMapping.mapping_id == cfg["mapping_id"]))
        ).scalar_one_or_none()
        if not m:
            errors.append({
                "node_id": node_id,
                "code": "MAPPING_NOT_FOUND",
                "message": f"매핑을 찾을 수 없습니다: {cfg['mapping_id']}",
            })

    if component_type == "STANDARD_DATASET" and cfg.get("dataset_type_id"):
        ds = (
            await db.execute(
                select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == cfg["dataset_type_id"])
            )
        ).scalar_one_or_none()
        if not ds:
            errors.append({
                "node_id": node_id,
                "code": "STANDARD_DATASET_NOT_FOUND",
                "message": f"표준 데이터셋을 찾을 수 없습니다: {cfg['dataset_type_id']}",
            })
        elif ds.status != "ACTIVE":
            errors.append({
                "node_id": node_id,
                "code": "STANDARD_DATASET_NOT_ACTIVE",
                "message": f"표준 데이터셋이 ACTIVE가 아닙니다: {ds.dataset_type_name}",
            })
        elif ds.recipe_supported_yn != "Y":
            warnings.append({
                "node_id": node_id,
                "code": "STANDARD_DATASET_NOT_RECIPE_SUPPORTED",
                "message": "선택한 표준 데이터셋은 Recipe 지원이 제한됩니다.",
            })

    if cfg.get("feature_set_id"):
        fs = (
            await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == cfg["feature_set_id"]))
        ).scalar_one_or_none()
        if not fs:
            errors.append({
                "node_id": node_id,
                "code": "FEATURE_SET_NOT_FOUND",
                "message": f"Feature Set을 찾을 수 없습니다: {cfg['feature_set_id']}",
            })

    if component_type == "BATCH_PREDICTION":
        start = cfg.get("predict_start_date")
        end = cfg.get("predict_end_date")
        if start and end and str(start) > str(end):
            errors.append({
                "node_id": node_id,
                "code": "INVALID_DATE_RANGE",
                "message": "예측 시작일이 종료일보다 늦습니다.",
            })

    if component_type == "MODEL_TRAINING" and cfg.get("config_id"):
        tc = (
            await db.execute(select(TrainingConfig).where(TrainingConfig.config_id == cfg["config_id"]))
        ).scalar_one_or_none()
        if not tc:
            errors.append({
                "node_id": node_id,
                "code": "MODEL_NOT_FOUND",
                "message": f"학습 설정을 찾을 수 없습니다: {cfg['config_id']}",
            })


def build_airflow_runtime_params(
    template: PipelineTemplate,
    node_config: dict[str, Any],
    *,
    pipeline_id: str | None = None,
) -> dict[str, Any]:
    nc = node_config or {}
    params: dict[str, Any] = {
        "pipeline_definition_id": pipeline_id,
        "template_code": template.template_code,
        "airflow_dag_id": template.airflow_dag_id,
    }

    ds = nc.get("DATA_SOURCE") or {}
    if ds.get("data_source_id"):
        params["source_id"] = ds["data_source_id"]
    if ds.get("mapping_id"):
        params["mapping_id"] = ds["mapping_id"]

    dm = nc.get("DATA_MAPPING") or {}
    if dm.get("mapping_id"):
        params["mapping_id"] = dm["mapping_id"]

    sd = nc.get("STANDARD_DATASET") or {}
    if sd.get("dataset_type_id"):
        params["dataset_type_id"] = sd["dataset_type_id"]

    for key in ("FEATURE_SET", "FEATURE_BUILD", "FEATURE_QUALITY"):
        block = nc.get(key) or {}
        if block.get("feature_set_id"):
            params["feature_set_id"] = block["feature_set_id"]
            break

    fb = nc.get("FEATURE_BUILD") or {}
    if fb.get("dataset_type_id"):
        params["dataset_type_id"] = fb["dataset_type_id"]

    mt = nc.get("MODEL_TRAINING") or {}
    if mt.get("config_id"):
        params["config_id"] = mt["config_id"]
    if mt.get("algorithm"):
        params["algorithm"] = mt["algorithm"]
    if mt.get("train_start_date"):
        params["train_start_date"] = mt["train_start_date"]
    if mt.get("train_end_date"):
        params["train_end_date"] = mt["train_end_date"]

    ms = nc.get("MODEL_SELECTION") or {}
    if ms.get("model_name"):
        params["model_name"] = ms["model_name"]
    if ms.get("registry_stage"):
        params["registry_stage"] = ms["registry_stage"]

    bp = nc.get("BATCH_PREDICTION") or {}
    if bp.get("site_ids"):
        params["site_ids"] = bp["site_ids"]
    if bp.get("predict_start_date"):
        params["predict_start_date"] = bp["predict_start_date"]
        params["start_at"] = bp["predict_start_date"]
    if bp.get("predict_end_date"):
        params["predict_end_date"] = bp["predict_end_date"]
        params["end_at"] = bp["predict_end_date"]

    pe = nc.get("PERFORMANCE_EVAL") or {}
    if pe.get("metric"):
        params["metric"] = pe["metric"]
    if pe.get("threshold") is not None:
        params["threshold"] = pe["threshold"]

    dc = nc.get("DRIFT_CHECK") or {}
    params["drift_check_enabled"] = bool(dc) and any(dc.values())
    if dc.get("drift_threshold") is not None:
        params["drift_threshold"] = dc["drift_threshold"]

    dq = nc.get("DATA_QUALITY") or {}
    if dq.get("quality_rule_set"):
        params["quality_rule_set"] = dq["quality_rule_set"]
    if dq.get("fail_on_error") is not None:
        params["fail_on_error"] = dq["fail_on_error"]

    mon = nc.get("MONITORING") or {}
    if mon.get("model_name"):
        params["model_name"] = mon["model_name"]

    return params


async def activate_pipeline_definition(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    validation = await validate_pipeline_definition(db, pipeline_id=pipeline_id)
    if not validation["valid"]:
        raise ValueError(validation["errors"][0]["message"] if validation["errors"] else "검증 실패")
    defn = (
        await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id))
    ).scalar_one()
    defn.status = "ACTIVE"
    defn.updated_at = utc_now()
    await db.flush()
    return await get_pipeline_definition(db, pipeline_id)


async def archive_pipeline_definition(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    defn = (
        await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id))
    ).scalar_one_or_none()
    if not defn:
        raise LookupError("PIPELINE_NOT_FOUND")
    defn.status = "ARCHIVED"
    defn.active_yn = "N"
    defn.updated_at = utc_now()
    await db.flush()
    template = (
        await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == defn.template_id))
    ).scalar_one_or_none()
    return _definition_dict(defn, template)


async def get_node_config_options(
    db: AsyncSession,
    component_type: str,
    *,
    template_id: str | None = None,
    pipeline_id: str | None = None,
) -> dict[str, Any]:
    options: dict[str, Any] = {"component_type": component_type, "fields": {}}

    if component_type in ("DATA_SOURCE",):
        sources = (await db.execute(select(DataSource).where(DataSource.active_yn == "Y"))).scalars().all()
        options["fields"]["data_source_id"] = [
            {"value": s.data_source_id, "label": f"{s.source_name} ({s.data_source_id})"}
            for s in sources
        ]
        mappings = (await db.execute(select(DataMapping).where(DataMapping.active_yn == "Y"))).scalars().all()
        options["fields"]["mapping_id"] = [
            {"value": m.mapping_id, "label": f"{m.mapping_name} ({m.target_table})"}
            for m in mappings
        ]

    if component_type in ("DATA_MAPPING",):
        mappings = (await db.execute(select(DataMapping).where(DataMapping.active_yn == "Y"))).scalars().all()
        options["fields"]["mapping_id"] = [
            {"value": m.mapping_id, "label": f"{m.mapping_name} ({m.target_table})"}
            for m in mappings
        ]

    if component_type in ("STANDARD_DATASET",):
        datasets = (
            await db.execute(
                select(StandardDatasetType).where(
                    StandardDatasetType.active_yn == "Y",
                    StandardDatasetType.status == "ACTIVE",
                )
            )
        ).scalars().all()
        options["fields"]["dataset_type_id"] = [
            {
                "value": d.dataset_type_id,
                "label": f"{d.dataset_type_name} ({d.target_table})",
                "recipe_supported": d.recipe_supported_yn == "Y",
                "build_supported": d.build_supported_yn == "Y",
            }
            for d in datasets
        ]

    if component_type in ("FEATURE_SET", "FEATURE_BUILD", "FEATURE_QUALITY"):
        sets = (await db.execute(select(FeatureSet))).scalars().all()
        options["fields"]["feature_set_id"] = [
            {"value": f.feature_set_id, "label": f.feature_set_name}
            for f in sets
        ]

    if component_type == "FEATURE_BUILD":
        datasets = (
            await db.execute(select(StandardDatasetType).where(StandardDatasetType.active_yn == "Y"))
        ).scalars().all()
        options["fields"]["dataset_type_id"] = [
            {"value": d.dataset_type_id, "label": d.dataset_type_name}
            for d in datasets
        ]

    if component_type == "MODEL_TRAINING":
        options["fields"]["algorithm"] = STATIC_OPTIONS["algorithm"]
        configs = (await db.execute(select(TrainingConfig))).scalars().all()
        options["fields"]["config_id"] = [
            {"value": c.config_id, "label": f"{c.config_name} ({c.algorithm})"}
            for c in configs
        ]

    if component_type in ("MODEL_SELECTION", "MONITORING"):
        options["fields"]["model_name"] = [
            {"value": "heat_demand_lightgbm", "label": "heat_demand_lightgbm"},
            {"value": "heat_demand_catboost", "label": "heat_demand_catboost"},
            {"value": "heat_demand_two_stage_catboost", "label": "heat_demand_two_stage_catboost"},
        ]
        options["fields"]["registry_stage"] = STATIC_OPTIONS["registry_stage"]

    if component_type == "BATCH_PREDICTION":
        options["fields"]["site_ids"] = [
            {"value": "SITE-001", "label": "중앙 (SITE-001)"},
            {"value": "SITE-002", "label": "강남 (SITE-002)"},
            {"value": "SITE-003", "label": "분당 (SITE-003)"},
            {"value": "SITE-004", "label": "고양 (SITE-004)"},
            {"value": "SITE-005", "label": "대전 (SITE-005)"},
        ]

    if component_type == "DATA_QUALITY":
        options["fields"]["quality_rule_set"] = STATIC_OPTIONS["quality_rule_set"]
        options["fields"]["fail_on_error"] = [
            {"value": "false", "label": "경고만"},
            {"value": "true", "label": "오류 시 중단"},
        ]

    if component_type == "PERFORMANCE_EVAL":
        options["fields"]["metric"] = STATIC_OPTIONS["metric"]

    if component_type == "DRIFT_CHECK":
        options["fields"]["drift_threshold"] = [
            {"value": "0.1", "label": "0.10"},
            {"value": "0.2", "label": "0.20"},
            {"value": "0.3", "label": "0.30"},
        ]

    _ = template_id, pipeline_id
    return options


async def runtime_preview(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    item = await get_pipeline_definition(db, pipeline_id)
    template = (
        await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == item["template_id"]))
    ).scalar_one()
    params = build_airflow_runtime_params(
        template,
        item.get("node_config") or {},
        pipeline_id=pipeline_id,
    )
    return {
        "pipeline_id": pipeline_id,
        "airflow_dag_id": item.get("airflow_dag_id"),
        "template_code": item.get("template_code"),
        "runtime_params": params,
        "note": "R8에서는 preview만 제공하며 실제 Airflow 실행은 연결하지 않습니다.",
    }
