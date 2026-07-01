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

    from app.services.feature_recipe_service import get_published_recipe_by_feature_name, recipe_registration_metadata

    recipe = await get_published_recipe_by_feature_name(db, name)
    if recipe:
        template_meta = recipe_registration_metadata(recipe)
        return {
            "feature_name": name,
            "status": "TEMPLATE_PUBLISHED",
            "recommended_name": name,
            "catalog_registered": True,
            "registry_registered": False,
            "computable": False,
            "message": "Recipe로 발행되었지만 실제 Feature Build 계산은 R6에서 제공됩니다.",
            **template_meta,
        }

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


async def load_catalog_feature_names(db: AsyncSession) -> frozenset[str]:
    rows = (await db.execute(select(Feature.feature_name))).all()
    return frozenset(r[0] for r in rows)


def registration_metadata_for_feature(
    feature_name: str,
    *,
    catalog_names: frozenset[str],
    recipe: Any | None = None,
) -> dict[str, Any]:
    """Feature Quality·Build 등에서 재사용하는 registration 메타데이터."""
    if recipe is not None:
        from app.services.feature_recipe_service import recipe_registration_metadata

        base = classify_feature_name(feature_name, catalog_registered=feature_name in catalog_names)
        template_meta = recipe_registration_metadata(recipe)
        return {
            **base,
            **template_meta,
            "status": "TEMPLATE_PUBLISHED",
            "registration_status": "TEMPLATE_PUBLISHED",
            "computable": False,
            "registry_registered": base.get("registry_registered", False),
            "registration_message": (
                "Recipe로 발행되었지만 실제 Feature Build 계산은 R6에서 제공됩니다."
            ),
        }

    reg = classify_feature_name(
        feature_name,
        catalog_registered=feature_name in catalog_names,
    )
    status = reg["status"]
    return {
        "feature_name": feature_name,
        "registration_status": status,
        "status": status,
        "catalog_registered": reg["catalog_registered"],
        "registry_registered": reg["registry_registered"],
        "computable": reg["computable"],
        "legacy_alias": status == "LEGACY_ALIAS",
        "recommended_name": reg.get("recommended_name"),
        "registration_message": reg["message"],
        "template_recipe_registered": False,
        "build_supported": reg["computable"],
    }


def quality_context_message(
    meta: dict[str, Any],
    *,
    has_missing_key: bool,
) -> str | None:
    """missing key 등 품질 이슈와 registration이 겹칠 때 추가 안내."""
    if not has_missing_key:
        return None
    status = meta.get("registration_status")
    name = meta.get("feature_name", "")
    if status == "LEGACY_ALIAS":
        rec = meta.get("recommended_name")
        return f"{name}는 레거시 별칭입니다. 공식명 {rec}를 사용하세요."
    if status == "CATALOG_ONLY":
        if meta.get("catalog_registered"):
            return (
                "카탈로그에는 등록되어 있으나 계산 로직이 없어 feature_json에 값이 없습니다."
            )
        return "Registry에 등록되지 않았고 계산 로직이 없어 feature_json에 값이 없습니다."
    if not meta.get("registry_registered") and not meta.get("computable"):
        return f"{name}는 Registry 미등록 Feature로 feature_json에 값이 없을 수 있습니다."
    return None


def summarize_registration_counts(feature_metas: list[dict[str, Any]]) -> dict[str, int]:
    catalog_only = 0
    legacy = 0
    non_computable = 0
    registry_missing = 0
    for m in feature_metas:
        status = m.get("registration_status")
        computable = m.get("computable")
        if status == "CATALOG_ONLY" or (status == "DUPLICATE" and not computable):
            catalog_only += 1
        if status == "LEGACY_ALIAS":
            legacy += 1
        if not computable:
            non_computable += 1
        if not m.get("registry_registered") and status != "LEGACY_ALIAS":
            registry_missing += 1
    return {
        "catalog_only_feature_count": catalog_only,
        "legacy_alias_feature_count": legacy,
        "non_computable_feature_count": non_computable,
        "registry_missing_feature_count": registry_missing,
    }


def compute_legacy_replacement_plan(features: list[str]) -> dict[str, Any]:
    """Legacy alias를 공식명으로 대체하는 계획을 계산한다 (DB 변경 없음)."""
    original_features = list(features)
    replaced_features: list[str] = []
    replacements: list[dict[str, str]] = []
    removed_duplicates: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for name in original_features:
        if name in LEGACY_ALIASES:
            to_name = LEGACY_ALIASES[name]
            if not is_computable(to_name):
                raise ValueError(
                    f"Legacy alias '{name}'의 공식명 '{to_name}'은 계산 가능하지 않습니다."
                )
            replacements.append({"from": name, "to": to_name, "reason": "LEGACY_ALIAS"})
            target = to_name
        else:
            target = name

        if target in seen:
            if name in LEGACY_ALIASES:
                removed_duplicates.append(name)
                warnings.append(
                    f"{name}를 {target}로 대체하면서 기존 {target}와 중복되어 1개를 제거했습니다."
                )
            continue
        seen.add(target)
        replaced_features.append(target)

    remaining_legacy = [f for f in replaced_features if f in LEGACY_ALIASES]
    remaining_non_computable = [f for f in replaced_features if not is_computable(f)]
    replacement_count = len(replacements)
    changed = replacement_count > 0 or original_features != replaced_features

    if replacement_count == 0:
        message = "대체할 Legacy Feature가 없습니다."
    else:
        message = f"{replacement_count}개 Legacy Feature를 공식명으로 대체할 수 있습니다."

    return {
        "changed": changed,
        "original_features": original_features,
        "replaced_features": replaced_features,
        "replacements": replacements,
        "removed_duplicates": removed_duplicates,
        "remaining_legacy_features": remaining_legacy,
        "remaining_non_computable_features": remaining_non_computable,
        "warnings": warnings,
        "replacement_count": replacement_count,
        "duplicate_removed_count": len(removed_duplicates),
        "remaining_legacy_count": len(remaining_legacy),
        "message": message,
    }


async def replace_legacy_features_in_feature_set(
    db: AsyncSession,
    feature_set_id: str,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Feature Set features 목록에서 Legacy alias를 공식명으로 대체한다."""
    from app.models.entities import FeatureSet

    fs = (
        await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))
    ).scalar_one_or_none()
    if not fs:
        raise LookupError(f"Feature Set을 찾을 수 없습니다: {feature_set_id}")

    plan = compute_legacy_replacement_plan(list(fs.features or []))
    plan["feature_set_id"] = feature_set_id
    plan["dry_run"] = dry_run

    if plan["remaining_legacy_features"]:
        raise ValueError(
            "대체 후에도 Legacy Feature가 남아 있습니다: "
            + ", ".join(plan["remaining_legacy_features"])
        )
    if is_tpl_feature_set(feature_set_id) and plan["remaining_non_computable_features"]:
        raise ValueError(
            "공식 TPL Feature Set에는 계산 가능한 Feature만 남을 수 있습니다: "
            + ", ".join(plan["remaining_non_computable_features"][:5])
        )

    if not dry_run and plan["changed"]:
        fs.features = plan["replaced_features"]
        plan["applied"] = True
        plan["message"] = (
            f"Legacy Feature {plan['replacement_count']}개를 공식명으로 대체했습니다."
        )
    else:
        plan["applied"] = False

    return plan
