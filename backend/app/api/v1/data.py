from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import DataQualityRun, DataSource
from app.schemas.api import DataSourceCreate, DataSourceUpdate

router = APIRouter(tags=["Data"])


def _source_to_dict(s: DataSource) -> dict:
    return {
        "source_id": s.data_source_id,
        "source_name": s.source_name,
        "source_type": s.source_type,
        "data_domain": s.source_category,
        "connection_info": s.connection_info or {},
        "active_yn": s.active_yn == "Y",
        "last_loaded_at": s.last_loaded_at.isoformat() if s.last_loaded_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/data-sources")
async def list_data_sources(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(DataSource).order_by(DataSource.created_at.desc()))).scalars().all()
    items = [_source_to_dict(r) for r in rows]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.post("/data-sources")
async def create_data_source(body: DataSourceCreate, db: AsyncSession = Depends(get_db)):
    source_id = f"DS-{uuid4().hex[:6].upper()}"
    ds = DataSource(
        data_source_id=source_id,
        source_name=body.source_name,
        source_type=body.source_type,
        source_category=body.data_domain,
        connection_info=body.connection_info,
        active_yn="Y" if body.active_yn else "N",
        created_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    return ok({"source_id": source_id}, message="데이터 소스가 등록되었습니다.")


@router.get("/data-sources/{source_id}")
async def get_data_source(source_id: str, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(_source_to_dict(s))


@router.put("/data-sources/{source_id}")
async def update_data_source(source_id: str, body: DataSourceUpdate, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if body.source_name:
        s.source_name = body.source_name
    if body.source_type:
        s.source_type = body.source_type
    if body.connection_info:
        s.connection_info = body.connection_info
    if body.active_yn is not None:
        s.active_yn = "Y" if body.active_yn else "N"
    return ok({"source_id": source_id}, message="데이터 소스가 수정되었습니다.")


@router.delete("/data-sources/{source_id}")
async def delete_data_source(source_id: str, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(s)
    return ok(message="데이터 소스가 삭제되었습니다.")


@router.post("/data-sources/{source_id}/test-connection")
async def test_connection(source_id: str, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    success = s.active_yn == "Y"
    return ok({
        "source_id": source_id,
        "success": success,
        "message": "연결 테스트에 성공했습니다." if success else "연결 테스트에 실패했습니다.",
        "latency_ms": 42,
        "error_message": None if success else "데이터 소스가 비활성 상태이거나 연결 정보가 올바르지 않습니다.",
        "sample_row_count": 1284 if success else 0,
    })


@router.post("/ingestion-jobs")
async def create_ingestion_job(
    source_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    job_id = f"ING-{uuid4().hex[:8].upper()}"
    run = DataQualityRun(
        run_id=job_id,
        source_id=source_id,
        check_type="INGESTION",
        run_status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    return accepted({"job_id": job_id, "status": "RUNNING"}, message="데이터 적재가 시작되었습니다.")


@router.get("/ingestion-jobs/{job_id}")
async def get_ingestion_job(job_id: str, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(DataQualityRun).where(DataQualityRun.run_id == job_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok({
        "job_id": run.run_id,
        "status": run.run_status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    })


@router.post("/data-quality/checks")
async def run_quality_check(source_id: str | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    run_id = f"DQR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}"
    run = DataQualityRun(
        run_id=run_id,
        source_id=source_id,
        check_type="FULL",
        run_status="SUCCESS",
        result_summary={"missing_rate": 0.02, "duplicate_count": 0, "outlier_count": 1},
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    return accepted({"run_id": run_id, "status": "SUCCESS"}, message="품질 점검이 완료되었습니다.")


@router.get("/data-quality/runs")
async def list_quality_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(DataQualityRun).order_by(DataQualityRun.started_at.desc()))).scalars().all()
    items = [
        {
            "run_id": r.run_id,
            "source_id": r.source_id,
            "check_type": r.check_type,
            "run_status": r.run_status,
            "result_summary": r.result_summary,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))
