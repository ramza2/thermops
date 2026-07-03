from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    DatasetVersionArchiveRequest,
    DatasetVersionCleanupPreviewRequest,
    DatasetVersionSelectionPreviewRequest,
)
from app.services.dataset_version_policy_service import (
    DatasetVersionPolicyError,
    archive_dataset_version,
    preview_cleanup_dataset_versions,
    selection_preview,
    set_primary_dataset_version,
)
from app.services.dataset_version_service import (
    get_dataset_version_detail,
    list_dataset_versions,
)

router = APIRouter(tags=["Dataset Version"])


@router.get("/dataset-versions")
async def get_dataset_versions(
    feature_set_id: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    build_scope: str | None = Query(default=None),
    is_primary: bool | None = Query(default=None),
    training_ready: bool | None = Query(default=None),
    serving_ready: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    items = await list_dataset_versions(
        db,
        feature_set_id=feature_set_id,
        role=role,
        status=status,
        build_scope=build_scope,
        is_primary=is_primary,
        training_ready=training_ready,
        serving_ready=serving_ready,
    )
    return ok(items)


@router.get("/dataset-versions/{dataset_version_id}")
async def get_dataset_version(dataset_version_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_dataset_version_detail(db, dataset_version_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.post("/dataset-versions/{dataset_version_id}/set-primary")
async def post_set_primary_dataset_version(
    dataset_version_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await set_primary_dataset_version(db, dataset_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="대표 학습 데이터 버전으로 지정되었습니다.")


@router.post("/dataset-versions/{dataset_version_id}/archive")
async def post_archive_dataset_version(
    dataset_version_id: str,
    body: DatasetVersionArchiveRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await archive_dataset_version(db, dataset_version_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="학습 데이터 버전이 보관 처리되었습니다.")


@router.post("/dataset-versions/selection-preview")
async def post_dataset_version_selection_preview(
    body: DatasetVersionSelectionPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    purpose = body.purpose.upper()
    if purpose not in {"TRAINING", "PREDICTION"}:
        raise HTTPException(status_code=400, detail="purpose must be TRAINING or PREDICTION")
    try:
        result = await selection_preview(
            db,
            body.feature_set_id,
            purpose,  # type: ignore[arg-type]
            explicit_dataset_version_id=body.explicit_dataset_version_id,
        )
    except DatasetVersionPolicyError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return ok(result)


@router.post("/dataset-versions/cleanup-preview")
async def post_dataset_version_cleanup_preview(
    body: DatasetVersionCleanupPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await preview_cleanup_dataset_versions(
        db,
        feature_set_id=body.feature_set_id,
        roles=body.roles,
        older_than_days=body.older_than_days,
    )
    result["dry_run"] = body.dry_run
    return ok(result)
