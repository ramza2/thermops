from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.core.time import utc_now
from app.models.entities import Feature, FeatureSet
from app.schemas.api import FeatureCreate, FeatureQualityRunCreate, FeatureSetCreate, FeatureSetLegacyReplaceRequest
from app.services.feature_build_service import (
    FeatureBuildParams,
    get_feature_build_job,
    list_feature_build_jobs,
    preview_features,
    run_feature_build,
)
from app.services.feature_dataset_service import get_feature_dataset_range
from app.services.feature_lineage_service import (
    LineageTableMissingError,
    get_lineage_by_dataset_version,
    get_lineage_by_job_id,
)
from app.services.feature_registry_service import get_registry_spec, list_registry_specs
from app.services.feature_quality_service import (
    FeatureQualityParams,
    get_feature_quality_run,
    list_feature_quality_runs,
    run_feature_quality_check,
)
from app.services.feature_registration_service import (
    LEGACY_ALIASES,
    classify_feature_name,
    is_computable,
    is_tpl_feature_set,
    replace_legacy_features_in_feature_set,
    validate_feature_name,
)

router = APIRouter(tags=["Feature"])


def _parse_optional_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).replace(tzinfo=None)


@router.get("/features")
async def list_features(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Feature).order_by(Feature.feature_name))).scalars().all()
    items = [
        {
            "feature_id": r.feature_id,
            "feature_name": r.feature_name,
            "feature_group": r.feature_group,
            "feature_type": r.feature_type,
            "calc_expression": r.calc_expression,
            "status": r.status,
            "description": r.description,
        }
        for r in rows
    ]
    start = (page - 1) * size
    page_items = items[start:start + size]
    enriched = []
    for f in page_items:
        enriched.append({
            **f,
            "registration": classify_feature_name(f["feature_name"], catalog_registered=True),
        })
    return paged(enriched, page, size, len(items))


@router.get("/features/validate-name")
async def validate_feature_name_api(
    feature_name: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await validate_feature_name(db, feature_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result)


@router.post("/features")
async def create_feature(body: FeatureCreate, db: AsyncSession = Depends(get_db)):
    fid = f"FEAT-{uuid4().hex[:6].upper()}"
    f = Feature(
        feature_id=fid,
        feature_name=body.feature_name,
        feature_group=body.feature_group,
        feature_type=body.feature_type,
        calc_expression=body.calc_expression,
        status="ACTIVE",
        description=body.description,
        created_at=utc_now(),
    )
    db.add(f)
    return ok({"feature_id": fid}, message="Feature가 등록되었습니다.")


@router.put("/features/{feature_id}")
async def update_feature(feature_id: str, body: FeatureCreate, db: AsyncSession = Depends(get_db)):
    f = (await db.execute(select(Feature).where(Feature.feature_id == feature_id))).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    f.feature_name = body.feature_name
    f.feature_group = body.feature_group
    f.feature_type = body.feature_type
    f.calc_expression = body.calc_expression
    f.description = body.description
    return ok({"feature_id": feature_id}, message="Feature가 수정되었습니다.")


@router.delete("/features/{feature_id}")
async def delete_feature(feature_id: str, db: AsyncSession = Depends(get_db)):
    f = (await db.execute(select(Feature).where(Feature.feature_id == feature_id))).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(f)
    return ok(message="Feature가 삭제되었습니다.")


@router.get("/feature-sets")
async def list_feature_sets(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FeatureSet).order_by(FeatureSet.created_at.desc()))).scalars().all()
    return ok([
        {
            "feature_set_id": r.feature_set_id,
            "feature_set_name": r.feature_set_name,
            "target_domain": r.target_domain,
            "features": r.features or [],
            "apply_site_scope": r.apply_site_scope,
            "description": r.description,
        }
        for r in rows
    ])


@router.post("/feature-sets")
async def create_feature_set(body: FeatureSetCreate, db: AsyncSession = Depends(get_db)):
    fsid = f"FS-{uuid4().hex[:6].upper()}"
    fs = FeatureSet(
        feature_set_id=fsid,
        feature_set_name=body.feature_set_name,
        target_domain=body.target_domain,
        features=body.features,
        apply_site_scope=body.apply_site_scope,
        description=body.description,
        active_yn="Y",
        created_at=utc_now(),
    )
    db.add(fs)
    return ok({"feature_set_id": fsid}, message="Feature Set이 등록되었습니다.")


