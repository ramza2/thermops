"""R11-S7-1 Visual Pipeline Manual Run PoC.

Wraps R10 run_load for a materialized operation. Execution occurs only via POST /runs.
Does not activate schedules, call due worker, or change sync/materialization status.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    ApiConnectorOperation,
    ApiConnectorTransformConfig,
    ApiConnectorWritePolicy,
    VisualPipelineCompileResult,
    VisualPipelineMaterializationResult,
    VisualPipelineRun,
)
from app.services.api_connector_service import ApiConnectorError, run_load
from app.services.visual_pipeline.compile_preview_service import calculate_graph_version_hash
from app.services.visual_pipeline.compile_result_service import (
    SYNC_IN_SYNC,
    get_latest_compile_result_row,
)
from app.services.visual_pipeline.visual_pipeline_service import (
    VISUAL_PIPELINE_KIND,
    _get_visual_definition,
    get_visual_pipeline,
)

RUN_VERSION = "R11-S7-1"
MANUAL_MODE = "MANUAL"
EXECUTION_SYNC = "SYNC"
MANUAL_MAX_PAGES = 1
MANUAL_MAX_LIMIT = 100

SECRET_KEY_PATTERN = re.compile(
    r"(authorization|token|api[_-]?key|password|secret|credential)",
    re.IGNORECASE,
)

ALLOWED_OVERRIDE_KEYS = frozenset(
    {
        "start_at",
        "end_at",
        "limit",
        "page",
        "page_no",
        "page_size",
        "size",
        "offset",
    }
)


class RunPreconditionError(Exception):
    """HTTP 409 — no run row, no R10 execution."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(self.message)


