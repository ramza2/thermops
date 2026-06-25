from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import SystemConfigUpdate
from app.services.system_config_service import (
    get_system_config,
    list_system_configs,
    reset_system_configs,
    update_system_config,
)

router = APIRouter(tags=["System"])


@router.get("/system-configs")
async def list_configs(db: AsyncSession = Depends(get_db)):
    items = await list_system_configs(db)
    return ok(items)


@router.get("/system-configs/{config_key}")
async def get_config(config_key: str, db: AsyncSession = Depends(get_db)):
    item = await get_system_config(db, config_key)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.put("/system-configs/{config_key}")
async def update_config(
    config_key: str,
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await update_system_config(db, config_key, body.config_value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(item, message="시스템 설정이 저장되었습니다.")


@router.post("/system-configs/reset")
async def reset_configs(db: AsyncSession = Depends(get_db)):
    items = await reset_system_configs(db)
    if not items:
        raise HTTPException(status_code=501, detail="초기화할 편집 가능한 설정이 없습니다.")
    return ok({"reset_count": len(items), "items": items}, message="시스템 설정이 기본값으로 초기화되었습니다.")
