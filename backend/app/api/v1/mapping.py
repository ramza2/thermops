from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.core.time import utc_now
from app.models.entities import DataMapping, DataSource
from app.schemas.api import MappingCreate, MappingUpdate
from app.services.mapping_service import preview_mapping_data, validate_mapping_rules

router = APIRouter(prefix="/mappings", tags=["Mapping"])


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
        m.target_table = body.target_table
    if body.columns:
        m.columns = [c.model_dump() for c in body.columns]
    m.updated_at = utc_now()
    return ok({"mapping_id": mapping_id}, message="데이터 매핑이 수정되었습니다.")


@router.post("/{mapping_id}/validate")
async def validate_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    m = await _get_mapping(db, mapping_id)
    source = await _get_source(db, m.source_id)
    return ok(validate_mapping_rules(m, source))


@router.post("/{mapping_id}/preview")
async def preview_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    m = await _get_mapping(db, mapping_id)
    source = await _get_source(db, m.source_id)
    try:
        rows = preview_mapping_data(source, m, limit=10)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({
        "mapping_id": mapping_id,
        "preview_rows": rows,
    })
