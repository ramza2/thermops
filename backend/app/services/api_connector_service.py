"""Generic REST API Connector Builder — 운영 서비스."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    ApiConnectorCallLog,
    ApiConnectorCredential,
    ApiConnectorLoadRun,
    ApiConnectorOperation,
    ApiConnectorPagination,
    ApiConnectorParam,
    ApiConnectorResponseSnapshot,
    DataMapping,
    DataSource,
)
from app.services.api_connector_http_client import build_full_url, encode_query_value, execute_http_request
from app.services.api_connector_loader import insert_rows, preview_load_rows
from app.services.api_connector_parser import normalize_items, parse_response_body
from app.services.standard_dataset_service import TargetTableNotAllowedError, validate_target_table_allowed
from app.utils.masking import mask_params_dict, mask_secret_value, mask_url
from app.utils.secret_crypto import decrypt_secret, store_secret

MAX_TEST_ITEMS = 10
MAX_LOAD_ITEMS = 1000
MAX_LOAD_PAGES = 5


class ApiConnectorError(ValueError):
    def __init__(self, message: str, *, error_code: str = "API_CONNECTOR_ERROR", **fields: Any):
        self.error_code = error_code
        self.fields = fields
        super().__init__(message)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _op_dict(op: ApiConnectorOperation) -> dict[str, Any]:
    return {
        "operation_id": op.operation_id,
        "data_source_id": op.data_source_id,
        "operation_name": op.operation_name,
        "operation_description": op.operation_description,
        "http_method": op.http_method,
        "endpoint_path": op.endpoint_path,
        "full_url_preview": op.full_url_preview,
        "request_content_type": op.request_content_type,
        "response_format": op.response_format,
        "response_item_path": op.response_item_path,
        "result_array_mode": op.result_array_mode,
        "target_table": op.target_table,
        "standard_dataset_id": op.standard_dataset_id,
        "active_yn": bool(op.active_yn),
        "archived_at": op.archived_at.isoformat() if op.archived_at else None,
        "metadata_json": op.metadata_json,
        "created_at": op.created_at.isoformat() if op.created_at else None,
        "updated_at": op.updated_at.isoformat() if op.updated_at else None,
    }


def _param_dict(p: ApiConnectorParam) -> dict[str, Any]:
    return {
        "param_id": p.param_id,
        "operation_id": p.operation_id,
        "param_name": p.param_name,
        "display_name": p.display_name,
        "param_location": p.param_location,
        "param_type": p.param_type,
        "required_yn": bool(p.required_yn),
        "default_value": p.default_value,
        "example_value": p.example_value,
        "allowed_values_json": p.allowed_values_json,
        "value_source": p.value_source,
        "secret_key_ref": p.secret_key_ref,
        "encode_yn": bool(p.encode_yn),
        "sort_order": p.sort_order,
        "active_yn": bool(p.active_yn),
        "metadata_json": p.metadata_json,
    }


def _credential_dict(c: ApiConnectorCredential, *, include_policy: bool = True) -> dict[str, Any]:
    data = {
        "credential_id": c.credential_id,
        "data_source_id": c.data_source_id,
        "credential_name": c.credential_name,
        "credential_type": c.credential_type,
        "key_location": c.key_location,
        "key_name": c.key_name,
        "secret_value_masked": c.secret_value_masked,
        "has_secret": bool(c.secret_value_encrypted),
        "active_yn": bool(c.active_yn),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
    if include_policy:
        data["encoding_policy"] = c.encoding_policy
    return data


def _pagination_dict(pg: ApiConnectorPagination) -> dict[str, Any]:
    return {
        "pagination_id": pg.pagination_id,
        "operation_id": pg.operation_id,
        "pagination_type": pg.pagination_type,
        "page_param_name": pg.page_param_name,
        "size_param_name": pg.size_param_name,
        "page_start": pg.page_start,
        "page_size": pg.page_size,
        "max_pages": pg.max_pages,
        "total_count_path": pg.total_count_path,
        "next_link_path": pg.next_link_path,
        "stop_condition": pg.stop_condition,
        "active_yn": bool(pg.active_yn),
    }


async def _get_source(db: AsyncSession, data_source_id: str) -> DataSource:
    row = (
        await db.execute(select(DataSource).where(DataSource.data_source_id == data_source_id))
    ).scalar_one_or_none()
    if not row:
        raise ApiConnectorError("데이터 소스를 찾을 수 없습니다.", error_code="DATA_SOURCE_NOT_FOUND")
    return row


async def _get_operation(db: AsyncSession, operation_id: str) -> ApiConnectorOperation:
    row = (
        await db.execute(select(ApiConnectorOperation).where(ApiConnectorOperation.operation_id == operation_id))
    ).scalar_one_or_none()
    if not row:
        raise ApiConnectorError("API 작업을 찾을 수 없습니다.", error_code="OPERATION_NOT_FOUND")
    return row


async def _get_params(db: AsyncSession, operation_id: str) -> list[ApiConnectorParam]:
    rows = (
        await db.execute(
            select(ApiConnectorParam)
            .where(ApiConnectorParam.operation_id == operation_id, ApiConnectorParam.active_yn.is_(True))
            .order_by(ApiConnectorParam.sort_order, ApiConnectorParam.param_name)
        )
    ).scalars().all()
    return list(rows)


async def _get_credential(db: AsyncSession, data_source_id: str) -> ApiConnectorCredential | None:
    return (
        await db.execute(
            select(ApiConnectorCredential).where(
                ApiConnectorCredential.data_source_id == data_source_id,
                ApiConnectorCredential.active_yn.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _get_pagination(db: AsyncSession, operation_id: str) -> ApiConnectorPagination | None:
    return (
        await db.execute(
            select(ApiConnectorPagination).where(
                ApiConnectorPagination.operation_id == operation_id,
                ApiConnectorPagination.active_yn.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _resolve_mapping(
    db: AsyncSession,
    data_source_id: str,
    target_table: str | None,
) -> DataMapping | None:
    if not target_table:
        return None
    return (
        await db.execute(
            select(DataMapping)
            .where(
                DataMapping.source_id == data_source_id,
                DataMapping.target_table == target_table,
                DataMapping.active_yn == "Y",
            )
            .order_by(DataMapping.updated_at.desc().nullslast(), DataMapping.created_at.desc())
        )
    ).scalars().first()


def _resolve_base_url(source: DataSource) -> str:
    info = source.connection_info or {}
    base = info.get("base_url") or info.get("baseUrl") or ""
    if not base:
        raise ApiConnectorError(
            "데이터 소스에 base_url이 설정되어 있지 않습니다.",
            error_code="INVALID_DATA_SOURCE",
        )
    return str(base).rstrip("/")


async def _build_request_params(
    db: AsyncSession,
    operation: ApiConnectorOperation,
    source: DataSource,
    runtime_params: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    params_def = await _get_params(db, operation.operation_id)
    credential = await _get_credential(db, source.data_source_id)
    runtime = dict(runtime_params or {})

    query: dict[str, str] = {}
    headers: dict[str, str] = {}
    body: dict[str, str] = {}

    for p in params_def:
        name = p.param_name
        val: str | None = None
        src = (p.value_source or "USER_INPUT").upper()
        if src == "SECRET_REF" and credential:
            plain = decrypt_secret(credential.secret_value_encrypted or "")
            val = plain
        elif name in runtime:
            val = str(runtime[name]) if runtime[name] is not None else None
        elif p.default_value is not None:
            val = str(p.default_value)
        elif p.required_yn:
            raise ApiConnectorError(f"필수 요청 파라미터가 없습니다: {name}", error_code="MISSING_PARAM")

        if val is None:
            continue

        loc = (p.param_location or "QUERY").upper()
        encode = bool(p.encode_yn)
        if credential and name == credential.key_name and credential.encoding_policy == "STORE_DECODED_ENCODE_ON_CALL":
            encode = True
        elif credential and credential.encoding_policy == "STORE_AS_IS":
            encode = bool(p.encode_yn)

        encoded_val = encode_query_value(val, encode=encode)
        if loc == "QUERY":
            query[name] = encoded_val if not encode else val  # httpx encodes query
            if encode:
                query[name] = val
        elif loc == "HEADER":
            headers[name] = val
        elif loc == "BODY":
            body[name] = val

    if credential and credential.credential_type != "NONE":
        plain = decrypt_secret(credential.secret_value_encrypted or "")
        if plain:
            if credential.key_location == "QUERY":
                if credential.encoding_policy == "STORE_DECODED_ENCODE_ON_CALL":
                    query[credential.key_name] = plain
                else:
                    query[credential.key_name] = plain
            elif credential.key_location == "HEADER":
                headers[credential.key_name] = plain

    return query, headers, body


async def list_operations(
    db: AsyncSession,
    *,
    data_source_id: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    q = select(ApiConnectorOperation).order_by(ApiConnectorOperation.created_at.desc())
    if data_source_id:
        q = q.where(ApiConnectorOperation.data_source_id == data_source_id)
    if not include_archived:
        q = q.where(ApiConnectorOperation.archived_at.is_(None))
    rows = (await db.execute(q)).scalars().all()
    return [_op_dict(r) for r in rows]


async def get_operation_detail(db: AsyncSession, operation_id: str) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    params = await _get_params(db, operation_id)
    pagination = await _get_pagination(db, operation_id)
    credential = await _get_credential(db, op.data_source_id)
    return {
        **_op_dict(op),
        "params": [_param_dict(p) for p in params],
        "pagination": _pagination_dict(pagination) if pagination else None,
        "credential": _credential_dict(credential) if credential else None,
    }


async def create_operation(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    data_source_id = payload["data_source_id"]
    source = await _get_source(db, data_source_id)
    base_url = _resolve_base_url(source)
    endpoint = payload["endpoint_path"]
    full_url = build_full_url(base_url, endpoint)
    now = utc_now()
    op_id = _new_id("ACO")
    op = ApiConnectorOperation(
        operation_id=op_id,
        data_source_id=data_source_id,
        operation_name=payload["operation_name"],
        operation_description=payload.get("operation_description"),
        http_method=(payload.get("http_method") or "GET").upper(),
        endpoint_path=endpoint,
        full_url_preview=mask_url(full_url),
        request_content_type=payload.get("request_content_type") or "QUERY",
        response_format=(payload.get("response_format") or "JSON").upper(),
        response_item_path=payload.get("response_item_path"),
        result_array_mode=payload.get("result_array_mode") or "AUTO",
        target_table=payload.get("target_table"),
        standard_dataset_id=payload.get("standard_dataset_id"),
        active_yn=True,
        metadata_json=payload.get("metadata_json"),
        created_at=now,
        updated_at=now,
    )
    if op.target_table:
        await validate_target_table_allowed(db, op.target_table)
    db.add(op)
    await db.flush()
    return _op_dict(op)


async def update_operation(db: AsyncSession, operation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    source = await _get_source(db, op.data_source_id)
    if "operation_name" in payload:
        op.operation_name = payload["operation_name"]
    if "operation_description" in payload:
        op.operation_description = payload["operation_description"]
    if "http_method" in payload:
        op.http_method = payload["http_method"].upper()
    if "endpoint_path" in payload:
        op.endpoint_path = payload["endpoint_path"]
    if "request_content_type" in payload:
        op.request_content_type = payload["request_content_type"]
    if "response_format" in payload:
        op.response_format = payload["response_format"].upper()
    if "response_item_path" in payload:
        op.response_item_path = payload["response_item_path"]
    if "result_array_mode" in payload:
        op.result_array_mode = payload["result_array_mode"]
    if "target_table" in payload:
        if payload["target_table"]:
            await validate_target_table_allowed(db, payload["target_table"])
        op.target_table = payload["target_table"]
    if "standard_dataset_id" in payload:
        op.standard_dataset_id = payload["standard_dataset_id"]
    if "active_yn" in payload:
        op.active_yn = bool(payload["active_yn"])
    base_url = _resolve_base_url(source)
    op.full_url_preview = mask_url(build_full_url(base_url, op.endpoint_path))
    op.updated_at = utc_now()
    await db.flush()
    return _op_dict(op)


async def archive_operation(db: AsyncSession, operation_id: str) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    op.archived_at = utc_now()
    op.active_yn = False
    op.updated_at = utc_now()
    await db.flush()
    return _op_dict(op)


async def replace_params(db: AsyncSession, operation_id: str, params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    await _get_operation(db, operation_id)
    existing = (
        await db.execute(select(ApiConnectorParam).where(ApiConnectorParam.operation_id == operation_id))
    ).scalars().all()
    for row in existing:
        await db.delete(row)
    out: list[ApiConnectorParam] = []
    for idx, item in enumerate(params):
        p = ApiConnectorParam(
            param_id=item.get("param_id") or _new_id("ACP"),
            operation_id=operation_id,
            param_name=item["param_name"],
            display_name=item.get("display_name"),
            param_location=item.get("param_location") or "QUERY",
            param_type=item.get("param_type") or "STRING",
            required_yn=bool(item.get("required_yn", False)),
            default_value=item.get("default_value"),
            example_value=item.get("example_value"),
            allowed_values_json=item.get("allowed_values_json"),
            value_source=item.get("value_source") or "USER_INPUT",
            secret_key_ref=item.get("secret_key_ref"),
            encode_yn=bool(item.get("encode_yn", True)),
            sort_order=int(item.get("sort_order", idx)),
            active_yn=bool(item.get("active_yn", True)),
            metadata_json=item.get("metadata_json"),
        )
        db.add(p)
        out.append(p)
    await db.flush()
    return [_param_dict(p) for p in out]


async def upsert_credential(db: AsyncSession, data_source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _get_source(db, data_source_id)
    existing = await _get_credential(db, data_source_id)
    now = utc_now()
    secret_plain = payload.get("secret_value")
    enc = None
    masked = None
    if secret_plain:
        enc, masked = store_secret(str(secret_plain))

    if existing:
        cred = existing
        cred.credential_name = payload.get("credential_name") or cred.credential_name
        cred.credential_type = payload.get("credential_type") or cred.credential_type
        cred.key_location = payload.get("key_location") or cred.key_location
        cred.key_name = payload.get("key_name") or cred.key_name
        cred.encoding_policy = payload.get("encoding_policy") or cred.encoding_policy
        if enc:
            cred.secret_value_encrypted = enc
            cred.secret_value_masked = masked
        cred.updated_at = now
    else:
        if not enc and payload.get("credential_type", "API_KEY") != "NONE":
            raise ApiConnectorError("인증 secret 값이 필요합니다.", error_code="MISSING_SECRET")
        cred = ApiConnectorCredential(
            credential_id=_new_id("ACC"),
            data_source_id=data_source_id,
            credential_name=payload.get("credential_name") or "default",
            credential_type=payload.get("credential_type") or "API_KEY",
            key_location=payload.get("key_location") or "QUERY",
            key_name=payload.get("key_name") or "serviceKey",
            secret_value_encrypted=enc,
            secret_value_masked=masked,
            encoding_policy=payload.get("encoding_policy") or "STORE_DECODED_ENCODE_ON_CALL",
            active_yn=True,
            created_at=now,
            updated_at=now,
        )
        db.add(cred)
    await db.flush()
    return _credential_dict(cred)


async def upsert_pagination(db: AsyncSession, operation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _get_operation(db, operation_id)
    existing = await _get_pagination(db, operation_id)
    if existing:
        pg = existing
        for key in (
            "pagination_type", "page_param_name", "size_param_name", "page_start",
            "page_size", "max_pages", "total_count_path", "next_link_path", "stop_condition", "active_yn",
        ):
            if key in payload:
                setattr(pg, key, payload[key])
    else:
        pg = ApiConnectorPagination(
            pagination_id=_new_id("ACPG"),
            operation_id=operation_id,
            pagination_type=payload.get("pagination_type") or "NONE",
            page_param_name=payload.get("page_param_name"),
            size_param_name=payload.get("size_param_name"),
            page_start=int(payload.get("page_start", 1)),
            page_size=int(payload.get("page_size", 100)),
            max_pages=min(int(payload.get("max_pages", 1)), MAX_LOAD_PAGES),
            total_count_path=payload.get("total_count_path"),
            next_link_path=payload.get("next_link_path"),
            stop_condition=payload.get("stop_condition") or "EMPTY_ITEMS",
            active_yn=bool(payload.get("active_yn", True)),
        )
        db.add(pg)
    await db.flush()
    return _pagination_dict(pg)


async def build_request_preview(
    db: AsyncSession,
    operation_id: str,
    runtime_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    source = await _get_source(db, op.data_source_id)
    base_url = _resolve_base_url(source)
    full_url = build_full_url(base_url, op.endpoint_path)
    query, headers, body = await _build_request_params(db, op, source, runtime_params)
    credential = await _get_credential(db, source.data_source_id)
    warnings: list[str] = []
    if credential and credential.encoding_policy == "STORE_AS_IS":
        warnings.append("Encoding key를 저장한 경우 이중 URL 인코딩될 수 있습니다. Decoding key 입력을 권장합니다.")
    return {
        "operation_id": operation_id,
        "masked_url": mask_url(full_url),
        "query_params_masked": mask_params_dict(query),
        "headers_masked": mask_params_dict(headers),
        "body_masked": mask_params_dict(body),
        "actual_call_ready": True,
        "encoding_policy": credential.encoding_policy if credential else None,
        "warnings": warnings,
        "service_key_hint": (
            "공공데이터포털 serviceKey는 Decoding 키 입력을 권장합니다. "
            "THERMOps가 호출 시 한 번만 URL 인코딩합니다."
        ),
    }


async def _execute_operation_call(
    db: AsyncSession,
    operation_id: str,
    *,
    runtime_params: dict[str, Any] | None = None,
    sample_limit: int = MAX_TEST_ITEMS,
    called_by: str | None = None,
    save_snapshot: bool = True,
) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    source = await _get_source(db, op.data_source_id)
    base_url = _resolve_base_url(source)
    full_url = build_full_url(base_url, op.endpoint_path)
    pagination = await _get_pagination(db, operation_id)

    all_items: list[dict[str, Any]] = []
    last_result: dict[str, Any] = {}
    pages = 1
    max_pages = 1
    page_no = 1
    if pagination and pagination.pagination_type == "PAGE_NO":
        max_pages = min(int(pagination.max_pages or 1), MAX_LOAD_PAGES)
        page_no = int(pagination.page_start or 1)

    for page_idx in range(max_pages):
        params = dict(runtime_params or {})
        if pagination and pagination.pagination_type == "PAGE_NO":
            if pagination.page_param_name:
                params[pagination.page_param_name] = str(page_no + page_idx)
            if pagination.size_param_name:
                params[pagination.size_param_name] = str(pagination.page_size or 100)

        query, headers, body = await _build_request_params(db, op, source, params)
        try:
            last_result = await asyncio.to_thread(
                execute_http_request,
                method=op.http_method,
                url=full_url,
                query_params=query,
                headers=headers,
                body=body if body else None,
                retries=0,
            )
        except ValueError as exc:
            log_id = _new_id("ACL")
            db.add(
                ApiConnectorCallLog(
                    call_log_id=log_id,
                    operation_id=operation_id,
                    data_source_id=source.data_source_id,
                    called_at=utc_now(),
                    called_by=called_by,
                    request_url_masked=mask_url(full_url),
                    request_params_masked=mask_params_dict(query),
                    http_status=None,
                    success_yn=False,
                    response_format=op.response_format,
                    error_message=str(exc),
                )
            )
            await db.flush()
            raise ApiConnectorError(str(exc), error_code="API_REQUEST_FAILED") from exc

        if last_result["http_status"] >= 400:
            msg = f"API 요청 실패 (HTTP {last_result['http_status']})"
            log_id = _new_id("ACL")
            db.add(
                ApiConnectorCallLog(
                    call_log_id=log_id,
                    operation_id=operation_id,
                    data_source_id=source.data_source_id,
                    called_at=utc_now(),
                    called_by=called_by,
                    request_url_masked=last_result.get("request_url_masked") or mask_url(full_url),
                    request_params_masked=mask_params_dict(query),
                    http_status=last_result["http_status"],
                    success_yn=False,
                    response_format=op.response_format,
                    duration_ms=last_result.get("duration_ms"),
                    error_message=msg,
                )
            )
            await db.flush()
            raise ApiConnectorError(msg, error_code="API_REQUEST_FAILED")

        payload = parse_response_body(last_result["text"], op.response_format)
        page_items = normalize_items(
            payload,
            item_path=op.response_item_path,
            array_mode=op.result_array_mode or "AUTO",
        )
        all_items.extend(page_items)
        pages = page_idx + 1
        if not page_items and pagination and pagination.stop_condition == "EMPTY_ITEMS":
            break
        if pagination and pagination.pagination_type != "PAGE_NO":
            break

    items = all_items[:sample_limit]
    snapshot_id = None
    log_id = _new_id("ACL")
    if save_snapshot:
        snapshot_id = _new_id("ACS")
        db.add(
            ApiConnectorResponseSnapshot(
                snapshot_id=snapshot_id,
                operation_id=operation_id,
                call_log_id=log_id,
                captured_at=utc_now(),
                response_format=op.response_format,
                raw_response_text=last_result.get("text", "")[:50000],
                normalized_items_json=items,
                item_count=len(all_items),
                sample_only_yn=len(all_items) > sample_limit,
            )
        )
    db.add(
        ApiConnectorCallLog(
            call_log_id=log_id,
            operation_id=operation_id,
            data_source_id=source.data_source_id,
            called_at=utc_now(),
            called_by=called_by,
            request_url_masked=last_result.get("request_url_masked"),
            request_params_masked=mask_params_dict(query),
            http_status=last_result.get("http_status"),
            success_yn=True,
            response_format=op.response_format,
            response_item_count=len(all_items),
            duration_ms=last_result.get("duration_ms"),
            raw_response_snapshot_id=snapshot_id,
        )
    )
    await db.flush()
    return {
        "call_log_id": log_id,
        "snapshot_id": snapshot_id,
        "items": items,
        "item_count": len(all_items),
        "sample_count": len(items),
        "http_status": last_result.get("http_status"),
        "duration_ms": last_result.get("duration_ms"),
        "pages_fetched": pages,
    }


async def test_call(
    db: AsyncSession,
    operation_id: str,
    runtime_params: dict[str, Any] | None = None,
    *,
    called_by: str | None = None,
) -> dict[str, Any]:
    result = await _execute_operation_call(
        db, operation_id, runtime_params=runtime_params, sample_limit=MAX_TEST_ITEMS, called_by=called_by
    )
    return {
        "success": True,
        "message": "테스트 호출에 성공했습니다.",
        "item_count": result["item_count"],
        "sample_items": result["items"],
        "http_status": result["http_status"],
        "duration_ms": result["duration_ms"],
        "call_log_id": result["call_log_id"],
        "snapshot_id": result["snapshot_id"],
    }


async def response_preview(
    db: AsyncSession,
    operation_id: str,
    runtime_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = await _execute_operation_call(db, operation_id, runtime_params=runtime_params, sample_limit=MAX_TEST_ITEMS)
    return {
        "operation_id": operation_id,
        "item_count": result["item_count"],
        "sample_items": result["items"],
        "snapshot_id": result["snapshot_id"],
    }


async def load_preview(
    db: AsyncSession,
    operation_id: str,
    runtime_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    if not op.target_table:
        raise ApiConnectorError("적재 대상 테이블이 설정되지 않았습니다.", error_code="MISSING_TARGET_TABLE")
    result = await _execute_operation_call(db, operation_id, runtime_params=runtime_params, sample_limit=MAX_TEST_ITEMS)
    mapping = await _resolve_mapping(db, op.data_source_id, op.target_table)
    preview = await preview_load_rows(
        db,
        target_table=op.target_table,
        items=result["items"],
        mapping=mapping,
        limit=10,
    )
    return {**preview, "snapshot_id": result["snapshot_id"], "api_item_count": result["item_count"]}


async def run_load(
    db: AsyncSession,
    operation_id: str,
    runtime_params: dict[str, Any] | None = None,
    *,
    called_by: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    if not op.target_table:
        raise ApiConnectorError("적재 대상 테이블이 설정되지 않았습니다.", error_code="MISSING_TARGET_TABLE")

    started = utc_now()
    load_id = _new_id("ACLR")
    query_masked: dict[str, Any] = {}
    run = ApiConnectorLoadRun(
        load_run_id=load_id,
        operation_id=operation_id,
        data_source_id=op.data_source_id,
        target_table=op.target_table,
        standard_dataset_id=op.standard_dataset_id,
        started_at=started,
        run_status="RUNNING",
        request_params_snapshot=runtime_params,
        request_params_masked=mask_params_dict(runtime_params or {}),
    )
    db.add(run)
    await db.flush()

    try:
        result = await _execute_operation_call(
            db,
            operation_id,
            runtime_params=runtime_params,
            sample_limit=MAX_LOAD_ITEMS,
            called_by=called_by,
        )
        run.raw_snapshot_id = result.get("snapshot_id")
        if dry_run:
            mapping = await _resolve_mapping(db, op.data_source_id, op.target_table)
            preview = await preview_load_rows(
                db,
                target_table=op.target_table,
                items=result["items"],
                mapping=mapping,
                limit=10,
            )
            run.run_status = "SUCCESS"
            run.finished_at = utc_now()
            run.result_summary = {"dry_run": True, **preview}
            await db.flush()
            return {
                "load_run_id": load_id,
                "status": "SUCCESS",
                "dry_run": True,
                **preview,
            }

        mapping = await _resolve_mapping(db, op.data_source_id, op.target_table)
        counts = await insert_rows(
            db,
            target_table=op.target_table,
            items=result["items"],
            mapping=mapping,
            max_rows=MAX_LOAD_ITEMS,
        )
        finished = utc_now()
        run.run_status = "SUCCESS" if counts["error_count"] == 0 else "WARNING"
        run.finished_at = finished
        run.inserted_count = counts["inserted_count"]
        run.skipped_count = counts["skipped_count"]
        run.error_count = counts["error_count"]
        run.result_summary = {
            "api_item_count": result["item_count"],
            **counts,
            "snapshot_id": result.get("snapshot_id"),
        }
        source = await _get_source(db, op.data_source_id)
        source.last_loaded_at = finished
        await db.flush()
        return {
            "load_run_id": load_id,
            "status": run.run_status,
            **counts,
            "api_item_count": result["item_count"],
        }
    except Exception as exc:
        run.run_status = "FAILED"
        run.finished_at = utc_now()
        run.error_message = str(exc)[:500]
        await db.flush()
        if isinstance(exc, ApiConnectorError):
            raise
        raise ApiConnectorError(str(exc), error_code="LOAD_FAILED") from exc


async def list_load_runs(db: AsyncSession, *, operation_id: str | None = None) -> list[dict[str, Any]]:
    q = select(ApiConnectorLoadRun).order_by(ApiConnectorLoadRun.started_at.desc())
    if operation_id:
        q = q.where(ApiConnectorLoadRun.operation_id == operation_id)
    rows = (await db.execute(q.limit(100))).scalars().all()
    return [
        {
            "load_run_id": r.load_run_id,
            "operation_id": r.operation_id,
            "data_source_id": r.data_source_id,
            "target_table": r.target_table,
            "run_status": r.run_status,
            "inserted_count": r.inserted_count,
            "skipped_count": r.skipped_count,
            "error_count": r.error_count,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "result_summary": r.result_summary,
            "error_message": r.error_message,
        }
        for r in rows
    ]


async def get_load_run(db: AsyncSession, load_run_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(select(ApiConnectorLoadRun).where(ApiConnectorLoadRun.load_run_id == load_run_id))
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "load_run_id": row.load_run_id,
        "operation_id": row.operation_id,
        "data_source_id": row.data_source_id,
        "target_table": row.target_table,
        "run_status": row.run_status,
        "request_params_masked": row.request_params_masked,
        "inserted_count": row.inserted_count,
        "skipped_count": row.skipped_count,
        "error_count": row.error_count,
        "raw_snapshot_id": row.raw_snapshot_id,
        "result_summary": row.result_summary,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


async def list_call_logs(db: AsyncSession, *, operation_id: str | None = None) -> list[dict[str, Any]]:
    q = select(ApiConnectorCallLog).order_by(ApiConnectorCallLog.called_at.desc())
    if operation_id:
        q = q.where(ApiConnectorCallLog.operation_id == operation_id)
    rows = (await db.execute(q.limit(100))).scalars().all()
    return [
        {
            "call_log_id": r.call_log_id,
            "operation_id": r.operation_id,
            "data_source_id": r.data_source_id,
            "called_at": r.called_at.isoformat() if r.called_at else None,
            "request_url_masked": r.request_url_masked,
            "request_params_masked": r.request_params_masked,
            "http_status": r.http_status,
            "success_yn": r.success_yn,
            "response_item_count": r.response_item_count,
            "duration_ms": r.duration_ms,
            "error_message": r.error_message,
            "raw_response_snapshot_id": r.raw_response_snapshot_id,
        }
        for r in rows
    ]


async def get_snapshot(db: AsyncSession, snapshot_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(ApiConnectorResponseSnapshot).where(ApiConnectorResponseSnapshot.snapshot_id == snapshot_id)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "snapshot_id": row.snapshot_id,
        "operation_id": row.operation_id,
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
        "response_format": row.response_format,
        "item_count": row.item_count,
        "sample_only_yn": row.sample_only_yn,
        "normalized_items_json": row.normalized_items_json,
        "raw_response_preview": (row.raw_response_text or "")[:2000],
    }
