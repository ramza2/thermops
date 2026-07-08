from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    ApiConnectorCredentialUpsert,
    ApiConnectorLoadRunRequest,
    ApiConnectorOperationCreate,
    ApiConnectorOperationUpdate,
    ApiConnectorPaginationUpsert,
    ApiConnectorParamsReplace,
    ApiConnectorRuntimeParams,
    ApiConnectorTransformConfigUpsert,
    ApiConnectorTransformPreviewRequest,
    ApiConnectorWritePolicyUpsert,
)
from app.services.api_connector_service import (
    ApiConnectorError,
    archive_operation,
    build_request_preview,
    create_operation,
    get_load_run,
    get_operation_detail,
    get_snapshot,
    list_call_logs,
    list_load_runs,
    list_operations,
    load_preview,
    replace_params,
    response_preview,
    run_load,
    test_call,
    transform_preview,
    update_operation,
    upsert_credential,
    upsert_pagination,
    upsert_transform_config,
)
from app.services.load_write_policy_service import (
    WritePolicyError,
    get_dedup_summary,
    get_target_table_columns,
    get_write_policy,
    list_dedup_summaries,
    list_write_policies,
    upsert_write_policy,
    validate_write_policy_payload,
)
from app.services.standard_dataset_service import TargetTableNotAllowedError
from app.services.wide_hour_transform_service import WideHourTransformError

router = APIRouter(tags=["API Connector"])


@router.get("/api-connectors/operations")
async def get_api_connector_operations(
    data_source_id: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_operations(db, data_source_id=data_source_id, include_archived=include_archived))


