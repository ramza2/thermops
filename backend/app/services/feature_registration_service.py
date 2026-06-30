"""Feature 등록·Registry·계산 가능 여부 검증."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Feature

# 레거시 별칭 → 공식 feature_name (ml/features.py·FS-TPL-* 정책과 동일)
LEGACY_ALIASES: dict[str, str] = {
    "hdd": "heating_degree_days",
    "cdd": "cooling_degree_days",
    "lag_24h_demand": "demand_lag_24h",
    "lag_168h_demand": "demand_lag_168h",
    "rolling_24h_avg": "demand_ma_24h",
    "rolling_mean_24h": "demand_ma_24h",
    "lag_24h": "demand_lag_24h",
    "lag_168h": "demand_lag_168h",
    "demand_rolling_24h_avg": "demand_ma_24h",
}

OFFICIAL_FEATURE_NAMES = frozenset({
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_ma_24h",
    "demand_ma_168h",
    "temperature_diff_24h",
    "heating_degree_days",
    "cooling_degree_days",
})

TPL_FEATURE_SET_PREFIX = "FS-TPL-"


def _ensure_ml_path() -> None:
    root = get_settings().project_root
    for candidate in (root / "ml", Path("/ml"), Path(__file__).resolve().parents[3] / "ml"):
        if candidate.exists():
            p = str(candidate.resolve())
            if p not in sys.path:
                sys.path.insert(0, p)
            break


def _registry_names() -> frozenset[str]:
    _ensure_ml_path()
    import feature_registry as reg  # noqa: WPS433

    return frozenset(reg.FEATURE_REGISTRY)


def _computable_names() -> frozenset[str]:
    _ensure_ml_path()
    import features as feat  # noqa: WPS433

    return frozenset(feat.ALL_COMPUTED_FEATURES)


def is_legacy_alias(feature_name: str) -> bool:
    return feature_name in LEGACY_ALIASES


def get_recommended_name(feature_name: str) -> str | None:
    return LEGACY_ALIASES.get(feature_name)


def is_registry_registered(feature_name: str) -> bool:
    return feature_name in _registry_names()


def is_computable(feature_name: str) -> bool:
    return feature_name in _computable_names()


def _build_message(
    feature_name: str,
    status: str,
    *,
    recommended_name: str | None,
    catalog_registered: bool,
    computable: bool,
) -> str:
    if status == "LEGACY_ALIAS" and recommended_name:
        return (
            f"{feature_name}는 레거시 별칭입니다. "
            f"신규 Feature에는 {recommended_name}를 사용하세요."
        )
    if status == "COMPUTABLE":
        return (
            "Registry에 등록된 코드 기반 Feature입니다. "
            "Feature Set에 포함 후 Feature 생성 시 사용할 수 있습니다."
        )
    if status == "DUPLICATE":
        return f"{feature_name}는 이미 카탈로그에 등록되어 있습니다."
    if status == "CATALOG_ONLY":
        if catalog_registered:
            return (
                "카탈로그에만 등록된 Feature입니다. "
                "현재 계산 로직이 없으므로 Feature 생성 결과에 값이 생성되지 않을 수 있습니다."
            )
        return (
            "현재 계산 로직이 없는 Feature입니다. "
            "카탈로그 등록은 가능하지만, 사용하려면 ml/features.py와 "
            "Feature Registry에 계산 로직을 추가해야 합니다."
        )
    if status == "REGISTERED_IN_REGISTRY":
        return "Feature Registry에 등록되어 있으나 카탈로그에는 없습니다."
    return f"{feature_name}는 Registry·카탈로그에 등록되지 않은 이름입니다."


def classify_feature_name(
    feature_name: str,
    *,
    catalog_registered: bool = False,
) -> dict[str, Any]:
    """이름만으로 Feature 등록 유형을 분류한다 (DB 조회 없음)."""
    name = feature_name.strip()
    registry_registered = is_registry_registered(name)
    computable = is_computable(name)

    if name in LEGACY_ALIASES:
        recommended = LEGACY_ALIASES[name]
        status = "LEGACY_ALIAS"
        return _result(
            name,
            status=status,
            recommended_name=recommended,
            catalog_registered=catalog_registered,
            registry_registered=registry_registered or is_registry_registered(recommended),
            computable=False,
        )

    if computable:
        status = "COMPUTABLE"
    elif catalog_registered:
        status = "DUPLICATE" if not registry_registered else "CATALOG_ONLY"
    elif registry_registered:
        status = "REGISTERED_IN_REGISTRY"
    else:
        status = "CATALOG_ONLY"

    return _result(
        name,
        status=status,
        recommended_name=name if computable else None,
        catalog_registered=catalog_registered,
        registry_registered=registry_registered,
        computable=computable,
    )


def _result(
    feature_name: str,
    *,
    status: str,
    recommended_name: str | None,
    catalog_registered: bool,
    registry_registered: bool,
    computable: bool,
) -> dict[str, Any]:
    message = _build_message(
        feature_name,
        status,
        recommended_name=recommended_name,
        catalog_registered=catalog_registered,
        computable=computable,
    )
    return {
        "feature_name": feature_name,
        "status": status,
        "recommended_name": recommended_name,
        "catalog_registered": catalog_registered,
        "registry_registered": registry_registered,
        "computable": computable,
        "message": message,
    }


async def validate_feature_name(db: AsyncSession, feature_name: str) -> dict[str, Any]:
    """카탈로그 등록 여부를 포함해 Feature명을 검증한다."""
    name = feature_name.strip()
    if not name:
        raise ValueError("feature_name이 비어 있습니다.")

    row = (
        await db.execute(select(Feature).where(Feature.feature_name == name))
    ).scalar_one_or_none()
    return classify_feature_name(name, catalog_registered=row is not None)


def analyze_feature_set_coverage(
    requested_features: list[str],
    computed_columns: list[str],
) -> dict[str, Any]:
    """Feature Set 요청 대비 실제 계산 컬럼 커버리지를 분석한다."""
    column_set = set(computed_columns)
    missing = [f for f in requested_features if f not in column_set]
    legacy_alias_features = [f for f in missing if f in LEGACY_ALIASES]
    catalog_only_features = [
        f for f in missing
        if f not in LEGACY_ALIASES and not is_computable(f)
    ]
    registry_missing = [
        f for f in missing
        if f not in LEGACY_ALIASES and is_computable(f)
    ]

    return {
        "requested_feature_count": len(requested_features),
        "generated_feature_count": len(requested_features) - len(missing),
        "missing_feature_count": len(missing),
        "missing_features": missing,
        "missing_computed_features": missing,
        "catalog_only_features": catalog_only_features,
        "legacy_alias_features": legacy_alias_features,
        "registry_missing_features": registry_missing,
    }


def is_tpl_feature_set(feature_set_id: str) -> bool:
    return feature_set_id.startswith(TPL_FEATURE_SET_PREFIX)
