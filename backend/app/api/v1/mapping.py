from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.models.entities import DataMapping
from app.schemas.api import MappingCreate, MappingUpdate

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
        created_at=datetime.now(timezone.utc),
    )
    db.add(m)
    await db.flush()
    return ok({"mapping_id": mapping_id}, message="데이터 매핑이 등록되었습니다.")


@router.put("/{mapping_id}")
async def update_mapping(mapping_id: str, body: MappingUpdate, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(DataMapping).where(DataMapping.mapping_id == mapping_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if body.mapping_name:
        m.mapping_name = body.mapping_name
    if body.target_table:
        m.target_table = body.target_table
    if body.columns:
        m.columns = [c.model_dump() for c in body.columns]
    m.updated_at = datetime.now(timezone.utc)
    return ok({"mapping_id": mapping_id}, message="데이터 매핑이 수정되었습니다.")


@router.post("/{mapping_id}/validate")
async def validate_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(DataMapping).where(DataMapping.mapping_id == mapping_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    cols = m.columns or []
    errors = [f"필수 컬럼 {c['target_column']} 매핑 누락" for c in cols if c.get("required_yn") and not c.get("source_column")]
    warnings = ["선택 컬럼 supply_temp가 매핑되지 않았습니다."] if len(cols) < 4 else []
    return ok({
        "mapping_id": mapping_id,
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    })


@router.post("/{mapping_id}/preview")
async def preview_mapping(mapping_id: str, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(select(DataMapping).where(DataMapping.mapping_id == mapping_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok({
        "mapping_id": mapping_id,
        "preview_rows": [
            {"site_id": "SITE-001", "measured_at": "2026-06-24T01:00:00+09:00", "heat_demand": 124.52},
            {"site_id": "SITE-001", "measured_at": "2026-06-24T02:00:00+09:00", "heat_demand": 118.30},
        ],
    })
