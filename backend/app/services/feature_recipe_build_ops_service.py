"""Recipe Build 운영 검증 — 이력 조회·Preview/Build 비교 (R6-S1)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DataQualityRun, FeatureDataset
from app.services.feature_build_service import _parse_result_summary
from app.services.feature_recipe_preview_service import preview_feature_recipe
from app.services.feature_recipe_service import get_recipe_or_raise, recipe_definition_from_row


def _match_recipe_in_summary(
    summary: dict[str, Any],
    *,
    recipe_id: str,
    feature_name: str | None,
) -> dict[str, Any] | None:
    by_feat = summary.get("template_build_status_by_feature") or {}
    if feature_name and feature_name in by_feat:
        entry = by_feat[feature_name]
        if entry.get("recipe_id") == recipe_id:
            return entry
    for entry in by_feat.values():
        if entry.get("recipe_id") == recipe_id:
            return entry
    recipe_features = summary.get("template_recipe_features") or []
    if feature_name and feature_name in recipe_features:
        return {"status": "UNKNOWN", "null_ratio": None}
    return None


async def list_recipe_build_history(
    db: AsyncSession,
    recipe_id: str,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    feature_name = recipe.feature_name

    rows = (
        await db.execute(
            select(DataQualityRun)
            .where(DataQualityRun.check_type == "FEATURE_BUILD")
            .order_by(DataQualityRun.started_at.desc())
            .limit(500)
        )
    ).scalars().all()

    items: list[dict[str, Any]] = []
    for run in rows:
        summary = _parse_result_summary(run.result_summary)
        entry = _match_recipe_in_summary(summary, recipe_id=recipe_id, feature_name=feature_name)
        if not entry:
            continue
        status = entry.get("status", "UNKNOWN")
        items.append({
            "job_id": run.run_id,
            "feature_set_id": summary.get("feature_set_id") or run.source_id,
            "dataset_version_id": summary.get("dataset_version_id"),
            "status": run.run_status,
            "template_feature_status": status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "row_count": summary.get("inserted_count"),
            "null_ratio": entry.get("null_ratio"),
            "warning_codes": entry.get("warning_codes") or [],
            "error_codes": entry.get("error_codes") or [],
            "warnings": (summary.get("template_build_warnings") or [])[:5],
        })
        if len(items) >= limit:
            break

    latest_status = items[0]["template_feature_status"] if items else "NO_BUILD"
    return {
        "recipe_id": recipe_id,
        "feature_name": feature_name,
        "latest_build_status": latest_status,
        "items": items,
        "total": len(items),
    }


async def compare_preview_with_build(
    db: AsyncSession,
    recipe_id: str,
    *,
    dataset_version_id: str | None = None,
    feature_set_id: str | None = None,
    sample_size: int = 20,
) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    feature_name = recipe.feature_name
    if not feature_name:
        raise ValueError("Recipe에 feature_name이 없습니다.")

    resolved_dsv = dataset_version_id
    if not resolved_dsv:
        hist = await list_recipe_build_history(db, recipe_id, limit=1)
        latest = (hist.get("items") or [None])[0]
        if not latest or not latest.get("dataset_version_id"):
            return {
                "recipe_id": recipe_id,
                "feature_name": feature_name,
                "dataset_version_id": None,
                "feature_set_id": feature_set_id,
                "comparable": False,
                "comparison_policy": "SAMPLE_BY_ENTITY_TIME",
                "items": [],
                "summary": {
                    "sample_count": 0,
                    "matched_count": 0,
                    "mismatch_count": 0,
                    "max_abs_diff": None,
                },
                "warnings": [
                    "dataset_version_id가 없어 최근 Build Job을 찾을 수 없습니다. "
                    "Feature Build를 먼저 실행하거나 dataset_version_id를 지정하세요.",
                ],
            }
        resolved_dsv = str(latest["dataset_version_id"])
        if not feature_set_id and latest.get("feature_set_id"):
            feature_set_id = latest.get("feature_set_id")

    rows = (
        await db.execute(
            select(FeatureDataset)
            .where(FeatureDataset.dataset_version_id == resolved_dsv)
            .order_by(FeatureDataset.site_id, FeatureDataset.feature_at.desc())
            .limit(min(sample_size * 5, 500))
        )
    ).scalars().all()

    if not rows:
        return {
            "recipe_id": recipe_id,
            "feature_name": feature_name,
            "dataset_version_id": resolved_dsv,
            "feature_set_id": feature_set_id,
            "comparable": False,
            "comparison_policy": "SAMPLE_BY_ENTITY_TIME",
            "items": [],
            "summary": {"sample_count": 0, "matched_count": 0, "mismatch_count": 0, "max_abs_diff": None},
            "warnings": ["dataset_version에 Feature Dataset 행이 없습니다."],
        }

    build_samples: list[dict[str, Any]] = []
    for row in rows[:sample_size]:
        fj = row.feature_json or {}
        build_val = fj.get(feature_name)
        build_samples.append({
            "entity_key": row.site_id,
            "time_key": row.feature_at.isoformat() if row.feature_at else None,
            "build_value": build_val,
        })

    feature_ats = [r.feature_at for r in rows if r.feature_at]
    start_at = min(feature_ats) if feature_ats else None
    end_at = max(feature_ats) if feature_ats else None

    definition = recipe_definition_from_row(recipe)
    if recipe.mapping_id:
        definition["mapping_id"] = recipe.mapping_id
    preview_req: dict[str, Any] = {
        **definition,
        "sample_size": sample_size,
    }
    if start_at:
        preview_req["start_at"] = start_at.isoformat()
    if end_at:
        preview_req["end_at"] = end_at.isoformat()

    preview_result = await preview_feature_recipe(db, preview_req)
    preview_rows = preview_result.get("preview_rows") or []
    if not preview_rows:
        return {
            "recipe_id": recipe_id,
            "feature_name": feature_name,
            "dataset_version_id": resolved_dsv,
            "feature_set_id": feature_set_id,
            "comparable": False,
            "comparison_policy": "SAMPLE_BY_ENTITY_TIME",
            "build_samples": build_samples,
            "items": [],
            "summary": {"sample_count": len(build_samples), "matched_count": 0, "mismatch_count": 0, "max_abs_diff": None},
            "warnings": ["Preview 재계산 결과가 없어 비교할 수 없습니다."],
        }

    entity_keys = list(recipe.entity_keys or ["site_id"])
    time_key = recipe.time_key or "measured_at"
    entity_col = entity_keys[0] if entity_keys else "site_id"

    preview_map: dict[tuple[str, str], Any] = {}
    for prow in preview_rows:
        ent = str(prow.get(entity_col, ""))
        tval = prow.get(time_key) or prow.get("measured_at")
        if tval is None:
            continue
        preview_map[(ent, str(tval)[:19])] = prow.get(feature_name)

    items: list[dict[str, Any]] = []
    matched = 0
    mismatch = 0
    max_diff = 0.0

    for sample in build_samples:
        ent = str(sample["entity_key"])
        tkey = str(sample["time_key"] or "")[:19]
        preview_val = preview_map.get((ent, tkey))
        build_val = sample["build_value"]
        match = False
        diff = None
        if preview_val is not None and build_val is not None:
            try:
                diff = float(build_val) - float(preview_val)
                match = abs(diff) < 1e-6
                max_diff = max(max_diff, abs(diff))
            except (TypeError, ValueError):
                match = preview_val == build_val
        elif preview_val is None and build_val is None:
            match = True
        if match:
            matched += 1
        else:
            mismatch += 1
        items.append({
            "entity_key": ent,
            "time_key": sample["time_key"],
            "preview_value": preview_val,
            "build_value": build_val,
            "match": match,
            "diff": diff,
        })

    comparable = len(preview_map) > 0
    warnings: list[str] = []
    if not comparable:
        warnings.append("Preview 키 매칭에 실패했습니다. entity/time 정렬이 다를 수 있습니다.")

    return {
        "recipe_id": recipe_id,
        "feature_name": feature_name,
        "dataset_version_id": resolved_dsv,
        "feature_set_id": feature_set_id,
        "comparable": comparable,
        "comparison_policy": "SAMPLE_BY_ENTITY_TIME",
        "items": items[:sample_size],
        "summary": {
            "sample_count": len(items),
            "matched_count": matched,
            "mismatch_count": mismatch,
            "max_abs_diff": max_diff if comparable else None,
        },
        "warnings": warnings,
    }
