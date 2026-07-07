from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    ForecastPreviewInputRequest,
    ForecastProviderConfigUpdate,
    ForecastRequestPreviewRequest,
    ForecastResolveBaseTimeRequest,
    ForecastTestCallRequest,
)
from app.services.forecast_input_provider_service import (
    ForecastProviderError,
    fetch_and_normalize_forecast,
    forecast_request_preview,
    get_forecast_snapshot,
    get_provider_config,
    list_forecast_snapshots,
    preview_forecast_input,
    resolve_base_time_options,
    save_provider_config,
)
from app.services.prediction_weather_input_service import list_prediction_weather_inputs
from app.services.weather_mapping_service import get_entity_forecast_grid

router = APIRouter(tags=["Forecast Provider"])


@router.get("/forecast-provider/config")
async def get_forecast_provider_config(db: AsyncSession = Depends(get_db)):
    config = await get_provider_config(db)
    return ok(config or {})


@router.put("/forecast-provider/config")
async def put_forecast_provider_config(
    body: ForecastProviderConfigUpdate, db: AsyncSession = Depends(get_db)
):
    item = await save_provider_config(db, body.model_dump(exclude_unset=True))
    return ok(item, message="예측 시점 단기예보 입력 생성기 설정이 저장되었습니다.")


@router.get("/forecast-provider/base-time-options")
async def get_forecast_base_time_options(db: AsyncSession = Depends(get_db)):
    from app.services.kma_short_forecast_parser import KMA_BASE_TIME_CANDIDATES

    config = await get_provider_config(db) or {}
    return ok(
        {
            "candidates": list(KMA_BASE_TIME_CANDIDATES),
            "base_time_policy": config.get("base_time_policy") or "LATEST_AVAILABLE",
            "delay_minutes": config.get("delay_minutes") or 60,
        }
    )


@router.post("/forecast-provider/resolve-base-time")
async def post_forecast_resolve_base_time(
    body: ForecastResolveBaseTimeRequest, db: AsyncSession = Depends(get_db)
):
    item = await resolve_base_time_options(db, base_date=body.base_date, base_time=body.base_time)
    return ok(item)


@router.post("/forecast-provider/request-preview")
async def post_forecast_request_preview(
    body: ForecastRequestPreviewRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await forecast_request_preview(
            db,
            entity_id=body.entity_id,
            base_date=body.base_date,
            base_time=body.base_time,
            source_operation_id=body.source_operation_id,
        )
    except ForecastProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/forecast-provider/test-call")
async def post_forecast_test_call(body: ForecastTestCallRequest, db: AsyncSession = Depends(get_db)):
    try:
        grid = await get_entity_forecast_grid(db, body.entity_id)
        if not grid:
            raise ForecastProviderError("단기예보 격자 정보를 찾을 수 없습니다.", error_code="FORECAST_GRID_NOT_FOUND")
        config = await get_provider_config(db) or {}
        operation_id = body.source_operation_id or config.get("source_operation_id")
        if not operation_id:
            raise ForecastProviderError(
                "Forecast Provider REST API 작업이 설정되지 않았습니다.",
                error_code="MISSING_SOURCE_OPERATION",
            )
        resolved = await resolve_base_time_options(db, base_date=body.base_date, base_time=body.base_time)
        result = await fetch_and_normalize_forecast(
            db,
            entity_id=body.entity_id,
            nx=int(grid["nx"]),
            ny=int(grid["ny"]),
            base_date=resolved["base_date"],
            base_time=resolved["base_time"],
            source_operation_id=operation_id,
            config=config,
            cache_policy=body.cache_policy,
        )
        item = {
            "success": True,
            "entity_id": body.entity_id,
            "nx": grid["nx"],
            "ny": grid["ny"],
            "row_count": len(result.get("normalized_rows") or []),
            "cache_hit": result.get("cache_hit", False),
            "snapshot_id": result.get("snapshot_id"),
            "warnings": result.get("warnings") or [],
        }
    except ForecastProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="단기예보 테스트 호출이 완료되었습니다.")


@router.post("/forecast-provider/preview-input")
async def post_forecast_preview_input(
    body: ForecastPreviewInputRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await preview_forecast_input(
            db,
            entity_id=body.entity_id,
            base_date=body.base_date,
            base_time=body.base_time,
            cache_policy=body.cache_policy,
            target_start_at=body.target_start_at,
            target_end_at=body.target_end_at,
            source_operation_id=body.source_operation_id,
        )
    except ForecastProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="단기예보 입력 미리보기가 완료되었습니다.")


@router.get("/forecast-provider/snapshots")
async def get_forecast_snapshots(
    prediction_job_id: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items = await list_forecast_snapshots(
        db, prediction_job_id=prediction_job_id, entity_id=entity_id, limit=limit
    )
    return ok(items)


@router.get("/forecast-provider/snapshots/{snapshot_id}")
async def get_forecast_snapshot_endpoint(snapshot_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_forecast_snapshot(db, snapshot_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.get("/prediction-jobs/{prediction_job_id}/weather-inputs")
async def get_prediction_job_weather_inputs(
    prediction_job_id: str, db: AsyncSession = Depends(get_db)
):
    items = await list_prediction_weather_inputs(db, prediction_job_id)
    return ok(items)
