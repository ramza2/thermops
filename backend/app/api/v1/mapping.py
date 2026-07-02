from uuid import uuid4

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.core.time import utc_now
from app.models.entities import DataMapping, DataSource
from app.schemas.api import MappingCreate, MappingUpdate
from app.services.mapping_service import (
    MappingValidationError,
    delete_data_mapping,
    get_mapping_delete_blockers,
    preview_mapping_data,
    validate_mapping_rules,
)
from app.services.standard_dataset_service import TargetTableNotAllowedError, validate_target_table_allowed

router = APIRouter(prefix="/mappings", tags=["Mapping"])


def _blockers_from_value_error(exc: ValueError) -> list[dict]:
    if exc.args and isinstance(exc.args[0], list):
        return exc.args[0]
    return []


def _mapping_dict(m: DataMapping) -> dict:
    return {
        "mapping_id": m.mapping_id,
        "source_id": m.source_id,
        "mapping_name": m.mapping_name,
        "target_table": m.target_table,
        "columns": m.columns or [],
        "active_yn": m.active_yn == "Y",
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def _get_mapping(db: AsyncSession, mapping_id: str) -> DataMapping:
    m = (await db.execute(select(DataMapping).where(DataMapping.mapping_id == mapping_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return m


async def _get_source(db: AsyncSession, source_id: str) -> DataSource:
    s = (await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")
    return s


@router.get("")
async def list_mappings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(DataMapping).order_by(DataMapping.created_at.desc()))).scalars().all()
    items = [_mapping_dict(r) for r in rows]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.post("")
async def create_mapping(body: MappingCreate, db: AsyncSession = Depends(get_db)):
    try:
        await validate_target_table_allowed(db, body.target_table)
    except TargetTableNotAllowedError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": exc.error_code,
                "message": str(exc),
                "allowed_tables": exc.allowed_tables,
            },
        ) from exc
    mapping_id = f"MAP-{uuid4().hex[:6].upper()}"
    m = DataMapping(
        mapping_id=mapping_id,
        source_id=body.source_id,
        mapping_name=body.mapping_name,
        target_table=body.target_table,
        columns=[c.model_dump() for c in body.columns],
        active_yn="Y",
        created_at=utc_now(),
    )
    db.add(m)
    await db.flush()
    return ok({"mapping_id": mapping_id}, message="데이터 매핑이 등록되었습니다.")


@router.put("/{mapping_id}")
async def update_mapping(mapping_id: str, body: MappingUpdate, db: AsyncSession = Depends(get_db)):
    m = await _get_mapping(db, mapping_id)
    if body.mapping_name:
        m.mapping_name = body.mapping_name
    if body.target_table:
        try:
            await validate_target_table_allowed(db, body.target_table)
        except TargetTableNotAllowedError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": exc.error_code,
                    "message": str(exc),
                    "allowed_tables": exc.allowed_tables,
                },
            ) from exc
        m.target_table = body.target_table
    if body.columns:
        m.columns = [c.model_dump() for c in body.columns]
    m.updated_at = utc_now()
    return ok({"mapping_id": mapping_id}, message="데이터 매핑이 수정되었습니다.")


@router.post("/{mapping_id}/validate")
async def validate_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    m = await _get_mapping(db, mapping_id)
    source = await _get_source(db, m.source_id)
    return ok(await asyncio.to_thread(validate_mapping_rules, m, source))


@router.post("/{mapping_id}/preview")
async def preview_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    m = await _get_mapping(db, mapping_id)
    source = await _get_source(db, m.source_id)
    try:
        rows = await asyncio.to_thread(preview_mapping_data, source, m, 10)
    except MappingValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "MAPPING_VALIDATION_FAILED",
                "message": str(exc),
                "errors": exc.errors,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({
        "mapping_id": mapping_id,
        "preview_rows": rows,
    })


@router.get("/{mapping_id}/delete-blockers")
async def get_mapping_delete_blockers_api(mapping_id: str, db: AsyncSession = Depends(get_db)):
    await _get_mapping(db, mapping_id)
    blockers = await get_mapping_delete_blockers(db, mapping_id)
    return ok({
        "mapping_id": mapping_id,
        "can_delete": len(blockers) == 0,
        "blockers": blockers,
    })


@router.delete("/{mapping_id}")
async def delete_mapping_endpoint(mapping_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await delete_data_mapping(db, mapping_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        items = _blockers_from_value_error(exc)
        message = items[0]["message"] if items else "삭제할 수 없습니다."
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MAPPING_IN_USE",
                "message": message,
                "blockers": items,
                "hint": "연결된 Feature Recipe를 먼저 삭제·비활성화하거나 다른 매핑으로 변경하세요.",
            },
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MAPPING_IN_USE",
                "message": "연결된 Column Role 또는 다른 참조 때문에 삭제할 수 없습니다.",
                "hint": "연결된 Feature Recipe·Column Role을 먼저 정리하세요.",
            },
        ) from exc
    return ok(message="데이터 매핑이 삭제되었습니다.")
