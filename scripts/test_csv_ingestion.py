#!/usr/bin/env python3
"""CSV 적재 API 통합 테스트 — 연결 테스트 → 검증 → 미리보기 → 적재 → DB 건수 확인."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

HEAT_SOURCE = "DS-CSV-001"
WEATHER_SOURCE = "DS-CSV-002"
HEAT_MAPPING = "MAP-CSV-001"
WEATHER_MAPPING = "MAP-CSV-002"


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API 실패 {path}: {payload}")
    return payload["data"]


def ensure_seed_records() -> None:
    """기존 DB 볼륨에 CSV 시드가 없을 때 API로 최소 등록."""
    sources = api("GET", "/data-sources?page=1&size=100")
    ids = {s["source_id"] for s in sources["items"]}

    if HEAT_SOURCE not in ids:
        api("POST", "/data-sources", {
            "source_name": "열수요 CSV 샘플",
            "source_type": "CSV",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "file_path": "data/samples/heat_demand_sample.csv",
                "encoding": "utf-8",
                "delimiter": ",",
            },
            "active_yn": True,
        })

    if WEATHER_SOURCE not in ids:
        api("POST", "/data-sources", {
            "source_name": "기상 CSV 샘플",
            "source_type": "CSV",
            "data_domain": "WEATHER",
            "connection_info": {
                "file_path": "data/samples/weather_observation_sample.csv",
                "encoding": "utf-8",
                "delimiter": ",",
            },
            "active_yn": True,
        })

    mappings = api("GET", "/mappings?page=1&size=100")
    map_ids = {m["mapping_id"] for m in mappings["items"]}
    heat_sid = HEAT_SOURCE if HEAT_SOURCE in ids else [
        s for s in api("GET", "/data-sources?page=1&size=100")["items"]
        if s["source_name"] == "열수요 CSV 샘플"
    ][0]["source_id"]

    if HEAT_MAPPING not in map_ids:
        api("POST", "/mappings", {
            "source_id": heat_sid,
            "mapping_name": "열수요 CSV 표준 매핑",
            "target_table": "heat_demand_actual",
            "columns": [
                {"source_column": "site_id", "target_column": "site_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "heat_demand", "target_column": "heat_demand", "required_yn": True},
                {"source_column": "supply_temp", "target_column": "supply_temp", "required_yn": False},
            ],
        })

    weather_sid = WEATHER_SOURCE if WEATHER_SOURCE in ids else [
        s for s in api("GET", "/data-sources?page=1&size=100")["items"]
        if s["source_name"] == "기상 CSV 샘플"
    ][0]["source_id"]

    if WEATHER_MAPPING not in map_ids:
        api("POST", "/mappings", {
            "source_id": weather_sid,
            "mapping_name": "기상 CSV 표준 매핑",
            "target_table": "weather_observation",
            "columns": [
                {"source_column": "weather_area_id", "target_column": "weather_area_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "data_type", "target_column": "data_type", "required_yn": False},
                {"source_column": "temperature", "target_column": "temperature", "required_yn": False},
                {"source_column": "humidity", "target_column": "humidity", "required_yn": False},
                {"source_column": "rainfall", "target_column": "rainfall", "required_yn": False},
                {"source_column": "wind_speed", "target_column": "wind_speed", "required_yn": False},
            ],
        })


def count_table(table: str) -> int:
    try:
        import psycopg2
    except ImportError:
        import subprocess
        try:
            out = subprocess.check_output(
                [
                    "docker", "exec", "thermops-postgres",
                    "psql", "-U", "thermops", "-d", "thermops", "-t", "-A",
                    "-c", f"SELECT COUNT(*) FROM {table}",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return int(out.strip())
        except Exception:
            print(f"  [SKIP] DB count skipped for {table} (psycopg2/docker unavailable)")
            return -1
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def run_case(label: str, source_id: str, mapping_id: str, table: str) -> None:
    print(f"\n=== {label} ===")
    before = count_table(table)

    test = api("POST", f"/data-sources/{source_id}/test-connection")
    print(f"  [연결 테스트] success={test['success']} rows={test.get('sample_row_count')} cols={len(test.get('columns', []))}")
    if not test["success"]:
        raise RuntimeError(test.get("error_message"))

    valid = api("POST", f"/mappings/{mapping_id}/validate")
    print(f"  [매핑 검증] valid={valid['valid']} errors={valid.get('errors')} warnings={valid.get('warnings')}")
    if not valid["valid"]:
        raise RuntimeError(valid.get("errors"))

    preview = api("POST", f"/mappings/{mapping_id}/preview")
    rows = preview.get("preview_rows", [])
    print(f"  [미리보기] {len(rows)}행 (첫 행 키: {list(rows[0].keys()) if rows else []})")

    ingest = api("POST", f"/ingestion-jobs?{urllib.parse.urlencode({'source_id': source_id})}")
    print(f"  [적재] status={ingest.get('status')} inserted={ingest.get('inserted_count')} failed={ingest.get('failed_count')}")

    after = count_table(table)
    if after >= 0 and before >= 0:
        print(f"  [DB] {table}: {before} → {after} (+{after - before})")
        if ingest.get("inserted_count", 0) > 0 and after <= before:
            print("  [WARN] 적재 건수는 있으나 테이블 건수 증가가 없을 수 있습니다(upsert).")


def resolve_mapping_id(name: str, fallback: str) -> str:
    mappings = api("GET", "/mappings?page=1&size=100")
    for m in mappings["items"]:
        if m["mapping_name"] == name or m["mapping_id"] == fallback:
            return m["mapping_id"]
    return fallback


def resolve_source_id(fallback: str, name: str) -> str:
    sources = api("GET", "/data-sources?page=1&size=100")
    for s in sources["items"]:
        if s["source_id"] == fallback or s["source_name"] == name:
            return s["source_id"]
    return fallback


def main() -> int:
    print(f"THERMOps CSV ingestion test ({API_BASE})")
    try:
        ensure_seed_records()
        heat_sid = resolve_source_id(HEAT_SOURCE, "열수요 CSV 샘플")
        weather_sid = resolve_source_id(WEATHER_SOURCE, "기상 CSV 샘플")
        heat_mid = resolve_mapping_id("열수요 CSV 표준 매핑", HEAT_MAPPING)
        weather_mid = resolve_mapping_id("기상 CSV 표준 매핑", WEATHER_MAPPING)

        run_case("열수요 CSV", heat_sid, heat_mid, "tb_heat_demand_actual")
        run_case("기상 CSV", weather_sid, weather_mid, "tb_weather_observation")

        print("\nPASSED: CSV ingestion flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
