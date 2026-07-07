#!/usr/bin/env python3
"""R10-S6 데이터 적재 스케줄러 테스트."""

from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_fixtures import psql_run, psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")
SEED_PATH = _SCRIPTS.parent / "db" / "init" / "02_seed_clean.sql"


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
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if expect_fail:
            return {"http_error": exc.code, "body": exc.read().decode()}
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success") and not expect_fail:
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload.get("data")


def test_time_service_local() -> None:
    from app.services.schedule_time_service import compute_next_run_at, is_schedule_due

    ref = datetime(2026, 6, 24, 10, 30, 0)
    daily = {
        "schedule_type": "DAILY",
        "timezone": "Asia/Seoul",
        "start_at": datetime(2026, 1, 1, 8, 0, 0),
    }
    nxt = compute_next_run_at(daily, from_time=ref)
    assert nxt == datetime(2026, 6, 25, 8, 0, 0)
    hourly = {"schedule_type": "HOURLY", "timezone": "Asia/Seoul", "start_at": datetime(2026, 1, 1, 0, 15, 0)}
    nxt_h = compute_next_run_at(hourly, from_time=ref)
    assert nxt_h == datetime(2026, 6, 24, 11, 15, 0)
    manual = {"schedule_type": "MANUAL", "active_yn": True}
    assert compute_next_run_at(manual, from_time=ref) is None
    assert is_schedule_due(manual, ref) is False
    due_sched = {
        "schedule_type": "HOURLY",
        "active_yn": True,
        "next_run_at": datetime(2026, 6, 24, 9, 0, 0),
        "last_run_status": "SUCCESS",
    }
    assert is_schedule_due(due_sched, ref) is True
    expired = {
        "schedule_type": "DAILY",
        "active_yn": True,
        "end_at": datetime(2026, 6, 24, 0, 0, 0),
    }
    assert is_schedule_due(expired, ref) is False
    print("  [ok] schedule_time_service local")


def test_runtime_template_local() -> None:
    from app.services.runtime_param_template_service import mask_runtime_params, resolve_runtime_params

    now = datetime(2026, 6, 24, 12, 0, 0)
    last_ok = datetime(2026, 6, 23, 8, 0, 0)
    tpl = {
        "bas_ymd": "{{today:YYYYMMDD}}",
        "prev": "{{yesterday:YYYYMMDD}}",
        "ts": "{{now:YYYY-MM-DDTHH:mm:ss}}",
        "serviceKey": "SECRET-KEY-123",
    }
    params = resolve_runtime_params(
        tpl,
        now=now,
        last_success_at=last_ok,
        start_at=datetime(2026, 1, 1),
        load_window_type="LAST_SUCCESS_TO_NOW",
    )
    assert params["bas_ymd"] == "20260624"
    assert params["prev"] == "20260623"
    assert params["ts"] == "2026-06-24T12:00:00"
    assert params["start_at"] == last_ok.isoformat()
    assert params["end_at"] == now.isoformat()
    masked = mask_runtime_params(params)
    blob = json.dumps(masked)
    assert "SECRET-KEY-123" not in blob
    assert "serviceKey" in blob
    print("  [ok] runtime params template + masking")


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


