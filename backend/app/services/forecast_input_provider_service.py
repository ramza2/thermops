"""Forecast On-demand Input Provider (R10-S5)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import ForecastInputSnapshot, ForecastProviderConfig
from app.services.api_connector_service import _execute_operation_call, build_request_preview
from app.services.kma_short_forecast_parser import (
    build_forecast_cache_key,
    match_forecast_rows_to_period,
    pivot_kma_short_forecast_items,
    resolve_latest_kma_base_time,
)
from app.services.notification_event_service import emit_notification_safe
from app.services.prediction_weather_input_service import save_prediction_weather_inputs
from app.services.weather_mapping_service import compute_weather_readiness, get_entity_forecast_grid
from app.utils.masking import mask_params_dict

DEFAULT_CONFIG_ID = "FPC-DEFAULT"
SOURCE_SYSTEM = "KMA_SHORT_FORECAST_API"
CACHE_POLICIES = frozenset({"USE_CACHE", "REFRESH", "DISABLED"})


class ForecastProviderError(ValueError):
    def __init__(self, message: str, *, error_code: str = "FORECAST_PROVIDER_ERROR"):
        self.error_code = error_code
        super().__init__(message)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _config_dict(row: ForecastProviderConfig) -> dict[str, Any]:
    return {
        "provider_config_id": row.provider_config_id,
        "provider_name": row.provider_name,
        "provider_type": row.provider_type,
        "source_operation_id": row.source_operation_id,
        "default_num_of_rows": row.default_num_of_rows,
        "default_data_type": row.default_data_type,
        "base_time_policy": row.base_time_policy,
        "delay_minutes": row.delay_minutes,
        "active_yn": bool(row.active_yn),
        "metadata_json": row.metadata_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _snapshot_dict(row: ForecastInputSnapshot) -> dict[str, Any]:
    return {
        "snapshot_id": row.snapshot_id,
        "prediction_job_id": row.prediction_job_id,
        "entity_id": row.entity_id,
        "nx": row.nx,
        "ny": row.ny,
        "source_system": row.source_system,
        "source_operation_id": row.source_operation_id,
        "request_base_date": row.request_base_date,
        "request_base_time": row.request_base_time,
        "forecast_base_at": row.forecast_base_at.isoformat() if row.forecast_base_at else None,
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "cache_key": row.cache_key,
        "request_params_masked": row.request_params_masked,
        "raw_response_snapshot_id": row.raw_response_snapshot_id,
        "row_count": row.row_count,
        "cache_hit_yn": bool(row.cache_hit_yn),
        "success_yn": bool(row.success_yn),
        "error_message": row.error_message,
        "normalized_rows_json": row.normalized_rows_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "metadata_json": row.metadata_json,
    }


async def get_provider_config(db: AsyncSession) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(ForecastProviderConfig).where(
                ForecastProviderConfig.provider_config_id == DEFAULT_CONFIG_ID
            )
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return _config_dict(row)


async def save_provider_config(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    row = (
        await db.execute(
            select(ForecastProviderConfig).where(
                ForecastProviderConfig.provider_config_id == DEFAULT_CONFIG_ID
            )
        )
    ).scalar_one_or_none()
    defaults = {
        "provider_name": "기상청 단기예보 Provider",
        "provider_type": "KMA_SHORT_FORECAST",
        "default_num_of_rows": 1000,
        "default_data_type": "JSON",
        "base_time_policy": "LATEST_AVAILABLE",
        "delay_minutes": 60,
        "active_yn": True,
    }
    merged = {**defaults, **{k: v for k, v in payload.items() if v is not None}}
    if row:
        for key in (
            "provider_name",
            "provider_type",
            "source_operation_id",
            "default_num_of_rows",
            "default_data_type",
            "base_time_policy",
            "delay_minutes",
            "active_yn",
            "metadata_json",
        ):
            if key in merged:
                setattr(row, key, merged[key])
        row.updated_at = now
    else:
        row = ForecastProviderConfig(
            provider_config_id=DEFAULT_CONFIG_ID,
            created_at=now,
            updated_at=now,
            **{k: merged[k] for k in defaults if k in merged},
            source_operation_id=merged.get("source_operation_id"),
            metadata_json=merged.get("metadata_json"),
        )
        db.add(row)
    await db.flush()
    return _config_dict(row)


async def resolve_base_time_options(
    db: AsyncSession,
    *,
    base_date: str | None = None,
    base_time: str | None = None,
) -> dict[str, Any]:
    config = await get_provider_config(db)
    delay = int((config or {}).get("delay_minutes") or 60)
    if base_date and base_time:
        from app.services.kma_short_forecast_parser import parse_kma_datetime

        base_at = parse_kma_datetime(base_date, base_time)
        return {
            "base_date": base_date,
            "base_time": base_time,
            "forecast_base_at": base_at.isoformat(),
            "policy": "MANUAL",
            "delay_minutes": delay,
        }
    resolved_date, resolved_time, base_at = resolve_latest_kma_base_time(delay_minutes=delay)
    return {
        "base_date": resolved_date,
        "base_time": resolved_time,
        "forecast_base_at": base_at.isoformat(),
        "policy": (config or {}).get("base_time_policy") or "LATEST_AVAILABLE",
        "delay_minutes": delay,
    }


def _runtime_params(
    *,
    nx: int,
    ny: int,
    base_date: str,
    base_time: str,
    config: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = {
        "nx": str(nx),
        "ny": str(ny),
        "base_date": base_date,
        "base_time": base_time,
        "pageNo": "1",
        "numOfRows": str(config.get("default_num_of_rows") or 1000),
        "dataType": config.get("default_data_type") or "JSON",
    }
    if overrides:
        for key, val in overrides.items():
            if val is not None:
                params[key] = str(val)
    return params


async def _find_cached_snapshot(db: AsyncSession, cache_key: str) -> ForecastInputSnapshot | None:
    return (
        await db.execute(
            select(ForecastInputSnapshot)
            .where(
                ForecastInputSnapshot.cache_key == cache_key,
                ForecastInputSnapshot.success_yn.is_(True),
            )
            .order_by(ForecastInputSnapshot.requested_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def fetch_and_normalize_forecast(
    db: AsyncSession,
    *,
    entity_id: str,
    nx: int,
    ny: int,
    base_date: str,
    base_time: str,
    source_operation_id: str,
    config: dict[str, Any],
    cache_policy: str = "USE_CACHE",
    prediction_job_id: str | None = None,
    target_start_at: datetime | None = None,
    target_end_at: datetime | None = None,
) -> dict[str, Any]:
    if cache_policy not in CACHE_POLICIES:
        raise ForecastProviderError("캐시 정책이 올바르지 않습니다.", error_code="INVALID_CACHE_POLICY")

    cache_key = build_forecast_cache_key(
        source_system=SOURCE_SYSTEM,
        nx=nx,
        ny=ny,
        base_date=base_date,
        base_time=base_time,
        source_operation_id=source_operation_id,
    )
    warnings: list[str] = []
    cache_hit = False
    normalized_rows: list[dict[str, Any]] = []
    raw_snapshot_id: str | None = None
    raw_response_json: list[dict[str, Any]] | None = None
    forecast_base_at: datetime | None = None

    if cache_policy == "USE_CACHE":
        cached = await _find_cached_snapshot(db, cache_key)
        if cached and cached.normalized_rows_json:
            cache_hit = True
            normalized_rows = list(cached.normalized_rows_json)
            raw_snapshot_id = cached.raw_response_snapshot_id
            forecast_base_at = cached.forecast_base_at
            snapshot_id = cached.snapshot_id
            matched_rows = normalized_rows
            match_warnings: list[str] = []
            if target_start_at and target_end_at:
                matched_rows, match_warnings = match_forecast_rows_to_period(
                    normalized_rows, start_at=target_start_at, end_at=target_end_at
                )
            warnings.extend(match_warnings)
            return {
                "snapshot_id": snapshot_id,
                "cache_hit": True,
                "cache_key": cache_key,
                "forecast_base_at": forecast_base_at.isoformat() if forecast_base_at else None,
                "normalized_rows": normalized_rows,
                "matched_rows": matched_rows,
                "warnings": warnings,
                "raw_response_snapshot_id": raw_snapshot_id,
            }

    runtime = _runtime_params(
        nx=nx, ny=ny, base_date=base_date, base_time=base_time, config=config
    )
    try:
        result = await _execute_operation_call(
            db,
            source_operation_id,
            runtime_params=runtime,
            sample_limit=5000,
            called_by="forecast_provider",
            save_snapshot=True,
        )
    except Exception as exc:
        now = utc_now()
        snapshot_id = _new_id("FIS")
        from app.services.kma_short_forecast_parser import parse_kma_datetime

        forecast_base_at = parse_kma_datetime(base_date, base_time)
        row = ForecastInputSnapshot(
            snapshot_id=snapshot_id,
            prediction_job_id=prediction_job_id,
            entity_id=entity_id,
            nx=nx,
            ny=ny,
            source_system=SOURCE_SYSTEM,
            source_operation_id=source_operation_id,
            request_base_date=base_date,
            request_base_time=base_time,
            forecast_base_at=forecast_base_at,
            requested_at=now,
            cache_key=cache_key,
            request_params_masked=mask_params_dict(runtime),
            row_count=0,
            cache_hit_yn=False,
            success_yn=False,
            error_message=str(exc)[:500],
            created_at=now,
        )
        db.add(row)
        await db.flush()
        await emit_notification_safe(
            db,
            event_source="FORECAST_PROVIDER",
            event_type="FORECAST_PROVIDER_FAILED",
            severity="ERROR",
            title=f"단기예보 입력 생성 실패: entity {entity_id}",
            message=str(exc)[:500],
            resource_type="forecast_snapshot",
            resource_id=snapshot_id,
            dedup_key=f"{entity_id}:{base_date}:{base_time}:FORECAST_PROVIDER_FAILED",
            event_payload_json={
                "entity_id": entity_id,
                "base_date": base_date,
                "base_time": base_time,
                "error_message": str(exc)[:500],
            },
        )
        raise ForecastProviderError(str(exc), error_code="FORECAST_API_FAILED") from exc

    raw_items = result.get("items") or []
    raw_snapshot_id = result.get("snapshot_id")
    normalized_rows, parse_warnings = pivot_kma_short_forecast_items(raw_items)
    warnings.extend(parse_warnings)
    if normalized_rows:
        forecast_base_at = datetime.fromisoformat(str(normalized_rows[0]["forecast_base_at"]))
    else:
        from app.services.kma_short_forecast_parser import parse_kma_datetime

        forecast_base_at = parse_kma_datetime(base_date, base_time)

    matched_rows = normalized_rows
    if target_start_at and target_end_at:
        matched_rows, match_warnings = match_forecast_rows_to_period(
            normalized_rows, start_at=target_start_at, end_at=target_end_at
        )
        warnings.extend(match_warnings)

    now = utc_now()
    snapshot_id = _new_id("FIS")
    row = ForecastInputSnapshot(
        snapshot_id=snapshot_id,
        prediction_job_id=prediction_job_id,
        entity_id=entity_id,
        nx=nx,
        ny=ny,
        source_system=SOURCE_SYSTEM,
        source_operation_id=source_operation_id,
        request_base_date=base_date,
        request_base_time=base_time,
        forecast_base_at=forecast_base_at,
        requested_at=now,
        cache_key=cache_key,
        request_params_masked=mask_params_dict(runtime),
        raw_response_snapshot_id=raw_snapshot_id,
        raw_response_json=raw_items[:200],
        normalized_rows_json=normalized_rows,
        row_count=len(normalized_rows),
        cache_hit_yn=False,
        success_yn=True,
        created_at=now,
    )
    db.add(row)
    await db.flush()

    return {
        "snapshot_id": snapshot_id,
        "cache_hit": cache_hit,
        "cache_key": cache_key,
        "forecast_base_at": forecast_base_at.isoformat() if forecast_base_at else None,
        "normalized_rows": normalized_rows,
        "matched_rows": matched_rows,
        "warnings": warnings,
        "raw_response_snapshot_id": raw_snapshot_id,
    }


async def preview_forecast_input(
    db: AsyncSession,
    *,
    entity_id: str,
    base_date: str | None = None,
    base_time: str | None = None,
    cache_policy: str = "REFRESH",
    target_start_at: datetime | None = None,
    target_end_at: datetime | None = None,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    readiness = await compute_weather_readiness(db, entity_id)
    if not readiness.get("forecast_ready"):
        raise ForecastProviderError(
            "단기예보 격자(nx/ny)가 준비되지 않았습니다. 예측 대상 화면에서 기상 매핑을 완료하세요.",
            error_code="FORECAST_NOT_READY",
        )
    grid = await get_entity_forecast_grid(db, entity_id)
    if not grid:
        raise ForecastProviderError("단기예보 격자 정보를 찾을 수 없습니다.", error_code="FORECAST_GRID_NOT_FOUND")

    config = await get_provider_config(db) or {}
    operation_id = source_operation_id or config.get("source_operation_id")
    if not operation_id:
        raise ForecastProviderError(
            "Forecast Provider에 연결할 REST API 작업(source_operation_id)이 설정되지 않았습니다.",
            error_code="MISSING_SOURCE_OPERATION",
        )

    resolved = await resolve_base_time_options(db, base_date=base_date, base_time=base_time)
    result = await fetch_and_normalize_forecast(
        db,
        entity_id=entity_id,
        nx=int(grid["nx"]),
        ny=int(grid["ny"]),
        base_date=resolved["base_date"],
        base_time=resolved["base_time"],
        source_operation_id=operation_id,
        config=config,
        cache_policy=cache_policy,
        target_start_at=target_start_at,
        target_end_at=target_end_at,
    )
    return {
        "entity_id": entity_id,
        "nx": grid["nx"],
        "ny": grid["ny"],
        "forecast_base_at": result.get("forecast_base_at"),
        "target_start_at": target_start_at.isoformat() if target_start_at else None,
        "target_end_at": target_end_at.isoformat() if target_end_at else None,
        "row_count": len(result.get("normalized_rows") or []),
        "matched_row_count": len(result.get("matched_rows") or []),
        "cache_hit": result.get("cache_hit", False),
        "snapshot_id": result.get("snapshot_id"),
        "sample_rows": (result.get("matched_rows") or result.get("normalized_rows") or [])[:5],
        "warnings": result.get("warnings") or [],
        "source_operation_id": operation_id,
    }


async def provide_forecast_for_prediction_job(
    db: AsyncSession,
    *,
    prediction_job_id: str,
    entity_id: str,
    target_start_at: datetime,
    target_end_at: datetime,
    base_date: str | None = None,
    base_time: str | None = None,
    cache_policy: str = "USE_CACHE",
    source_operation_id: str | None = None,
    weather_input_required: bool = True,
) -> dict[str, Any]:
    try:
        readiness = await compute_weather_readiness(db, entity_id)
        if not readiness.get("forecast_ready"):
            raise ForecastProviderError(
                "단기예보 격자(nx/ny)가 준비되지 않았습니다.",
                error_code="FORECAST_NOT_READY",
            )
        grid = await get_entity_forecast_grid(db, entity_id)
        if not grid:
            raise ForecastProviderError("단기예보 격자 정보를 찾을 수 없습니다.", error_code="FORECAST_GRID_NOT_FOUND")

        config = await get_provider_config(db) or {}
        operation_id = source_operation_id or config.get("source_operation_id")
        if not operation_id:
            raise ForecastProviderError(
                "Forecast Provider REST API 작업이 설정되지 않았습니다.",
                error_code="MISSING_SOURCE_OPERATION",
            )

        resolved = await resolve_base_time_options(db, base_date=base_date, base_time=base_time)
        fetch_result = await fetch_and_normalize_forecast(
            db,
            entity_id=entity_id,
            nx=int(grid["nx"]),
            ny=int(grid["ny"]),
            base_date=resolved["base_date"],
            base_time=resolved["base_time"],
            source_operation_id=operation_id,
            config=config,
            cache_policy=cache_policy,
            prediction_job_id=prediction_job_id,
            target_start_at=target_start_at,
            target_end_at=target_end_at,
        )
        matched_rows = fetch_result.get("matched_rows") or []
        saved = await save_prediction_weather_inputs(
            db,
            prediction_job_id=prediction_job_id,
            snapshot_id=fetch_result.get("snapshot_id"),
            entity_id=entity_id,
            nx=int(grid["nx"]),
            ny=int(grid["ny"]),
            rows=matched_rows,
        )
        return {
            "enabled": True,
            "entity_id": entity_id,
            "nx": grid["nx"],
            "ny": grid["ny"],
            "source_operation_id": operation_id,
            "forecast_base_at": fetch_result.get("forecast_base_at"),
            "target_row_count": len(fetch_result.get("normalized_rows") or []),
            "matched_row_count": len(matched_rows),
            "saved_input_count": len(saved),
            "cache_hit": fetch_result.get("cache_hit", False),
            "snapshot_id": fetch_result.get("snapshot_id"),
            "warnings": fetch_result.get("warnings") or [],
        }
    except ForecastProviderError as exc:
        if weather_input_required:
            raise
        return {
            "enabled": True,
            "entity_id": entity_id,
            "failed": True,
            "error_message": str(exc),
            "warnings": [f"단기예보 입력 생성 실패: {exc}"],
        }


async def list_forecast_snapshots(
    db: AsyncSession,
    *,
    prediction_job_id: str | None = None,
    entity_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = select(ForecastInputSnapshot).order_by(ForecastInputSnapshot.requested_at.desc())
    if prediction_job_id:
        q = q.where(ForecastInputSnapshot.prediction_job_id == prediction_job_id)
    if entity_id:
        q = q.where(ForecastInputSnapshot.entity_id == entity_id)
    rows = (await db.execute(q.limit(limit))).scalars().all()
    return [_snapshot_dict(r) for r in rows]


async def get_forecast_snapshot(db: AsyncSession, snapshot_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(ForecastInputSnapshot).where(ForecastInputSnapshot.snapshot_id == snapshot_id)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    data = _snapshot_dict(row)
    data["sample_rows"] = (row.normalized_rows_json or [])[:10]
    return data


async def forecast_request_preview(
    db: AsyncSession,
    *,
    entity_id: str,
    base_date: str | None = None,
    base_time: str | None = None,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    grid = await get_entity_forecast_grid(db, entity_id)
    if not grid:
        raise ForecastProviderError("단기예보 격자 정보를 찾을 수 없습니다.", error_code="FORECAST_GRID_NOT_FOUND")
    config = await get_provider_config(db) or {}
    operation_id = source_operation_id or config.get("source_operation_id")
    if not operation_id:
        raise ForecastProviderError(
            "Forecast Provider REST API 작업이 설정되지 않았습니다.",
            error_code="MISSING_SOURCE_OPERATION",
        )
    resolved = await resolve_base_time_options(db, base_date=base_date, base_time=base_time)
    runtime = _runtime_params(
        nx=int(grid["nx"]),
        ny=int(grid["ny"]),
        base_date=resolved["base_date"],
        base_time=resolved["base_time"],
        config=config,
    )
    preview = await build_request_preview(db, operation_id, runtime)
    return {
        "entity_id": entity_id,
        "nx": grid["nx"],
        "ny": grid["ny"],
        "base_date": resolved["base_date"],
        "base_time": resolved["base_time"],
        "forecast_base_at": resolved.get("forecast_base_at"),
        "source_operation_id": operation_id,
        **preview,
    }


def ensure_no_secret_leak(payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    banned = ("servicekey=", "decoding", "encoding")
    return not any(token in text for token in banned if token != "decoding")
