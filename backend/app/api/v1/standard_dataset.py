from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    StandardDatasetTypeCreate,
    StandardDatasetTypeUpdate,
    ValidateTargetTableRequest,
)
from app.services.standard_dataset_service import (
    TargetTableNotAllowedError,
    activate_standard_dataset_type,
    archive_standard_dataset_type,
    create_standard_dataset_type,
    get_standard_dataset_type,
    list_mapping_target_tables,
    list_standard_dataset_types,
    update_standard_dataset_type,
    validate_target_table_allowed,
)

router = APIRouter(tags=["Standard Dataset"])


@router.get("/standard-dataset-types")
async def get_standard_dataset_types(
    status: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    category: str | None = Query(default=None),
    mapping_supported: bool | None = Query(default=None),
    recipe_supported: bool | None = Query(default=None),
    build_supported: bool | None = Query(default=None),
    include_columns: bool = Query(default=False),
    include_planned: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    items = await list_standard_dataset_types(
        db,
        status=status,
        domain=domain,
        category=category,
        mapping_supported=mapping_supported,
        recipe_supported=recipe_supported,
        build_supported=build_supported,
        include_columns=include_columns,
        include_planned=include_planned,
    )
    return ok({"items": items, "total": len(items)})


@router.get("/standard-dataset-types/{dataset_type_id}")
async def get_standard_dataset_type_detail(
    dataset_type_id: str,
    include_columns: bool = Query(default=True),
    include_recipe_availability: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await get_standard_dataset_type(
            db,
            dataset_type_id,
            include_columns=include_columns,
            include_recipe_availability=include_recipe_availability,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.get("/standard-target-tables")
async def get_standard_target_tables(
    mapping_supported: bool = Query(default=True),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    items = await list_mapping_target_tables(
        db,
        active_only=active_only,
        mapping_supported=mapping_supported,
    )
    return ok({"items": items})


@router.post("/standard-dataset-types/validate-target-table")
async def post_validate_target_table(
    body: ValidateTargetTableRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await validate_target_table_allowed(db, body.target_table)
    except TargetTableNotAllowedError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": exc.error_code,
                "message": str(exc),
                "valid": False,
                "allowed_tables": exc.allowed_tables,
                "warnings": exc.warnings,
            },
        ) from exc
    return ok(result)


@router.post("/standard-dataset-types")
async def post_standard_dataset_type(
    body: StandardDatasetTypeCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await create_standard_dataset_type(db, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="학습 데이터셋 유형이 등록되었습니다.")


@router.put("/standard-dataset-types/{dataset_type_id}")
async def put_standard_dataset_type(
    dataset_type_id: str,
    body: StandardDatasetTypeUpdate,
    db: AsyncSession = Depends(get_db),
):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        item = await update_standard_dataset_type(db, dataset_type_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="학습 데이터셋 유형이 수정되었습니다.")


@router.post("/standard-dataset-types/{dataset_type_id}/activate")
async def post_activate_standard_dataset_type(
    dataset_type_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await activate_standard_dataset_type(db, dataset_type_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="표준 데이터셋 유형이 ACTIVE로 전환되었습니다.")


@router.post("/standard-dataset-types/{dataset_type_id}/archive")
async def post_archive_standard_dataset_type(
    dataset_type_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await archive_standard_dataset_type(db, dataset_type_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="표준 데이터셋 유형이 보관(ARCHIVED) 처리되었습니다.")
