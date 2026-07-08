#!/usr/bin/env python3
"""R10-S7 운영 점검 / 통합 시나리오 검증."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_fixtures import FS_LAG_ROLL_ID, ensure_csv_ingested, ensure_feature_dataset_built, ensure_test_platform, psql_run, psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
ROOT_BASE = API_BASE.rsplit("/api/v1", 1)[0]
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")
SEED_PATH = _SCRIPTS.parent / "db" / "init" / "02_seed_clean.sql"
SECRET_TOKEN = "TEST_SECRET_R10S7_SHOULD_NOT_LEAK"
LEAK_KEYS = ("TEST_SECRET_R10S7_SHOULD_NOT_LEAK", "serviceKey", "Authorization", "token")


def _assert_no_leak(payload: object, *, label: str, allow_words: tuple[str, ...] = ("serviceKey",)) -> None:
    blob = json.dumps(payload, ensure_ascii=False)
    assert SECRET_TOKEN not in blob, f"{label}: secret token leaked"
    blob_lower = blob.lower()
    for key in LEAK_KEYS:
        if key == SECRET_TOKEN:
            continue
        key_lower = key.lower()
        if key in allow_words:
            continue
        assert f"{key_lower}\":" not in blob_lower, f"{label}: raw key leaked ({key})"
    assert "****" in blob or "masked" in blob_lower or "secret" not in blob_lower, f"{label}: masking evidence missing"


def api(method: str, path: str, body: dict | None = None, *, expect_fail: bool = False, timeout: int = 180) -> dict | list | None:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if expect_fail:
            return {"http_error": exc.code, "body": exc.read().decode()}
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success") and not expect_fail:
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload.get("data")


def fetch_openapi() -> dict:
    req = urllib.request.Request(f"{ROOT_BASE}/openapi.json", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def ensure_rest_source(name: str) -> str:
    sources = api("GET", "/data-sources?page=1&size=100")
    items = sources.get("items", []) if isinstance(sources, dict) else sources
    for s in items:
        if s.get("source_name") == name:
            return s["source_id"]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": name,
            "source_type": "REST_API",
            "data_domain": "REFERENCE",
            "connection_info": {"base_url": INTERNAL_BASE},
            "active_yn": True,
        },
    )
    return created["source_id"]


def create_standard_dataset(
    *,
    suffix: str,
    code_prefix: str,
    name_prefix: str,
    table_prefix: str,
    columns: list[dict],
) -> tuple[str, str]:
    table = f"{table_prefix}_{suffix}"
    code = f"{code_prefix}_{suffix.upper()}"
    created = api(
        "POST",
        "/standard-dataset-types",
        {
            "dataset_type_code": code,
            "dataset_type_name": f"{name_prefix} {suffix}",
            "target_table": table,
            "status": "DRAFT",
            "managed_table": True,
            "mapping_supported": True,
            "columns": columns,
        },
    )
    ds_id = created["dataset_type_id"]
    api("POST", f"/standard-dataset-types/{ds_id}/validate")
    api("POST", f"/standard-dataset-types/{ds_id}/preview-create-table")
    api("POST", f"/standard-dataset-types/{ds_id}/create-physical-table", {"confirm": True})
    api("POST", f"/standard-dataset-types/{ds_id}/activate")
    return ds_id, table


def create_forecast_ready_entity(tag: str) -> tuple[str, int, int]:
    ent = api(
        "POST",
        "/prediction-entities",
        {
            "entity_code": f"SITE-{tag}",
            "entity_name": f"R10 통합지점 {tag}",
            "entity_type": "SITE",
            "business_domain": "HEAT_DEMAND",
        },
    )
    entity_id = ent["entity_id"]
    api(
        "POST",
        f"/prediction-entities/{entity_id}/locations",
        {"address": "서울", "latitude": 37.5665, "longitude": 126.9780, "active_yn": True},
    )
    grid_conv = api("POST", "/weather/convert-latlon-to-grid", {"latitude": 37.5665, "longitude": 126.9780})
    grid = api(
        "POST",
        "/weather/forecast-grids",
        {"nx": grid_conv["nx"], "ny": grid_conv["ny"], "grid_name": f"R10 grid {tag}"},
    )
    api(
        "POST",
        f"/prediction-entities/{entity_id}/weather-mappings",
        {
            "forecast_grid_id": grid["forecast_grid_id"],
            "mapping_type": "FORECAST_GRID",
            "mapping_method": "LATLON_TO_GRID",
        },
    )
    readiness = api("GET", f"/prediction-entities/{entity_id}/weather-readiness")
    assert readiness.get("forecast_ready") is True
    return entity_id, int(grid_conv["nx"]), int(grid_conv["ny"])


def main() -> int:
    print(f"THERMOps R10 operational integration test ({API_BASE})")
    try:
        # Scenario A: clean installation / empty tables
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            clean_tables = (
                "tb_standard_dataset_type",
                "tb_data_source",
                "tb_api_connector_operation",
                "tb_prediction_entity",
                "tb_external_code_mapping",
                "tb_unmapped_external_code",
                "tb_api_connector_transform_config",
                "tb_forecast_provider_config",
                "tb_forecast_input_snapshot",
                "tb_prediction_weather_input",
                "tb_data_load_schedule",
                "tb_data_load_schedule_run",
                "tb_data_load_schedule_event",
            )
            for tbl in clean_tables:
                count = int(psql_scalar(f"SELECT COUNT(*) FROM {tbl}") or "0")
                assert count == 0, f"{tbl} expected 0 got {count}"
            seed = SEED_PATH.read_text(encoding="utf-8").lower()
            for keyword in ("tb_data_source", "tb_standard_dataset_type", "tb_api_connector_operation", "tb_data_load_schedule"):
                assert f"insert into {keyword}" not in seed
            print("  [ok] clean seed R10 tables are empty")
            print("PASS")
            return 0

        # Scenario D/F prerequisites (test platform for prediction flow)
        ensure_test_platform()
        ensure_csv_ingested(api)
        ensure_feature_dataset_built(api, FS_LAG_ROLL_ID, timeout=180)

        tag = uuid.uuid4().hex[:8]
        entity_id, nx, ny = create_forecast_ready_entity(tag)
        print(f"  [ok] prediction entity ready {entity_id} nx={nx} ny={ny}")

        # Scenario B: standard datasets + physical tables
        _, heat_table = create_standard_dataset(
            suffix=tag,
            code_prefix="R10S7_HEAT",
            name_prefix="R10S7 Heat Demand",
            table_prefix="std_r10s7_heat",
            columns=[
                {"column_name": "measured_at", "data_type": "TIMESTAMP", "required": True, "default_column_role": "TIME_KEY"},
                {"column_name": "heat_demand", "data_type": "NUMERIC", "numeric_precision": 18, "numeric_scale": 4, "default_column_role": "TARGET"},
                {"column_name": "entity_id", "data_type": "VARCHAR", "data_length": 64, "default_column_role": "ENTITY_KEY"},
                {"column_name": "site_id", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "external_node_id", "data_type": "VARCHAR", "data_length": 64},
            ],
        )
        _, asos_table = create_standard_dataset(
            suffix=tag,
            code_prefix="R10S7_ASOS",
            name_prefix="R10S7 ASOS",
            table_prefix="std_r10s7_asos",
            columns=[
                {"column_name": "station_code", "data_type": "VARCHAR", "data_length": 32, "required": True},
                {"column_name": "observed_at", "data_type": "TIMESTAMP", "required": True, "default_column_role": "TIME_KEY"},
                {"column_name": "temperature", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "humidity", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "wind_speed", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "precipitation", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
                {"column_name": "source_system", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "source_operation_id", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "raw_json", "data_type": "JSONB"},
            ],
        )
        _, cal_date_table = create_standard_dataset(
            suffix=tag,
            code_prefix="R10S7_CALD",
            name_prefix="R10S7 Calendar Date",
            table_prefix="std_r10s7_cal_date",
            columns=[
                {"column_name": "calendar_date", "data_type": "DATE", "required": True, "default_column_role": "TIME_KEY"},
                {"column_name": "year", "data_type": "INTEGER"},
                {"column_name": "month", "data_type": "INTEGER"},
                {"column_name": "day", "data_type": "INTEGER"},
                {"column_name": "day_of_week", "data_type": "INTEGER"},
                {"column_name": "day_name", "data_type": "VARCHAR", "data_length": 8},
                {"column_name": "is_holiday", "data_type": "BOOLEAN"},
                {"column_name": "special_day_name", "data_type": "VARCHAR", "data_length": 100},
            ],
        )
        _, cal_hour_table = create_standard_dataset(
            suffix=tag,
            code_prefix="R10S7_CALH",
            name_prefix="R10S7 Calendar Hour",
            table_prefix="std_r10s7_cal_hour",
            columns=[
                {"column_name": "measured_at", "data_type": "TIMESTAMP", "required": True, "default_column_role": "TIME_KEY"},
                {"column_name": "calendar_date", "data_type": "DATE"},
                {"column_name": "hour", "data_type": "INTEGER"},
                {"column_name": "is_holiday", "data_type": "BOOLEAN"},
                {"column_name": "special_day_name", "data_type": "VARCHAR", "data_length": 100},
            ],
        )
        print("  [ok] standard dataset fixtures created (heat/asos/calendar date/hour)")

        # Scenario C: heat-demand wide-hour transform
        source_id = ensure_rest_source(f"TEST R10-S7 REST {tag}")
        cred = api(
            "PUT",
            f"/api-connectors/data-sources/{source_id}/credential",
            {
                "credential_type": "API_KEY",
                "key_location": "QUERY",
                "key_name": "serviceKey",
                "secret_value": SECRET_TOKEN,
                "encoding_policy": "STORE_DECODED_ENCODE_ON_CALL",
            },
        )
        _assert_no_leak(cred, label="credential response", allow_words=("serviceKey",))

        mapping = api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"ND-{tag}",
                "external_code_name": "R10 통합 노드",
                "target_type": "PREDICTION_ENTITY",
                "target_id": entity_id,
            },
        )
        assert mapping.get("mapping_id")

        heat_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"R10S7 Heat Wide {tag}",
                "endpoint_path": "/sample-external/heat-demand-wide",
                "response_item_path": "data.items",
                "target_table": heat_table,
            },
        )
        heat_op_id = heat_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{heat_op_id}/transform-config",
            {"transform_type": "WIDE_HOUR_TO_LONG", "unmapped_policy": "LOG_ONLY"},
        )
        api(
            "PUT",
            f"/api-connectors/operations/{heat_op_id}/params",
            {
                "params": [
                    {"param_name": "nd_id", "param_location": "QUERY", "param_type": "STRING", "default_value": f"ND-{tag}"},
                    {"param_name": "nd_name", "param_location": "QUERY", "param_type": "STRING", "default_value": "통합테스트"},
                    {"param_name": "bas_ymd", "param_location": "QUERY", "param_type": "STRING", "default_value": "20260101"},
                ]
            },
        )
        api(
            "PUT",
            f"/api-connectors/operations/{heat_op_id}/write-policy",
            {
                "write_mode": "UPSERT",
                "conflict_key_columns_json": ["entity_id", "measured_at"],
                "duplicate_within_batch_policy": "KEEP_LAST",
                "null_update_policy": "KEEP_EXISTING",
            },
        )
        heat_preview = api("POST", f"/api-connectors/operations/{heat_op_id}/load-preview", {"runtime_params": {}})
        assert heat_preview.get("transform_applied") is True
        assert int(heat_preview.get("transformed_row_count") or 0) >= 24
        heat_run = api("POST", f"/api-connectors/operations/{heat_op_id}/load-run", {"runtime_params": {}})
        assert heat_run.get("status") in ("SUCCESS", "COMPLETED")
        assert int(heat_run.get("inserted_count") or 0) >= 24
        heat_run_2 = api("POST", f"/api-connectors/operations/{heat_op_id}/load-run", {"runtime_params": {}})
        assert int(heat_run_2.get("inserted_count") or 0) == 0
        assert int(heat_run_2.get("updated_count") or 0) >= 0
        unmapped = api(
            "POST",
            f"/api-connectors/operations/{heat_op_id}/load-preview",
            {"runtime_params": {"nd_id": f"UNMAP-{tag}", "nd_name": "미매핑", "bas_ymd": "20260102"}},
        )
        assert len(unmapped.get("unmapped_codes") or []) >= 1
        unmapped_rows = api("GET", "/external-code-mappings/unmapped?source_system=HEAT_DEMAND_API")
        assert isinstance(unmapped_rows, list) and len(unmapped_rows) >= 1
        print("  [ok] heat wide-hour transform + unmapped logging")

        # Scenario D: ASOS / Calendar ingestion
        station_code = f"ST{tag[:4]}"
        api(
            "POST",
            "/weather/observation-stations",
            {"station_code": station_code, "station_name": f"R10S7 관측소 {tag}", "station_type": "ASOS"},
        )
        asos_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"R10S7 ASOS {tag}",
                "endpoint_path": "/sample-external/asos-hourly",
                "response_item_path": "data.items",
                "target_table": asos_table,
            },
        )
        asos_op_id = asos_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/transform-config",
            {"transform_type": "ASOS_HOURLY_TO_CANONICAL", "source_system": "KMA_ASOS_API", "station_unmapped_policy": "WARN_ONLY"},
        )
        api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/params",
            {"params": [{"param_name": "stn_id", "param_location": "QUERY", "param_type": "STRING", "default_value": station_code}]},
        )
        asos_run = api("POST", f"/api-connectors/operations/{asos_op_id}/load-run", {"runtime_params": {}})
        assert asos_run.get("status") in ("SUCCESS", "COMPLETED")
        assert int(psql_scalar(f"SELECT COUNT(*) FROM {asos_table}") or "0") >= 1

        cal_date_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"R10S7 Calendar Date {tag}",
                "endpoint_path": "/sample-external/special-days",
                "response_item_path": "data.items",
                "target_table": cal_date_table,
            },
        )
        cal_date_op_id = cal_date_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{cal_date_op_id}/transform-config",
            {"transform_type": "CALENDAR_SPECIAL_DAY_TO_DATE", "calendar_mode": "FULL_CALENDAR_WITH_OVERLAY", "calendar_year": 2026, "calendar_month": 1},
        )
        cal_date_run = api("POST", f"/api-connectors/operations/{cal_date_op_id}/load-run", {"runtime_params": {}})
        assert cal_date_run.get("status") in ("SUCCESS", "COMPLETED")
        assert int(psql_scalar(f"SELECT COUNT(*) FROM {cal_date_table}") or "0") == 31

        cal_hour_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"R10S7 Calendar Hour {tag}",
                "endpoint_path": "/sample-external/special-days",
                "response_item_path": "data.items",
                "target_table": cal_hour_table,
            },
        )
        cal_hour_op_id = cal_hour_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{cal_hour_op_id}/transform-config",
            {"transform_type": "CALENDAR_DATE_TO_HOUR", "calendar_year": 2026, "calendar_month": 1, "hour_start": 0, "hour_end": 23},
        )
        cal_hour_run = api("POST", f"/api-connectors/operations/{cal_hour_op_id}/load-run", {"runtime_params": {}})
        assert cal_hour_run.get("status") in ("SUCCESS", "COMPLETED")
        assert int(psql_scalar(f"SELECT COUNT(*) FROM {cal_hour_table}") or "0") == 744
        print("  [ok] ASOS/Calendar transforms load-run validated")

        # Scenario E: scheduler run-now/run-due/retry/event
        sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"R10S7 스케줄 {tag}",
                "operation_id": asos_op_id,
                "schedule_type": "HOURLY",
                "run_policy": "LOAD_RUN",
                "load_window_type": "FIXED_OFFSET",
                "window_offset_minutes": 60,
                "runtime_params_template": {"serviceKey": SECRET_TOKEN, "stn_id": station_code},
                "retry_enabled_yn": True,
                "max_retry_count": 1,
                "retry_interval_minutes": 10,
            },
        )
        schedule_id = sched["schedule_id"]
        rendered = api(
            "POST",
            "/data-load-schedules/render-runtime-params",
            {
                "runtime_params_template": {"serviceKey": SECRET_TOKEN, "bas_ymd": "{{today:YYYYMMDD}}"},
                "load_window_type": "FIXED_OFFSET",
                "window_offset_minutes": 30,
            },
        )
        _assert_no_leak(rendered.get("runtime_params_masked"), label="render-runtime-params masked", allow_words=("serviceKey",))
        run_now = api("POST", f"/data-load-schedules/{schedule_id}/run-now", {})
        assert run_now.get("schedule_run_id")
        run_detail = api("GET", f"/data-load-schedule-runs/{run_now['schedule_run_id']}")
        assert run_detail.get("api_load_run_id")
        _assert_no_leak(run_detail.get("runtime_params_masked"), label="schedule run masked", allow_words=("serviceKey",))
        psql_run(
            f"UPDATE tb_data_load_schedule SET next_run_at = NOW() - INTERVAL '1 hour', "
            f"last_run_status = 'SUCCESS' WHERE schedule_id = '{schedule_id}'"
        )
        due = api("GET", "/data-load-schedules/due")
        assert any(x["schedule_id"] == schedule_id for x in due)
        due_result = api("POST", "/data-load-schedules/run-due", {})
        assert int(due_result.get("executed_count") or 0) >= 1
        events = api("GET", f"/data-load-schedules/{schedule_id}/events")
        event_types = {e.get("event_type") for e in events}
        assert "CREATED" in event_types and ("RUN_STARTED" in event_types or "RUN_SUCCEEDED" in event_types)

        fail_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"R10S7 RetryFail {tag}",
                "endpoint_path": "/sample-external/not-found-endpoint",
                "response_item_path": "data.items",
                "target_table": asos_table,
            },
        )
        fail_sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"R10S7 retry {tag}",
                "operation_id": fail_op["operation_id"],
                "schedule_type": "MANUAL",
                "run_policy": "LOAD_RUN",
                "retry_enabled_yn": True,
                "max_retry_count": 1,
            },
        )
        failed = api("POST", f"/data-load-schedules/{fail_sched['schedule_id']}/run-now", {})
        assert failed.get("run_status") == "FAILED"
        retried = api("POST", f"/data-load-schedule-runs/{failed['schedule_run_id']}/retry", {})
        assert retried.get("attempt_no") == 2 and retried.get("run_source") == "RETRY"
        print("  [ok] scheduler run-now/run-due/event/retry validated")

        # Scenario F: forecast provider + prediction summary
        forecast_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"R10S7 Forecast Op {tag}",
                "endpoint_path": "/sample-external/kma-short-forecast",
                "response_item_path": "data.items",
                "response_format": "JSON",
            },
        )
        forecast_op_id = forecast_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{forecast_op_id}/params",
            {
                "params": [
                    {"param_name": "base_date", "param_location": "QUERY", "param_type": "STRING"},
                    {"param_name": "base_time", "param_location": "QUERY", "param_type": "STRING"},
                    {"param_name": "nx", "param_location": "QUERY", "param_type": "STRING"},
                    {"param_name": "ny", "param_location": "QUERY", "param_type": "STRING"},
                ]
            },
        )
        api("PUT", "/forecast-provider/config", {"source_operation_id": forecast_op_id, "provider_name": "R10S7 Forecast"})
        preview = api(
            "POST",
            "/forecast-provider/preview-input",
            {"entity_id": entity_id, "base_date": "20260101", "base_time": "0800", "cache_policy": "REFRESH"},
        )
        assert preview.get("snapshot_id")
        preview_cached = api(
            "POST",
            "/forecast-provider/preview-input",
            {"entity_id": entity_id, "base_date": "20260101", "base_time": "0800", "cache_policy": "USE_CACHE"},
        )
        assert preview_cached.get("cache_hit") is True
        snap = api("GET", f"/forecast-provider/snapshots/{preview['snapshot_id']}")
        _assert_no_leak(snap, label="forecast snapshot", allow_words=("serviceKey",))

        # prediction forecast summary
        models = api("GET", "/models")
        model_version_id = None
        for m in models:
            versions = api("GET", f"/models/{m['model_name']}/versions")
            for v in versions:
                if v.get("model_stage") in ("CHAMPION", "CANDIDATE", "STAGING"):
                    model_version_id = v["model_version_id"]
                    break
            if model_version_id:
                break
        assert model_version_id, "model version is required for integration prediction"
        ds_range = api("GET", f"/feature-sets/{FS_LAG_ROLL_ID}/dataset-range")
        start_at = ds_range["min_target_at"]
        end_at = ds_range["max_target_at"]
        start_dt = datetime.fromisoformat(str(start_at).replace("Z", ""))
        psql_run(
            f"DELETE FROM tb_prediction_actual_match WHERE model_version_id = '{model_version_id}'; "
            f"DELETE FROM tb_heat_demand_prediction WHERE model_version_id = '{model_version_id}' "
            f"AND site_id IN ('SITE-001', 'SITE-002');"
        )
        pred = api(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": FS_LAG_ROLL_ID,
                "model_version_id": model_version_id,
                "start_at": start_at,
                "end_at": end_at,
                "entity_id": entity_id,
                "prediction_horizon": "BATCH",
                "overwrite_yn": True,
                "forecast_provider_enabled": True,
                "forecast_base_date": start_dt.strftime("%Y%m%d"),
                "forecast_base_time": f"{max(2, min(20, start_dt.hour or 8)):02d}00",
                "forecast_cache_policy": "REFRESH",
                "weather_input_required": False,
            },
            timeout=300,
        )
        assert pred.get("status") == "SUCCESS"
        summary = (pred.get("result_summary") or {}).get("forecast_input_summary") or {}
        assert summary.get("enabled") is True
        _assert_no_leak(summary, label="prediction forecast summary", allow_words=("serviceKey",))
        weather_rows = api("GET", f"/prediction-jobs/{pred['job_id']}/weather-inputs")
        assert isinstance(weather_rows, list)
        print("  [ok] forecast preview/cache/prediction integration validated")

        # Route checks
        openapi = fetch_openapi()
        paths = openapi.get("paths", {})
        required_routes = (
            "/api/v1/api-connectors/operations",
            "/api/v1/prediction-entities",
            "/api/v1/external-code-mappings",
            "/api/v1/forecast-provider/config",
            "/api/v1/data-load-schedules",
            "/api/v1/data-load-schedule-runs",
            "/api/v1/prediction-jobs",
            "/api/v1/standard-dataset-types",
        )
        for p in required_routes:
            assert p in paths, f"openapi path missing: {p}"
        print("  [ok] R10 API routes exposed in OpenAPI")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

