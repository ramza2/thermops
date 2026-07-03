"""Feature Dataset 생성 서비스."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import (
    Calendar,
    DataQualityRun,
    DatasetVersion,
    FeatureDataset,
    FeatureSet,
    HeatDemandActual,
    SiteWeatherMapping,
    WeatherObservation,
)
from app.services.feature_lineage_service import save_feature_lineage
from app.services.feature_recipe_engine_service import (
    build_template_diagnostics,
    build_template_features,
    split_feature_names_by_recipe,
    summarize_template_build_result,
)
from app.services.feature_recipe_service import load_published_recipes_for_features
from app.services.feature_registration_service import (
    analyze_feature_set_coverage,
    is_tpl_feature_set,
)
from app.services.dataset_version_policy_service import (
    classify_build_scope,
    classify_dataset_version_metadata,
)

MIN_HISTORY_HOURS = 168


@dataclass
class FeatureBuildParams:
    feature_set_id: str
    site_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


def _load_ml_features():
    root = get_settings().project_root
    for candidate in (root / "ml", Path("/ml"), Path(__file__).resolve().parents[3] / "ml"):
        if candidate.exists():
            p = str(candidate.resolve())
            if p not in sys.path:
                sys.path.insert(0, p)
            break
    import features as feat  # noqa: WPS433

    return feat


async def _load_site_weather_map(db: AsyncSession) -> dict[str, str]:
    rows = (
        await db.execute(
            select(SiteWeatherMapping.site_id, SiteWeatherMapping.weather_area_id)
            .where(SiteWeatherMapping.active_yn == "Y")
            .order_by(SiteWeatherMapping.priority_no)
        )
    ).all()
    mapping: dict[str, str] = {}
    for site_id, area_id in rows:
        if site_id not in mapping:
            mapping[site_id] = area_id
    return mapping


async def _fetch_heat(
    db: AsyncSession, site_id: str | None, start_at: datetime | None, end_at: datetime | None
) -> pd.DataFrame:
    clauses = []
    if site_id:
        clauses.append(HeatDemandActual.site_id == site_id)
    if start_at:
        clauses.append(HeatDemandActual.measured_at >= start_at)
    if end_at:
        clauses.append(HeatDemandActual.measured_at <= end_at)
    q = select(
        HeatDemandActual.site_id,
        HeatDemandActual.measured_at,
        HeatDemandActual.heat_demand,
    )
    if clauses:
        q = q.where(and_(*clauses))
    rows = (await db.execute(q.order_by(HeatDemandActual.site_id, HeatDemandActual.measured_at))).all()
    return pd.DataFrame(rows, columns=["site_id", "measured_at", "heat_demand"])


async def _fetch_weather(
    db: AsyncSession, area_ids: list[str], start_at: datetime | None, end_at: datetime | None
) -> pd.DataFrame:
    if not area_ids:
        return pd.DataFrame(columns=["weather_area_id", "measured_at", "temperature", "humidity", "rainfall", "wind_speed"])
    clauses = [WeatherObservation.weather_area_id.in_(area_ids)]
    if start_at:
        clauses.append(WeatherObservation.measured_at >= start_at)
    if end_at:
        clauses.append(WeatherObservation.measured_at <= end_at)
    q = select(
        WeatherObservation.weather_area_id,
        WeatherObservation.measured_at,
        WeatherObservation.temperature,
        WeatherObservation.humidity,
        WeatherObservation.rainfall,
        WeatherObservation.wind_speed,
    ).where(and_(*clauses))
    rows = (await db.execute(q.order_by(WeatherObservation.weather_area_id, WeatherObservation.measured_at))).all()
    return pd.DataFrame(
        rows,
        columns=["weather_area_id", "measured_at", "temperature", "humidity", "rainfall", "wind_speed"],
    )


async def _fetch_calendar(db: AsyncSession, start_at: datetime | None, end_at: datetime | None) -> pd.DataFrame:
    clauses = []
    if start_at:
        clauses.append(Calendar.calendar_date >= start_at.date())
    if end_at:
        clauses.append(Calendar.calendar_date <= end_at.date())
    q = select(
        Calendar.calendar_date,
        Calendar.day_of_week,
        Calendar.is_weekend,
        Calendar.is_holiday,
        Calendar.season,
    )
    if clauses:
        q = q.where(and_(*clauses))
    rows = (await db.execute(q)).all()
    return pd.DataFrame(rows, columns=["calendar_date", "day_of_week", "is_weekend", "is_holiday", "season"])


async def get_feature_set(db: AsyncSession, feature_set_id: str) -> FeatureSet:
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise ValueError(f"Feature Set을 찾을 수 없습니다: {feature_set_id}")
    return fs


async def build_feature_dataframe(
    db: AsyncSession, params: FeatureBuildParams, feature_names: list[str] | None = None
) -> tuple[pd.DataFrame, list[str], list[str], dict[str, Any]]:
    """Feature DataFrame, warnings/errors, 커버리지 분석 반환."""
    warnings: list[str] = []
    errors: list[str] = []

    site_map = await _load_site_weather_map(db)
    heat_df = await _fetch_heat(db, params.site_id, params.start_at, params.end_at)
    if heat_df.empty:
        errors.append("열수요 실적 데이터가 없습니다.")
        return pd.DataFrame(), warnings, errors, {}

    area_ids = list({site_map.get(s) for s in heat_df["site_id"].unique() if site_map.get(s)})
    missing_map = [s for s in heat_df["site_id"].unique() if s not in site_map]
    if missing_map:
        warnings.append(f"기상 권역 매핑 없음: {', '.join(missing_map[:5])}")

    weather_df = await _fetch_weather(db, area_ids, params.start_at, params.end_at)
    cal_df = await _fetch_calendar(db, params.start_at, params.end_at)
    if cal_df.empty:
        warnings.append("tb_calendar 데이터가 없어 요일·공휴일 Feature가 기본값으로 계산됩니다.")

    feat = _load_ml_features()
    full_df = feat.build_feature_frame(heat_df, weather_df, cal_df, site_map)

    for site_id, grp in full_df.groupby("site_id"):
        span = (grp["measured_at"].max() - grp["measured_at"].min()).total_seconds() / 3600 + 1
        if span < MIN_HISTORY_HOURS:
            warnings.append(f"{site_id}: 이력 {int(span)}h — lag_168h 일부 결측 가능")

    coverage: dict[str, Any] = {}
    if feature_names:
        coverage = analyze_feature_set_coverage(feature_names, list(full_df.columns))
        missing_feats = coverage.get("missing_features") or []
        if missing_feats:
            preview = ", ".join(missing_feats[:5])
            if len(missing_feats) > 5:
                preview += f" 외 {len(missing_feats) - 5}건"
            warnings.append(f"미계산 Feature: {preview}")
            catalog_only = coverage.get("catalog_only_features") or []
            if catalog_only:
                warnings.append(
                    f"카탈로그 전용(계산 로직 없음): {', '.join(catalog_only[:5])}"
                )
            legacy = coverage.get("legacy_alias_features") or []
            if legacy:
                warnings.append(
                    f"레거시 별칭(공식명 사용 권장): {', '.join(legacy[:5])}"
                )

    return full_df, warnings, errors, coverage


async def preview_features(
    db: AsyncSession,
    feature_set_id: str,
    site_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    fs = await get_feature_set(db, feature_set_id)
    params = FeatureBuildParams(
        feature_set_id=feature_set_id,
        site_id=site_id,
        start_at=start_at,
        end_at=end_at,
    )
    df, warnings, errors, _coverage = await build_feature_dataframe(db, params, fs.features or [])
    if errors:
        raise ValueError("; ".join(errors))

    feat = _load_ml_features()
    preview = feat.rows_to_preview(df, fs.features or [], limit=limit)
    return {
        "feature_set_id": feature_set_id,
        "preview": preview,
        "preview_rows": preview,
        "feature_names": fs.features or [],
        "warnings": warnings,
        "errors": errors,
    }


def _dataset_version_id(feature_set_id: str) -> str:
    stamp = utc_now().strftime("%Y%m%d%H%M%S%f")
    return f"DSV-{feature_set_id}-{stamp}"[:80]


def _feature_config_hash(feature_names: list[str]) -> str:
    payload = ",".join(sorted(feature_names))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


async def run_feature_build(db: AsyncSession, params: FeatureBuildParams) -> dict[str, Any]:
    started = utc_now()
    job_id = f"FBJ-{started.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    fs = await get_feature_set(db, params.feature_set_id)
    feature_names: list[str] = fs.features or []

    published_recipes = await load_published_recipes_for_features(db, feature_names)
    code_feature_names, template_recipes = split_feature_names_by_recipe(
        feature_names, published_recipes
    )

    run = DataQualityRun(
        run_id=job_id,
        source_id=params.feature_set_id,
        check_type="FEATURE_BUILD",
        run_status="RUNNING",
        started_at=started,
    )
    db.add(run)
    await db.flush()

    try:
        df, warnings, errors, coverage = await build_feature_dataframe(
            db, params, code_feature_names or None
        )
        if errors:
            raise ValueError("; ".join(errors))

        if df.empty:
            raise ValueError("생성할 Feature 행이 없습니다.")

        template_result: dict[str, Any] = {}
        template_lineage_map: dict[str, dict[str, Any]] = {}
        if template_recipes:
            if is_tpl_feature_set(params.feature_set_id):
                tpl_names = [r.feature_name for r in template_recipes if r.feature_name]
                warnings.append(
                    f"공식 TPL Feature Set에 TEMPLATE Recipe Feature 포함: {', '.join(tpl_names)}"
                )
            template_result = build_template_features(df, template_recipes)
            df = template_result["feature_frame"]
            warnings.extend(template_result.get("warnings") or [])
            for item in template_result.get("lineage_items") or []:
                template_lineage_map[item["feature_name"]] = item

        final_coverage = analyze_feature_set_coverage(feature_names, list(df.columns))
        template_summary = summarize_template_build_result(
            template_result,
            code_feature_count=len(code_feature_names),
        )
        if template_recipes:
            template_summary.update(
                build_template_diagnostics(template_recipes, template_result, df)
            )
        final_coverage.update(template_summary)

        generated_count = final_coverage.get("generated_feature_count", 0)
        missing_count = final_coverage.get("missing_feature_count", 0)
        if missing_count > 0 and generated_count > 0:
            missing_feats = final_coverage.get("missing_features") or []
            preview = ", ".join(missing_feats[:5])
            if len(missing_feats) > 5:
                preview += f" 외 {len(missing_feats) - 5}건"
            warnings.append(f"미계산 Feature: {preview}")

        if generated_count == 0:
            raise ValueError("Feature Set에 포함된 Feature를 계산할 수 없습니다.")

        dataset_version_id = _dataset_version_id(params.feature_set_id)
        start_ts = params.start_at or df["measured_at"].min()
        end_ts = params.end_at or df["measured_at"].max()
        site_count = int(df["site_id"].nunique())

        dv = DatasetVersion(
            dataset_version_id=dataset_version_id,
            dataset_type="FEATURE",
            feature_set_id=params.feature_set_id,
            base_start_at=start_ts,
            base_end_at=end_ts,
            feature_config_hash=_feature_config_hash(feature_names),
            record_count=0,
            feature_count=len(feature_names),
            build_started_at=started,
            created_by="feature_build_api",
            created_at=utc_now(),
        )
        db.add(dv)
        await db.flush()

        # 동일 버전 재실행 시 기존 행 제거
        await db.execute(delete(FeatureDataset).where(FeatureDataset.dataset_version_id == dataset_version_id))

        inserted = 0
        now = utc_now()
        for _, row in df.iterrows():
            feat_values = {name: _json_val(row.get(name)) for name in feature_names if name in row.index}
            feat_values["feature_set_id"] = params.feature_set_id
            feat_values["heat_demand"] = _json_val(row.get("heat_demand"))

            record = FeatureDataset(
                dataset_version_id=dataset_version_id,
                site_id=str(row["site_id"]),
                feature_at=row["measured_at"].to_pydatetime()
                if hasattr(row["measured_at"], "to_pydatetime")
                else row["measured_at"],
                target_heat_demand=float(row["heat_demand"]) if pd.notna(row["heat_demand"]) else None,
                temp=_json_val(row.get("temperature")),
                humidity=_json_val(row.get("humidity")),
                lag_24h_demand=_json_val(row.get("demand_lag_24h")),
                lag_168h_demand=_json_val(row.get("demand_lag_168h")),
                rolling_24h_avg=_json_val(row.get("demand_ma_24h")),
                feature_json=feat_values,
                created_at=now,
            )
            db.add(record)
            inserted += 1

        dv.record_count = inserted

        site_ids = sorted(str(s) for s in df["site_id"].unique())
        lineage_count = 0
        lineage_error: str | None = None
        try:
            async with db.begin_nested():
                lineage_count = await save_feature_lineage(
                    db,
                    dataset_version_id=dataset_version_id,
                    job_id=job_id,
                    feature_set_id=params.feature_set_id,
                    site_filter=params.site_id,
                    feature_names=feature_names,
                    build_start_at=start_ts.to_pydatetime() if hasattr(start_ts, "to_pydatetime") else start_ts,
                    build_end_at=end_ts.to_pydatetime() if hasattr(end_ts, "to_pydatetime") else end_ts,
                    site_ids=site_ids,
                    template_lineage_map=template_lineage_map,
                )
        except Exception as lineage_exc:
            lineage_error = str(lineage_exc)
            warnings.append(f"Lineage 저장 실패 (Feature 데이터는 생성됨): {lineage_error}")

        finished = utc_now()

        result_summary = {
            "dataset_version_id": dataset_version_id,
            "feature_set_id": params.feature_set_id,
            "target_table": "tb_feature_dataset",
            "inserted_count": inserted,
            "lineage_count": lineage_count,
            "lineage_error": lineage_error,
            "site_count": site_count,
            "checked_start_at": start_ts.isoformat() if hasattr(start_ts, "isoformat") else str(start_ts),
            "checked_end_at": end_ts.isoformat() if hasattr(end_ts, "isoformat") else str(end_ts),
            "feature_names": feature_names,
            "warnings": warnings,
            "errors": errors,
            **final_coverage,
        }

        has_template_issues = bool(
            template_summary.get("template_build_failed_features")
            or template_summary.get("template_build_unsupported_features")
        )
        if errors:
            run_status = "FAILED"
        elif warnings or has_template_issues or missing_count > 0:
            run_status = "WARNING"
        else:
            run_status = "SUCCESS"

        requested = len(feature_names) or 1
        generated = int(final_coverage.get("generated_feature_count") or 0)
        coverage_ratio = round(generated / requested, 6) if requested else None
        null_cells = 0
        total_cells = 0
        for name in feature_names:
            if name in df.columns:
                col = df[name]
                null_cells += int(col.isna().sum())
                total_cells += len(col)
        null_ratio = round(null_cells / total_cells, 6) if total_cells else None
        build_scope = classify_build_scope(
            site_id=params.site_id,
            start_at=params.start_at,
            end_at=params.end_at,
        )
        meta = classify_dataset_version_metadata(
            build_scope=build_scope,
            record_count=inserted,
            coverage_ratio=coverage_ratio,
            null_ratio=null_ratio,
            run_status=run_status,
            feature_count=len(feature_names),
        )
        dv.build_scope = build_scope
        dv.coverage_ratio = coverage_ratio
        dv.null_ratio = null_ratio
        dv.dataset_version_role = meta["dataset_version_role"]
        dv.dataset_version_status = meta["dataset_version_status"]
        dv.is_training_ready = meta["is_training_ready"]
        dv.is_serving_ready = meta["is_serving_ready"]
        dv.quality_score = meta["quality_score"]
        dv.is_primary = False
        dv.build_finished_at = finished
        dv.metadata_json = {
            "build_scope": build_scope,
            "dataset_version_role": meta["dataset_version_role"],
            "dataset_version_status": meta["dataset_version_status"],
            "coverage_ratio": coverage_ratio,
            "null_ratio": null_ratio,
            "quality_score": meta["quality_score"],
        }
        result_summary.update({
            "build_scope": build_scope,
            "dataset_version_role": meta["dataset_version_role"],
            "dataset_version_status": meta["dataset_version_status"],
            "coverage_ratio": coverage_ratio,
            "null_ratio": null_ratio,
            "quality_score": meta["quality_score"],
        })

        run.run_status = run_status
        run.finished_at = finished
        run.result_summary = result_summary

        return {
            "job_id": job_id,
            "status": run.run_status,
            "inserted_count": inserted,
            "lineage_count": lineage_count,
            "dataset_version_id": dataset_version_id,
            "site_count": site_count,
            "checked_start_at": result_summary["checked_start_at"],
            "checked_end_at": result_summary["checked_end_at"],
            "feature_names": feature_names,
            "warnings": warnings,
            "result_summary": result_summary,
        }
    except Exception as exc:
        finished = utc_now()
        run.run_status = "FAILED"
        run.finished_at = finished
        run.result_summary = {"error_message": str(exc), "feature_set_id": params.feature_set_id}
        return {
            "job_id": job_id,
            "status": "FAILED",
            "inserted_count": 0,
            "error_message": str(exc),
            "result_summary": run.result_summary,
            "warnings": [],
            "feature_names": feature_names,
        }


def _json_val(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


async def get_feature_build_job(db: AsyncSession, job_id: str) -> dict[str, Any] | None:
    run = (
        await db.execute(
            select(DataQualityRun).where(
                DataQualityRun.run_id == job_id,
                DataQualityRun.check_type == "FEATURE_BUILD",
            )
        )
    ).scalar_one_or_none()
    if not run:
        return None
    return _run_to_job_summary(run, include_summary=True)


def _parse_result_summary(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            import json

            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _build_job_message(status: str, summary: dict[str, Any]) -> str:
    if status == "SUCCESS":
        return "Feature build completed"
    if status == "WARNING":
        return "Feature build completed with warnings"
    if status == "FAILED":
        return str(summary.get("error_message") or "Feature build failed")
    if status == "RUNNING":
        return "Feature build in progress"
    return f"Feature build status: {status}"


def _run_to_job_summary(run: DataQualityRun, *, include_summary: bool = True) -> dict[str, Any]:
    summary = _parse_result_summary(run.result_summary)
    feature_set_id = summary.get("feature_set_id") or run.source_id
    started = run.started_at
    finished = run.finished_at
    duration_seconds: float | None = None
    if started and finished:
        duration_seconds = (finished - started).total_seconds()

    item: dict[str, Any] = {
        "job_id": run.run_id,
        "run_id": run.run_id,
        "feature_set_id": feature_set_id,
        "status": run.run_status,
        "started_at": started.isoformat() if started else None,
        "ended_at": finished.isoformat() if finished else None,
        "finished_at": finished.isoformat() if finished else None,
        "duration_seconds": duration_seconds,
        "dataset_version_id": summary.get("dataset_version_id"),
        "row_count": summary.get("inserted_count"),
        "inserted_count": summary.get("inserted_count"),
        "lineage_count": summary.get("lineage_count"),
        "lineage_error": summary.get("lineage_error"),
        "message": _build_job_message(run.run_status, summary),
        "error_message": summary.get("error_message"),
        "warnings": summary.get("warnings", []),
        "feature_names": summary.get("feature_names", []),
    }
    if include_summary:
        item["result_summary"] = summary
    return item


async def list_feature_build_jobs(
    db: AsyncSession,
    *,
    feature_set_id: str | None = None,
    status: str | None = None,
    feature_name: str | None = None,
    recipe_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_summary: bool = True,
) -> dict[str, Any]:
    """FEATURE_BUILD 이력 목록 (tb_data_quality_run)."""
    clauses = [DataQualityRun.check_type == "FEATURE_BUILD"]
    if feature_set_id:
        clauses.append(DataQualityRun.source_id == feature_set_id)
    if status:
        clauses.append(DataQualityRun.run_status == status)

    where = and_(*clauses)
    fetch_limit = limit + offset
    if feature_name or recipe_id:
        fetch_limit = min(500, max(fetch_limit * 10, 100))

    rows = (
        await db.execute(
            select(DataQualityRun)
            .where(where)
            .order_by(DataQualityRun.started_at.desc())
            .limit(fetch_limit)
        )
    ).scalars().all()

    if feature_name or recipe_id:
        filtered: list[DataQualityRun] = []
        for run in rows:
            summary = _parse_result_summary(run.result_summary)
            if recipe_id:
                by_feat = summary.get("template_build_status_by_feature") or {}
                if not any(v.get("recipe_id") == recipe_id for v in by_feat.values()):
                    if feature_name and feature_name not in (summary.get("template_recipe_features") or []):
                        continue
            elif feature_name:
                if feature_name not in (summary.get("feature_names") or []):
                    if feature_name not in (summary.get("template_recipe_features") or []):
                        continue
            filtered.append(run)
        rows = filtered

    total = len(rows)
    page_rows = rows[offset : offset + limit]
    items = [_run_to_job_summary(r, include_summary=include_summary) for r in page_rows]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