class RunRequestValidationError(Exception):
    """HTTP 400 — invalid request payload."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(self.message)


def _new_visual_run_id() -> str:
    return f"VPR-{uuid4().hex[:8].upper()}"


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    text = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if text and not text.endswith("Z") and "+" not in text and "T" in text:
        return f"{text}Z"
    return text


def _issue(
    code: str,
    message: str,
    *,
    step_id: str | None = None,
    node_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "severity": "ERROR",
        "code": code,
        "message": message,
        "phase": "RUN",
        "step_id": step_id,
        "node_id": node_id,
        "details": details or {},
    }


def _sanitize_error_message(msg: str | None) -> str | None:
    if not msg:
        return None
    text = str(msg)
    for marker in ("Bearer ", "Authorization:", "password=", "api_key="):
        if marker.lower() in text.lower():
            return "Run execution failed (details redacted)."
    return text[:500]


def _origin_pipeline_id(metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    origin = metadata.get("visual_pipeline_origin")
    if not isinstance(origin, dict):
        return None
    pid = origin.get("pipeline_id")
    return str(pid) if pid else None


def _validate_request_body(body: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(body or {})
    mode = str(payload.get("mode") or MANUAL_MODE).strip().upper() or MANUAL_MODE
    if mode != MANUAL_MODE:
        raise RunRequestValidationError("RUN_MODE_NOT_SUPPORTED", "Only mode=MANUAL is supported.")

    dry_run = payload.get("dry_run")
    if dry_run is True:
        raise RunRequestValidationError("RUN_DRY_RUN_NOT_SUPPORTED", "dry_run=true is not supported.")

    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    override = params.get("request_params_override")
    if override is not None and not isinstance(override, dict):
        raise RunRequestValidationError("RUN_INVALID_PARAMS", "request_params_override must be an object.")

    sanitized_override: dict[str, Any] = {}
    for key, value in (override or {}).items():
        key_s = str(key)
        if SECRET_KEY_PATTERN.search(key_s):
            raise RunRequestValidationError(
                "RUN_SECRET_INLINE_FORBIDDEN",
                f"request_params_override key '{key_s}' is not allowed.",
            )
        if key_s not in ALLOWED_OVERRIDE_KEYS:
            raise RunRequestValidationError(
                "RUN_PARAM_NOT_ALLOWED",
                f"request_params_override key '{key_s}' is not in the allowlist.",
            )
        sanitized_override[key_s] = value

    max_pages = params.get("max_pages", MANUAL_MAX_PAGES)
    try:
        max_pages_i = int(max_pages)
    except (TypeError, ValueError) as exc:
        raise RunRequestValidationError("RUN_INVALID_PARAMS", "max_pages must be an integer.") from exc
    if max_pages_i < 1 or max_pages_i > MANUAL_MAX_PAGES:
        raise RunRequestValidationError(
            "RUN_INVALID_PARAMS",
            f"max_pages must be between 1 and {MANUAL_MAX_PAGES}.",
        )

    limit = params.get("limit", MANUAL_MAX_LIMIT)
    try:
        limit_i = int(limit)
    except (TypeError, ValueError) as exc:
        raise RunRequestValidationError("RUN_INVALID_PARAMS", "limit must be an integer.") from exc
    if limit_i < 1 or limit_i > MANUAL_MAX_LIMIT:
        raise RunRequestValidationError(
            "RUN_INVALID_PARAMS",
            f"limit must be between 1 and {MANUAL_MAX_LIMIT}.",
        )

    return {
        "materialization_result_id": payload.get("materialization_result_id"),
        "compile_result_id": payload.get("compile_result_id"),
        "mode": mode,
        "params": {
            "request_params_override": sanitized_override,
            "max_pages": max_pages_i,
            "limit": limit_i,
        },
    }


async def _resolve_materialization_row(
    db: AsyncSession,
    pipeline_id: str,
    materialization_result_id: str | None,
) -> VisualPipelineMaterializationResult:
    if materialization_result_id:
        row = (
            await db.execute(
                select(VisualPipelineMaterializationResult).where(
                    VisualPipelineMaterializationResult.materialization_result_id
                    == materialization_result_id,
                    VisualPipelineMaterializationResult.pipeline_id == pipeline_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise RunPreconditionError("RUN_MATERIALIZATION_REQUIRED")
        if str(row.materialization_status or "").upper() != "SUCCESS":
            raise RunPreconditionError("RUN_MATERIALIZATION_NOT_SUCCESS")
        return row

    row = (
        await db.execute(
            select(VisualPipelineMaterializationResult)
            .where(
                VisualPipelineMaterializationResult.pipeline_id == pipeline_id,
                VisualPipelineMaterializationResult.materialization_status == "SUCCESS",
            )
            .order_by(VisualPipelineMaterializationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None:
        return row

    any_row = (
        await db.execute(
            select(VisualPipelineMaterializationResult)
            .where(VisualPipelineMaterializationResult.pipeline_id == pipeline_id)
            .order_by(VisualPipelineMaterializationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if any_row is not None and str(any_row.materialization_status or "").upper() != "SUCCESS":
        raise RunPreconditionError("RUN_MATERIALIZATION_NOT_SUCCESS")
    raise RunPreconditionError("RUN_MATERIALIZATION_REQUIRED")


async def _resolve_compile_row(
    db: AsyncSession,
    pipeline_id: str,
    compile_result_id: str | None,
    *,
    materialization_row: VisualPipelineMaterializationResult,
) -> VisualPipelineCompileResult:
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
            raise RunPreconditionError("RUN_COMPILE_REQUIRED")
        if str(row.compile_status or "").upper() != "SUCCESS":
            raise RunPreconditionError("RUN_COMPILE_NOT_SUCCESS")
        if row.compile_result_id != materialization_row.compile_result_id:
            raise RunPreconditionError("RUN_MATERIALIZATION_STALE")
        return row

    row = (
        await db.execute(
            select(VisualPipelineCompileResult).where(
                VisualPipelineCompileResult.compile_result_id == materialization_row.compile_result_id,
                VisualPipelineCompileResult.pipeline_id == pipeline_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise RunPreconditionError("RUN_COMPILE_REQUIRED")
    if str(row.compile_status or "").upper() != "SUCCESS":
        raise RunPreconditionError("RUN_COMPILE_NOT_SUCCESS")
    return row


async def _assert_no_running(db: AsyncSession, pipeline_id: str) -> None:
    count = (
        await db.execute(
            select(func.count())
            .select_from(VisualPipelineRun)
            .where(
                VisualPipelineRun.pipeline_id == pipeline_id,
                VisualPipelineRun.run_status == "RUNNING",
            )
        )
    ).scalar_one()
    if int(count or 0) > 0:
        raise RunPreconditionError("RUN_CONCURRENT_RUN_EXISTS")


async def _load_r10_row(
    db: AsyncSession,
    model: type,
    row_id: str,
    *,
    id_field: str,
    pipeline_id: str,
) -> Any:
    row = (
        await db.execute(select(model).where(getattr(model, id_field) == row_id))
    ).scalar_one_or_none()
    if row is None:
        raise RunPreconditionError("RUN_OBJECT_NOT_FOUND")
    meta = getattr(row, "metadata_json", None)
    if meta is not None:
        origin_pid = _origin_pipeline_id(meta)
        if origin_pid and origin_pid != pipeline_id:
            raise RunPreconditionError("RUN_OBJECT_STALE")
    return row


async def _validate_preconditions(
    db: AsyncSession,
    pipeline_id: str,
    request: dict[str, Any],
) -> tuple[Any, VisualPipelineCompileResult, VisualPipelineMaterializationResult, dict[str, Any], str]:
    defn = await _get_visual_definition(db, pipeline_id)
    if (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")

    detail = await get_visual_pipeline(db, pipeline_id)
    graph = detail.get("graph") if isinstance(detail.get("graph"), dict) else {}
    current_hash = calculate_graph_version_hash(graph)

    if (defn.current_sync_status or "") != SYNC_IN_SYNC:
        raise RunPreconditionError("RUN_COMPILE_STALE")

    await _assert_no_running(db, pipeline_id)

    mat_row = await _resolve_materialization_row(
        db, pipeline_id, request.get("materialization_result_id")
    )
    compile_row = await _resolve_compile_row(
        db,
        pipeline_id,
        request.get("compile_result_id"),
        materialization_row=mat_row,
    )

    compile_hash = compile_row.graph_version_hash or ""
    mat_hash = mat_row.graph_version_hash or ""
    if current_hash != compile_hash or current_hash != mat_hash:
        raise RunPreconditionError("RUN_MATERIALIZATION_STALE")

    objects = dict(mat_row.objects_json or {})
    operation_id = str(objects.get("operation_id") or "").strip()
    write_policy_id = str(objects.get("write_policy_id") or "").strip()
    if not operation_id or not write_policy_id:
        raise RunPreconditionError("RUN_OBJECT_NOT_FOUND")

    op = await _load_r10_row(
        db, ApiConnectorOperation, operation_id, id_field="operation_id", pipeline_id=pipeline_id
    )
    wp = await _load_r10_row(
        db,
        ApiConnectorWritePolicy,
        write_policy_id,
        id_field="write_policy_id",
        pipeline_id=pipeline_id,
    )
    if str(wp.operation_id) != str(op.operation_id):
        raise RunPreconditionError("RUN_OBJECT_STALE")

    artifact = compile_row.compiled_artifact_json if isinstance(compile_row.compiled_artifact_json, dict) else {}
    meta = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    has_transform = bool(meta.get("has_transform"))
    transform_id = objects.get("transform_config_id")
    if has_transform:
        if not transform_id:
            raise RunPreconditionError("RUN_OBJECT_NOT_FOUND")
        await _load_r10_row(
            db,
            ApiConnectorTransformConfig,
            str(transform_id),
            id_field="transform_config_id",
            pipeline_id=pipeline_id,
        )
    elif transform_id:
        await _load_r10_row(
            db,
            ApiConnectorTransformConfig,
            str(transform_id),
            id_field="transform_config_id",
            pipeline_id=pipeline_id,
        )

    pattern = str(meta.get("pattern") or "")
    if pattern and pattern not in {"REST_TRANSFORM_UPSERT", "REST_UPSERT_DIRECT"}:
        raise RunPreconditionError("RUN_UNSUPPORTED_PIPELINE_SHAPE")

    return defn, compile_row, mat_row, objects, current_hash


def _build_runtime_params(request: dict[str, Any]) -> dict[str, Any]:
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    runtime = dict(params.get("request_params_override") or {})
    limit = int(params.get("limit") or MANUAL_MAX_LIMIT)
    runtime["limit"] = min(limit, MANUAL_MAX_LIMIT)
    return runtime


def _row_to_response(row: VisualPipelineRun) -> dict[str, Any]:
    result_json = dict(row.result_json or {})
    summary = result_json.get("summary") if isinstance(result_json.get("summary"), dict) else result_json
    return {
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "mode": row.mode,
        "execution_mode": row.execution_mode,
        "run_status": row.run_status,
        "compile_result_id": row.compile_result_id,
        "materialization_result_id": row.materialization_result_id,
        "graph_version_hash": row.graph_version_hash,
        "load_run_id": row.load_run_id,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "result": summary,
        "issues": list(row.issues_json or []),
        "error_message": row.error_message,
        "schedule_active_changed": False,
        "current_sync_status_changed": False,
        "persisted": True,
    }


def _summary_row(row: VisualPipelineRun) -> dict[str, Any]:
    result_json = dict(row.result_json or {})
    summary = result_json.get("summary") if isinstance(result_json.get("summary"), dict) else {}
    return {
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "mode": row.mode,
        "execution_mode": row.execution_mode,
        "run_status": row.run_status,
        "compile_result_id": row.compile_result_id,
        "materialization_result_id": row.materialization_result_id,
        "load_run_id": row.load_run_id,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "created_at": _iso(row.created_at),
        "result_summary": {
            "target_table": summary.get("target_table"),
            "inserted_count": summary.get("inserted_count"),
            "updated_count": summary.get("updated_count"),
            "skipped_count": summary.get("skipped_count"),
            "failed_count": summary.get("failed_count"),
        },
    }


async def create_manual_run(
    db: AsyncSession,
    pipeline_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = _validate_request_body(body)
    defn, compile_row, mat_row, objects, current_hash = await _validate_preconditions(
        db, pipeline_id, request
    )
    sync_before = defn.current_sync_status

    operation_id = str(objects["operation_id"])
    write_policy_id = str(objects["write_policy_id"])
    transform_config_id = objects.get("transform_config_id")

    op = (
        await db.execute(
            select(ApiConnectorOperation).where(ApiConnectorOperation.operation_id == operation_id)
        )
    ).scalar_one()
    target_table = op.target_table

    started = utc_now()
    run_row = VisualPipelineRun(
        visual_run_id=_new_visual_run_id(),
        pipeline_id=pipeline_id,
        compile_result_id=compile_row.compile_result_id,
        materialization_result_id=mat_row.materialization_result_id,
        graph_version_hash=current_hash,
        mode=MANUAL_MODE,
        execution_mode=EXECUTION_SYNC,
        run_status="RUNNING",
        request_json=request,
        result_json={},
        issues_json=[],
        started_at=started,
        created_at=started,
    )
    db.add(run_row)
    await db.flush()

    runtime_params = _build_runtime_params(request)
    issues: list[dict[str, Any]] = []
    load_result: dict[str, Any] | None = None
    run_status = "FAILED"
    error_message: str | None = None

    try:
        load_result = await run_load(
            db,
            operation_id,
            runtime_params,
            called_by="visual_pipeline_manual_run",
            dry_run=False,
        )
        status = str(load_result.get("status") or "SUCCESS").upper()
        error_count = int(load_result.get("error_count") or 0)
        if status == "FAILED":
            run_status = "FAILED"
            error_message = "Load run failed"
            issues.append(
                _issue("RUN_WRITE_POLICY_FAILED", "R10 load run returned FAILED status.", step_id="write")
            )
        elif status == "WARNING" or error_count > 0:
            run_status = "PARTIAL"
        else:
            run_status = "SUCCESS"
    except ApiConnectorError as exc:
        code = getattr(exc, "error_code", None) or "RUN_REST_CALL_FAILED"
        if "EXTRACT" in str(code).upper() or "ITEM" in str(code).upper():
            issue_code = "RUN_RESPONSE_EXTRACTION_FAILED"
        elif "WRITE" in str(code).upper() or "UPSERT" in str(code).upper():
            issue_code = "RUN_WRITE_POLICY_FAILED"
        elif "TRANSFORM" in str(code).upper():
            issue_code = "RUN_TRANSFORM_FAILED"
        else:
            issue_code = "RUN_REST_CALL_FAILED"
        issues.append(_issue(issue_code, str(exc), step_id="rest_call"))
        error_message = _sanitize_error_message(str(exc))
        run_status = "FAILED"
    except Exception as exc:  # noqa: BLE001 — persist FAILED run row
        issues.append(_issue("RUN_UNKNOWN_ERROR", str(exc), step_id="run"))
        error_message = _sanitize_error_message(str(exc))
        run_status = "FAILED"

    finished = utc_now()
    fetched = int((load_result or {}).get("api_item_count") or (load_result or {}).get("raw_item_count") or 0)
    summary = {
        "operation_id": operation_id,
        "write_policy_id": write_policy_id,
        "transform_config_id": transform_config_id,
        "target_table": target_table,
        "fetched_count": fetched,
        "inserted_count": int((load_result or {}).get("inserted_count") or 0),
        "updated_count": int((load_result or {}).get("updated_count") or 0),
        "skipped_count": int((load_result or {}).get("skipped_count") or 0),
        "failed_count": int((load_result or {}).get("error_count") or 0),
    }

    run_row.run_status = run_status
    run_row.load_run_id = (load_result or {}).get("load_run_id")
    run_row.finished_at = finished
    run_row.issues_json = issues
    run_row.error_message = error_message
    run_row.result_json = {
        "summary": summary,
        "load_result": {
            k: load_result.get(k)
            for k in (
                "load_run_id",
                "status",
                "inserted_count",
                "updated_count",
                "skipped_count",
                "error_count",
                "api_item_count",
            )
            if load_result and k in load_result
        },
        "run_version": RUN_VERSION,
    }
    await db.flush()

    defn.current_sync_status = sync_before
    await db.flush()

    return _row_to_response(run_row)


async def list_visual_pipeline_runs(
    db: AsyncSession,
    pipeline_id: str,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    await _get_visual_definition(db, pipeline_id)
    lim = max(1, min(int(limit), 100))
    rows = (
        await db.execute(
            select(VisualPipelineRun)
            .where(VisualPipelineRun.pipeline_id == pipeline_id)
            .order_by(VisualPipelineRun.created_at.desc())
            .limit(lim)
        )
    ).scalars().all()
    return {"items": [_summary_row(r) for r in rows], "limit": lim}


async def get_visual_pipeline_run(
    db: AsyncSession,
    pipeline_id: str,
    visual_run_id: str,
) -> dict[str, Any]:
    await _get_visual_definition(db, pipeline_id)
    row = (
        await db.execute(
            select(VisualPipelineRun).where(
                VisualPipelineRun.pipeline_id == pipeline_id,
                VisualPipelineRun.visual_run_id == visual_run_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise LookupError("VISUAL_PIPELINE_RUN_NOT_FOUND")
    return _row_to_response(row)
