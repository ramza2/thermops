from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok
from app.schemas.api import (
    PipelineDefinitionCreate,
    PipelineDefinitionRunRequest,
    PipelineDefinitionUpdate,
    PipelineDefinitionValidateRequest,
)
from app.services.pipeline_builder_service import (
    activate_pipeline_definition,
    archive_pipeline_definition,
    create_pipeline_definition,
    get_node_config_options,
    get_pipeline_definition,
    get_pipeline_template,
    list_pipeline_definitions,
    list_pipeline_templates,
    runtime_preview,
    update_pipeline_definition,
    validate_pipeline_definition,
)
from app.services.pipeline_execution_service import (
    get_pipeline_run_link,
    list_pipeline_definition_runs,
    list_pipeline_run_links,
    run_pipeline_definition,
    sync_pipeline_run_link_status,
)

router = APIRouter(tags=["Pipeline Builder"])


@router.get("/pipeline-templates")
async def get_pipeline_templates(
    status: str | None = Query(default=None),
    pipeline_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    items = await list_pipeline_templates(
        db, status=status, pipeline_type=pipeline_type, active_only=active_only
    )
    return ok({"items": items, "total": len(items)})


@router.get("/pipeline-templates/{template_id}")
async def get_pipeline_template_detail(template_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_pipeline_template(db, template_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.get("/pipeline-definitions")
async def get_pipeline_definitions(
    status: str | None = Query(default=None),
    pipeline_type: str | None = Query(default=None),
    template_id: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    items = await list_pipeline_definitions(
        db,
        status=status,
        pipeline_type=pipeline_type,
        template_id=template_id,
        active_only=active_only,
    )
    return ok({"items": items, "total": len(items)})


@router.get("/pipeline-definitions/{pipeline_id}")
async def get_pipeline_definition_detail(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_pipeline_definition(db, pipeline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/pipeline-definitions")
async def post_pipeline_definition(body: PipelineDefinitionCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_pipeline_definition(db, body.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Pipeline Definition이 등록되었습니다.")


@router.put("/pipeline-definitions/{pipeline_id}")
async def put_pipeline_definition(
    pipeline_id: str,
    body: PipelineDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        item = await update_pipeline_definition(db, pipeline_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Pipeline Definition이 수정되었습니다.")


@router.post("/pipeline-definitions/{pipeline_id}/validate")
async def post_validate_pipeline_definition(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await validate_pipeline_definition(db, pipeline_id=pipeline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(result)


@router.post("/pipeline-definitions/validate")
async def post_validate_pipeline_draft(body: PipelineDefinitionValidateRequest, db: AsyncSession = Depends(get_db)):
    if not body.template_id:
        raise HTTPException(status_code=400, detail="template_id가 필요합니다.")
    try:
        result = await validate_pipeline_definition(
            db,
            payload={"template_id": body.template_id, "node_config": body.node_config or {}},
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(result)


@router.post("/pipeline-definitions/{pipeline_id}/activate")
async def post_activate_pipeline_definition(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await activate_pipeline_definition(db, pipeline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Pipeline Definition이 ACTIVE로 전환되었습니다.")


@router.post("/pipeline-definitions/{pipeline_id}/archive")
async def post_archive_pipeline_definition(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await archive_pipeline_definition(db, pipeline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="Pipeline Definition이 보관 처리되었습니다.")


@router.get("/pipeline-node-options")
async def get_pipeline_node_options_api(
    component_type: str = Query(...),
    template_id: str | None = Query(default=None),
    pipeline_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    options = await get_node_config_options(
        db, component_type, template_id=template_id, pipeline_id=pipeline_id
    )
    return ok(options)


@router.post("/pipeline-definitions/{pipeline_id}/runtime-preview")
async def post_runtime_preview(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await runtime_preview(db, pipeline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(result)


@router.post("/pipeline-definitions/{pipeline_id}/run")
async def post_run_pipeline_definition(
    pipeline_id: str,
    body: PipelineDefinitionRunRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_pipeline_definition(db, pipeline_id, body.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.dry_run:
        return ok(result, message=result.get("message", "dry_run 완료"))
    if result.get("run_status") == "FAILED":
        return accepted(result, message=result.get("error_message", "Airflow 트리거 실패"))
    return accepted(result, message=result.get("message", "Pipeline Definition 실행 요청이 등록되었습니다."))


@router.get("/pipeline-definitions/{pipeline_id}/runs")
async def get_pipeline_definition_runs(
    pipeline_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        items = await list_pipeline_definition_runs(db, pipeline_id, limit=limit, status=status)
    except Exception:
        raise HTTPException(status_code=404, detail="PIPELINE_NOT_FOUND") from None
    return ok({"items": items, "total": len(items)})


@router.get("/pipeline-run-links")
async def get_pipeline_run_links(
    pipeline_id: str | None = Query(default=None),
    template_id: str | None = Query(default=None),
    airflow_dag_id: str | None = Query(default=None),
    run_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items = await list_pipeline_run_links(
        db,
        pipeline_id=pipeline_id,
        template_id=template_id,
        airflow_dag_id=airflow_dag_id,
        run_status=run_status,
        limit=limit,
    )
    return ok({"items": items, "total": len(items)})


@router.get("/pipeline-run-links/{link_id}")
async def get_pipeline_run_link_detail(link_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_pipeline_run_link(db, link_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/pipeline-run-links/{link_id}/sync-status")
async def post_sync_pipeline_run_link(link_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await sync_pipeline_run_link_status(db, link_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="실행 상태가 동기화되었습니다.")
