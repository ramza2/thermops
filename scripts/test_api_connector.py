#!/usr/bin/env python3
"""REST API Connector 통합 테스트 — 연결/스키마/미리보기/적재/빈 응답 처리."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

API_SOURCE_ID = "DS-API-HEAT-TEST"
API_MAPPING_ID = "MAP-API-HEAT-TEST"

# backend 컨테이너 내부에서 자기 자신 호출
API_CONNECTION = {
    "base_url": os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1"),
    "endpoint": "/sample-external/heat-demand",
    "method": "GET",
    "headers": {},
    "query_params": {"start_at": "{start_at}", "end_at": "{end_at}"},
    "auth_type": "NONE",
    "api_key_header": None,
    "api_key": None,
    "item_path": "data.items",
    "pagination": {"type": "NONE"},
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
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run(["python", "scripts/apply_dev_migrations.py"], check=True, cwd=root)


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
    db_url = os.environ.get("DATABASE_URL", "postgresql://thermops:thermops@localhost:5432/thermops")
    conn = psycopg2.connect(db_url.replace("+asyncpg", ""))
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
        if s["source_id"] == API_SOURCE_ID or s["source_name"] == "열수요 REST API 테스트":
            source_id = s["source_id"]
            break

    if not source_id:
        created = api("POST", "/data-sources", {
            "source_name": "열수요 REST API 테스트",
            "source_type": "REST_API",
            "data_domain": "HEAT_DEMAND",
            "connection_info": API_CONNECTION,
            "active_yn": True,
        })
        source_id = created["source_id"]
    else:
        api("PUT", f"/data-sources/{source_id}", {
            "connection_info": API_CONNECTION,
            "active_yn": True,
        })

    mapping_id = None
    for m in api("GET", "/mappings?page=1&size=100")["items"]:
        if m["source_id"] == source_id and m["mapping_name"] == "열수요 REST API 표준 매핑":
            mapping_id = m["mapping_id"]
            break

    if not mapping_id:
        api("POST", "/mappings", {
            "source_id": source_id,
            "mapping_name": "열수요 REST API 표준 매핑",
            "target_table": "heat_demand_actual",
            "columns": [
                {"source_column": "site_id", "target_column": "site_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "heat_demand", "target_column": "heat_demand", "required_yn": True},
                {"source_column": "supply_temp", "target_column": "supply_temp", "required_yn": False},
            ],
        })
        for m in api("GET", "/mappings?page=1&size=100")["items"]:
            if m["source_id"] == source_id and m["mapping_name"] == "열수요 REST API 표준 매핑":
                mapping_id = m["mapping_id"]
                break

    if not mapping_id:
        raise RuntimeError("매핑 생성 실패")
    return source_id, mapping_id


def main() -> int:
    print(f"THERMOps REST API connector test ({API_BASE})")
    try:
        ensure_external_table()
        source_id, mapping_id = ensure_source_and_mapping()
        table = "tb_heat_demand_actual"
        before = count_table(table)

        test = api("POST", f"/data-sources/{source_id}/test-connection")
        print(
            f"  [연결 테스트] success={test['success']} latency={test.get('latency_ms')}ms "
            f"status={test.get('status_code')} rows={test.get('sample_row_count')}"
        )
        if not test["success"]:
            raise RuntimeError(test.get("error_message"))

        schema = api("GET", f"/data-sources/{source_id}/discover-schema")
        fields = [f["name"] for f in schema.get("fields", [])]
        print(f"  [스키마 탐색] fields={fields}")
        if not fields:
            raise RuntimeError("JSON 필드가 비어 있습니다.")

        valid = api("POST", f"/mappings/{mapping_id}/validate")
        if not valid["valid"]:
            raise RuntimeError(valid.get("errors"))
        print(f"  [매핑 검증] valid={valid['valid']}")

        preview = api("POST", f"/mappings/{mapping_id}/preview")
        print(f"  [미리보기] {len(preview.get('preview_rows', []))}행")

        ingest = api("POST", f"/ingestion-jobs?{urllib.parse.urlencode({'source_id': source_id, 'limit': 30})}")
        print(
            f"  [적재] inserted={ingest.get('inserted_count')} connector={ingest.get('connector_type')} "
            f"source_type={ingest.get('source_type')}"
        )
        after = count_table(table)
        if after >= 0:
            print(f"  [DB] {table}: {before} → {after}")

        empty_preview = api(
            "POST",
            f"/data-sources/{source_id}/preview?"
            + urllib.parse.urlencode({
                "start_at": "2099-01-01T00:00:00",
                "end_at": "2099-01-02T00:00:00",
                "limit": 5,
            }),
        )
        empty_rows = empty_preview.get("rows", [])
        print(f"  [빈 응답] rows={len(empty_rows)} (기대: 0)")
        if empty_rows:
            print("  [WARN] 미래 구간 필터에서도 행이 반환됨")

        empty_ingest = api(
            "POST",
            f"/ingestion-jobs?{urllib.parse.urlencode({
                'source_id': source_id,
                'start_at': '2099-01-01T00:00:00',
                'end_at': '2099-01-02T00:00:00',
                'limit': 10,
            })}",
        )
        print(
            f"  [빈 적재] inserted={empty_ingest.get('inserted_count')} "
            f"failed={empty_ingest.get('failed_count')} status={empty_ingest.get('status')}"
        )

        print("\nPASSED: REST_API connector flow")
        return 0
    except (urllib.error.URLError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
