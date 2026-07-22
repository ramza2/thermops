"""R11-S6-4 Visual Pipeline → R10 materialization PoC.

Creates/updates R10 config rows from a SUCCESS compile artifact.
Does not run connectors, transform, upsert writes, activate schedules, or change sync status.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    ApiConnectorOperation,
    ApiConnectorTransformConfig,
    ApiConnectorWritePolicy,
    DataLoadSchedule,
    VisualPipelineMaterializationResult,
)
from app.services.api_connector_service import (
    ApiConnectorError,
    create_operation,
    replace_params,
    update_operation,
    upsert_pagination,
    upsert_transform_config,
)
from app.services.data_load_scheduler_service import (
    DataLoadSchedulerError,
    create_schedule,
    update_schedule,
)
from app.services.load_write_policy_service import WritePolicyError, upsert_write_policy
from app.services.standard_dataset_service import TargetTableNotAllowedError
from app.services.visual_pipeline.compile_preview_service import calculate_graph_version_hash
from app.services.visual_pipeline.compile_result_service import get_latest_compile_result_row
from app.services.visual_pipeline.visual_pipeline_service import (
    _get_visual_definition,
    get_visual_pipeline,
)

MATERIALIZATION_VERSION = "R11-S6-4"
ACTIVATION_NOT_REQUESTED = "NOT_REQUESTED"


class MaterializePreconditionError(Exception):
    """HTTP 409-class precondition failure."""

    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or code
        super().__init__(self.message)


class MaterializeDomainError(Exception):
    """Domain mapping failure → HTTP 200 + FAILED (R10 rollback)."""

    def __init__(self, code: str, message: str, *, node_id: str | None = None, details: Any = None):
        self.code = code
        self.message = message
        self.node_id = node_id
        self.details = details
        super().__init__(message)

    def to_issue(self) -> dict[str, Any]:
        issue: dict[str, Any] = {
            "severity": "ERROR",
            "code": self.code,
            "message": self.message,
            "phase": "MATERIALIZE",
        }
        if self.node_id:
            issue["node_id"] = self.node_id
        if self.details is not None:
            issue["details"] = self.details
        return issue


def _new_materialization_result_id() -> str:
    return f"VPM-{uuid4().hex[:8].upper()}"


def _origin(
    *,
    pipeline_id: str,
    node_id: str,
    component_type: str,
    compile_result_id: str,
    graph_version_hash: str | None,
    object_type: str,
) -> dict[str, Any]:
    return {
        "pipeline_id": pipeline_id,
        "node_id": node_id,
        "component_type": component_type,
        "compile_result_id": compile_result_id,
        "graph_version_hash": graph_version_hash,
        "object_type": object_type,
        "materialization_version": MATERIALIZATION_VERSION,
    }


def _merge_origin_metadata(existing: dict[str, Any] | None, origin: dict[str, Any]) -> dict[str, Any]:
    meta = dict(existing or {})
    meta["visual_pipeline_origin"] = origin
    return meta


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    text = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if text and not text.endswith("Z") and "+" not in text and "T" in text:
        return f"{text}Z"
    return text


def _row_to_response(row: VisualPipelineMaterializationResult) -> dict[str, Any]:
    return {
        "materialization_result_id": row.materialization_result_id,
        "pipeline_id": row.pipeline_id,
        "compile_result_id": row.compile_result_id,
        "materialization_status": row.materialization_status,
        "graph_version_hash": row.graph_version_hash,
        "materialization_version": row.materialization_version,
        "materialized_at": _iso(row.created_at),
        "objects": dict(row.objects_json or {}),
        "created": dict(row.created_json or {}),
        "updated": dict(row.updated_json or {}),
        "skipped": list(row.skipped_json or []),
        "issues": list(row.issues_json or []),
        "warnings": list(row.warnings_json or []),
        "activation": row.activation or ACTIVATION_NOT_REQUESTED,
        "run_created": bool(row.run_created),
        "error_message": row.error_message,
        "persisted": True,
    }


async def _find_by_origin(
    db: AsyncSession,
    model: type,
    *,
    pipeline_id: str,
    node_id: str,
) -> Any | None:
    stmt = select(model).where(
        model.metadata_json.contains(
            {"visual_pipeline_origin": {"pipeline_id": pipeline_id, "node_id": node_id}}
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return None
    # Prefer non-archived operations when applicable
    for row in rows:
        if hasattr(row, "archived_at") and row.archived_at:
            continue
        return row
    return rows[0]


def _normalize_params(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            name = item.get("param_name") or item.get("name")
            if not name:
                continue
            out.append(
                {
                    "param_name": str(name),
                    "display_name": item.get("display_name"),
                    "param_location": item.get("param_location") or item.get("location") or "QUERY",
                    "param_type": item.get("param_type") or item.get("type") or "STRING",
                    "required_yn": bool(item.get("required_yn", False)),
                    "default_value": item.get("default_value", item.get("value")),
                    "example_value": item.get("example_value"),
                    "value_source": item.get("value_source") or "USER_INPUT",
                    "secret_key_ref": item.get("secret_key_ref"),
                    "encode_yn": bool(item.get("encode_yn", True)),
                    "sort_order": int(item.get("sort_order", idx)),
                    "active_yn": bool(item.get("active_yn", True)),
                }
            )
        return out
    if isinstance(raw, dict):
        out = []
        for idx, (key, value) in enumerate(raw.items()):
            if str(key).lower() in {"authorization", "password", "api_key", "token", "secret"}:
                continue
            out.append(
                {
                    "param_name": str(key),
                    "param_location": "QUERY",
                    "param_type": "STRING",
                    "required_yn": False,
                    "default_value": None if value is None else str(value),
                    "value_source": "USER_INPUT",
                    "encode_yn": True,
                    "sort_order": idx,
                    "active_yn": True,
                }
            )
        return out
    return []


def _normalize_pagination(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    return {
        "pagination_type": raw.get("pagination_type") or "NONE",
        "page_param_name": raw.get("page_param_name"),
        "size_param_name": raw.get("size_param_name"),
        "page_start": raw.get("page_start", 1),
        "page_size": raw.get("page_size", 100),
        "max_pages": raw.get("max_pages", 1),
        "total_count_path": raw.get("total_count_path"),
        "next_link_path": raw.get("next_link_path"),
        "stop_condition": raw.get("stop_condition") or "EMPTY_ITEMS",
        "active_yn": bool(raw.get("active_yn", True)),
    }


def _step_by_type(artifact: dict[str, Any], step_type: str) -> dict[str, Any] | None:
    for step in artifact.get("steps") or []:
        if isinstance(step, dict) and step.get("type") == step_type:
            return step
    return None


async def _materialize_operation(
    db: AsyncSession,
    *,
    pipeline_id: str,
    compile_result_id: str,
    graph_version_hash: str | None,
    source_step: dict[str, Any],
    load_cfg: dict[str, Any],
    created: dict[str, Any],
    updated: dict[str, Any],
    warnings: list[str],
) -> str:
    node_id = str(source_step.get("node_id") or "")
    cfg = dict(source_step.get("config") or {})
    data_source_id = str(cfg.get("data_source_id") or "").strip()
    if not data_source_id:
        raise MaterializeDomainError(
            "MATERIALIZE_DATA_SOURCE_REQUIRED",
            "REST source data_source_id is required for materialization.",
            node_id=node_id,
        )

    origin = _origin(
        pipeline_id=pipeline_id,
        node_id=node_id,
        component_type=str(source_step.get("component_type") or "VP_REST_API_SOURCE"),
        compile_result_id=compile_result_id,
        graph_version_hash=graph_version_hash,
        object_type="operation",
    )
    existing = await _find_by_origin(
        db, ApiConnectorOperation, pipeline_id=pipeline_id, node_id=node_id
    )

    op_payload = {
        "data_source_id": data_source_id,
        "operation_name": str(cfg.get("operation_name") or f"vp-{node_id}")[:200],
        "http_method": str(cfg.get("http_method") or "GET").upper(),
        "endpoint_path": str(cfg.get("endpoint_path") or "/"),
        "response_item_path": cfg.get("response_item_path"),
        "target_table": load_cfg.get("target_table"),
        "standard_dataset_id": load_cfg.get("standard_dataset_id"),
        "metadata_json": _merge_origin_metadata(None, origin),
    }
    # credential_ref is reference-only; keep in metadata, never as secret
    if cfg.get("credential_ref"):
        op_payload["metadata_json"]["credential_ref"] = cfg.get("credential_ref")

    try:
        if existing:
            await update_operation(
                db,
                existing.operation_id,
                {
                    "operation_name": op_payload["operation_name"],
                    "http_method": op_payload["http_method"],
                    "endpoint_path": op_payload["endpoint_path"],
                    "response_item_path": op_payload["response_item_path"],
                    "target_table": op_payload["target_table"],
                    "standard_dataset_id": op_payload["standard_dataset_id"],
                },
            )
            existing.metadata_json = _merge_origin_metadata(existing.metadata_json, origin)
            if cfg.get("credential_ref"):
                meta = dict(existing.metadata_json or {})
                meta["credential_ref"] = cfg.get("credential_ref")
                existing.metadata_json = meta
            await db.flush()
            operation_id = existing.operation_id
            updated["operation_id"] = operation_id
        else:
            created_op = await create_operation(db, op_payload)
            operation_id = created_op["operation_id"]
            created["operation_id"] = operation_id
    except ApiConnectorError as exc:
        code = getattr(exc, "error_code", None) or "MATERIALIZE_OPERATION_FAILED"
        raise MaterializeDomainError(str(code), str(exc), node_id=node_id) from exc
    except TargetTableNotAllowedError as exc:
        raise MaterializeDomainError(
            "MATERIALIZE_TARGET_TABLE_NOT_ALLOWED",
            str(exc),
            node_id=node_id,
        ) from exc

    params = _normalize_params(cfg.get("request_params"))
    if params:
        await replace_params(db, operation_id, params)
    pagination = _normalize_pagination(cfg.get("pagination"))
    if pagination and str(pagination.get("pagination_type") or "NONE").upper() != "NONE":
        await upsert_pagination(db, operation_id, pagination)
    elif pagination is None and cfg.get("pagination"):
        warnings.append("pagination present but empty/invalid; skipped")

    return operation_id


async def _materialize_transform(
    db: AsyncSession,
    *,
    pipeline_id: str,
    compile_result_id: str,
    graph_version_hash: str | None,
    transform_step: dict[str, Any],
    operation_id: str,
    created: dict[str, Any],
    updated: dict[str, Any],
) -> str:
    node_id = str(transform_step.get("node_id") or "")
    cfg = dict(transform_step.get("config") or {})
    origin = _origin(
        pipeline_id=pipeline_id,
        node_id=node_id,
        component_type=str(transform_step.get("component_type") or "VP_TRANSFORM"),
        compile_result_id=compile_result_id,
        graph_version_hash=graph_version_hash,
        object_type="transform_config",
    )
    payload: dict[str, Any] = {
        "transform_type": str(cfg.get("transform_type") or "NONE").upper(),
        "metadata_json": origin,
    }
    if isinstance(cfg.get("mapping_config"), dict):
        # mapping_config is form-level; store under metadata for PoC if no typed fields
        payload["metadata_json"] = {**origin, "mapping_config": cfg.get("mapping_config")}
    if cfg.get("unmapped_policy"):
        payload["unmapped_policy"] = cfg["unmapped_policy"]

    existing = (
        await db.execute(
            select(ApiConnectorTransformConfig).where(
                ApiConnectorTransformConfig.operation_id == operation_id
            )
        )
    ).scalar_one_or_none()
    was_create = existing is None

    try:
        result = await upsert_transform_config(db, operation_id, payload)
    except Exception as exc:  # noqa: BLE001 — map any transform config error
        raise MaterializeDomainError(
            "MATERIALIZE_TRANSFORM_FAILED",
            str(exc),
            node_id=node_id,
        ) from exc

    # ensure origin metadata persisted (save_transform_config may merge)
    row = (
        await db.execute(
            select(ApiConnectorTransformConfig).where(
                ApiConnectorTransformConfig.operation_id == operation_id
            )
        )
    ).scalar_one()
    row.metadata_json = _merge_origin_metadata(row.metadata_json, origin)
    if isinstance(cfg.get("mapping_config"), dict):
        meta = dict(row.metadata_json or {})
        meta["mapping_config"] = cfg.get("mapping_config")
        row.metadata_json = meta
    await db.flush()

    transform_id = result.get("transform_config_id") or row.transform_config_id
    if was_create:
        created["transform_config_id"] = transform_id
    else:
        updated["transform_config_id"] = transform_id
    return str(transform_id)


async def _materialize_write_policy(
    db: AsyncSession,
    *,
    pipeline_id: str,
    compile_result_id: str,
    graph_version_hash: str | None,
    load_step: dict[str, Any],
    operation_id: str,
    created: dict[str, Any],
    updated: dict[str, Any],
) -> str:
    node_id = str(load_step.get("node_id") or "")
    cfg = dict(load_step.get("config") or {})
    origin = _origin(
        pipeline_id=pipeline_id,
        node_id=node_id,
        component_type=str(load_step.get("component_type") or "VP_UPSERT_LOAD"),
        compile_result_id=compile_result_id,
        graph_version_hash=graph_version_hash,
        object_type="write_policy",
    )
    payload = {
        "write_mode": str(cfg.get("write_mode") or "INSERT_ONLY").upper(),
        "conflict_key_columns_json": cfg.get("conflict_key_columns_json") or [],
        "duplicate_within_batch_policy": cfg.get("duplicate_within_batch_policy") or "KEEP_LAST",
        "null_update_policy": cfg.get("null_update_policy") or "KEEP_EXISTING",
        "active_yn": True,
        "metadata_json": origin,
    }
    existing = (
        await db.execute(
            select(ApiConnectorWritePolicy).where(
                ApiConnectorWritePolicy.operation_id == operation_id,
                ApiConnectorWritePolicy.active_yn.is_(True),
            )
        )
    ).scalar_one_or_none()
    was_create = existing is None

    try:
        result = await upsert_write_policy(db, operation_id, payload)
    except (WritePolicyError, TargetTableNotAllowedError, ApiConnectorError) as exc:
        raise MaterializeDomainError(
            "MATERIALIZE_WRITE_POLICY_FAILED",
            str(exc),
            node_id=node_id,
        ) from exc

    policy_id = result.get("write_policy_id")
    if not policy_id:
        row = (
            await db.execute(
                select(ApiConnectorWritePolicy).where(
                    ApiConnectorWritePolicy.operation_id == operation_id,
                    ApiConnectorWritePolicy.active_yn.is_(True),
                )
            )
        ).scalar_one()
        policy_id = row.write_policy_id
        row.metadata_json = _merge_origin_metadata(row.metadata_json, origin)
        await db.flush()
    else:
        row = (
            await db.execute(
                select(ApiConnectorWritePolicy).where(
                    ApiConnectorWritePolicy.write_policy_id == policy_id
                )
            )
        ).scalar_one_or_none()
        if row:
            row.metadata_json = _merge_origin_metadata(row.metadata_json, origin)
            await db.flush()

    if was_create:
        created["write_policy_id"] = policy_id
    else:
        updated["write_policy_id"] = policy_id
    return str(policy_id)


async def _materialize_schedule(
    db: AsyncSession,
    *,
    pipeline_id: str,
    compile_result_id: str,
    graph_version_hash: str | None,
    schedule_artifact: dict[str, Any],
    operation_id: str,
    created: dict[str, Any],
    updated: dict[str, Any],
) -> str:
    node_id = str(schedule_artifact.get("node_id") or "")
    origin = _origin(
        pipeline_id=pipeline_id,
        node_id=node_id,
        component_type=str(schedule_artifact.get("component_type") or "VP_CRON_SCHEDULE"),
        compile_result_id=compile_result_id,
        graph_version_hash=graph_version_hash,
        object_type="schedule",
    )
    schedule_name = f"VP-{pipeline_id[-8:]}-{node_id}"[:200]
    payload = {
        "schedule_name": schedule_name,
        "operation_id": operation_id,
        "schedule_type": str(schedule_artifact.get("schedule_type") or "CRON").upper(),
        "cron_expression": schedule_artifact.get("cron_expression"),
        "timezone": schedule_artifact.get("timezone") or "Asia/Seoul",
        "start_at": schedule_artifact.get("start_at"),
        "end_at": schedule_artifact.get("end_at"),
        "active_yn": False,  # S6-4 safety: never activate
        "retry_enabled_yn": bool(schedule_artifact.get("retry_enabled_yn", False)),
        "max_retry_count": int(schedule_artifact.get("max_retry_count") or 0),
        "retry_interval_minutes": int(schedule_artifact.get("retry_interval_minutes") or 10),
        "metadata_json": origin,
    }

    existing = await _find_by_origin(
        db, DataLoadSchedule, pipeline_id=pipeline_id, node_id=node_id
    )
    try:
        if existing:
            await update_schedule(
                db,
                existing.schedule_id,
                {
                    "schedule_name": schedule_name,
                    "operation_id": operation_id,
                    "schedule_type": payload["schedule_type"],
                    "cron_expression": payload["cron_expression"],
                    "timezone": payload["timezone"],
                    "start_at": payload["start_at"],
                    "end_at": payload["end_at"],
                    "active_yn": False,
                    "retry_enabled_yn": payload["retry_enabled_yn"],
                    "max_retry_count": payload["max_retry_count"],
                    "retry_interval_minutes": payload["retry_interval_minutes"],
                    "metadata_json": _merge_origin_metadata(existing.metadata_json, origin),
                },
            )
            # Force inactive even if update path skipped falsy somehow
            existing.active_yn = False
            existing.metadata_json = _merge_origin_metadata(existing.metadata_json, origin)
            await db.flush()
            schedule_id = existing.schedule_id
            updated["schedule_id"] = schedule_id
        else:
            created_sched = await create_schedule(db, payload)
            schedule_id = created_sched["schedule_id"]
            # belt-and-suspenders
            row = (
                await db.execute(
                    select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id)
                )
            ).scalar_one()
            row.active_yn = False
            row.metadata_json = _merge_origin_metadata(row.metadata_json, origin)
            await db.flush()
            created["schedule_id"] = schedule_id
    except DataLoadSchedulerError as exc:
        code = getattr(exc, "error_code", None) or "MATERIALIZE_SCHEDULE_FAILED"
        raise MaterializeDomainError(str(code), str(exc), node_id=node_id) from exc

    return str(schedule_id)


async def _materialize_r10(
    db: AsyncSession,
    *,
    pipeline_id: str,
    compile_result_id: str,
    graph_version_hash: str | None,
    artifact: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str], list[str]]:
    created: dict[str, Any] = {}
    updated: dict[str, Any] = {}
    skipped: list[str] = []
    warnings: list[str] = []
    objects: dict[str, Any] = {}

    source_step = _step_by_type(artifact, "source")
    transform_step = _step_by_type(artifact, "transform")
    load_step = _step_by_type(artifact, "load")
    schedule_artifact = artifact.get("schedule") if isinstance(artifact.get("schedule"), dict) else None

    if not source_step:
        raise MaterializeDomainError(
            "MATERIALIZE_SOURCE_STEP_MISSING",
            "Compiled artifact has no source step.",
        )
    if not load_step:
        raise MaterializeDomainError(
            "MATERIALIZE_LOAD_STEP_MISSING",
            "Compiled artifact has no load step.",
        )

    load_cfg = dict(load_step.get("config") or {})
    # Prefer top-level write_policy mirror when present
    if isinstance(artifact.get("write_policy"), dict) and artifact["write_policy"]:
        load_cfg = {**load_cfg, **dict(artifact["write_policy"])}

    operation_id = await _materialize_operation(
        db,
        pipeline_id=pipeline_id,
        compile_result_id=compile_result_id,
        graph_version_hash=graph_version_hash,
        source_step=source_step,
        load_cfg=load_cfg,
        created=created,
        updated=updated,
        warnings=warnings,
    )
    objects["operation_id"] = operation_id
    objects["source_node_id"] = source_step.get("node_id")

    if transform_step:
        transform_id = await _materialize_transform(
            db,
            pipeline_id=pipeline_id,
            compile_result_id=compile_result_id,
            graph_version_hash=graph_version_hash,
            transform_step=transform_step,
            operation_id=operation_id,
            created=created,
            updated=updated,
        )
        objects["transform_config_id"] = transform_id
        objects["transform_node_id"] = transform_step.get("node_id")
    else:
        skipped.append("transform_config")

    write_policy_id = await _materialize_write_policy(
        db,
        pipeline_id=pipeline_id,
        compile_result_id=compile_result_id,
        graph_version_hash=graph_version_hash,
        load_step={**load_step, "config": load_cfg},
        operation_id=operation_id,
        created=created,
        updated=updated,
    )
    objects["write_policy_id"] = write_policy_id
    objects["load_node_id"] = load_step.get("node_id")

    if schedule_artifact and schedule_artifact.get("enabled", True):
        schedule_id = await _materialize_schedule(
            db,
            pipeline_id=pipeline_id,
            compile_result_id=compile_result_id,
            graph_version_hash=graph_version_hash,
            schedule_artifact=schedule_artifact,
            operation_id=operation_id,
            created=created,
            updated=updated,
        )
        objects["schedule_id"] = schedule_id
        objects["schedule_node_id"] = schedule_artifact.get("node_id")
    else:
        skipped.append("schedule")

    return objects, created, updated, skipped, warnings


async def _resolve_compile_result(
    db: AsyncSession,
    pipeline_id: str,
    compile_result_id: str | None,
):
    from app.models.entities import VisualPipelineCompileResult

    if compile_result_id:
        row = (
            await db.execute(
                select(VisualPipelineCompileResult).where(
                    VisualPipelineCompileResult.compile_result_id == compile_result_id,
                    VisualPipelineCompileResult.pipeline_id == pipeline_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise MaterializePreconditionError("VISUAL_PIPELINE_COMPILE_REQUIRED")
        if str(row.compile_status or "").upper() != "SUCCESS":
            raise MaterializePreconditionError("VISUAL_PIPELINE_COMPILE_NOT_SUCCESS")
        return row

    row = await get_latest_compile_result_row(db, pipeline_id, status="SUCCESS")
    if row is None:
        # Distinguish failed-only vs no compile
        any_row = await get_latest_compile_result_row(db, pipeline_id)
        if any_row is not None and str(any_row.compile_status or "").upper() != "SUCCESS":
            raise MaterializePreconditionError("VISUAL_PIPELINE_COMPILE_NOT_SUCCESS")
        raise MaterializePreconditionError("VISUAL_PIPELINE_COMPILE_REQUIRED")
    return row


async def materialize_visual_pipeline(
    db: AsyncSession,
    pipeline_id: str,
    *,
    compile_result_id: str | None = None,
    mode: str = "UPSERT",
) -> dict[str, Any]:
    mode_u = str(mode or "UPSERT").strip().upper() or "UPSERT"
    if mode_u != "UPSERT":
        raise ValueError("MATERIALIZE_MODE_MUST_BE_UPSERT")

    definition = await _get_visual_definition(db, pipeline_id)
    # raises LookupError if missing

    detail = await get_visual_pipeline(db, pipeline_id)
    graph = detail.get("graph") if isinstance(detail.get("graph"), dict) else {}
    current_hash = calculate_graph_version_hash(graph)

    compile_row = await _resolve_compile_result(db, pipeline_id, compile_result_id)
    if (compile_row.graph_version_hash or "") != current_hash:
        raise MaterializePreconditionError("VISUAL_PIPELINE_COMPILE_STALE")

    artifact = compile_row.compiled_artifact_json
    if not isinstance(artifact, dict):
        raise MaterializePreconditionError("VISUAL_PIPELINE_COMPILE_REQUIRED")

    # Snapshot sync status — must remain unchanged after materialize
    sync_before = definition.current_sync_status

    objects: dict[str, Any] = {}
    created: dict[str, Any] = {}
    updated: dict[str, Any] = {}
    skipped: list[str] = []
    warnings: list[str] = []
    issues: list[dict[str, Any]] = []
    status = "SUCCESS"
    error_message: str | None = None

    try:
        async with db.begin_nested():
            objects, created, updated, skipped, warnings = await _materialize_r10(
                db,
                pipeline_id=pipeline_id,
                compile_result_id=compile_row.compile_result_id,
                graph_version_hash=compile_row.graph_version_hash,
                artifact=artifact,
            )
    except MaterializeDomainError as exc:
        status = "FAILED"
        issues = [exc.to_issue()]
        error_message = exc.code
        objects = {}
        created = {}
        updated = {}
        skipped = []
    except (ApiConnectorError, WritePolicyError, DataLoadSchedulerError, TargetTableNotAllowedError) as exc:
        status = "FAILED"
        code = getattr(exc, "error_code", None) or type(exc).__name__
        issues = [
            {
                "severity": "ERROR",
                "code": str(code),
                "message": str(exc),
                "phase": "MATERIALIZE",
            }
        ]
        error_message = str(code)
        objects = {}
        created = {}
        updated = {}
        skipped = []

    now = utc_now()
    result_row = VisualPipelineMaterializationResult(
        materialization_result_id=_new_materialization_result_id(),
        pipeline_id=pipeline_id,
        compile_result_id=compile_row.compile_result_id,
        materialization_status=status,
        graph_version_hash=compile_row.graph_version_hash,
        materialization_version=MATERIALIZATION_VERSION,
        objects_json=objects,
        created_json=created,
        updated_json=updated,
        skipped_json=skipped,
        issues_json=issues,
        warnings_json=warnings,
        activation=ACTIVATION_NOT_REQUESTED,
        run_created=False,
        error_message=error_message,
        created_at=now,
    )
    db.add(result_row)

    # Never change sync status
    definition.current_sync_status = sync_before
    await db.flush()

    return _row_to_response(result_row)


async def get_latest_visual_pipeline_materialization_result(
    db: AsyncSession,
    pipeline_id: str,
) -> dict[str, Any]:
    await _get_visual_definition(db, pipeline_id)

    row = (
        await db.execute(
            select(VisualPipelineMaterializationResult)
            .where(VisualPipelineMaterializationResult.pipeline_id == pipeline_id)
            .order_by(VisualPipelineMaterializationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise LookupError("MATERIALIZATION_RESULT_NOT_FOUND")
    return _row_to_response(row)
