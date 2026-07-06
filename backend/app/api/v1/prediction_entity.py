from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    LatLonToGridRequest,
    PredictionEntityCreate,
    PredictionEntityLocationCreate,
    PredictionEntityLocationUpdate,
    PredictionEntityUpdate,
    WeatherForecastGridUpsert,
    WeatherMappingCreate,
    WeatherMappingUpdate,
    WeatherObservationStationUpsert,
)
from app.services.prediction_entity_service import (
    PredictionEntityError,
    activate_location,
    archive_entity,
    create_entity,
    create_location,
    get_entity_detail,
    list_entities,
    list_locations,
    update_entity,
    update_location,
)
from app.services.weather_mapping_service import (
    archive_weather_mapping,
    compute_weather_readiness,
    convert_latlon_to_grid,
    create_weather_mapping,
    list_forecast_grids,
    list_observation_stations,
    list_weather_mappings,
    update_weather_mapping,
    upsert_forecast_grid,
    upsert_observation_station,
    weather_mapping_preview,
)

router = APIRouter(tags=["Prediction Entity"])


@router.get("/prediction-entities")
async def get_prediction_entities(
    entity_type: str | None = Query(default=None),
    business_domain: str | None = Query(default=None),
    active_yn: bool | None = Query(default=True),
    keyword: str | None = Query(default=None),
    weather_ready: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    items = await list_entities(
        db, entity_type=entity_type, business_domain=business_domain, active_yn=active_yn, keyword=keyword
    )
    enriched = []
    for item in items:
        readiness = await compute_weather_readiness(db, item["entity_id"])
        row = {**item, "weather_readiness": readiness}
        if weather_ready is True and not readiness.get("forecast_ready"):
            continue
        if weather_ready is False and readiness.get("forecast_ready"):
            continue
        enriched.append(row)
    return ok(enriched)


@router.post("/prediction-entities")
async def post_prediction_entity(body: PredictionEntityCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_entity(db, body.model_dump())
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="예측 대상이 등록되었습니다.")


@router.get("/prediction-entities/{entity_id}")
async def get_prediction_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_entity_detail(db, entity_id)
        readiness = await compute_weather_readiness(db, entity_id)
        mappings = await list_weather_mappings(db, entity_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok({**item, "weather_readiness": readiness, "weather_mappings": mappings})


@router.put("/prediction-entities/{entity_id}")
async def put_prediction_entity(
    entity_id: str, body: PredictionEntityUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await update_entity(db, entity_id, body.model_dump(exclude_unset=True))
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="예측 대상이 수정되었습니다.")


@router.post("/prediction-entities/{entity_id}/archive")
async def post_prediction_entity_archive(entity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await archive_entity(db, entity_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="예측 대상이 보관 처리되었습니다.")


@router.get("/prediction-entities/{entity_id}/locations")
async def get_prediction_entity_locations(entity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        items = await list_locations(db, entity_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(items)


@router.post("/prediction-entities/{entity_id}/locations")
async def post_prediction_entity_location(
    entity_id: str, body: PredictionEntityLocationCreate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await create_location(db, entity_id, body.model_dump())
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="위치 정보가 등록되었습니다.")


@router.put("/prediction-entities/{entity_id}/locations/{location_id}")
async def put_prediction_entity_location(
    entity_id: str,
    location_id: str,
    body: PredictionEntityLocationUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await update_location(db, entity_id, location_id, body.model_dump(exclude_unset=True))
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="위치 정보가 수정되었습니다.")


@router.post("/prediction-entities/{entity_id}/locations/{location_id}/activate")
async def post_prediction_entity_location_activate(
    entity_id: str, location_id: str, db: AsyncSession = Depends(get_db)
):
    try:
        item = await activate_location(db, entity_id, location_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="위치 정보가 활성화되었습니다.")


@router.get("/weather/forecast-grids")
async def get_weather_forecast_grids(
    active_only: bool = Query(default=True), db: AsyncSession = Depends(get_db)
):
    return ok(await list_forecast_grids(db, active_only=active_only))


@router.post("/weather/forecast-grids")
async def post_weather_forecast_grid(body: WeatherForecastGridUpsert, db: AsyncSession = Depends(get_db)):
    try:
        item = await upsert_forecast_grid(db, body.model_dump())
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="단기예보 격자가 저장되었습니다.")


@router.get("/weather/observation-stations")
async def get_weather_observation_stations(
    active_only: bool = Query(default=True), db: AsyncSession = Depends(get_db)
):
    return ok(await list_observation_stations(db, active_only=active_only))


@router.post("/weather/observation-stations")
async def post_weather_observation_station(
    body: WeatherObservationStationUpsert, db: AsyncSession = Depends(get_db)
):
    try:
        item = await upsert_observation_station(db, body.model_dump())
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="관측소가 저장되었습니다.")


@router.get("/prediction-entities/{entity_id}/weather-mappings")
async def get_prediction_entity_weather_mappings(entity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        items = await list_weather_mappings(db, entity_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(items)


@router.post("/prediction-entities/{entity_id}/weather-mappings")
async def post_prediction_entity_weather_mapping(
    entity_id: str, body: WeatherMappingCreate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await create_weather_mapping(db, entity_id, body.model_dump())
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="기상 매핑이 등록되었습니다.")


@router.put("/prediction-entities/{entity_id}/weather-mappings/{mapping_id}")
async def put_prediction_entity_weather_mapping(
    entity_id: str,
    mapping_id: str,
    body: WeatherMappingUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await update_weather_mapping(db, entity_id, mapping_id, body.model_dump(exclude_unset=True))
    except PredictionEntityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="기상 매핑이 수정되었습니다.")


@router.post("/prediction-entities/{entity_id}/weather-mappings/{mapping_id}/archive")
async def post_prediction_entity_weather_mapping_archive(
    entity_id: str, mapping_id: str, db: AsyncSession = Depends(get_db)
):
    try:
        item = await archive_weather_mapping(db, entity_id, mapping_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="기상 매핑이 보관 처리되었습니다.")


@router.get("/prediction-entities/{entity_id}/weather-readiness")
async def get_prediction_entity_weather_readiness(entity_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await compute_weather_readiness(db, entity_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/weather/convert-latlon-to-grid")
async def post_convert_latlon_to_grid(body: LatLonToGridRequest):
    try:
        item = convert_latlon_to_grid(body.latitude, body.longitude)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/prediction-entities/{entity_id}/weather-mapping-preview")
async def post_prediction_entity_weather_mapping_preview(
    entity_id: str, db: AsyncSession = Depends(get_db)
):
    try:
        item = await weather_mapping_preview(db, entity_id)
    except PredictionEntityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)
