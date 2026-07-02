from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    FeatureColumnRoleBulkUpdateRequest,
    FeatureColumnRoleInferRequest,
    FeatureColumnRoleValidateRequest,
)
from app.services.feature_column_role_service import (
    infer_column_roles,
    list_column_roles,
    list_role_codes,
    upsert_column_roles,
    validate_column_roles,
)

router = APIRouter(tags=["Feature Column Role"])


@router.get("/feature-column-role-codes")
async def get_feature_column_role_codes():
    return ok({"items": list_role_codes()})


@router.get("/feature-column-roles")
async def get_feature_column_roles(
    mapping_id: str | None = Query(default=None),
    data_source_id: str | None = Query(default=None),
    target_table: str | None = Query(default=None),
    source_table: str | None = Query(default=None),
    include_inferred: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await list_column_roles(
            db,
            mapping_id=mapping_id,
            data_source_id=data_source_id,
            target_table=target_table,
            source_table=source_table,
            include_inferred=include_inferred,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(result)


@router.post("/feature-column-roles/infer")
async def infer_feature_column_roles(
    body: FeatureColumnRoleInferRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.standard_dataset_service import get_default_column_roles_for_target_table

    columns = [c.model_dump() for c in body.columns]
    standard_roles: dict[str, str] = {}
    if body.target_table:
        standard_roles = await get_default_column_roles_for_target_table(db, body.target_table)
    items = infer_column_roles(
        columns,
        target_table=body.target_table,
        source_table=body.source_table,
        standard_roles=standard_roles or None,
    )
    role_values = [
        {
            "source_column": i["source_column"],
            "target_column": i.get("target_column"),
            "column_role": i["column_role"],
        }
        for i in items
    ]
    validation = validate_column_roles(role_values, mapping_columns=columns)
    from app.services.feature_column_role_service import summarize_role_coverage

    summary = summarize_role_coverage(role_values)
    return ok({
        "items": items,
        "mapping_id": body.mapping_id,
        "target_table": body.target_table,
        "summary": summary,
        "validation": validation,
    })


@router.post("/feature-column-roles/validate")
async def validate_feature_column_roles(body: FeatureColumnRoleValidateRequest):
    roles = [r.model_dump() for r in body.roles]
    mapping_columns = [c.model_dump() for c in body.mapping_columns] if body.mapping_columns else None
    validation = validate_column_roles(roles, mapping_columns=mapping_columns)
    from app.services.feature_column_role_service import summarize_role_coverage

    summary = summarize_role_coverage(roles)
    return ok({
        "mapping_id": body.mapping_id,
        "validation": validation,
        "summary": summary,
    })


@router.put("/feature-column-roles")
async def bulk_update_feature_column_roles(
    body: FeatureColumnRoleBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    roles = [r.model_dump() for r in body.roles]
    try:
        result = await upsert_column_roles(db, body.mapping_id, roles)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    msg = f"컬럼 역할 {result['saved_count']}건이 저장되었습니다."
    if result["validation"].get("warnings"):
        msg += f" (경고 {len(result['validation']['warnings'])}건)"
    return ok(result, message=msg)
