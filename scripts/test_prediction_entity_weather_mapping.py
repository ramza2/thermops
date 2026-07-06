#!/usr/bin/env python3
"""R10-S1 Prediction Entity / Location / Weather Mapping 테스트."""

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


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | None:
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


def test_kma_grid_local() -> None:
    from app.utils.kma_grid import latlon_to_kma_grid, validate_latlon

    validate_latlon(37.5665, 126.9780)
    result = latlon_to_kma_grid(37.5665, 126.9780)
    assert "nx" in result and "ny" in result
    print(f"  [ok] latlon_to_kma_grid nx={result['nx']} ny={result['ny']}")


def main() -> int:
    print(f"THERMOps prediction entity weather mapping test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            tables = [
                "tb_prediction_entity",
                "tb_prediction_entity_location",
                "tb_weather_forecast_grid",
                "tb_weather_observation_station",
                "tb_prediction_entity_weather_mapping",
            ]
            for t in tables:
                assert int(psql_scalar(f"SELECT COUNT(*) FROM {t}") or "0") == 0
            assert len(api("GET", "/prediction-entities") or []) == 0
            print("  [ok] clean DB prediction entity tables empty")
            print("PASS")
            return 0

        test_kma_grid_local()

        ops = api("GET", "/prediction-entities")
        assert isinstance(ops, list)
        print(f"  [ok] entities list ({len(ops)} rows)")

        code = f"TEST-PE-{uuid.uuid4().hex[:8].upper()}"
        ent = api(
            "POST",
            "/prediction-entities",
            {
                "entity_code": code,
                "entity_name": "테스트 지점",
                "entity_type": "SITE",
                "business_domain": "HEAT_DEMAND",
            },
        )
        entity_id = ent["entity_id"]
        print(f"  [ok] entity created {entity_id}")

        dup2 = api(
            "POST",
            "/prediction-entities",
            {"entity_code": code, "entity_name": "중복", "entity_type": "SITE"},
            expect_fail=True,
        )
        assert dup2 and dup2.get("http_error") == 400
        print("  [ok] entity_code duplicate blocked")

        bad_loc = api(
            "POST",
            f"/prediction-entities/{entity_id}/locations",
            {"latitude": 999, "longitude": 0},
            expect_fail=True,
        )
        assert bad_loc and bad_loc.get("http_error") == 400
        print("  [ok] latitude validation")

        loc = api(
            "POST",
            f"/prediction-entities/{entity_id}/locations",
            {"address": "서울", "latitude": 37.5665, "longitude": 126.9780, "active_yn": True},
        )
        assert loc.get("location_id")
        print("  [ok] location created")

        grid_conv = api("POST", "/weather/convert-latlon-to-grid", {"latitude": 37.5665, "longitude": 126.9780})
        assert grid_conv.get("nx") and grid_conv.get("ny")
        print(f"  [ok] convert-latlon-to-grid nx={grid_conv['nx']} ny={grid_conv['ny']}")

        grid = api(
            "POST",
            "/weather/forecast-grids",
            {"nx": grid_conv["nx"], "ny": grid_conv["ny"], "grid_name": "TEST 격자"},
        )
        grid_id = grid["forecast_grid_id"]
        print(f"  [ok] forecast grid {grid_id}")

        station = api(
            "POST",
            "/weather/observation-stations",
            {
                "station_code": f"TEST-ST-{uuid.uuid4().hex[:6].upper()}",
                "station_name": "테스트 ASOS",
                "station_type": "ASOS",
                "latitude": 37.57,
                "longitude": 126.97,
            },
        )
        station_id = station["station_id"]
        print(f"  [ok] observation station {station_id}")

        bad_map = api(
            "POST",
            f"/prediction-entities/{entity_id}/weather-mappings",
            {"mapping_type": "BOTH"},
            expect_fail=True,
        )
        assert bad_map and bad_map.get("http_error") == 400
        print("  [ok] mapping without grid/station rejected")

        fmap = api(
            "POST",
            f"/prediction-entities/{entity_id}/weather-mappings",
            {
                "forecast_grid_id": grid_id,
                "mapping_type": "FORECAST_GRID",
                "mapping_method": "LATLON_TO_GRID",
            },
        )
        assert fmap.get("mapping_id")
        print("  [ok] forecast mapping created")

        smap = api(
            "POST",
            f"/prediction-entities/{entity_id}/weather-mappings",
            {
                "station_id": station_id,
                "mapping_type": "OBSERVATION_STATION",
                "mapping_method": "MANUAL",
            },
        )
        assert smap.get("mapping_id")
        print("  [ok] observation mapping created")

        readiness = api("GET", f"/prediction-entities/{entity_id}/weather-readiness")
        assert readiness.get("location_ready") is True
        assert readiness.get("forecast_ready") is True
        assert readiness.get("observation_ready") is True
        print("  [ok] weather_readiness all ready")

        preview = api("POST", f"/prediction-entities/{entity_id}/weather-mapping-preview")
        assert preview.get("grid_suggestion")
        print("  [ok] weather-mapping-preview")

        api("POST", f"/prediction-entities/{entity_id}/weather-mappings/{fmap['mapping_id']}/archive")
        readiness2 = api("GET", f"/prediction-entities/{entity_id}/weather-readiness")
        assert readiness2.get("forecast_ready") is False
        print("  [ok] archive mapping updates readiness")

        detail = api("GET", f"/prediction-entities/{entity_id}")
        assert detail.get("entity_code") == code
        print("  [ok] entity detail")

        bad_msg = api(
            "POST",
            "/prediction-entities",
            {"entity_code": "", "entity_name": "x"},
            expect_fail=True,
        )
        assert bad_msg and bad_msg.get("http_error") == 400
        assert "코드" in bad_msg.get("body", "") or "필수" in bad_msg.get("body", "")
        print("  [ok] user-friendly validation message")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
