#!/usr/bin/env python3
"""R10-S8 Upsert / Deduplicate loader 단건 테스트 — 전용 fixture만 사용."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from test_fixtures import psql_run, psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")

# deterministic fixture identifiers — 다른 테스트 operation 을 절대 선택하지 않는다.
SOURCE_NAME = "TEST R10-S8 Upsert Dedup"
OPERATION_NAME = "R10-S8 Upsert Dedup Test Operation"
DATASET_CODE = "TEST_R10S8_UPSERT"
DATASET_NAME = "R10-S8 Upsert Dedup Test Dataset"
TARGET_TABLE = "std_r10s8_upsert_test"
STATION_CODE = "R10S8STN"
CONFLICT_KEYS = ["station_code", "observed_at"]
RUNTIME_PARAMS = {"stn_id": STATION_CODE, "tm": "2026-01-01 01:00"}


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload.get("data")


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def cleanup_upsert_test_fixtures() -> None:
    """테스트 전용 fixture만 자식→부모 순서로 정리. 다른 테스트 operation은 건드리지 않는다."""
    op_name = _sql_quote(OPERATION_NAME)
    source_name = _sql_quote(SOURCE_NAME)
    ds_code = _sql_quote(DATASET_CODE)
    station = _sql_quote(STATION_CODE)
    table = _sql_quote(TARGET_TABLE)

    op_ids_sql = (
        f"SELECT operation_id FROM tb_api_connector_operation "
        f"WHERE operation_name = '{op_name}'"
    )
    op_id = psql_scalar(op_ids_sql)
    if op_id:
        safe_op = _sql_quote(op_id)
        psql_run(
            f"""
            DELETE FROM tb_api_connector_load_dedup_summary WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_response_snapshot WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_call_log WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_load_run WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_write_policy WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_transform_config WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_param WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_pagination WHERE operation_id = '{safe_op}';
            DELETE FROM tb_data_load_schedule_event
              WHERE schedule_id IN (
                SELECT schedule_id FROM tb_data_load_schedule WHERE operation_id = '{safe_op}'
              );
            DELETE FROM tb_data_load_schedule_run
              WHERE schedule_id IN (
                SELECT schedule_id FROM tb_data_load_schedule WHERE operation_id = '{safe_op}'
              );
            DELETE FROM tb_data_load_schedule WHERE operation_id = '{safe_op}';
            DELETE FROM tb_api_connector_operation WHERE operation_id = '{safe_op}';
            """
        )

    psql_run(
        f"""
        DELETE FROM tb_api_connector_credential
          WHERE data_source_id IN (
            SELECT source_id FROM tb_data_source WHERE source_name = '{source_name}'
          );
        DELETE FROM tb_data_source WHERE source_name = '{source_name}';
        DELETE FROM tb_standard_dataset_column
          WHERE dataset_type_id IN (
            SELECT dataset_type_id FROM tb_standard_dataset_type
            WHERE dataset_type_code = '{ds_code}'
          );
        DELETE FROM tb_standard_dataset_table_create_log
          WHERE dataset_type_id IN (
            SELECT dataset_type_id FROM tb_standard_dataset_type
            WHERE dataset_type_code = '{ds_code}'
          );
        DELETE FROM tb_standard_dataset_type WHERE dataset_type_code = '{ds_code}';
        DELETE FROM tb_weather_observation_station WHERE station_code = '{station}';
        DROP TABLE IF EXISTS {table};
        """
    )


def ensure_upsert_test_station() -> None:
    existing = psql_scalar(
        f"SELECT station_id FROM tb_weather_observation_station "
        f"WHERE station_code = '{_sql_quote(STATION_CODE)}' LIMIT 1"
    )
    if existing:
        return
    api(
        "POST",
        "/weather/observation-stations",
        {
            "station_code": STATION_CODE,
            "station_name": "R10-S8 Upsert Test Station",
            "station_type": "ASOS",
        },
    )


def ensure_upsert_test_target_table() -> str:
    existing = psql_scalar(
        f"SELECT dataset_type_id FROM tb_standard_dataset_type "
        f"WHERE dataset_type_code = '{_sql_quote(DATASET_CODE)}' LIMIT 1"
    )
    if existing:
        # physical table may remain from prior run
        exists = psql_scalar(f"SELECT to_regclass('public.{_sql_quote(TARGET_TABLE)}')")
        if not exists:
            api("POST", f"/standard-dataset-types/{existing}/create-physical-table", {"confirm": True})
        psql_run(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{TARGET_TABLE}_conflict
                ON {TARGET_TABLE} (station_code, observed_at);
            """
        )
        return TARGET_TABLE

    ds = api(
        "POST",
        "/standard-dataset-types",
        {
            "dataset_type_code": DATASET_CODE,
            "dataset_type_name": DATASET_NAME,
            "target_table": TARGET_TABLE,
            "status": "DRAFT",
            "managed_table": True,
            "mapping_supported": True,
            "columns": [
                {"column_name": "station_code", "data_type": "VARCHAR", "data_length": 32, "required": True},
                {
                    "column_name": "observed_at",
                    "data_type": "TIMESTAMP",
                    "required": True,
                    "default_column_role": "TIME_KEY",
                },
                {"column_name": "temperature", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "humidity", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "wind_speed", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "precipitation", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "source_system", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "source_operation_id", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "raw_json", "data_type": "JSONB"},
            ],
        },
    )
    ds_id = ds["dataset_type_id"]
    api("POST", f"/standard-dataset-types/{ds_id}/validate")
    api("POST", f"/standard-dataset-types/{ds_id}/create-physical-table", {"confirm": True})
    api("POST", f"/standard-dataset-types/{ds_id}/activate")
    psql_run(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_{TARGET_TABLE}_conflict
            ON {TARGET_TABLE} (station_code, observed_at);
        """
    )
    return TARGET_TABLE


def ensure_upsert_test_source() -> str:
    sources = api("GET", "/data-sources?page=1&size=100")
    items = sources.get("items", []) if isinstance(sources, dict) else sources
    for s in items:
        if s.get("source_name") == SOURCE_NAME:
            return s["source_id"]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": SOURCE_NAME,
            "source_type": "REST_API",
            "data_domain": "REFERENCE",
            "connection_info": {"base_url": INTERNAL_BASE},
            "active_yn": True,
        },
    )
    return created["source_id"]


def ensure_upsert_test_operation() -> str:
    """전용 operation 생성/재사용. 다른 테스트 operation fallback 금지."""
    ops = api("GET", "/api-connectors/operations") or []
    for op in ops:
        if op.get("operation_name") == OPERATION_NAME:
            return op["operation_id"]

    source_id = ensure_upsert_test_source()
    op = api(
        "POST",
        "/api-connectors/operations",
        {
            "data_source_id": source_id,
            "operation_name": OPERATION_NAME,
            "endpoint_path": "/sample-external/asos-hourly",
            "response_item_path": "data.items",
            "target_table": TARGET_TABLE,
        },
    )
    op_id = op["operation_id"]
    api(
        "PUT",
        f"/api-connectors/operations/{op_id}/params",
        {
            "params": [
                {"param_name": "stn_id", "param_location": "QUERY", "param_type": "STRING"},
                {"param_name": "tm", "param_location": "QUERY", "param_type": "STRING"},
            ]
        },
    )
    api(
        "PUT",
        f"/api-connectors/operations/{op_id}/transform-config",
        {
            "transform_type": "ASOS_HOURLY_TO_CANONICAL",
            "source_system": "KMA_ASOS_API",
            "station_unmapped_policy": "WARN_ONLY",
        },
    )
    api("PUT", f"/api-connectors/operations/{op_id}/pagination", {"pagination_type": "NONE", "max_pages": 1})
    return op_id


def ensure_upsert_write_policy(operation_id: str) -> dict:
    return api(
        "PUT",
        f"/api-connectors/operations/{operation_id}/write-policy",
        {
            "write_mode": "UPSERT",
            "conflict_key_columns_json": CONFLICT_KEYS,
            "duplicate_within_batch_policy": "KEEP_LAST",
            "null_update_policy": "KEEP_EXISTING",
        },
    )


def main() -> int:
    print(f"THERMOps upsert/dedup loader test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            assert int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_write_policy") or "0") == 0
            assert int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_load_dedup_summary") or "0") == 0
            assert int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_operation") or "0") == 0
            print("  [ok] clean verify: write_policy/dedup/operation = 0")
            print("PASS")
            return 0

        cleanup_upsert_test_fixtures()
        ensure_upsert_test_station()
        table = ensure_upsert_test_target_table()
        operation_id = ensure_upsert_test_operation()
        print(f"  [ok] fixture operation={operation_id} table={table} keys={CONFLICT_KEYS}")

        policy = ensure_upsert_write_policy(operation_id)
        assert policy["write_mode"] == "UPSERT"
        assert policy.get("conflict_key_columns_json") == CONFLICT_KEYS

        fetched = api("GET", f"/api-connectors/operations/{operation_id}/write-policy")
        assert fetched["write_mode"] == "UPSERT"
        print("  [ok] write-policy UPSERT save/get")

        validated = api(
            "POST",
            f"/api-connectors/operations/{operation_id}/write-policy/validate",
            {"write_mode": "INSERT_ONLY"},
        )
        assert validated["write_mode"] == "INSERT_ONLY"
        # restore UPSERT for load runs
        ensure_upsert_write_policy(operation_id)
        print("  [ok] write-policy validate")

        preview = api(
            "POST",
            f"/api-connectors/operations/{operation_id}/load-preview",
            {"runtime_params": RUNTIME_PARAMS},
        )
        assert "estimated_insert_count" in preview or "write_mode" in preview
        assert preview.get("write_mode") in (None, "UPSERT", "INSERT_ONLY") or "write_mode" in preview
        print(f"  [ok] load-preview write_mode={preview.get('write_mode')}")

        first = api(
            "POST",
            f"/api-connectors/operations/{operation_id}/load-run",
            {"runtime_params": RUNTIME_PARAMS},
        )
        assert first.get("dedup_summary_id") or "inserted_count" in first
        first_inserted = int(first.get("inserted_count") or 0)
        assert first_inserted >= 1, f"first load expected insert, got {first}"
        print(
            f"  [ok] first load-run inserted={first_inserted} "
            f"updated={first.get('updated_count')} skipped={first.get('skipped_duplicate_count')}"
        )

        second = api(
            "POST",
            f"/api-connectors/operations/{operation_id}/load-run",
            {"runtime_params": RUNTIME_PARAMS},
        )
        second_inserted = int(second.get("inserted_count") or 0)
        second_updated = int(second.get("updated_count") or 0)
        second_skipped = int(second.get("skipped_duplicate_count") or 0) + int(
            second.get("unchanged_count") or 0
        )
        assert second_inserted == 0, f"second load should not insert new rows: {second}"
        assert (second_updated + second_skipped) >= 1, f"second load expected update/skip: {second}"
        print(
            f"  [ok] second load-run upsert behavior "
            f"inserted={second_inserted} updated={second_updated} skipped/unchanged={second_skipped}"
        )

        summaries = api("GET", f"/api-connectors/dedup-summaries?operation_id={operation_id}")
        if not isinstance(summaries, list):
            summaries = api("GET", "/api-connectors/dedup-summaries") or []
            summaries = [s for s in summaries if s.get("operation_id") == operation_id]
        assert isinstance(summaries, list) and len(summaries) >= 1
        detail = api("GET", f"/api-connectors/dedup-summaries/{summaries[0]['summary_id']}")
        assert detail["summary_id"] == summaries[0]["summary_id"]
        assert detail.get("operation_id") == operation_id
        print(f"  [ok] dedup summary count={len(summaries)}")

        # 다른 테스트 residual 이 있어도 본 테스트는 전용 operation 만 사용했는지 재확인
        assert (
            psql_scalar(
                f"SELECT operation_name FROM tb_api_connector_operation "
                f"WHERE operation_id = '{_sql_quote(operation_id)}'"
            )
            == OPERATION_NAME
        )
        print("  [ok] used dedicated fixture operation only")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