def create_load_run_operation(suffix: str) -> tuple[str, str]:
    station_code = f"ST{suffix[:4]}"
    api(
        "POST",
        "/weather/observation-stations",
        {
            "station_code": station_code,
            "station_name": f"Scheduler test {suffix}",
            "station_type": "ASOS",
        },
    )
    table = f"std_sched_{suffix}"
    code = f"SCHED_{suffix.upper()}"
    ds = api(
        "POST",
        "/standard-dataset-types",
        {
            "dataset_type_code": code,
            "dataset_type_name": f"Scheduler Load {suffix}",
            "target_table": table,
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

    source_id = ensure_rest_source(f"TEST R10-S6 Load {suffix}")
    op = api(
        "POST",
        "/api-connectors/operations",
        {
            "data_source_id": source_id,
            "operation_name": f"TEST scheduler load {suffix}",
            "endpoint_path": "/sample-external/asos-hourly",
            "response_item_path": "data.items",
            "target_table": table,
        },
    )
    op_id = op["operation_id"]
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
    return op_id, table


def main() -> int:
    print(f"THERMOps data load scheduler test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            for tbl in (
                "tb_data_load_schedule",
                "tb_data_load_schedule_run",
                "tb_data_load_schedule_event",
            ):
                count = int(psql_scalar(f"SELECT COUNT(*) FROM {tbl}") or "0")
                assert count == 0, f"{tbl} expected 0 got {count}"
            seed_text = SEED_PATH.read_text(encoding="utf-8").lower()
            assert "tb_data_load_schedule" not in seed_text or "insert into tb_data_load_schedule" not in seed_text
            print("  [ok] clean DB schedule tables empty")
            print("  [ok] operational seed has no schedule samples")
            print("PASS")
            return 0

        test_time_service_local()
        test_runtime_template_local()

        suffix = uuid.uuid4().hex[:8]
        load_op, target_table = create_load_run_operation(suffix)
        print(f"  [ok] fixture operation load={load_op} table={target_table}")

        sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"TEST 일정 {suffix}",
                "schedule_description": "스케줄러 테스트",
                "operation_id": load_op,
                "schedule_type": "DAILY",
                "run_policy": "LOAD_PREVIEW",
                "load_window_type": "NONE",
                "runtime_params_template": {},
                "retry_enabled_yn": True,
                "max_retry_count": 1,
                "retry_interval_minutes": 10,
                "start_at": "2026-06-01T08:00:00",
            },
        )
        schedule_id = sched["schedule_id"]
        assert sched.get("next_run_at")
        print(f"  [ok] schedule created {schedule_id}")

        listed = api("GET", "/data-load-schedules")
        assert any(x["schedule_id"] == schedule_id for x in listed)
        got = api("GET", f"/data-load-schedules/{schedule_id}")
        assert got["schedule_name"] == f"TEST 일정 {suffix}"
        print("  [ok] schedule list/get")

        updated = api(
            "PUT",
            f"/data-load-schedules/{schedule_id}",
            {"schedule_description": "수정됨", "schedule_type": "HOURLY"},
        )
        assert updated["schedule_description"] == "수정됨"
        print("  [ok] schedule update")

        api("POST", f"/data-load-schedules/{schedule_id}/deactivate")
        inactive = api("GET", f"/data-load-schedules/{schedule_id}")
        assert inactive["active_yn"] is False
        api("POST", f"/data-load-schedules/{schedule_id}/activate")
        active = api("GET", f"/data-load-schedules/{schedule_id}")
        assert active["active_yn"] is True
        print("  [ok] activate/deactivate")

        preview_nr = api(
            "POST",
            "/data-load-schedules/preview-next-run",
            {"schedule_type": "DAILY", "start_at": "2026-06-01T08:00:00"},
        )
        assert preview_nr.get("next_run_at")
        print("  [ok] preview-next-run")

        rendered = api(
            "POST",
            "/data-load-schedules/render-runtime-params",
            {
                "runtime_params_template": {"bas_ymd": "{{today:YYYYMMDD}}"},
                "load_window_type": "FIXED_OFFSET",
                "window_offset_minutes": 60,
            },
        )
        assert rendered["runtime_params"]["bas_ymd"]
        assert "runtime_params_masked" in rendered
        print("  [ok] render-runtime-params")

        validation = api("POST", f"/data-load-schedules/{schedule_id}/validate")
        assert validation.get("valid") is True
        print("  [ok] validate schedule")

        manual_sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"TEST manual {suffix}",
                "operation_id": load_op,
                "schedule_type": "MANUAL",
                "run_policy": "LOAD_PREVIEW",
            },
        )
        due_all = api("GET", "/data-load-schedules/due")
        assert not any(x["schedule_id"] == manual_sched["schedule_id"] for x in due_all)
        print("  [ok] MANUAL excluded from due")

        psql_run(
            f"UPDATE tb_data_load_schedule SET next_run_at = NOW() - INTERVAL '2 hours', "
            f"last_run_status = 'SUCCESS' WHERE schedule_id = '{schedule_id}'"
        )
        due = api("GET", "/data-load-schedules/due")
        assert any(x["schedule_id"] == schedule_id for x in due)
        print("  [ok] due schedules query")

        run_now = api("POST", f"/data-load-schedules/{schedule_id}/run-now", {})
        assert run_now["run_status"] in ("SUCCESS", "WARNING")
        assert run_now.get("schedule_run_id")
        blob = json.dumps(run_now)
        assert "SECRET" not in blob.upper() or "MASK" in blob.upper()
        after_sched = api("GET", f"/data-load-schedules/{schedule_id}")
        assert after_sched.get("last_success_at")
        assert after_sched.get("last_run_status") in ("SUCCESS", "WARNING")
        assert after_sched.get("next_run_at")
        print("  [ok] run-now success + schedule status updated")

        load_sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"TEST load-run {suffix}",
                "operation_id": load_op,
                "schedule_type": "HOURLY",
                "run_policy": "LOAD_RUN",
                "runtime_params_template": {},
            },
        )
        load_sid = load_sched["schedule_id"]
        psql_run(
            f"UPDATE tb_data_load_schedule SET next_run_at = NOW() - INTERVAL '1 hour', "
            f"last_run_status = 'SUCCESS' WHERE schedule_id = '{load_sid}'"
        )
        due_result = api("POST", "/data-load-schedules/run-due", {})
        assert due_result.get("executed_count", 0) >= 1
        runs = api("GET", f"/data-load-schedule-runs?schedule_id={load_sid}")
        load_run_row = next(r for r in runs if r.get("run_source") == "RUN_DUE")
        assert load_run_row.get("api_load_run_id")
        assert load_run_row["run_status"] in ("SUCCESS", "WARNING")
        print("  [ok] run-due + api_load_run_id linked")

        events = api("GET", f"/data-load-schedules/{schedule_id}/events")
        assert len(events) >= 2
        event_types = {e["event_type"] for e in events}
        assert "CREATED" in event_types
        assert "RUN_STARTED" in event_types or "RUN_SUCCEEDED" in event_types
        print("  [ok] schedule events recorded")

        fail_source = ensure_rest_source(f"TEST R10-S6 Fail {suffix}")
        fail_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": fail_source,
                "operation_name": f"TEST fail {suffix}",
                "endpoint_path": "/sample-external/not-found-endpoint",
                "response_item_path": "data.items",
                "target_table": target_table,
            },
        )
        fail_sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"TEST fail sched {suffix}",
                "operation_id": fail_op["operation_id"],
                "schedule_type": "MANUAL",
                "run_policy": "LOAD_RUN",
                "retry_enabled_yn": True,
                "max_retry_count": 1,
            },
        )
        fail_run = api("POST", f"/data-load-schedules/{fail_sched['schedule_id']}/run-now", {})
        assert fail_run["run_status"] == "FAILED"
        assert fail_run.get("error_message")
        fail_runs = api("GET", f"/data-load-schedule-runs?schedule_id={fail_sched['schedule_id']}")
        failed_row = next(r for r in fail_runs if r["schedule_run_id"] == fail_run["schedule_run_id"])
        assert failed_row["run_status"] == "FAILED"
        assert failed_row.get("error_message")
        fail_sched_after = api("GET", f"/data-load-schedules/{fail_sched['schedule_id']}")
        assert fail_sched_after.get("last_failure_at")
        print("  [ok] failure recorded")

        retry = api("POST", f"/data-load-schedule-runs/{failed_row['schedule_run_id']}/retry", {})
        assert retry["attempt_no"] == 2
        assert retry["run_source"] == "RETRY"
        print("  [ok] retry API")

        api("POST", f"/data-load-schedules/{schedule_id}/deactivate")
        psql_run(
            f"UPDATE tb_data_load_schedule SET next_run_at = NOW() - INTERVAL '1 hour' "
            f"WHERE schedule_id = '{schedule_id}'"
        )
        due_inactive = api("GET", "/data-load-schedules/due")
        assert not any(x["schedule_id"] == schedule_id for x in due_inactive)
        print("  [ok] inactive excluded from due")

        end_sched = api(
            "POST",
            "/data-load-schedules",
            {
                "schedule_name": f"TEST ended {suffix}",
                "operation_id": load_op,
                "schedule_type": "HOURLY",
                "run_policy": "LOAD_PREVIEW",
                "end_at": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )
        assert not any(x["schedule_id"] == end_sched["schedule_id"] for x in api("GET", "/data-load-schedules/due"))
        print("  [ok] end_at past excluded from due")

        api("POST", f"/data-load-schedules/{schedule_id}/archive", {})
        archived = api("GET", f"/data-load-schedules/{schedule_id}")
        assert archived.get("metadata_json", {}).get("archived_at")
        print("  [ok] archive")

        run_detail = api("GET", f"/data-load-schedule-runs/{run_now['schedule_run_id']}")
        assert run_detail["schedule_run_id"] == run_now["schedule_run_id"]
        print("  [ok] schedule run detail")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
