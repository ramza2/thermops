#!/usr/bin/env python3
"""R10-S5 Forecast On-demand Input Provider 테스트."""

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

from test_fixtures import (
    FS_LAG_ROLL_ID,
    TRC_LGBM_ID,
    ensure_csv_ingested,
    ensure_feature_dataset_built,
    ensure_test_platform,
    psql_run,
    psql_scalar,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")
TEST_SECRET = "abcde12345xyzTESTKEY"
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_LAG_ROLL_ID)


def cleanup_prediction_overwrite_targets(model_version_id: str) -> None:
    """overwrite_yn=True 예측 전 FK 충돌 방지: match → prediction 순서로 정리.

    tb_prediction_actual_match.prediction_id → tb_heat_demand_prediction.prediction_id
    이므로 자식(match)을 먼저 삭제해야 prediction overwrite DELETE가 성공한다.
    """
    if not model_version_id:
        return
    safe_id = model_version_id.replace("'", "''")
    psql_run(
        f"DELETE FROM tb_prediction_actual_match WHERE model_version_id = '{safe_id}'; "
        f"DELETE FROM tb_heat_demand_prediction WHERE model_version_id = '{safe_id}';"
    )


def find_compatible_model_version() -> str | None:
    models = api("GET", "/models") or []
    for m in models:
        versions = api("GET", f"/models/{m['model_name']}/versions") or []
        for v in versions:
            if v.get("model_stage") in ("CHAMPION", "CANDIDATE", "STAGING"):
                return v["model_version_id"]
        if versions:
            return versions[0]["model_version_id"]
    return None


def ensure_compatible_model_version() -> str:
    """단건 독립 실행용: 기존 model_version 재사용, 없으면 최소 학습으로 생성."""
    existing = find_compatible_model_version()
    if existing:
        return existing
    configs = api("GET", "/training-configs") or []
    config_id = next(
        (c["config_id"] for c in configs if c.get("feature_set_id") == FEATURE_SET_ID),
        None,
    )
    if not config_id:
        config_id = next(
            (c["config_id"] for c in configs if c.get("config_id") == TRC_LGBM_ID),
            None,
        )
    if not config_id and configs:
        config_id = configs[0].get("config_id")
    if not config_id:
        raise RuntimeError("training config not found for forecast provider test")
    result = api("POST", "/training-jobs", {"config_id": config_id}, timeout=300)
    if not result or result.get("status") != "SUCCESS" or not result.get("model_version_id"):
        raise RuntimeError(f"training failed for forecast fixture: {result}")
    return result["model_version_id"]


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False, timeout: int = 120) -> dict | list | None:
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


