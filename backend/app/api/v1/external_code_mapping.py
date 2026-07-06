from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    ArchiveMappingRequest,
    ExternalCodeMappingCreate,
    ExternalCodeMappingUpdate,
    ExternalCodeResolveBatchRequest,
    ExternalCodeResolveRequest,
    UnmappedAssignRequest,
    UnmappedIgnoreRequest,
)
from app.services.external_code_mapping_service import (
    ExternalCodeMappingError,
    activate_mapping,
    archive_mapping,
    archive_unmapped,
    assign_unmapped,
    create_mapping,
    deactivate_mapping,
    get_mapping,
    get_options,
    get_unmapped,
    ignore_unmapped,
    list_mappings,
    list_unmapped,
    resolve_external_code,
    resolve_external_codes_batch,
    resolve_or_log_unmapped,
    search_target_candidates,
    update_mapping,
)

router = APIRouter(tags=["External Code Mapping"])


@router.get("/external-code-mappings/options")
async def get_external_code_mapping_options(db: AsyncSession = Depends(get_db)):
    return ok(await get_options(db))


@router.get("/external-code-mappings/target-candidates")
async def get_external_code_target_candidates(
    target_type: str = Query(...),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        items = await search_target_candidates(db, target_type=target_type, keyword=keyword, limit=limit)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(items)


@router.post("/external-code-mappings/resolve")
async def post_external_code_resolve(body: ExternalCodeResolveRequest, db: AsyncSession = Depends(get_db)):
    result = await resolve_or_log_unmapped(
        db,
        source_system=body.source_system,
        external_code_group=body.external_code_group,
        external_code=body.external_code,
        target_type=body.target_type,
        at_date=body.at_date,
    )
    return ok(result)


@router.post("/external-code-mappings/resolve-batch")
async def post_external_code_resolve_batch(body: ExternalCodeResolveBatchRequest, db: AsyncSession = Depends(get_db)):
    items = await resolve_external_codes_batch(db, [i.model_dump() for i in body.items])
    return ok(items)


@router.get("/external-code-mappings/unmapped")
async def get_unmapped_external_codes(
    source_system: str | None = Query(default=None),
    external_code_group: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    items = await list_unmapped(
        db,
        source_system=source_system,
        external_code_group=external_code_group,
        review_status=review_status,
        keyword=keyword,
    )
    return ok(items)


@router.get("/external-code-mappings/unmapped/{unmapped_id}")
async def get_unmapped_external_code(unmapped_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_unmapped(db, unmapped_id)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/external-code-mappings/unmapped/{unmapped_id}/assign")
async def post_unmapped_assign(
    unmapped_id: str, body: UnmappedAssignRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await assign_unmapped(db, unmapped_id, body.model_dump())
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="미매핑 코드가 내부 대상과 연결되었습니다.")


@router.post("/external-code-mappings/unmapped/{unmapped_id}/ignore")
async def post_unmapped_ignore(
    unmapped_id: str, body: UnmappedIgnoreRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await ignore_unmapped(db, unmapped_id, body.ignored_reason)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="미매핑 코드를 무시 처리했습니다.")


@router.post("/external-code-mappings/unmapped/{unmapped_id}/archive")
async def post_unmapped_archive(unmapped_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await archive_unmapped(db, unmapped_id)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="미매핑 코드를 보관 처리했습니다.")


@router.get("/external-code-mappings")
async def get_external_code_mappings(
    source_system: str | None = Query(default=None),
    external_code_group: str | None = Query(default=None),
    external_code: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    mapping_status: str | None = Query(default=None),
    active_yn: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    items = await list_mappings(
        db,
        source_system=source_system,
        external_code_group=external_code_group,
        external_code=external_code,
        target_type=target_type,
        mapping_status=mapping_status,
        active_yn=active_yn,
        keyword=keyword,
    )
    return ok(items)


@router.post("/external-code-mappings")
async def post_external_code_mapping(body: ExternalCodeMappingCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_mapping(db, body.model_dump())
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="외부 코드 매핑이 등록되었습니다.")


@router.get("/external-code-mappings/{mapping_id}")
async def get_external_code_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_mapping(db, mapping_id)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.put("/external-code-mappings/{mapping_id}")
async def put_external_code_mapping(
    mapping_id: str, body: ExternalCodeMappingUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await update_mapping(db, mapping_id, body.model_dump(exclude_unset=True))
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="외부 코드 매핑이 수정되었습니다.")


@router.post("/external-code-mappings/{mapping_id}/archive")
async def post_external_code_mapping_archive(
    mapping_id: str, body: ArchiveMappingRequest | None = None, db: AsyncSession = Depends(get_db)
):
    try:
        item = await archive_mapping(db, mapping_id, body.archived_reason if body else None)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="외부 코드 매핑이 보관 처리되었습니다.")


@router.post("/external-code-mappings/{mapping_id}/activate")
async def post_external_code_mapping_activate(mapping_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await activate_mapping(db, mapping_id)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="외부 코드 매핑이 활성화되었습니다.")


@router.post("/external-code-mappings/{mapping_id}/deactivate")
async def post_external_code_mapping_deactivate(mapping_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await deactivate_mapping(db, mapping_id)
    except ExternalCodeMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="외부 코드 매핑이 비활성화되었습니다.")
