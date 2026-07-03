"""Dataset Version(학습 데이터 버전) 운영 정책·자동 선택."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import DatasetVersion, FeatureDataset

Purpose = Literal["TRAINING", "PREDICTION"]

EXCLUDED_ROLES_AUTO = frozenset({"PARTIAL", "TEMPORARY", "ARCHIVED"})
EXCLUDED_STATUS_AUTO = frozenset({"BUILD_FAILED", "ARCHIVED", "PARTIAL"})
TRAINING_READY_STATUSES = frozenset({"TRAINING_READY", "BUILD_SUCCESS", "BUILD_WARNING", "SERVING_READY"})
SERVING_READY_STATUSES = frozenset({"SERVING_READY", "BUILD_SUCCESS", "BUILD_WARNING", "TRAINING_READY"})

COVERAGE_MIN = 0.8
NULL_RATIO_MAX = 0.5


@dataclass
class DatasetVersionSelectionResult:
    dataset_version_id: str | None
    selection_reason: str
    warnings: list[str] = field(default_factory=list)
    excluded_candidates: list[dict[str, str]] = field(default_factory=list)


class DatasetVersionPolicyError(ValueError):
    def __init__(self, error_code: str, message: str, **fields: Any):
        self.error_code = error_code
        self.message = message
        self.fields = fields
        super().__init__(message)


def _feature_set_filter(feature_set_id: str):
    return FeatureDataset.feature_json["feature_set_id"].astext == feature_set_id


def dataset_version_to_dict(dv: DatasetVersion) -> dict[str, Any]:
    return {
        "dataset_version_id": dv.dataset_version_id,
        "feature_set_id": dv.feature_set_id,
        "dataset_type": dv.dataset_type,
        "dataset_version_role": dv.dataset_version_role,
        "dataset_version_status": dv.dataset_version_status,
        "build_scope": dv.build_scope,
        "is_primary": bool(dv.is_primary),
        "is_training_ready": bool(dv.is_training_ready),
        "is_serving_ready": bool(dv.is_serving_ready),
        "record_count": dv.record_count,
        "feature_count": dv.feature_count,
        "coverage_ratio": float(dv.coverage_ratio) if dv.coverage_ratio is not None else None,
        "null_ratio": float(dv.null_ratio) if dv.null_ratio is not None else None,
        "quality_score": float(dv.quality_score) if dv.quality_score is not None else None,
        "base_start_at": dv.base_start_at.isoformat() if dv.base_start_at else None,
        "base_end_at": dv.base_end_at.isoformat() if dv.base_end_at else None,
        "build_started_at": dv.build_started_at.isoformat() if dv.build_started_at else None,
        "build_finished_at": dv.build_finished_at.isoformat() if dv.build_finished_at else None,
        "archived_at": dv.archived_at.isoformat() if dv.archived_at else None,
        "archived_reason": dv.archived_reason,
        "selection_policy_note": dv.selection_policy_note,
        "created_by": dv.created_by,
        "created_at": dv.created_at.isoformat() if dv.created_at else None,
        "metadata_json": dv.metadata_json,
    }


def classify_build_scope(
    *,
    site_id: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
    preview: bool = False,
) -> str:
    if preview:
        return "PREVIEW"
    if site_id or start_at or end_at:
        return "PARTIAL"
    return "FULL"


def calculate_dataset_version_quality(
    *,
    feature_count: int,
    record_count: int,
    coverage_ratio: float | None,
    null_ratio: float | None,
) -> float:
    if record_count <= 0 or feature_count <= 0:
        return 0.0
    cov = coverage_ratio if coverage_ratio is not None else 1.0
    null_penalty = null_ratio if null_ratio is not None else 0.0
    row_score = min(record_count / 1000.0, 1.0)
    return round(max(0.0, min(1.0, cov * 0.5 + (1.0 - null_penalty) * 0.3 + row_score * 0.2)), 4)


def classify_dataset_version_metadata(
    *,
    build_scope: str,
    record_count: int,
    coverage_ratio: float | None,
    null_ratio: float | None,
    run_status: str,
    feature_count: int,
) -> dict[str, Any]:
    quality_score = calculate_dataset_version_quality(
        feature_count=feature_count,
        record_count=record_count,
        coverage_ratio=coverage_ratio,
        null_ratio=null_ratio,
    )
    if run_status == "FAILED" or record_count <= 0:
        return {
            "dataset_version_role": "TEMPORARY",
            "dataset_version_status": "BUILD_FAILED",
            "is_training_ready": False,
            "is_serving_ready": False,
            "quality_score": quality_score,
        }
    if build_scope in {"PARTIAL", "PREVIEW"}:
        return {
            "dataset_version_role": "PARTIAL",
            "dataset_version_status": "PARTIAL",
            "is_training_ready": False,
            "is_serving_ready": False,
            "quality_score": quality_score,
        }
    cov_ok = coverage_ratio is None or coverage_ratio >= COVERAGE_MIN
    null_ok = null_ratio is None or null_ratio <= NULL_RATIO_MAX
    training_ready = cov_ok and null_ok and record_count > 0
    status = "BUILD_SUCCESS"
    if run_status == "WARNING" or not cov_ok or not null_ok:
        status = "BUILD_WARNING"
        if not training_ready:
            status = "BUILD_WARNING"
    role = "CANDIDATE"
    serving_ready = training_ready
    if training_ready:
        status = "TRAINING_READY" if status == "BUILD_SUCCESS" else status
        if serving_ready:
            status = "SERVING_READY" if status in {"BUILD_SUCCESS", "TRAINING_READY"} else status
    return {
        "dataset_version_role": role,
        "dataset_version_status": status,
        "is_training_ready": training_ready,
        "is_serving_ready": serving_ready,
        "quality_score": quality_score,
    }


def _auto_exclude_reason(dv: DatasetVersion) -> str | None:
    if (dv.record_count or 0) <= 0:
        return "ZERO_RECORD_EXCLUDED"
    role = (dv.dataset_version_role or "CANDIDATE").upper()
    status = (dv.dataset_version_status or "BUILD_SUCCESS").upper()
    if dv.archived_at is not None or role == "ARCHIVED" or status == "ARCHIVED":
        return "ARCHIVED_EXCLUDED"
    if role in EXCLUDED_ROLES_AUTO:
        return f"{role}_EXCLUDED"
    if status in EXCLUDED_STATUS_AUTO:
        return f"{status}_EXCLUDED"
    if dv.coverage_ratio is not None and float(dv.coverage_ratio) < COVERAGE_MIN:
        return "LOW_COVERAGE_EXCLUDED"
    return None


def _is_training_eligible(dv: DatasetVersion) -> bool:
    if _auto_exclude_reason(dv):
        return False
    if dv.is_training_ready:
        return True
    status = (dv.dataset_version_status or "").upper()
    return status in TRAINING_READY_STATUSES


def _is_serving_eligible(dv: DatasetVersion) -> bool:
    if _auto_exclude_reason(dv):
        return False
    if dv.is_serving_ready:
        return True
    status = (dv.dataset_version_status or "").upper()
    return status in SERVING_READY_STATUSES


async def get_dataset_version(db: AsyncSession, dataset_version_id: str) -> DatasetVersion | None:
    return (
        await db.execute(
            select(DatasetVersion).where(DatasetVersion.dataset_version_id == dataset_version_id)
        )
    ).scalar_one_or_none()


async def load_dataset_versions_for_feature_set(
    db: AsyncSession,
    feature_set_id: str,
) -> list[DatasetVersion]:
    rows = (
        await db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.feature_set_id == feature_set_id)
            .order_by(DatasetVersion.created_at.desc())
        )
    ).scalars().all()
    if rows:
        return list(rows)
    dsv_ids = (
        await db.execute(
            select(FeatureDataset.dataset_version_id)
            .where(_feature_set_filter(feature_set_id))
            .group_by(FeatureDataset.dataset_version_id)
        )
    ).scalars().all()
    if not dsv_ids:
        return []
    legacy = (
        await db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_version_id.in_(dsv_ids))
            .order_by(DatasetVersion.created_at.desc())
        )
    ).scalars().all()
    return list(legacy)


def _sort_key_quality(dv: DatasetVersion) -> tuple:
    return (
        float(dv.quality_score or 0),
        int(dv.record_count or 0),
        dv.created_at,
    )


async def _resolve_explicit(
    db: AsyncSession,
    feature_set_id: str,
    dataset_version_id: str,
    purpose: Purpose,
) -> DatasetVersionSelectionResult:
    dv = await get_dataset_version(db, dataset_version_id)
    if not dv:
        raise DatasetVersionPolicyError(
            "DATASET_VERSION_NOT_FOUND",
            f"학습 데이터 버전을 찾을 수 없습니다: {dataset_version_id}",
        )
    fs_id = dv.feature_set_id
    if not fs_id:
        rows = (
            await db.execute(
                select(FeatureDataset.feature_json["feature_set_id"].astext)
                .where(FeatureDataset.dataset_version_id == dataset_version_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        fs_id = rows
    if fs_id and fs_id != feature_set_id:
        raise DatasetVersionPolicyError(
            "DATASET_VERSION_FEATURE_SET_MISMATCH",
            f"학습 데이터 버전이 변수 구성({feature_set_id})과 일치하지 않습니다.",
            dataset_version_id=dataset_version_id,
            feature_set_id=feature_set_id,
        )
    role = (dv.dataset_version_role or "").upper()
    status = (dv.dataset_version_status or "").upper()
    if dv.archived_at or role == "ARCHIVED" or status == "ARCHIVED":
        raise DatasetVersionPolicyError(
            "EXPLICIT_ARCHIVED_BLOCKED",
            "보관된 학습 데이터 버전은 사용할 수 없습니다.",
            dataset_version_id=dataset_version_id,
        )
    if status == "BUILD_FAILED":
        raise DatasetVersionPolicyError(
            "EXPLICIT_FAILED_BLOCKED",
            "생성에 실패한 학습 데이터 버전은 사용할 수 없습니다.",
            dataset_version_id=dataset_version_id,
        )
    warnings: list[str] = []
    if role == "PARTIAL" or (dv.build_scope or "").upper() in {"PARTIAL", "PREVIEW"}:
        warnings.append("일부 생성 학습 데이터 버전입니다. 자동 선택에서는 제외되지만 명시 선택으로 사용합니다.")
    if purpose == "TRAINING" and not _is_training_eligible(dv) and not warnings:
        warnings.append("학습 가능 상태가 아닐 수 있습니다.")
    if purpose == "PREDICTION" and not _is_serving_eligible(dv) and not warnings:
        warnings.append("예측 사용 가능 상태가 아닐 수 있습니다.")
    return DatasetVersionSelectionResult(
        dataset_version_id=dataset_version_id,
        selection_reason="EXPLICIT_SELECTED",
        warnings=warnings,
    )


async def _auto_select(
    db: AsyncSession,
    feature_set_id: str,
    purpose: Purpose,
) -> DatasetVersionSelectionResult:
    versions = await load_dataset_versions_for_feature_set(db, feature_set_id)
    excluded: list[dict[str, str]] = []
    eligible: list[DatasetVersion] = []
    for dv in versions:
        reason = _auto_exclude_reason(dv)
        if reason:
            excluded.append({"dataset_version_id": dv.dataset_version_id, "reason": reason})
            continue
        if purpose == "TRAINING" and not _is_training_eligible(dv):
            excluded.append({"dataset_version_id": dv.dataset_version_id, "reason": "NOT_TRAINING_READY"})
            continue
        if purpose == "PREDICTION" and not _is_serving_eligible(dv):
            excluded.append({"dataset_version_id": dv.dataset_version_id, "reason": "NOT_SERVING_READY"})
            continue
        eligible.append(dv)

    primaries = [dv for dv in eligible if dv.is_primary or (dv.dataset_version_role or "").upper() == "PRIMARY"]
    if primaries:
        chosen = sorted(primaries, key=_sort_key_quality, reverse=True)[0]
        reason = "PRIMARY_SERVING_READY" if purpose == "PREDICTION" else "PRIMARY_TRAINING_READY"
        return DatasetVersionSelectionResult(
            dataset_version_id=chosen.dataset_version_id,
            selection_reason=reason,
            excluded_candidates=excluded,
        )

    candidates = [dv for dv in eligible if (dv.dataset_version_role or "CANDIDATE").upper() == "CANDIDATE"]
    if candidates:
        chosen = sorted(candidates, key=_sort_key_quality, reverse=True)[0]
        return DatasetVersionSelectionResult(
            dataset_version_id=chosen.dataset_version_id,
            selection_reason="CANDIDATE_QUALITY_BEST",
            excluded_candidates=excluded,
        )

    if eligible:
        chosen = sorted(eligible, key=lambda dv: (int(dv.record_count or 0), dv.created_at), reverse=True)[0]
        return DatasetVersionSelectionResult(
            dataset_version_id=chosen.dataset_version_id,
            selection_reason="FALLBACK_RECORD_COUNT",
            warnings=["명시적 운영 정책 후보가 없어 record_count 기준으로 선택했습니다."],
            excluded_candidates=excluded,
        )

    return DatasetVersionSelectionResult(
        dataset_version_id=None,
        selection_reason="NO_ELIGIBLE_DATASET_VERSION",
        excluded_candidates=excluded,
    )


async def select_dataset_version_for_training(
    db: AsyncSession,
    feature_set_id: str,
    *,
    explicit_dataset_version_id: str | None = None,
) -> DatasetVersionSelectionResult:
    if explicit_dataset_version_id:
        return await _resolve_explicit(db, feature_set_id, explicit_dataset_version_id, "TRAINING")
    return await _auto_select(db, feature_set_id, "TRAINING")


async def select_dataset_version_for_prediction(
    db: AsyncSession,
    feature_set_id: str,
    *,
    explicit_dataset_version_id: str | None = None,
) -> DatasetVersionSelectionResult:
    if explicit_dataset_version_id:
        return await _resolve_explicit(db, feature_set_id, explicit_dataset_version_id, "PREDICTION")
    return await _auto_select(db, feature_set_id, "PREDICTION")


async def set_primary_dataset_version(db: AsyncSession, dataset_version_id: str) -> dict[str, Any]:
    dv = await get_dataset_version(db, dataset_version_id)
    if not dv:
        raise ValueError(f"학습 데이터 버전을 찾을 수 없습니다: {dataset_version_id}")
    if not dv.feature_set_id:
        raise ValueError("feature_set_id가 없는 학습 데이터 버전은 대표로 지정할 수 없습니다.")
    if dv.archived_at or (dv.dataset_version_role or "").upper() == "ARCHIVED":
        raise ValueError("보관된 학습 데이터 버전은 대표로 지정할 수 없습니다.")
    if (dv.dataset_version_status or "").upper() == "BUILD_FAILED":
        raise ValueError("생성 실패한 학습 데이터 버전은 대표로 지정할 수 없습니다.")

    await db.execute(
        update(DatasetVersion)
        .where(
            DatasetVersion.feature_set_id == dv.feature_set_id,
            DatasetVersion.is_primary.is_(True),
            DatasetVersion.dataset_version_id != dataset_version_id,
        )
        .values(is_primary=False, dataset_version_role="CANDIDATE")
    )
    dv.is_primary = True
    dv.dataset_version_role = "PRIMARY"
    if dv.is_training_ready:
        dv.dataset_version_status = "TRAINING_READY"
    if dv.is_serving_ready and dv.dataset_version_status in {"TRAINING_READY", "BUILD_SUCCESS"}:
        dv.dataset_version_status = "SERVING_READY"
    dv.selection_policy_note = "사용자가 대표 학습 데이터 버전으로 지정함"
    await db.flush()
    return dataset_version_to_dict(dv)


async def archive_dataset_version(
    db: AsyncSession,
    dataset_version_id: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    dv = await get_dataset_version(db, dataset_version_id)
    if not dv:
        raise ValueError(f"학습 데이터 버전을 찾을 수 없습니다: {dataset_version_id}")
    now = utc_now()
    dv.archived_at = now
    dv.archived_reason = reason or "사용자 보관 처리"
    dv.dataset_version_role = "ARCHIVED"
    dv.dataset_version_status = "ARCHIVED"
    dv.is_primary = False
    dv.is_training_ready = False
    dv.is_serving_ready = False
    dv.selection_policy_note = "보관 처리됨 — 자동 선택 제외"
    await db.flush()
    return dataset_version_to_dict(dv)


async def preview_cleanup_dataset_versions(
    db: AsyncSession,
    *,
    feature_set_id: str | None = None,
    roles: list[str] | None = None,
    older_than_days: int | None = None,
) -> dict[str, Any]:
    q = select(DatasetVersion)
    if feature_set_id:
        q = q.where(DatasetVersion.feature_set_id == feature_set_id)
    target_roles = roles or ["TEMPORARY", "PARTIAL"]
    q = q.where(DatasetVersion.dataset_version_role.in_(target_roles))
    if older_than_days is not None:
        cutoff = utc_now().replace(microsecond=0) - timedelta(days=older_than_days)
        q = q.where(DatasetVersion.created_at < cutoff)
    rows = (await db.execute(q.order_by(DatasetVersion.created_at.desc()))).scalars().all()
    items = [dataset_version_to_dict(r) for r in rows]
    return {"dry_run": True, "count": len(items), "items": items}


async def selection_preview(
    db: AsyncSession,
    feature_set_id: str,
    purpose: Purpose,
    *,
    explicit_dataset_version_id: str | None = None,
) -> dict[str, Any]:
    if purpose == "TRAINING":
        result = await select_dataset_version_for_training(
            db, feature_set_id, explicit_dataset_version_id=explicit_dataset_version_id
        )
    else:
        result = await select_dataset_version_for_prediction(
            db, feature_set_id, explicit_dataset_version_id=explicit_dataset_version_id
        )
    selected = None
    if result.dataset_version_id:
        dv = await get_dataset_version(db, result.dataset_version_id)
        if dv:
            selected = dataset_version_to_dict(dv)
    return {
        "feature_set_id": feature_set_id,
        "purpose": purpose,
        "selected": selected,
        "selection_reason": result.selection_reason,
        "warnings": result.warnings,
        "excluded_candidates": result.excluded_candidates,
    }
