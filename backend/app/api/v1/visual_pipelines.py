"""R11 Visual Pipeline Studio API — catalog (S1) + graph CRUD (S2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok
from app.services.visual_pipeline.component_catalog_service import (
    get_component,
    list_components,
    list_connection_rules,
)
from app.services.visual_pipeline.graph_schema_service import VisualPipelineGraphError
from app.services.visual_pipeline.visual_pipeline_service import (
    VisualPipelineError,
    archive_visual_pipeline,
    create_visual_pipeline,
    create_visual_pipeline_version,
    get_visual_pipeline,
    get_visual_pipeline_version,
    list_visual_pipeline_versions,
    list_visual_pipelines,
    update_visual_pipeline,
)

router = APIRouter(tags=["Visual Pipeline Studio"])


class VisualPipelineCreateBody(BaseModel):
    pipeline_name: str
    description: str | None = None
    graph: Any = None
    created_by: str | None = None


class VisualPipelineUpdateBody(BaseModel):
    pipeline_name: str | None = None
    description: str | None = None
    status: str | None = None
    graph: Any = None
    change_summary: str | None = None
    create_version: bool = False


class VisualPipelineVersionCreateBody(BaseModel):
    change_summary: str | None = Field(default=None)


class VisualPipelineValidateGraphBody(BaseModel):
    graph: Any = None
    pipeline_id: str | None = None
    validation_level: str = Field(default="BASIC", description="BASIC | STRICT")


class VisualPipelineValidateBody(BaseModel):
    graph: Any = None
    validation_level: str = Field(default="BASIC", description="BASIC | STRICT")


class VisualPipelineCompilePreviewBody(BaseModel):
    validation_level: str = Field(default="STRICT", description="STRICT only (R11-S6-1)")


class VisualPipelineCompileBody(BaseModel):
    validation_level: str = Field(default="STRICT", description="STRICT only (R11-S6-2)")


class VisualPipelineMaterializeBody(BaseModel):
    compile_result_id: str | None = None
    mode: str = Field(default="UPSERT", description="UPSERT only (R11-S6-4)")


class VisualPipelineManualRunParamsBody(BaseModel):
    request_params_override: dict[str, Any] | None = None
    max_pages: int | None = Field(default=1, ge=1, le=1)
    limit: int | None = Field(default=100, ge=1, le=100)


class VisualPipelineManualRunBody(BaseModel):
    materialization_result_id: str | None = None
    compile_result_id: str | None = None
    mode: str = Field(default="MANUAL", description="MANUAL only (R11-S7-1)")
    dry_run: bool = False
    idempotency_key: str | None = None
    params: VisualPipelineManualRunParamsBody | None = None


class VisualPipelineScheduleActivationBody(BaseModel):
    materialization_result_id: str | None = None
    compile_result_id: str | None = None


# --- S1 Catalog (static paths before /{pipeline_id}) ---


@router.get("/visual-pipelines/components")
async def get_visual_pipeline_components(
    status: str | None = Query(default=None, description="ACTIVE | DISABLED | EXPERIMENTAL"),
    category: str | None = Query(default=None, description="DATA_INPUT | TRANSFORM | LOAD | ..."),
):
    data = list_components(status=status, category=category)
    return ok(data)


@router.get("/visual-pipelines/components/{component_type}")
async def get_visual_pipeline_component(component_type: str):
    try:
        item = get_component(component_type)
    except LookupError:
        raise HTTPException(status_code=404, detail="COMPONENT_NOT_FOUND") from None
    return ok(item)


@router.get("/visual-pipelines/connection-rules")
async def get_visual_pipeline_connection_rules():
    return ok(list_connection_rules())


@router.post("/visual-pipelines/validate-graph")
async def post_validate_visual_pipeline_graph(body: VisualPipelineValidateGraphBody):
    """Validate a client graph. Does not write to DB."""
    from app.services.visual_pipeline.graph_validation_service import validate_visual_pipeline_graph

    result = validate_visual_pipeline_graph(
        body.graph,
        validation_level=body.validation_level,
        pipeline_id=body.pipeline_id,
    )
    return ok(result)


# --- S2 CRUD / versions ---


@router.get("/visual-pipelines")
async def get_visual_pipelines(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    data = await list_visual_pipelines(
        db,
        status=status,
        q=q,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ok(data)


@router.post("/visual-pipelines")
async def post_visual_pipeline(body: VisualPipelineCreateBody, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_visual_pipeline(db, body.model_dump())
    except VisualPipelineGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisualPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Visual Pipeline이 생성되었습니다.")


@router.get("/visual-pipelines/{pipeline_id}/versions")
async def get_visual_pipeline_versions(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        data = await list_visual_pipeline_versions(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(data)


@router.post("/visual-pipelines/{pipeline_id}/versions")
async def post_visual_pipeline_version(
    pipeline_id: str,
    body: VisualPipelineVersionCreateBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    payload = body.model_dump() if body else {}
    try:
        item = await create_visual_pipeline_version(
            db, pipeline_id, change_summary=payload.get("change_summary")
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except VisualPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Visual Pipeline version이 생성되었습니다.")


@router.get("/visual-pipelines/{pipeline_id}/versions/{version_id}")
async def get_visual_pipeline_version_detail(
    pipeline_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await get_visual_pipeline_version(db, pipeline_id, version_id)
    except LookupError as exc:
        detail = str(exc) if str(exc) else "VISUAL_PIPELINE_VERSION_NOT_FOUND"
        raise HTTPException(status_code=404, detail=detail) from None
    return ok(item)


@router.post("/visual-pipelines/{pipeline_id}/archive")
async def post_archive_visual_pipeline(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await archive_visual_pipeline(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(item, message="Visual Pipeline이 보관 처리되었습니다.")


@router.post("/visual-pipelines/{pipeline_id}/validate")
async def post_validate_visual_pipeline(
    pipeline_id: str,
    body: VisualPipelineValidateBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Validate body graph or saved current_graph_json. Does not write to DB."""
    from app.services.visual_pipeline.graph_validation_service import validate_visual_pipeline_graph

    payload = body.model_dump() if body else {}
    graph = payload.get("graph")
    level = payload.get("validation_level") or "BASIC"
    if graph is None:
        try:
            detail = await get_visual_pipeline(db, pipeline_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
        graph = detail.get("graph")
    result = validate_visual_pipeline_graph(graph, validation_level=level, pipeline_id=pipeline_id)
    return ok(result)


@router.post("/visual-pipelines/{pipeline_id}/compile-preview")
async def post_compile_visual_pipeline_preview(
    pipeline_id: str,
    body: VisualPipelineCompilePreviewBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Compile saved current_graph_json to artifact preview. No DB write / status update."""
    from app.services.visual_pipeline.compile_preview_service import compile_visual_pipeline_preview

    payload = body.model_dump() if body else {}
    level = str(payload.get("validation_level") or "STRICT").strip().upper() or "STRICT"
    if level != "STRICT":
        raise HTTPException(
            status_code=400,
            detail="COMPILE_PREVIEW_VALIDATION_LEVEL_MUST_BE_STRICT",
        )

    try:
        detail = await get_visual_pipeline(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None

    graph = detail.get("graph")
    result = compile_visual_pipeline_preview(pipeline_id, graph, validation_level=level)
    return ok(result)


@router.post("/visual-pipelines/{pipeline_id}/compile")
async def post_compile_visual_pipeline(
    pipeline_id: str,
    body: VisualPipelineCompileBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Compile saved graph, persist result, update sync status. No R10 materialization."""
    from app.services.visual_pipeline.compile_result_service import compile_and_persist_visual_pipeline

    payload = body.model_dump() if body else {}
    level = str(payload.get("validation_level") or "STRICT").strip().upper() or "STRICT"
    if level != "STRICT":
        raise HTTPException(
            status_code=400,
            detail="COMPILE_VALIDATION_LEVEL_MUST_BE_STRICT",
        )

    try:
        result = await compile_and_persist_visual_pipeline(
            db,
            pipeline_id,
            validation_level=level,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(result)


@router.get("/visual-pipelines/{pipeline_id}/compile-result")
async def get_compile_visual_pipeline_result(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return latest compile result for a visual pipeline."""
    from app.services.visual_pipeline.compile_result_service import (
        get_latest_visual_pipeline_compile_result,
    )

    try:
        result = await get_latest_visual_pipeline_compile_result(db, pipeline_id)
    except LookupError as exc:
        detail = str(exc) if str(exc) else "COMPILE_RESULT_NOT_FOUND"
        if detail == "VISUAL_PIPELINE_NOT_FOUND":
            raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
        raise HTTPException(status_code=404, detail="COMPILE_RESULT_NOT_FOUND") from None
    return ok(result)


@router.post("/visual-pipelines/{pipeline_id}/materialize")
async def post_materialize_visual_pipeline(
    pipeline_id: str,
    body: VisualPipelineMaterializeBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Materialize SUCCESS compile artifact into R10 config rows. No run/activation."""
    from app.services.visual_pipeline.materialization_service import (
        MaterializePreconditionError,
        materialize_visual_pipeline,
    )

    payload = body.model_dump() if body else {}
    mode = str(payload.get("mode") or "UPSERT").strip().upper() or "UPSERT"
    if mode != "UPSERT":
        raise HTTPException(status_code=400, detail="MATERIALIZE_MODE_MUST_BE_UPSERT")

    try:
        result = await materialize_visual_pipeline(
            db,
            pipeline_id,
            compile_result_id=payload.get("compile_result_id"),
            mode=mode,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except MaterializePreconditionError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return ok(result)


@router.get("/visual-pipelines/{pipeline_id}/materialization-result")
async def get_materialize_visual_pipeline_result(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return latest materialization result for a visual pipeline."""
    from app.services.visual_pipeline.materialization_service import (
        get_latest_visual_pipeline_materialization_result,
    )

    try:
        result = await get_latest_visual_pipeline_materialization_result(db, pipeline_id)
    except LookupError as exc:
        detail = str(exc) if str(exc) else "MATERIALIZATION_RESULT_NOT_FOUND"
        if detail == "VISUAL_PIPELINE_NOT_FOUND":
            raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
        raise HTTPException(status_code=404, detail="MATERIALIZATION_RESULT_NOT_FOUND") from None
    return ok(result)


@router.post("/visual-pipelines/{pipeline_id}/runs")
async def post_visual_pipeline_manual_run(
    pipeline_id: str,
    background_tasks: BackgroundTasks,
    body: VisualPipelineManualRunBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Manual Run (R11-S7-6): accept BACKGROUND job; executor=background_tasks|worker."""
    from app.services.visual_pipeline.manual_run_service import (
        EXECUTOR_BACKGROUND_TASKS,
        RunPreconditionError,
        RunRequestValidationError,
        create_manual_run,
        execute_visual_pipeline_run_background,
        resolve_vp_run_executor,
    )

    payload = body.model_dump() if body else {}
    if payload.get("params") is None:
        payload["params"] = {}
    executor = resolve_vp_run_executor()
    try:
        result = await create_manual_run(db, pipeline_id, payload, executor=executor)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except RunPreconditionError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from None
    except RunRequestValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from None

    if result.get("executor", executor) == EXECUTOR_BACKGROUND_TASKS:
        background_tasks.add_task(execute_visual_pipeline_run_background, result["visual_run_id"])
    return JSONResponse(
        status_code=202,
        content=jsonable_encoder(
            accepted(result, message="Visual Pipeline Manual Run이 접수되었습니다.")
        ),
    )


@router.get("/visual-pipelines/{pipeline_id}/runs")
async def get_visual_pipeline_runs(
    pipeline_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.services.visual_pipeline.manual_run_service import list_visual_pipeline_runs

    try:
        result = await list_visual_pipeline_runs(db, pipeline_id, limit=limit)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(result)


@router.get("/visual-pipelines/{pipeline_id}/runs/{run_id}")
async def get_visual_pipeline_run_detail(
    pipeline_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    from app.services.visual_pipeline.manual_run_service import get_visual_pipeline_run

    try:
        result = await get_visual_pipeline_run(db, pipeline_id, run_id)
    except LookupError as exc:
        detail = str(exc) if str(exc) else "VISUAL_PIPELINE_RUN_NOT_FOUND"
        if detail == "VISUAL_PIPELINE_NOT_FOUND":
            raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_RUN_NOT_FOUND") from None
    return ok(result)


@router.post("/visual-pipelines/{pipeline_id}/schedule-activations")
async def post_visual_pipeline_schedule_activation(
    pipeline_id: str,
    body: VisualPipelineScheduleActivationBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Activate schedule (R11-S7-8). Does not call run_load or create run rows."""
    from app.services.visual_pipeline.schedule_activation_service import (
        ActivationPreconditionError,
        activate_schedule,
    )

    payload = body.model_dump() if body else {}
    try:
        result = await activate_schedule(db, pipeline_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except ActivationPreconditionError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from None
    return ok(result, message="Visual Pipeline Schedule Activation이 완료되었습니다.")


@router.get("/visual-pipelines/{pipeline_id}/schedule-activations/current")
async def get_visual_pipeline_schedule_activation_current(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    from app.services.visual_pipeline.schedule_activation_service import get_current_activation

    try:
        result = await get_current_activation(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(result)


@router.get("/visual-pipelines/{pipeline_id}/schedule-activations")
async def get_visual_pipeline_schedule_activations(
    pipeline_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.services.visual_pipeline.schedule_activation_service import list_activations

    try:
        result = await list_activations(db, pipeline_id, limit=limit)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(result)


@router.post("/visual-pipelines/{pipeline_id}/schedule-activations/{activation_id}/deactivate")
async def post_visual_pipeline_schedule_deactivation(
    pipeline_id: str,
    activation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deactivate schedule. Idempotent if already inactive. Does not cancel queued runs."""
    from app.services.visual_pipeline.schedule_activation_service import (
        ActivationNotFoundError,
        ActivationPreconditionError,
        deactivate_schedule,
    )

    try:
        result = await deactivate_schedule(db, pipeline_id, activation_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except ActivationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from None
    except ActivationPreconditionError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from None
    return ok(result, message="Visual Pipeline Schedule Activation이 비활성화되었습니다.")


@router.get("/visual-pipelines/{pipeline_id}")
async def get_visual_pipeline_detail(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_visual_pipeline(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(item)


@router.put("/visual-pipelines/{pipeline_id}")
async def put_visual_pipeline(
    pipeline_id: str,
    body: VisualPipelineUpdateBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await update_visual_pipeline(db, pipeline_id, body.model_dump(exclude_unset=True))
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except VisualPipelineGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisualPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Visual Pipeline이 수정되었습니다.")