@router.get("/feature-sets/{feature_set_id}")
async def get_feature_set(feature_set_id: str, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok({
        "feature_set_id": fs.feature_set_id,
        "feature_set_name": fs.feature_set_name,
        "target_domain": fs.target_domain,
        "features": fs.features or [],
        "apply_site_scope": fs.apply_site_scope,
        "description": fs.description,
    })


@router.get("/feature-sets/{feature_set_id}/dataset-range")
async def get_feature_set_dataset_range(feature_set_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await get_feature_dataset_range(db, feature_set_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(result)


@router.delete("/feature-sets/{feature_set_id}")
async def delete_feature_set(feature_set_id: str, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(fs)
    return ok(message="Feature Set이 삭제되었습니다.")


@router.put("/feature-sets/{feature_set_id}")
async def update_feature_set(feature_set_id: str, body: FeatureSetCreate, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    existing = set(fs.features or [])
    requested = list(body.features or [])

    if is_tpl_feature_set(feature_set_id):
        blocked = [n for n in requested if not is_computable(n)]
        if blocked:
            raise HTTPException(
                status_code=400,
                detail=(
                    "공식 TPL Feature Set에는 계산 가능한 Registry Feature만 포함할 수 있습니다: "
                    + ", ".join(blocked[:5])
                ),
            )

    new_names = [n for n in requested if n not in existing]
    legacy_new = [n for n in new_names if n in LEGACY_ALIASES]
    if legacy_new:
        alias = legacy_new[0]
        official = LEGACY_ALIASES[alias]
        raise HTTPException(
            status_code=400,
            detail=f"레거시 별칭 '{alias}'는 신규 추가할 수 없습니다. 공식명 '{official}'을 사용하세요.",
        )

    fs.feature_set_name = body.feature_set_name
    fs.features = requested
    fs.apply_site_scope = body.apply_site_scope
    fs.description = body.description
    return ok({"feature_set_id": feature_set_id}, message="Feature Set이 수정되었습니다.")


@router.post("/feature-sets/{feature_set_id}/replace-legacy-features")
async def replace_legacy_features_api(
    feature_set_id: str,
    body: FeatureSetLegacyReplaceRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    dry_run = True if body is None else body.dry_run
    try:
        result = await replace_legacy_features_in_feature_set(
            db, feature_set_id, dry_run=dry_run
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    msg = result.get("message", "Legacy Feature 대체 계획을 반환했습니다.")
    return ok(result, message=msg)


@router.post("/feature-sets/{feature_set_id}/preview")
async def preview_feature_set(
    feature_set_id: str,
    site_id: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await preview_features(
            db,
            feature_set_id,
            site_id=site_id,
            start_at=_parse_optional_dt(start_at),
            end_at=_parse_optional_dt(end_at),
            limit=10,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result)


@router.post("/feature-build-jobs")
async def create_feature_build_job(
    feature_set_id: str = Query(...),
    site_id: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    params = FeatureBuildParams(
        feature_set_id=feature_set_id,
        site_id=site_id,
        start_at=_parse_optional_dt(start_at),
        end_at=_parse_optional_dt(end_at),
    )
    try:
        result = await run_feature_build(db, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result.get("error_message", "Feature 생성 실패"))

    msg = f"Feature {result['inserted_count']}건이 생성되었습니다."
    if result.get("warnings"):
        msg += f" (경고 {len(result['warnings'])}건)"
    return ok(result, message=msg)


@router.get("/feature-build-jobs")
async def list_feature_build_jobs_endpoint(
    feature_set_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_summary: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    result = await list_feature_build_jobs(
        db,
        feature_set_id=feature_set_id,
        status=status,
        limit=limit,
        offset=offset,
        include_summary=include_summary,
    )
    return ok(result)


@router.get("/feature-build-jobs/{job_id}")
async def get_feature_build_job_endpoint(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await get_feature_build_job(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(result)


@router.get("/feature-registry")
async def list_feature_registry():
    return ok(list_registry_specs())


@router.get("/feature-registry/{feature_name}")
async def get_feature_registry_item(feature_name: str):
    spec = get_registry_spec(feature_name)
    if not spec:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(spec)


@router.get("/feature-lineage")
async def get_feature_lineage(
    dataset_version_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = await get_lineage_by_dataset_version(db, dataset_version_id)
    except LineageTableMissingError as exc:
        await db.rollback()
        return ok({
            "dataset_version_id": dataset_version_id,
            "lineage_count": 0,
            "items": [],
            "migration_warning": str(exc),
        })
    return ok({
        "dataset_version_id": dataset_version_id,
        "lineage_count": len(rows),
        "items": rows,
    })


@router.get("/feature-build-jobs/{job_id}/lineage")
async def get_feature_build_job_lineage(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        rows = await get_lineage_by_job_id(db, job_id)
    except LineageTableMissingError as exc:
        await db.rollback()
        job = await get_feature_build_job(db, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
        return ok({
            "job_id": job_id,
            "lineage_count": 0,
            "items": [],
            "migration_warning": str(exc),
        })
    if not rows:
        job = await get_feature_build_job(db, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        return ok({"job_id": job_id, "lineage_count": 0, "items": []})
    return ok({
        "job_id": job_id,
        "dataset_version_id": rows[0].get("dataset_version_id"),
        "lineage_count": len(rows),
        "items": rows,
    })


@router.post("/feature-quality-runs")
async def create_feature_quality_run(
    body: FeatureQualityRunCreate,
    db: AsyncSession = Depends(get_db),
):
    params = FeatureQualityParams(
        feature_set_id=body.feature_set_id,
        dataset_version_id=body.dataset_version_id,
    )
    try:
        result = await run_feature_quality_check(db, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    status = result.get("status", "FAILED")
    score = result.get("score")
    msg = f"Feature 품질 점검이 완료되었습니다. (상태: {status}"
    if score is not None:
        msg += f", 점수: {score}"
    msg += ")"
    return ok(result, message=msg)


@router.get("/feature-quality-runs")
async def list_feature_quality_runs_endpoint(
    feature_set_id: str | None = Query(default=None),
    dataset_version_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_summary: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    result = await list_feature_quality_runs(
        db,
        feature_set_id=feature_set_id,
        dataset_version_id=dataset_version_id,
        status=status,
        limit=limit,
        offset=offset,
        include_summary=include_summary,
    )
    return ok(result)


@router.get("/feature-quality-runs/{run_id}")
async def get_feature_quality_run_endpoint(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await get_feature_quality_run(db, run_id)
    if not result:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(result)
