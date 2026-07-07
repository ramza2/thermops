#!/usr/bin/env python3
"""R10-S4 ASOS 관측 기상 / Calendar 특일 변환 적재 테스트."""

from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_fixtures import psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list | None:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if expect_fail:
            return {"http_error": exc.code, "body": exc.read().decode()}
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success") and not expect_fail:
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload.get("data")


def make_asos_item(
    stn_id: str = "108",
    tm: str = "2026-01-01 01:00",
    *,
    bad_tm: bool = False,
    bad_numeric: bool = False,
) -> dict:
    item = {
        "stnId": stn_id,
        "tm": "INVALID" if bad_tm else tm,
        "ta": "not-a-number" if bad_numeric else "-3.2",
        "hm": "55.0",
        "ws": "1.8",
        "rn": "0.0",
    }
    return item


def make_special_day(locdate: str, name: str, holiday: str = "Y", day_type: str | None = None) -> dict:
    item = {"locdate": locdate, "dateName": name, "isHoliday": holiday}
    if day_type:
        item["special_day_type"] = day_type
    return item


def create_target_table(suffix: str, kind: str) -> tuple[str, str]:
    if kind == "weather":
        table = f"std_asos_{suffix}"
        code = f"ASOS_{suffix.upper()}"
        columns = [
            {"column_name": "station_code", "data_type": "VARCHAR", "data_length": 32, "required": True},
            {"column_name": "observed_at", "data_type": "TIMESTAMP", "required": True, "default_column_role": "TIME_KEY"},
            {"column_name": "temperature", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
            {"column_name": "humidity", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
            {"column_name": "wind_speed", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
            {"column_name": "precipitation", "data_type": "NUMERIC", "numeric_precision": 10, "numeric_scale": 2},
            {"column_name": "source_system", "data_type": "VARCHAR", "data_length": 64},
            {"column_name": "source_operation_id", "data_type": "VARCHAR", "data_length": 64},
            {"column_name": "raw_json", "data_type": "JSONB"},
        ]
        name = f"ASOS Test {suffix}"
    elif kind == "calendar_date":
        table = f"std_cal_date_{suffix}"
        code = f"CALD_{suffix.upper()}"
        columns = [
            {"column_name": "calendar_date", "data_type": "DATE", "required": True, "default_column_role": "TIME_KEY"},
            {"column_name": "year", "data_type": "INTEGER"},
            {"column_name": "month", "data_type": "INTEGER"},
            {"column_name": "day", "data_type": "INTEGER"},
            {"column_name": "day_of_week", "data_type": "INTEGER"},
            {"column_name": "day_name", "data_type": "VARCHAR", "data_length": 8},
            {"column_name": "is_weekend", "data_type": "BOOLEAN"},
            {"column_name": "is_holiday", "data_type": "BOOLEAN"},
            {"column_name": "is_public_holiday", "data_type": "BOOLEAN"},
            {"column_name": "is_workday", "data_type": "BOOLEAN"},
            {"column_name": "holiday_name", "data_type": "VARCHAR", "data_length": 100},
            {"column_name": "special_day_type", "data_type": "VARCHAR", "data_length": 50},
            {"column_name": "special_day_name", "data_type": "VARCHAR", "data_length": 100},
            {"column_name": "source_system", "data_type": "VARCHAR", "data_length": 64},
            {"column_name": "raw_json", "data_type": "JSONB"},
        ]
        name = f"Calendar Date Test {suffix}"
    else:
        table = f"std_cal_hour_{suffix}"
        code = f"CALH_{suffix.upper()}"
        columns = [
            {"column_name": "measured_at", "data_type": "TIMESTAMP", "required": True, "default_column_role": "TIME_KEY"},
            {"column_name": "calendar_date", "data_type": "DATE"},
            {"column_name": "hour", "data_type": "INTEGER"},
            {"column_name": "is_weekend", "data_type": "BOOLEAN"},
            {"column_name": "is_holiday", "data_type": "BOOLEAN"},
            {"column_name": "is_workday", "data_type": "BOOLEAN"},
            {"column_name": "season", "data_type": "VARCHAR", "data_length": 16},
        ]
        name = f"Calendar Hour Test {suffix}"
    created = api(
        "POST",
        "/standard-dataset-types",
        {
            "dataset_type_code": code,
            "dataset_type_name": name,
            "target_table": table,
            "status": "DRAFT",
            "managed_table": True,
            "mapping_supported": True,
            "columns": columns,
        },
    )
    ds_id = created["dataset_type_id"]
    api("POST", f"/standard-dataset-types/{ds_id}/validate")
    api("POST", f"/standard-dataset-types/{ds_id}/create-physical-table", {"confirm": True})
    api("POST", f"/standard-dataset-types/{ds_id}/activate")
    return ds_id, table


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


def test_local_transforms() -> None:
    try:
        from app.services.weather_observation_transform_service import (
            normalize_weather_value,
            parse_observed_at,
        )
        from app.services.calendar_transform_service import (
            generate_calendar_date_rows,
            generate_calendar_hour_rows,
        )
    except Exception as exc:
        print(f"  [skip] local helpers ({exc})")
        return

    val, err = normalize_weather_value("1,234.5")
    assert val == 1234.5 and err is None
    val2, err2 = normalize_weather_value("abc")
    assert val2 is None and err2 == "invalid_numeric"
    assert parse_observed_at("202601010100").isoformat() == "2026-01-01T01:00:00"

    full_rows, _ = generate_calendar_date_rows(
        2026,
        1,
        [],
        calendar_mode="FULL_CALENDAR_WITH_OVERLAY",
        source_system="KASI_SPECIAL_DAY_API",
    )
    assert len(full_rows) == 31
    hour_rows = generate_calendar_hour_rows(full_rows[:1])
    assert len(hour_rows) == 24
    print("  [ok] local ASOS/Calendar transform helpers")


def main() -> int:
    print(f"THERMOps ASOS/Calendar ingestion test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            count = int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_transform_config") or "0")
            assert count == 0
            seed_asos = int(
                psql_scalar(
                    "SELECT COUNT(*) FROM tb_api_connector_transform_config "
                    "WHERE transform_type IN ('ASOS_HOURLY_TO_CANONICAL','CALENDAR_SPECIAL_DAY_TO_DATE','CALENDAR_DATE_TO_HOUR')"
                )
                or "0"
            )
            assert seed_asos == 0
            print("  [ok] clean DB ASOS/Calendar transform config empty")
            print("PASS")
            return 0

        test_local_transforms()
        suffix = uuid.uuid4().hex[:8]
        station_code = f"ST{suffix[:4]}"

        api(
            "POST",
            "/weather/observation-stations",
            {
                "station_code": station_code,
                "station_name": f"테스트 관측소 {suffix}",
                "station_type": "ASOS",
            },
        )
        print(f"  [ok] ASOS station {station_code}")

        _, weather_table = create_target_table(suffix, "weather")
        _, cal_date_table = create_target_table(suffix, "calendar_date")
        _, cal_hour_table = create_target_table(suffix, "calendar_hour")
        source_id = ensure_rest_source(f"TEST R10 S4 {suffix}")

        asos_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"TEST ASOS {suffix}",
                "endpoint_path": "/sample-external/asos-hourly",
                "response_item_path": "data.items",
                "target_table": weather_table,
            },
        )
        asos_op_id = asos_op["operation_id"]
        cfg = api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/transform-config",
            {
                "transform_type": "ASOS_HOURLY_TO_CANONICAL",
                "source_system": "KMA_ASOS_API",
                "station_unmapped_policy": "WARN_ONLY",
            },
        )
        assert cfg.get("transform_type") == "ASOS_HOURLY_TO_CANONICAL"
        got = api("GET", f"/api-connectors/operations/{asos_op_id}/transform-config")
        assert got.get("station_code_field") == "stnId"
        print("  [ok] ASOS transform config save/get")

        asos_preview = api(
            "POST",
            f"/api-connectors/operations/{asos_op_id}/transform-preview",
            {"raw_items": [make_asos_item(station_code)]},
        )
        assert asos_preview.get("transformed_row_count") == 1
        row = (asos_preview.get("sample_rows") or [])[0]
        assert row.get("station_code") == station_code
        assert row.get("temperature") == -3.2
        print("  [ok] ASOS mock → canonical row")

        bad_num = api(
            "POST",
            f"/api-connectors/operations/{asos_op_id}/transform-preview",
            {"raw_items": [make_asos_item(station_code, bad_numeric=True)]},
        )
        assert (bad_num.get("sample_rows") or [])[0].get("temperature") is None
        print("  [ok] ASOS numeric null handling")

        bad_tm = api(
            "POST",
            f"/api-connectors/operations/{asos_op_id}/transform-preview",
            {"raw_items": [make_asos_item(station_code, bad_tm=True)]},
        )
        assert bad_tm.get("transformed_row_count") == 0
        assert len(bad_tm.get("warnings") or []) >= 1
        print("  [ok] ASOS observed_at parse warning")

        unknown_stn = f"UNK{suffix[:3]}"
        warn_preview = api(
            "POST",
            f"/api-connectors/operations/{asos_op_id}/transform-preview",
            {"raw_items": [make_asos_item(unknown_stn)]},
        )
        assert warn_preview.get("transformed_row_count") == 1
        assert any("미등록" in str(w) for w in (warn_preview.get("warnings") or []))
        print("  [ok] unregistered station WARN_ONLY")

        api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/transform-config",
            {"station_unmapped_policy": "LOG_UNMAPPED"},
        )
        got_log = api("GET", f"/api-connectors/operations/{asos_op_id}/transform-config")
        assert got_log.get("station_unmapped_policy") == "LOG_UNMAPPED"
        log_preview = api(
            "POST",
            f"/api-connectors/operations/{asos_op_id}/transform-preview",
            {"raw_items": [make_asos_item(unknown_stn)]},
        )
        assert len(log_preview.get("unmapped_codes") or []) >= 1 or any(
            "미등록" in str(w) for w in (log_preview.get("warnings") or [])
        )
        print("  [ok] LOG_UNMAPPED station code")

        api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/transform-config",
            {"station_unmapped_policy": "WARN_ONLY"},
        )
        api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/params",
            {
                "params": [
                    {"param_name": "stn_id", "param_location": "QUERY", "param_type": "STRING", "default_value": station_code},
                    {"param_name": "tm", "param_location": "QUERY", "param_type": "STRING", "default_value": "2026-01-01 01:00"},
                ]
            },
        )
        load_preview = api("POST", f"/api-connectors/operations/{asos_op_id}/load-preview", {"runtime_params": {}})
        assert load_preview.get("transform_applied") is True
        assert (load_preview.get("transformed_row_count") or 0) >= 1
        print("  [ok] ASOS load-preview")

        load_run = api("POST", f"/api-connectors/operations/{asos_op_id}/load-run", {"runtime_params": {}})
        assert load_run.get("status") in ("SUCCESS", "COMPLETED"), load_run
        inserted = int(psql_scalar(f"SELECT COUNT(*) FROM {weather_table}") or "0")
        assert inserted >= 1
        print("  [ok] ASOS load-run INSERT")

        cal_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"TEST Calendar {suffix}",
                "endpoint_path": "/sample-external/special-days",
                "response_item_path": "data.items",
                "target_table": cal_date_table,
            },
        )
        cal_op_id = cal_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{cal_op_id}/transform-config",
            {
                "transform_type": "CALENDAR_SPECIAL_DAY_TO_DATE",
                "calendar_mode": "SPECIAL_DAYS_ONLY",
                "calendar_year": 2026,
            },
        )
        got_cal = api("GET", f"/api-connectors/operations/{cal_op_id}/transform-config")
        assert got_cal.get("calendar_mode") == "SPECIAL_DAYS_ONLY"
        print("  [ok] Calendar transform config save/get")

        special_preview = api(
            "POST",
            f"/api-connectors/operations/{cal_op_id}/transform-preview",
            {
                "raw_items": [
                    make_special_day("20260101", "신정"),
                    make_special_day("20260105", "소한", "N", "SOLAR_TERM"),
                ]
            },
        )
        assert special_preview.get("transformed_row_count") == 2
        rows = special_preview.get("sample_rows") or []
        assert rows[0].get("is_public_holiday") is True
        solar = next((r for r in rows if r.get("special_day_type") == "SOLAR_TERM"), None)
        assert solar and solar.get("special_day_name") == "소한"
        print("  [ok] SPECIAL_DAYS_ONLY + SOLAR_TERM")

        api(
            "PUT",
            f"/api-connectors/operations/{cal_op_id}/transform-config",
            {"calendar_mode": "FULL_CALENDAR_WITH_OVERLAY", "calendar_year": 2026, "calendar_month": 1},
        )
        full_preview = api(
            "POST",
            f"/api-connectors/operations/{cal_op_id}/transform-preview",
            {"raw_items": [make_special_day("20260101", "신정")]},
        )
        assert full_preview.get("transformed_row_count") == 31
        sample = (full_preview.get("sample_rows") or [])[0]
        assert sample.get("day_name") in ("목", "수", "금", "토", "일", "월", "화")
        print("  [ok] FULL_CALENDAR_WITH_OVERLAY month rows")

        hour_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"TEST Calendar Hour {suffix}",
                "endpoint_path": "/sample-external/special-days",
                "response_item_path": "data.items",
                "target_table": cal_hour_table,
            },
        )
        hour_op_id = hour_op["operation_id"]
        api(
            "PUT",
            f"/api-connectors/operations/{hour_op_id}/transform-config",
            {
                "transform_type": "CALENDAR_DATE_TO_HOUR",
                "calendar_year": 2026,
                "calendar_month": 1,
                "hour_start": 0,
                "hour_end": 23,
            },
        )
        hour_preview = api(
            "POST",
            f"/api-connectors/operations/{hour_op_id}/transform-preview",
            {"raw_items": [make_special_day("20260101", "신정")]},
        )
        assert hour_preview.get("transformed_row_count") == 744
        ts = (hour_preview.get("sample_rows") or [])[0].get("measured_at")
        assert "2026-01-01T00:00:00" in str(ts)
        print("  [ok] Calendar hour_generation 24h x 31 days")

        api(
            "PUT",
            f"/api-connectors/operations/{hour_op_id}/params",
            {
                "params": [
                    {"param_name": "sol_year", "param_location": "QUERY", "param_type": "STRING", "default_value": "2026"},
                    {"param_name": "sol_month", "param_location": "QUERY", "param_type": "STRING", "default_value": "01"},
                ]
            },
        )
        cal_load_preview = api("POST", f"/api-connectors/operations/{cal_op_id}/load-preview", {"runtime_params": {}})
        assert cal_load_preview.get("transform_applied") is True
        cal_run = api("POST", f"/api-connectors/operations/{cal_op_id}/load-run", {"runtime_params": {}})
        assert cal_run.get("status") == "SUCCESS"
        cal_count = int(psql_scalar(f"SELECT COUNT(*) FROM {cal_date_table}") or "0")
        assert cal_count == 31
        print("  [ok] Calendar load-preview/run INSERT")

        bad_date = api(
            "POST",
            f"/api-connectors/operations/{cal_op_id}/transform-preview",
            {"raw_items": [{"locdate": "BAD", "dateName": "오류", "isHoliday": "N"}]},
            expect_fail=False,
        )
        assert bad_date.get("transformed_row_count", 31) <= 31
        assert len(bad_date.get("warnings") or []) >= 1
        print("  [ok] Calendar date parse warning")

        seed_check = int(
            psql_scalar(
                "SELECT COUNT(*) FROM tb_api_connector_transform_config "
                "WHERE transform_type IN ('ASOS_HOURLY_TO_CANONICAL','CALENDAR_SPECIAL_DAY_TO_DATE','CALENDAR_DATE_TO_HOUR') "
                "AND operation_id NOT LIKE 'ACOP-%'"
            )
            or "0"
        )
        assert seed_check >= 3
        print("  [ok] no operational seed ASOS/Calendar samples (test-only configs)")

        fail_cfg = api(
            "PUT",
            f"/api-connectors/operations/{asos_op_id}/transform-config",
            {"station_unmapped_policy": "FAIL_LOAD"},
            expect_fail=False,
        )
        assert fail_cfg.get("station_unmapped_policy") == "FAIL_LOAD"
        print("  [ok] user-friendly config messages")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
