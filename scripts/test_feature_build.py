#!/usr/bin/env python3
"""Feature 생성 API 통합 테스트."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    FS_TWO_STAGE_ID,
    ensure_csv_ingested,
    ensure_test_calendar,
    ensure_test_platform,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_TWO_STAGE_ID)


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def ensure_calendar_seed() -> None:
    ensure_test_calendar()


def resolve_feature_set_id() -> str:
    sets = api("GET", "/feature-sets")
    for fs in sets:
        if fs.get("feature_set_id") == FEATURE_SET_ID:
            return FEATURE_SET_ID
        if fs.get("feature_set_name") == "Two-Stage Ready Feature Set":
            return fs["feature_set_id"]
    raise RuntimeError(f"Feature Set not found: {FEATURE_SET_ID}")


def count_feature_dataset(dataset_version_id: str | None = None) -> int:
    try:
        import psycopg2
    except ImportError:
        where = f"WHERE dataset_version_id = '{dataset_version_id}'" if dataset_version_id else ""
        out = subprocess.check_output(
            [
                "docker", "exec", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-t", "-A",
                "-c", f"SELECT COUNT(*) FROM tb_feature_dataset {where}",
            ],
            text=True,
        )
        return int(out.strip())
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            if dataset_version_id:
                cur.execute("SELECT COUNT(*) FROM tb_feature_dataset WHERE dataset_version_id = %s", (dataset_version_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM tb_feature_dataset")
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def sample_feature_json(dataset_version_id: str) -> dict | None:
    try:
        import psycopg2
    except ImportError:
        out = subprocess.check_output(
            [
                "docker", "exec", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-t", "-A",
                "-c",
                f"""SELECT feature_json::text FROM tb_feature_dataset
                WHERE dataset_version_id = '{dataset_version_id}'
                  AND feature_json->>'demand_lag_24h' IS NOT NULL
                  AND feature_json->>'temperature_diff_24h' IS NOT NULL
                  AND feature_json->>'demand_ma_24h' IS NOT NULL
                LIMIT 1""",
            ],
            text=True,
        )
        text = out.strip()
        return json.loads(text) if text else None
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT feature_json FROM tb_feature_dataset
                WHERE dataset_version_id = %s
                  AND feature_json->>'demand_lag_24h' IS NOT NULL
                  AND feature_json->>'temperature_diff_24h' IS NOT NULL
                  AND feature_json->>'demand_ma_24h' IS NOT NULL
                LIMIT 1
                """,
                (dataset_version_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def main() -> int:
    print(f"THERMOps feature build test ({API_BASE})")
    try:
        ensure_test_platform()
        ensure_csv_ingested(api)
        ensure_calendar_seed()
        fs_id = resolve_feature_set_id()
        print(f"  feature_set_id={fs_id}")

        sets = api("GET", "/feature-sets")
        print(f"  [list] feature sets: {len(sets)}")

        preview = api("POST", f"/feature-sets/{fs_id}/preview")
        rows = preview.get("preview_rows") or preview.get("preview") or []
        print(f"  [preview] rows={len(rows)}")
        if not rows:
            raise RuntimeError("preview returned no rows")

        qs = urllib.parse.urlencode({"feature_set_id": fs_id})
        build = api("POST", f"/feature-build-jobs?{qs}")
        print(f"  [build] job_id={build.get('job_id')} status={build.get('status')} inserted={build.get('inserted_count')}")
        if build.get("status") not in ("SUCCESS", "WARNING"):
            raise RuntimeError(f"build failed: {build}")
        if build.get("inserted_count", 0) <= 0:
            raise RuntimeError("inserted_count is 0")

        job = api("GET", f"/feature-build-jobs/{build['job_id']}")
        print(f"  [job] status={job.get('status')} dataset={job.get('dataset_version_id')}")

        dsv = build.get("dataset_version_id")
        count = count_feature_dataset(dsv)
        print(f"  [DB] tb_feature_dataset rows for {dsv}: {count}")
        if count <= 0:
            raise RuntimeError("no rows in tb_feature_dataset")

        sample = sample_feature_json(dsv)
        if not sample:
            raise RuntimeError("feature_json sample missing")
        required = ["demand_lag_24h", "temperature_diff_24h", "demand_ma_24h"]
        missing = [k for k in required if k not in sample or sample[k] is None]
        if missing:
            raise RuntimeError(f"missing feature values in sample: {missing}")
        print(f"  [features] OK sample keys include {required}")

        print("\nPASSED: feature build flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
