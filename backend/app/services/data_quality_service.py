"""데이터 품질 점검 — 열수요 실적·기상 관측 DB 기반."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    DataQualityRun,
    DataSource,
    HeatDemandActual,
    Site,
    WeatherArea,
    WeatherObservation,
)

MIN_HISTORY_HOURS = 168
HEAT_TABLE = "tb_heat_demand_actual"
WEATHER_TABLE = "tb_weather_observation"


@dataclass
class QualityCheckParams:
    source_id: str | None = None
    data_domain: str | None = None
    site_id: str | None = None
    weather_area_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


@dataclass
class QualitySummary:
    target_table: str
    data_domain: str
    total_count: int = 0
    checked_start_at: str | None = None
    checked_end_at: str | None = None
    missing_count: int = 0
    duplicate_count: int = 0
    time_gap_count: int = 0
    outlier_count: int = 0
    invalid_reference_count: int = 0
    min_history_hours: int = MIN_HISTORY_HOURS
    quality_score: float = 100.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_table": self.target_table,
            "data_domain": self.data_domain,
            "total_count": self.total_count,
            "checked_start_at": self.checked_start_at,
            "checked_end_at": self.checked_end_at,
            "missing_count": self.missing_count,
            "duplicate_count": self.duplicate_count,
            "time_gap_count": self.time_gap_count,
            "outlier_count": self.outlier_count,
            "invalid_reference_count": self.invalid_reference_count,
            "min_history_hours": self.min_history_hours,
            "quality_score": round(self.quality_score, 2),
            "warnings": self.warnings,
            "errors": self.errors,
            "missing_rate": round(self.missing_count / self.total_count, 4) if self.total_count else 0.0,
        }


def _compute_quality_score(summary: QualitySummary) -> float:
    if summary.total_count == 0:
        return 0.0 if summary.errors else 100.0
    missing_rate = summary.missing_count / summary.total_count
    duplicate_rate = summary.duplicate_count / summary.total_count
    gap_rate = summary.time_gap_count / summary.total_count
    outlier_rate = summary.outlier_count / summary.total_count
    return max(0.0, 100.0 - missing_rate * 40 - duplicate_rate * 20 - gap_rate * 20 - outlier_rate * 20)


def _count_hourly_gaps(timestamps: list[datetime]) -> int:
    if len(timestamps) < 2:
        return 0
    gaps = 0
    for prev, curr in zip(timestamps, timestamps[1:]):
        delta_h = (curr - prev).total_seconds() / 3600
        if delta_h > 1.01:
            gaps += int(round(delta_h)) - 1
    return gaps


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


async def resolve_domains(db: AsyncSession, params: QualityCheckParams) -> list[str]:
    if params.source_id:
        source = (
            await db.execute(select(DataSource).where(DataSource.data_source_id == params.source_id))
        ).scalar_one_or_none()
        if not source:
            raise ValueError(f"데이터 소스를 찾을 수 없습니다: {params.source_id}")
        domain = source.source_category.upper()
        if domain in ("HEAT_DEMAND", "WEATHER"):
            return [domain]
        raise ValueError(f"지원하지 않는 data_domain: {domain}")

    if params.data_domain:
        domain = params.data_domain.upper()
        if domain == "ALL":
            return ["HEAT_DEMAND", "WEATHER"]
        if domain in ("HEAT_DEMAND", "WEATHER"):
            return [domain]
        raise ValueError(f"지원하지 않는 data_domain: {domain}")

    return ["HEAT_DEMAND", "WEATHER"]


def _heat_filters(params: QualityCheckParams) -> list:
    clauses = []
    if params.site_id:
        clauses.append(HeatDemandActual.site_id == params.site_id)
    if params.start_at:
        clauses.append(HeatDemandActual.measured_at >= params.start_at)
    if params.end_at:
        clauses.append(HeatDemandActual.measured_at <= params.end_at)
    return clauses


def _weather_filters(params: QualityCheckParams) -> list:
    clauses = []
    if params.weather_area_id:
        clauses.append(WeatherObservation.weather_area_id == params.weather_area_id)
    if params.start_at:
        clauses.append(WeatherObservation.measured_at >= params.start_at)
    if params.end_at:
        clauses.append(WeatherObservation.measured_at <= params.end_at)
    return clauses


async def check_heat_demand(db: AsyncSession, params: QualityCheckParams) -> QualitySummary:
    summary = QualitySummary(target_table=HEAT_TABLE, data_domain="HEAT_DEMAND")
    filters = _heat_filters(params)

    total = (
        await db.execute(select(func.count()).select_from(HeatDemandActual).where(and_(*filters) if filters else True))
    ).scalar_one()
    summary.total_count = int(total)

    if summary.total_count == 0:
        summary.warnings.append("점검 대상 열수요 데이터가 없습니다.")
        summary.quality_score = _compute_quality_score(summary)
        return summary

    bounds = (
        await db.execute(
            select(func.min(HeatDemandActual.measured_at), func.max(HeatDemandActual.measured_at)).where(
                and_(*filters) if filters else True
            )
        )
    ).one()
    summary.checked_start_at = _iso(bounds[0])
    summary.checked_end_at = _iso(bounds[1])

    base = and_(*filters) if filters else True

    summary.missing_count = int(
        (
            await db.execute(
                select(func.count()).select_from(HeatDemandActual).where(
                    base,
                    (HeatDemandActual.site_id.is_(None))
                    | (HeatDemandActual.site_id == "")
                    | (HeatDemandActual.measured_at.is_(None))
                    | (HeatDemandActual.heat_demand.is_(None)),
                )
            )
        ).scalar_one()
    )

    negative_count = int(
        (
            await db.execute(
                select(func.count()).select_from(HeatDemandActual).where(base, HeatDemandActual.heat_demand < 0)
            )
        ).scalar_one()
    )
    if negative_count:
        summary.errors.append(f"heat_demand 음수 {negative_count}건")

    zero_count = int(
        (
            await db.execute(
                select(func.count()).select_from(HeatDemandActual).where(base, HeatDemandActual.heat_demand <= 0)
            )
        ).scalar_one()
    )
    if zero_count:
        summary.warnings.append(f"heat_demand 0 이하 {zero_count}건")

    valid_sites = {r[0] for r in (await db.execute(select(Site.site_id))).all()}
    distinct_sites = [
        r[0]
        for r in (
            await db.execute(select(HeatDemandActual.site_id).where(base).distinct())
        ).all()
    ]
    invalid_sites = [s for s in distinct_sites if s and s not in valid_sites]
    if invalid_sites:
        summary.invalid_reference_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(HeatDemandActual).where(
                        base, HeatDemandActual.site_id.in_(invalid_sites)
                    )
                )
            ).scalar_one()
        )
        summary.errors.append(f"tb_site에 없는 site_id: {', '.join(invalid_sites[:5])}")

    dup_rows = (
        await db.execute(
            select(HeatDemandActual.site_id, HeatDemandActual.measured_at, func.count())
            .where(base)
            .group_by(HeatDemandActual.site_id, HeatDemandActual.measured_at)
            .having(func.count() > 1)
        )
    ).all()
    summary.duplicate_count = sum(int(r[2]) - 1 for r in dup_rows)

    rows = (
        await db.execute(
            select(HeatDemandActual.site_id, HeatDemandActual.measured_at, HeatDemandActual.heat_demand).where(base)
        )
    ).all()

    by_site: dict[str, list[datetime]] = {}
    demands: list[float] = []
    for site_id, measured_at, heat_demand in rows:
        if site_id and measured_at:
            by_site.setdefault(site_id, []).append(measured_at)
        if heat_demand is not None:
            demands.append(float(heat_demand))

    for site_id, times in by_site.items():
        times.sort()
        summary.time_gap_count += _count_hourly_gaps(times)
        span_h = (times[-1] - times[0]).total_seconds() / 3600 + 1 if len(times) > 1 else 1
        if span_h < MIN_HISTORY_HOURS:
            summary.warnings.append(
                f"{site_id}: 이력 {int(span_h)}시간 — lag_168h 생성에 {MIN_HISTORY_HOURS}시간 필요"
            )

    if len(demands) >= 2:
        avg = mean(demands)
        std = pstdev(demands)
        if std > 0:
            lower, upper = avg - 3 * std, avg + 3 * std
            summary.outlier_count = sum(1 for v in demands if v < lower or v > upper)

    summary.quality_score = _compute_quality_score(summary)
    return summary


async def check_weather(db: AsyncSession, params: QualityCheckParams) -> QualitySummary:
    summary = QualitySummary(target_table=WEATHER_TABLE, data_domain="WEATHER")
    filters = _weather_filters(params)

    total = (
        await db.execute(
            select(func.count()).select_from(WeatherObservation).where(and_(*filters) if filters else True)
        )
    ).scalar_one()
    summary.total_count = int(total)

    if summary.total_count == 0:
        summary.warnings.append("점검 대상 기상 데이터가 없습니다.")
        summary.quality_score = _compute_quality_score(summary)
        return summary

    bounds = (
        await db.execute(
            select(func.min(WeatherObservation.measured_at), func.max(WeatherObservation.measured_at)).where(
                and_(*filters) if filters else True
            )
        )
    ).one()
    summary.checked_start_at = _iso(bounds[0])
    summary.checked_end_at = _iso(bounds[1])

    base = and_(*filters) if filters else True

    summary.missing_count = int(
        (
            await db.execute(
                select(func.count()).select_from(WeatherObservation).where(
                    base,
                    (WeatherObservation.weather_area_id.is_(None))
                    | (WeatherObservation.weather_area_id == "")
                    | (WeatherObservation.measured_at.is_(None))
                    | (WeatherObservation.data_type.is_(None))
                    | (WeatherObservation.data_type == "")
                    | (
                        WeatherObservation.temperature.is_(None)
                        & WeatherObservation.humidity.is_(None)
                        & WeatherObservation.rainfall.is_(None)
                        & WeatherObservation.wind_speed.is_(None)
                    ),
                )
            )
        ).scalar_one()
    )

    valid_areas = {r[0] for r in (await db.execute(select(WeatherArea.weather_area_id))).all()}
    distinct_areas = [
        r[0]
        for r in (
            await db.execute(select(WeatherObservation.weather_area_id).where(base).distinct())
        ).all()
    ]
    invalid_areas = [a for a in distinct_areas if a and a not in valid_areas]
    if invalid_areas:
        summary.invalid_reference_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(WeatherObservation).where(
                        base, WeatherObservation.weather_area_id.in_(invalid_areas)
                    )
                )
            ).scalar_one()
        )
        summary.errors.append(f"tb_weather_area에 없는 weather_area_id: {', '.join(invalid_areas[:5])}")

    dup_rows = (
        await db.execute(
            select(
                WeatherObservation.weather_area_id,
                WeatherObservation.measured_at,
                WeatherObservation.data_type,
                func.count(),
            )
            .where(base)
            .group_by(
                WeatherObservation.weather_area_id,
                WeatherObservation.measured_at,
                WeatherObservation.data_type,
            )
            .having(func.count() > 1)
        )
    ).all()
    summary.duplicate_count = sum(int(r[3]) - 1 for r in dup_rows)

    rows = (
        await db.execute(
            select(
                WeatherObservation.weather_area_id,
                WeatherObservation.data_type,
                WeatherObservation.measured_at,
                WeatherObservation.temperature,
                WeatherObservation.humidity,
                WeatherObservation.rainfall,
                WeatherObservation.wind_speed,
            ).where(base)
        )
    ).all()

    by_key: dict[tuple[str, str], list[datetime]] = {}
    for area_id, data_type, measured_at, temp, hum, rain, wind in rows:
        if area_id and data_type and measured_at:
            by_key.setdefault((area_id, data_type), []).append(measured_at)
        if temp is not None and (temp < -40 or temp > 50):
            summary.outlier_count += 1
        if hum is not None and (hum < 0 or hum > 100):
            summary.outlier_count += 1
        if rain is not None and rain < 0:
            summary.outlier_count += 1
        if wind is not None and wind < 0:
            summary.outlier_count += 1

    for times in by_key.values():
        times.sort()
        summary.time_gap_count += _count_hourly_gaps(times)

    summary.quality_score = _compute_quality_score(summary)
    return summary


def _merge_summaries(summaries: list[QualitySummary], data_domain: str, check_type: str) -> dict[str, Any]:
    if len(summaries) == 1:
        result = summaries[0].to_dict()
        result["check_type"] = check_type
        return result

    total = sum(s.total_count for s in summaries)
    merged = QualitySummary(
        target_table=",".join(s.target_table for s in summaries),
        data_domain=data_domain,
        total_count=total,
        missing_count=sum(s.missing_count for s in summaries),
        duplicate_count=sum(s.duplicate_count for s in summaries),
        time_gap_count=sum(s.time_gap_count for s in summaries),
        outlier_count=sum(s.outlier_count for s in summaries),
        invalid_reference_count=sum(s.invalid_reference_count for s in summaries),
        warnings=[w for s in summaries for w in s.warnings],
        errors=[e for s in summaries for e in s.errors],
    )
    starts = [s.checked_start_at for s in summaries if s.checked_start_at]
    ends = [s.checked_end_at for s in summaries if s.checked_end_at]
    merged.checked_start_at = min(starts) if starts else None
    merged.checked_end_at = max(ends) if ends else None
    merged.quality_score = _compute_quality_score(merged)
    result = merged.to_dict()
    result["check_type"] = check_type
    result["checks"] = [s.to_dict() for s in summaries]
    return result


def _determine_status(summary_dict: dict[str, Any]) -> str:
    if summary_dict.get("errors"):
        return "FAILED"
    if summary_dict.get("warnings"):
        return "WARNING"
    return "SUCCESS"


async def run_quality_check(db: AsyncSession, params: QualityCheckParams) -> dict[str, Any]:
    started = utc_now()
    run_id = f"DQR-{started.strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}"

    try:
        domains = await resolve_domains(db, params)
    except ValueError as exc:
        finished = utc_now()
        summary = {
            "data_domain": params.data_domain or "UNKNOWN",
            "errors": [str(exc)],
            "quality_score": 0.0,
            "total_count": 0,
        }
        run = DataQualityRun(
            run_id=run_id,
            source_id=params.source_id,
            check_type="QUALITY",
            run_status="FAILED",
            result_summary=summary,
            started_at=started,
            finished_at=finished,
        )
        db.add(run)
        await db.flush()
        return {"run_id": run_id, "status": "FAILED", "result_summary": summary, "error_message": str(exc)}

    summaries: list[QualitySummary] = []
    for domain in domains:
        if domain == "HEAT_DEMAND":
            summaries.append(await check_heat_demand(db, params))
        elif domain == "WEATHER":
            summaries.append(await check_weather(db, params))

    check_type = domains[0] if len(domains) == 1 else "FULL"
    merged_domain = domains[0] if len(domains) == 1 else "ALL"
    result_summary = _merge_summaries(summaries, merged_domain, check_type)
    status = _determine_status(result_summary)
    finished = utc_now()

    run = DataQualityRun(
        run_id=run_id,
        source_id=params.source_id,
        check_type=check_type,
        run_status=status,
        result_summary=result_summary,
        started_at=started,
        finished_at=finished,
    )
    db.add(run)
    await db.flush()

    return {
        "run_id": run_id,
        "status": status,
        "result_summary": result_summary,
        "error_message": "; ".join(result_summary.get("errors", [])) or None,
    }