@router.post("/api-connectors/operations")
async def post_api_connector_operation(body: ApiConnectorOperationCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_operation(db, body.model_dump())
    except (ApiConnectorError, TargetTableNotAllowedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="API 작업이 등록되었습니다.")


@router.get("/api-connectors/operations/{operation_id}")
async def get_api_connector_operation(operation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_operation_detail(db, operation_id)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.put("/api-connectors/operations/{operation_id}")
async def put_api_connector_operation(
    operation_id: str,
    body: ApiConnectorOperationUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await update_operation(db, operation_id, body.model_dump(exclude_unset=True))
    except (ApiConnectorError, TargetTableNotAllowedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="API 작업이 수정되었습니다.")


@router.post("/api-connectors/operations/{operation_id}/archive")
async def post_archive_api_connector_operation(operation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await archive_operation(db, operation_id)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="API 작업이 보관 처리되었습니다.")


@router.get("/api-connectors/operations/{operation_id}/params")
async def get_api_connector_params(operation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_operation_detail(db, operation_id)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item.get("params", []))


@router.put("/api-connectors/operations/{operation_id}/params")
async def put_api_connector_params(
    operation_id: str,
    body: ApiConnectorParamsReplace,
    db: AsyncSession = Depends(get_db),
):
    try:
        items = await replace_params(db, operation_id, [p.model_dump() for p in body.params])
    except ApiConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(items, message="요청 파라미터가 저장되었습니다.")


@router.get("/api-connectors/data-sources/{data_source_id}/credential")
async def get_api_connector_credential(data_source_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.api_connector_service import _get_credential, _credential_dict, _get_source

    await _get_source(db, data_source_id)
    cred = await _get_credential(db, data_source_id)
    return ok(_credential_dict(cred) if cred else None)


@router.put("/api-connectors/data-sources/{data_source_id}/credential")
async def put_api_connector_credential(
    data_source_id: str,
    body: ApiConnectorCredentialUpsert,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await upsert_credential(db, data_source_id, body.model_dump(exclude_unset=True))
    except ApiConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="인증 정보가 저장되었습니다.")


@router.post("/api-connectors/data-sources/{data_source_id}/credential/test")
async def post_test_api_connector_credential(data_source_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.api_connector_service import _get_credential

    cred = await _get_credential(db, data_source_id)
    if not cred or not cred.secret_value_encrypted:
        raise HTTPException(status_code=400, detail="저장된 인증 정보가 없습니다.")
    return ok(
        {
            "success": True,
            "message": "인증 정보가 저장되어 있습니다.",
            "secret_value_masked": cred.secret_value_masked,
            "encoding_policy": cred.encoding_policy,
        }
    )


@router.get("/api-connectors/operations/{operation_id}/pagination")
async def get_api_connector_pagination(operation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_operation_detail(db, operation_id)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item.get("pagination"))


@router.put("/api-connectors/operations/{operation_id}/pagination")
async def put_api_connector_pagination(
    operation_id: str,
    body: ApiConnectorPaginationUpsert,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await upsert_pagination(db, operation_id, body.model_dump(exclude_unset=True))
    except ApiConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="페이징 설정이 저장되었습니다.")


@router.post("/api-connectors/operations/{operation_id}/request-preview")
async def post_request_preview(
    operation_id: str,
    body: ApiConnectorRuntimeParams,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await build_request_preview(db, operation_id, body.runtime_params)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/api-connectors/operations/{operation_id}/test-call")
async def post_test_call(
    operation_id: str,
    body: ApiConnectorRuntimeParams,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await test_call(db, operation_id, body.runtime_params, called_by="api")
    except ApiConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/api-connectors/operations/{operation_id}/response-preview")
async def post_response_preview(
    operation_id: str,
    body: ApiConnectorRuntimeParams,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await response_preview(db, operation_id, body.runtime_params)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/api-connectors/operations/{operation_id}/load-preview")
async def post_load_preview(
    operation_id: str,
    body: ApiConnectorRuntimeParams,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await load_preview(db, operation_id, body.runtime_params)
    except (ApiConnectorError, WideHourTransformError) as exc:
        code = getattr(exc, "error_code", "API_CONNECTOR_ERROR")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.get("/api-connectors/operations/{operation_id}/transform-config")
async def get_api_connector_transform_config(operation_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.wide_hour_transform_service import get_transform_config

    try:
        await get_operation_detail(db, operation_id)
    except ApiConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(await get_transform_config(db, operation_id))


@router.put("/api-connectors/operations/{operation_id}/transform-config")
async def put_api_connector_transform_config(
    operation_id: str,
    body: ApiConnectorTransformConfigUpsert,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await upsert_transform_config(db, operation_id, body.model_dump(exclude_unset=True))
    except (ApiConnectorError, WideHourTransformError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="변환 설정이 저장되었습니다.")


@router.post("/api-connectors/operations/{operation_id}/transform-preview")
async def post_transform_preview(
    operation_id: str,
    body: ApiConnectorTransformPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await transform_preview(
            db,
            operation_id,
            raw_items=body.raw_items,
            runtime_params=body.runtime_params,
        )
    except (ApiConnectorError, WideHourTransformError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/api-connectors/operations/{operation_id}/load-run")
async def post_load_run(
    operation_id: str,
    body: ApiConnectorLoadRunRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await run_load(
            db,
            operation_id,
            body.runtime_params,
            called_by="api",
            dry_run=body.dry_run,
        )
    except (ApiConnectorError, WideHourTransformError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 실행이 완료되었습니다.")


@router.get("/api-connectors/operations/{operation_id}/write-policy")
async def get_operation_write_policy(operation_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_write_policy(db, operation_id)
    except WritePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.put("/api-connectors/operations/{operation_id}/write-policy")
async def put_operation_write_policy(
    operation_id: str,
    body: ApiConnectorWritePolicyUpsert,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await upsert_write_policy(db, operation_id, body.model_dump(exclude_unset=True))
    except WritePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 방식 정책이 저장되었습니다.")


@router.post("/api-connectors/operations/{operation_id}/write-policy/validate")
async def post_operation_write_policy_validate(
    operation_id: str,
    body: ApiConnectorWritePolicyUpsert,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await validate_write_policy_payload(db, operation_id, body.model_dump(exclude_unset=True))
    except WritePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/api-connectors/operations/{operation_id}/write-policy/preview-dedup")
async def post_operation_write_policy_preview_dedup(
    operation_id: str,
    body: ApiConnectorRuntimeParams,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await load_preview(db, operation_id, body.runtime_params)
    except (ApiConnectorError, WideHourTransformError, WritePolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.get("/api-connectors/write-policies")
async def get_api_connector_write_policies(db: AsyncSession = Depends(get_db)):
    return ok(await list_write_policies(db))


@router.get("/api-connectors/target-table-columns")
async def get_api_connector_target_table_columns(
    target_table: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await get_target_table_columns(db, target_table)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.get("/api-connectors/dedup-summaries")
async def get_api_connector_dedup_summaries(
    operation_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_dedup_summaries(db, operation_id=operation_id))


@router.get("/api-connectors/dedup-summaries/{summary_id}")
async def get_api_connector_dedup_summary(summary_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_dedup_summary(db, summary_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.get("/api-connectors/load-runs")
async def get_load_runs(
    operation_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_load_runs(db, operation_id=operation_id))


@router.get("/api-connectors/load-runs/{load_run_id}")
async def get_load_run_detail(load_run_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_load_run(db, load_run_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.get("/api-connectors/call-logs")
async def get_call_logs(
    operation_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_call_logs(db, operation_id=operation_id))


@router.get("/api-connectors/snapshots/{snapshot_id}")
async def get_response_snapshot(snapshot_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_snapshot(db, snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)
