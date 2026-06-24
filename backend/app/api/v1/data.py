from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.core.time import utc_now
from app.models.entities import DataQualityRun, DataSource
from app.schemas.api import DataSourceCreate, DataSourceUpdate
from app.services.csv_source_service import is_csv_source, test_csv_connection
from app.services.data_quality_service import QualityCheckParams, run_quality_check
from app.services.ingestion_service import IngestionError, fail_ingestion_job, run_ingestion

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
        created_at=utc_now(),
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
    if s.active_yn != "Y":
        return ok({
            "source_id": source_id,
            "success": False,
            "message": "연결 테스트에 실패했습니다.",
            "latency_ms": 0,
            "error_message": "데이터 소스가 비활성 상태입니다.",
            "sample_row_count": 0,
            "columns": [],
        })
    if is_csv_source(s.source_type):
        result = test_csv_connection(s.connection_info)
        return ok({"source_id": source_id, **result})
    return ok({
        "source_id": source_id,
        "success": False,
        "message": "연결 테스트에 실패했습니다.",
        "latency_ms": 0,
        "error_message": "1단계 CSV 적재에서는 CSV/FILE_CSV 소스만 파일 연결 테스트를 지원합니다.",
        "sample_row_count": 0,
        "columns": [],
    })


@router.post("/ingestion-jobs")
async def create_ingestion_job(
    source_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    job_id = f"ING-{uuid4().hex[:8].upper()}"
    run = DataQualityRun(
        run_id=job_id,
        source_id=source_id,
        check_type="INGESTION",
        run_status="RUNNING",
        started_at=utc_now(),
    )
    db.add(run)
    await db.flush()

    try:
        result = await run_ingestion(db, source_id, job_id)
        message = f"데이터 {result['inserted_count']}건이 적재되었습니다."
        if result.get("failed_count", 0) > 0:
            message += f" (실패 {result['failed_count']}건)"
        return ok({
            "job_id": job_id,
            "status": result["status"],
            "inserted_count": result["inserted_count"],
            "failed_count": result["failed_count"],
            "result_summary": result["result_summary"],
        }, message=message)
    except IngestionError as exc:
        await fail_ingestion_job(db, job_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ingestion-jobs/{job_id}")
async def get_ingestion_job(job_id: str, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(DataQualityRun).where(DataQualityRun.run_id == job_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    summary = run.result_summary or {}
    return ok({
        "job_id": run.run_id,
        "status": run.run_status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "result_summary": summary,
        "inserted_count": summary.get("inserted_count"),
        "failed_count": summary.get("failed_count"),
        "error_message": summary.get("error_message"),
    })


def _parse_optional_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).replace(tzinfo=None)


@router.post("/data-quality/checks")
async def run_quality_check_endpoint(
    source_id: str | None = Query(default=None),
    data_domain: str | None = Query(default=None, description="HEAT_DEMAND | WEATHER | ALL"),
    site_id: str | None = Query(default=None),
    weather_area_id: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    params = QualityCheckParams(
        source_id=source_id,
        data_domain=data_domain,
        site_id=site_id,
        weather_area_id=weather_area_id,
        start_at=_parse_optional_dt(start_at),
        end_at=_parse_optional_dt(end_at),
    )
    try:
        result = await run_quality_check(db, params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    score = (result.get("result_summary") or {}).get("quality_score")
    message = f"품질 점검이 완료되었습니다. (점수: {score})" if score is not None else "품질 점검이 완료되었습니다."
    return ok(result, message=message)


@router.get("/data-quality/runs")
async def list_quality_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(DataQualityRun)
            .where(DataQualityRun.check_type != "INGESTION")
            .order_by(DataQualityRun.started_at.desc())
        )
    ).scalars().all()
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
