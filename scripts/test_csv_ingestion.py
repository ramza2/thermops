#!/usr/bin/env python3
"""CSV 적재 API 통합 테스트 — 연결 테스트 → 검증 → 미리보기 → 적재 → DB 건수 확인."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import ensure_heat_csv_fixture, ensure_weather_csv_fixture

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)


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


def ensure_seed_records() -> tuple[dict[str, str], dict[str, str]]:
    """테스트용 CSV 소스·매핑 확보 (clean seed에는 포함되지 않음)."""
    heat = ensure_heat_csv_fixture(api)
    weather = ensure_weather_csv_fixture(api)
    return heat, weather


def psql_scalar(sql: str) -> str:
    try:
        import psycopg2
    except ImportError:
        import subprocess
        out = subprocess.check_output(
            [
                "docker", "exec", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops",
                "-t", "-A", "-c", sql,
            ],
            text=True,
        )
        return out.strip()
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return str(row[0]).strip() if row and row[0] is not None else ""
    finally:
        conn.close()


def main() -> int:
    print(f"THERMOps CSV ingestion test ({API_BASE})")
    try:
        heat, weather = ensure_seed_records()
        heat_source = heat["source_id"]
        weather_source = weather["source_id"]
        heat_mapping = heat["mapping_id"]
        weather_mapping = weather["mapping_id"]
        print(f"  [fixture] heat source={heat_source} mapping={heat_mapping}")
        print(f"  [fixture] weather source={weather_source} mapping={weather_mapping}")

        conn = api("POST", f"/data-sources/{heat_source}/test-connection")
        assert conn.get("success") is True, conn
        print("  [ok] heat CSV connection test")

        validate = api("POST", f"/mappings/{heat_mapping}/validate")
        assert validate.get("valid") is True, validate
        print("  [ok] heat mapping validate")

        preview = api("POST", f"/mappings/{heat_mapping}/preview")
        assert preview.get("preview_rows"), preview
        print(f"  [ok] heat mapping preview ({len(preview['preview_rows'])} rows)")

        before_heat = int(psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_actual") or "0")
        params = urllib.parse.urlencode({
            "source_id": heat_source,
            "load_mode": "UPSERT",
            "limit": "1000",
        })
        ingest = api("POST", f"/ingestion-jobs?{params}")
        assert ingest.get("status") == "SUCCESS", ingest
        after_heat = int(psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_actual") or "0")
        assert after_heat >= before_heat, (before_heat, after_heat)
        print(f"  [ok] heat ingest rows={ingest.get('loaded_count', 0)}")

        before_weather = int(psql_scalar("SELECT COUNT(*) FROM tb_weather_observation") or "0")
        params = urllib.parse.urlencode({
            "source_id": weather_source,
            "load_mode": "UPSERT",
            "limit": "1000",
        })
        ingest_w = api("POST", f"/ingestion-jobs?{params}")
        assert ingest_w.get("status") == "SUCCESS", ingest_w
        after_weather = int(psql_scalar("SELECT COUNT(*) FROM tb_weather_observation") or "0")
        assert after_weather >= before_weather, (before_weather, after_weather)
        print(f"  [ok] weather ingest rows={ingest_w.get('loaded_count', 0)}")

        print("\nPASSED: CSV ingestion flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError, AssertionError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
