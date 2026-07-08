#!/usr/bin/env python3
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

from test_fixtures import psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

CONFLICT_KEY_CANDIDATES: list[list[str]] = [
    ["entity_id", "measured_at"],
    ["station_code", "observed_at"],
]


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload.get("data")


def pick_operation_and_conflict_keys(ops: list[dict]) -> tuple[dict, list[str]]:
    for keys in CONFLICT_KEY_CANDIDATES:
        for op in ops:
            target_table = op.get("target_table")
            if not target_table:
                continue
            cols = api(
                "GET",
                f"/api-connectors/target-table-columns?target_table={urllib.parse.quote(target_table)}",
            )
            colset = set(cols.get("columns") or [])
            if all(key in colset for key in keys):
                return op, keys
    raise RuntimeError("conflict key 후보에 맞는 operation/target_table을 찾지 못했습니다.")


def main() -> int:
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            assert int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_write_policy") or "0") == 0
            assert int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_load_dedup_summary") or "0") == 0
            print("PASS")
            return 0

        ops = api("GET", "/api-connectors/operations")
        if not ops:
            print("SKIP: operation not found")
            return 0
        op, conflict_keys = pick_operation_and_conflict_keys(ops)
        operation_id = op["operation_id"]
        print(f"  [ok] operation={operation_id} table={op.get('target_table')} keys={conflict_keys}")

        policy = api("PUT", f"/api-connectors/operations/{operation_id}/write-policy", {
            "write_mode": "UPSERT",
            "conflict_key_columns_json": conflict_keys,
            "duplicate_within_batch_policy": "KEEP_LAST",
            "null_update_policy": "KEEP_EXISTING",
        })
        assert policy["write_mode"] == "UPSERT"

        fetched = api("GET", f"/api-connectors/operations/{operation_id}/write-policy")
        assert fetched["write_mode"] == "UPSERT"

        validated = api("POST", f"/api-connectors/operations/{operation_id}/write-policy/validate", {
            "write_mode": "INSERT_ONLY",
        })
        assert validated["write_mode"] == "INSERT_ONLY"

        preview = api("POST", f"/api-connectors/operations/{operation_id}/load-preview", {"runtime_params": {}})
        assert "estimated_insert_count" in preview
        assert "write_mode" in preview

        run = api("POST", f"/api-connectors/operations/{operation_id}/load-run", {"runtime_params": {}})
        assert "updated_count" in run
        assert "dedup_summary_id" in run

        summaries = api("GET", "/api-connectors/dedup-summaries")
        assert isinstance(summaries, list)
        if summaries:
            detail = api("GET", f"/api-connectors/dedup-summaries/{summaries[0]['summary_id']}")
            assert detail["summary_id"] == summaries[0]["summary_id"]

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