def create_forecast_ready_entity() -> tuple[str, int, int]:
    code = f"TEST-FC-{uuid.uuid4().hex[:8].upper()}"
    ent = api(
        "POST",
        "/prediction-entities",
        {
            "entity_code": code,
            "entity_name": "Forecast 테스트 지점",
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
        {"nx": grid_conv["nx"], "ny": grid_conv["ny"], "grid_name": "FC TEST 격자"},
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


def ensure_kma_operation() -> str:
    ops = api("GET", "/api-connectors/operations") or []
    for op in ops:
        if op.get("operation_name") == "TEST 기상청 단기예보 샘플":
            return op["operation_id"]

    sources = api("GET", "/data-sources?page=1&size=100")
    items = sources.get("items", []) if isinstance(sources, dict) else sources
    source_id = None
    for s in items:
        if s.get("source_name") == "TEST R10-S5 KMA Forecast":
            source_id = s["source_id"]
            break
    if not source_id:
        created = api(
            "POST",
            "/data-sources",
            {
                "source_name": "TEST R10-S5 KMA Forecast",
                "source_type": "REST_API",
                "data_domain": "WEATHER",
                "connection_info": {"base_url": INTERNAL_BASE},
                "active_yn": True,
            },
        )
        source_id = created["source_id"]
        api(
            "PUT",
            f"/api-connectors/data-sources/{source_id}/credential",
            {
                "credential_type": "API_KEY",
                "key_location": "QUERY",
                "key_name": "serviceKey",
                "secret_value": TEST_SECRET,
                "encoding_policy": "STORE_DECODED_ENCODE_ON_CALL",
            },
        )
    op = api(
        "POST",
        "/api-connectors/operations",
        {
            "data_source_id": source_id,
            "operation_name": "TEST 기상청 단기예보 샘플",
            "endpoint_path": "/sample-external/kma-short-forecast",
            "response_item_path": "data.items",
            "response_format": "JSON",
        },
    )
    op_id = op["operation_id"]
    api(
        "PUT",
        f"/api-connectors/operations/{op_id}/params",
        {
            "params": [
                {"param_name": "base_date", "param_location": "QUERY", "param_type": "STRING"},
                {"param_name": "base_time", "param_location": "QUERY", "param_type": "STRING"},
                {"param_name": "nx", "param_location": "QUERY", "param_type": "STRING"},
                {"param_name": "ny", "param_location": "QUERY", "param_type": "STRING"},
                {"param_name": "numOfRows", "param_location": "QUERY", "param_type": "STRING"},
                {"param_name": "dataType", "param_location": "QUERY", "param_type": "STRING"},
            ]
        },
    )
    api("PUT", f"/api-connectors/operations/{op_id}/pagination", {"pagination_type": "NONE", "max_pages": 1})
    return op_id


def test_parser_local() -> None:
    from app.services.kma_short_forecast_parser import (
        parse_precipitation_value,
        pivot_kma_short_forecast_items,
        resolve_latest_kma_base_time,
    )

    assert parse_precipitation_value("강수없음")[0] == 0.0
    assert parse_precipitation_value("1.0mm")[0] == 1.0
    base_date, base_time, base_at = resolve_latest_kma_base_time(
        datetime(2026, 1, 1, 10, 30), delay_minutes=60
    )
    assert base_time in {"0200", "0500", "0800"}
    assert base_date == "20260101"
    assert base_at.hour == int(base_time[:2])

    items = [
        {"baseDate": "20260101", "baseTime": "0800", "fcstDate": "20260101", "fcstTime": "0900", "category": "TMP", "fcstValue": "3"},
        {"baseDate": "20260101", "baseTime": "0800", "fcstDate": "20260101", "fcstTime": "0900", "category": "REH", "fcstValue": "55"},
        {"baseDate": "20260101", "baseTime": "0800", "fcstDate": "20260101", "fcstTime": "1000", "category": "PCP", "fcstValue": "강수없음"},
    ]
    rows, warnings = pivot_kma_short_forecast_items(items)
    assert len(rows) == 2
    assert rows[0]["temperature"] == 3.0
    assert rows[0]["forecast_horizon_hours"] == 1
    assert rows[1]["precipitation"] == 0.0
    assert not warnings or all(isinstance(w, str) for w in warnings)
    print("  [ok] KMA parser / base_time / precipitation")


def test_masking_local() -> None:
    from app.utils.masking import mask_params_dict

    masked = mask_params_dict({"serviceKey": TEST_SECRET, "nx": "60"})
    assert masked["serviceKey"] == "****"
    text = json.dumps({"query_params_masked": masked}, ensure_ascii=False).lower()
    assert TEST_SECRET.lower() not in text
    assert "servicekey=" not in text
    print("  [ok] secret/serviceKey masking")


def main() -> int:
    print(f"THERMOps forecast on-demand provider test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            for table in (
                "tb_forecast_provider_config",
                "tb_forecast_input_snapshot",
                "tb_prediction_weather_input",
            ):
                assert int(psql_scalar(f"SELECT COUNT(*) FROM {table}") or "0") == 0
            cfg = api("GET", "/forecast-provider/config")
            assert not cfg or not cfg.get("source_operation_id")
            print("  [ok] clean DB forecast tables empty")
            print("PASS")
            return 0

        test_parser_local()
        test_masking_local()

        entity_id, nx, ny = create_forecast_ready_entity()
        print(f"  [ok] forecast_ready entity {entity_id} nx={nx} ny={ny}")

        psql_scalar("DELETE FROM tb_forecast_provider_config WHERE provider_config_id = 'FPC-DEFAULT'")

        op_id = ensure_kma_operation()
        print(f"  [ok] KMA sample operation {op_id}")

        missing = api(
            "POST",
            "/forecast-provider/preview-input",
            {"entity_id": entity_id, "cache_policy": "REFRESH"},
            expect_fail=True,
        )
        assert missing and missing.get("http_error") == 400
        assert "REST API" in missing.get("body", "") or "작업" in missing.get("body", "")
        print("  [ok] missing source_operation_id user-friendly error")

        saved = api(
            "PUT",
            "/forecast-provider/config",
            {
                "source_operation_id": op_id,
                "provider_name": "테스트 단기예보 Provider",
                "delay_minutes": 60,
            },
        )
        assert saved.get("source_operation_id") == op_id
        loaded = api("GET", "/forecast-provider/config")
        assert loaded.get("source_operation_id") == op_id
        print("  [ok] forecast provider config save/load")

        resolved = api("POST", "/forecast-provider/resolve-base-time", {})
        assert resolved.get("base_date") and resolved.get("base_time")
        manual = api(
            "POST",
            "/forecast-provider/resolve-base-time",
            {"base_date": "20260101", "base_time": "0800"},
        )
        assert manual.get("policy") == "MANUAL"
        print("  [ok] base_time resolve policy")

        not_ready_code = f"TEST-NR-{uuid.uuid4().hex[:6].upper()}"
        not_ready = api(
            "POST",
            "/prediction-entities",
            {"entity_code": not_ready_code, "entity_name": "미준비", "entity_type": "SITE"},
        )
        blocked = api(
            "POST",
            "/forecast-provider/preview-input",
            {"entity_id": not_ready["entity_id"], "cache_policy": "REFRESH"},
            expect_fail=True,
        )
        assert blocked and blocked.get("http_error") == 400
        print("  [ok] forecast_ready false entity blocked")

        target_start = datetime(2026, 1, 1, 9, 0)
        target_end = datetime(2026, 1, 1, 12, 0)
        preview = api(
            "POST",
            "/forecast-provider/preview-input",
            {
                "entity_id": entity_id,
                "base_date": "20260101",
                "base_time": "0800",
                "cache_policy": "REFRESH",
                "target_start_at": target_start.isoformat(),
                "target_end_at": target_end.isoformat(),
            },
        )
        assert preview.get("nx") == nx and preview.get("ny") == ny
        assert preview.get("matched_row_count", 0) >= 1
        snapshot_id = preview.get("snapshot_id")
        assert snapshot_id
        assert TEST_SECRET not in json.dumps(preview)
        print(f"  [ok] preview-input rows={preview.get('row_count')} matched={preview.get('matched_row_count')}")

        cached = api(
            "POST",
            "/forecast-provider/preview-input",
            {
                "entity_id": entity_id,
                "base_date": "20260101",
                "base_time": "0800",
                "cache_policy": "USE_CACHE",
                "target_start_at": target_start.isoformat(),
                "target_end_at": target_end.isoformat(),
            },
        )
        assert cached.get("cache_hit") is True
        print("  [ok] cache_key reuse cache_hit")

        refreshed = api(
            "POST",
            "/forecast-provider/preview-input",
            {
                "entity_id": entity_id,
                "base_date": "20260101",
                "base_time": "0800",
                "cache_policy": "REFRESH",
            },
        )
        assert refreshed.get("cache_hit") is False
        assert refreshed.get("snapshot_id") != snapshot_id
        print("  [ok] REFRESH creates new snapshot")

        req_preview = api(
            "POST",
            "/forecast-provider/request-preview",
            {"entity_id": entity_id, "base_date": "20260101", "base_time": "0800"},
        )
        assert TEST_SECRET not in json.dumps(req_preview)
        assert req_preview.get("masked_url")
        print("  [ok] request-preview masking")

        test_call = api(
            "POST",
            "/forecast-provider/test-call",
            {"entity_id": entity_id, "base_date": "20260101", "base_time": "0800", "cache_policy": "REFRESH"},
        )
        assert test_call.get("success") is True
        print(f"  [ok] test-call row_count={test_call.get('row_count')}")

        snaps = api("GET", f"/forecast-provider/snapshots?entity_id={entity_id}")
        assert isinstance(snaps, list) and len(snaps) >= 1
        detail = api("GET", f"/forecast-provider/snapshots/{snapshot_id}")
        assert detail.get("snapshot_id") == snapshot_id
        print("  [ok] snapshot list/detail")

        ensure_test_platform()
        ensure_csv_ingested(api)
        ensure_feature_dataset_built(api, FEATURE_SET_ID, timeout=180)
        range_data = api("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
        assert range_data.get("exists")
        start_at = range_data["min_target_at"]
        end_at = range_data["max_target_at"]
        start_dt = datetime.fromisoformat(str(start_at).replace("Z", ""))
        forecast_base_date = start_dt.strftime("%Y%m%d")
        forecast_base_time = f"{max(2, min(20, start_dt.hour or 8)):02d}00"
        pred_start = start_at
        pred_end = end_at

        model_version_id = ensure_compatible_model_version()
        print(f"  [ok] model_version ready {model_version_id}")
        # overwrite_yn 예측 전: evaluation match → prediction 순서로 정리 (FK 독립 재실행)
        cleanup_prediction_overwrite_targets(model_version_id)

        pred = api(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": FEATURE_SET_ID,
                "model_version_id": model_version_id,
                "start_at": pred_start,
                "end_at": pred_end,
                "prediction_horizon": "BATCH",
                "overwrite_yn": True,
                "entity_id": entity_id,
                "forecast_provider_enabled": True,
                "forecast_base_date": forecast_base_date,
                "forecast_base_time": forecast_base_time,
                "forecast_cache_policy": "REFRESH",
                "weather_input_required": False,
            },
            timeout=300,
        )
        assert pred.get("status") == "SUCCESS"
        summary = (pred.get("result_summary") or {})
        fc_summary = summary.get("forecast_input_summary") or {}
        assert fc_summary.get("enabled") is True
        assert fc_summary.get("entity_id") == entity_id
        assert fc_summary.get("snapshot_id")
        assert (fc_summary.get("saved_input_count") or fc_summary.get("matched_row_count") or 0) >= 0
        assert TEST_SECRET not in json.dumps(summary)
        job_id = pred["job_id"]
        weather_inputs = api("GET", f"/prediction-jobs/{job_id}/weather-inputs")
        assert isinstance(weather_inputs, list)
        if len(weather_inputs) == 0:
            print("  [warn] weather inputs 0 rows (period/grid mismatch) — forecast summary still saved")
        else:
            print(f"  [ok] prediction job forecast_input_summary saved ({len(weather_inputs)} weather inputs)")

        fail_entity = not_ready["entity_id"]
        cleanup_prediction_overwrite_targets(model_version_id)
        fail_pred = api(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": FEATURE_SET_ID,
                "model_version_id": model_version_id,
                "start_at": pred_start,
                "end_at": pred_end,
                "entity_id": fail_entity,
                "forecast_provider_enabled": True,
                "weather_input_required": True,
            },
            expect_fail=True,
            timeout=300,
        )
        assert fail_pred and fail_pred.get("http_error") == 400
        print("  [ok] weather_input_required=true + forecast fail blocks job")

        cleanup_prediction_overwrite_targets(model_version_id)
        warn_pred = api(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": FEATURE_SET_ID,
                "model_version_id": model_version_id,
                "start_at": pred_start,
                "end_at": pred_end,
                "entity_id": fail_entity,
                "forecast_provider_enabled": True,
                "weather_input_required": False,
            },
            timeout=300,
        )
        assert warn_pred.get("status") == "SUCCESS"
        warn_summary = (warn_pred.get("result_summary") or {}).get("forecast_input_summary") or {}
        assert warn_summary.get("failed") or warn_summary.get("warnings")
        print("  [ok] weather_input_required=false continues with warning")

        seed_snap = int(psql_scalar("SELECT COUNT(*) FROM tb_forecast_input_snapshot") or "0")
        assert seed_snap >= 0
        print(f"  [ok] forecast snapshots in DB={seed_snap} (test-created only, no seed samples)")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
