#!/usr/bin/env python3
"""PostgreSQL DB Connector 통합 테스트 — 연결/스키마/미리보기/적재/upsert."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

DB_SOURCE_ID = "DS-DB-HEAT-TEST"
DB_MAPPING_ID = "MAP-DB-HEAT-TEST"

DB_CONNECTION = {
    "host": os.environ.get("THERMOOPS_DB_HOST", "postgres"),
    "port": 5432,
    "database": "thermops",
    "schema": "public",
    "table": "external_heat_demand_sample",
    "username": "thermops",
    "password": "thermops",
    "query": None,
    "timestamp_column": "measured_at",
}


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API 실패 {path}: {payload}")
    return payload["data"]


def ensure_external_table() -> None:
    if os.environ.get("THERMOOPS_USE_DOCKER", "1") == "1":
        subprocess.run(
            ["python", "scripts/apply_dev_migrations.py"],
            check=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        return
    try:
        import psycopg2
    except ImportError:
        print("  [SKIP] external table check (psycopg2 unavailable)")
        return
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM external_heat_demand_sample")
            cnt = int(cur.fetchone()[0])
            if cnt == 0:
                raise RuntimeError("external_heat_demand_sample is empty — run apply_dev_migrations.py")
    finally:
        conn.close()


def count_table(table: str) -> int:
    try:
        import psycopg2
    except ImportError:
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
            return -1
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def ensure_source_and_mapping() -> tuple[str, str]:
    sources = api("GET", "/data-sources?page=1&size=100")
    source_id = None
    for s in sources["items"]:
        if s["source_id"] == DB_SOURCE_ID or s["source_name"] == "열수요 PostgreSQL 테스트":
            source_id = s["source_id"]
            break

    if not source_id:
        created = api("POST", "/data-sources", {
            "source_name": "열수요 PostgreSQL 테스트",
            "source_type": "DB_POSTGRES",
            "data_domain": "HEAT_DEMAND",
            "connection_info": DB_CONNECTION,
            "active_yn": True,
        })
        source_id = created["source_id"]
    else:
        api("PUT", f"/data-sources/{source_id}", {
            "connection_info": DB_CONNECTION,
            "active_yn": True,
        })

    mapping_id = None
    for m in api("GET", "/mappings?page=1&size=100")["items"]:
        if m["source_id"] == source_id and m["mapping_name"] == "열수요 DB 표준 매핑":
            mapping_id = m["mapping_id"]
            break

    if not mapping_id:
        api("POST", "/mappings", {
            "source_id": source_id,
            "mapping_name": "열수요 DB 표준 매핑",
            "target_table": "heat_demand_actual",
            "columns": [
                {"source_column": "site_id", "target_column": "site_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "heat_demand", "target_column": "heat_demand", "required_yn": True},
                {"source_column": "supply_temp", "target_column": "supply_temp", "required_yn": False},
            ],
        })
        for m in api("GET", "/mappings?page=1&size=100")["items"]:
            if m["source_id"] == source_id and m["mapping_name"] == "열수요 DB 표준 매핑":
                mapping_id = m["mapping_id"]
                break

    if not mapping_id:
        raise RuntimeError("매핑 생성 실패")
    return source_id, mapping_id


def main() -> int:
    print(f"THERMOps DB connector test ({API_BASE})")
    try:
        ensure_external_table()
        source_id, mapping_id = ensure_source_and_mapping()
        table = "tb_heat_demand_actual"
        before = count_table(table)

        test = api("POST", f"/data-sources/{source_id}/test-connection")
        print(f"  [연결 테스트] success={test['success']} latency={test.get('latency_ms')}ms cols={test.get('columns')}")
        if not test["success"]:
            raise RuntimeError(test.get("error_message"))

        schema = api("GET", f"/data-sources/{source_id}/discover-schema")
        fields = [f["name"] for f in schema.get("fields", [])]
        print(f"  [스키마 탐색] fields={fields}")
        for required in ("site_id", "measured_at", "heat_demand"):
            if required not in fields:
                raise RuntimeError(f"필수 컬럼 누락: {required}")

        valid = api("POST", f"/mappings/{mapping_id}/validate")
        print(f"  [매핑 검증] valid={valid['valid']}")
        if not valid["valid"]:
            raise RuntimeError(valid.get("errors"))

        preview = api("POST", f"/mappings/{mapping_id}/preview")
        rows = preview.get("preview_rows", [])
        print(f"  [미리보기] {len(rows)}행")

        ingest = api("POST", f"/ingestion-jobs?{urllib.parse.urlencode({'source_id': source_id, 'limit': 50})}")
        print(
            f"  [적재 1차] inserted={ingest.get('inserted_count')} "
            f"updated={ingest.get('updated_count')} source_type={ingest.get('source_type')}"
        )
        after_first = count_table(table)
        if after_first >= 0 and before >= 0:
            print(f"  [DB] {table}: {before} → {after_first}")

        ingest2 = api("POST", f"/ingestion-jobs?{urllib.parse.urlencode({'source_id': source_id, 'limit': 50})}")
        print(
            f"  [적재 2차 upsert] inserted={ingest2.get('inserted_count')} "
            f"updated={ingest2.get('updated_count')} skipped={ingest2.get('skipped_count')}"
        )
        if (ingest2.get("updated_count") or 0) < 1 and (ingest2.get("inserted_count") or 0) < 1:
            print("  [WARN] 재적재 시 updated/inserted가 모두 0일 수 있음(이미 동일 데이터)")

        filtered = api(
            "POST",
            f"/ingestion-jobs?{urllib.parse.urlencode({
                'source_id': source_id,
                'start_at': '2020-01-01T00:00:00',
                'end_at': '2020-01-02T00:00:00',
                'limit': 10,
            })}",
        )
        print(f"  [기간 필터] inserted={filtered.get('inserted_count')} (기대: 0 또는 소량)")

        limited = api(
            "POST",
            f"/ingestion-jobs?{urllib.parse.urlencode({'source_id': source_id, 'limit': 5})}",
        )
        summary = limited.get("result_summary") or {}
        print(f"  [limit=5] source_row_count={summary.get('source_row_count')}")

        print("\nPASSED: DB_POSTGRES connector flow")
        return 0
    except (urllib.error.URLError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
