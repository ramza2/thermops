#!/usr/bin/env python3
"""Pipeline Builder API 테스트 (Phase R8)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list:
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
        detail = exc.read().decode()
        if expect_fail:
            try:
                return json.loads(detail)
            except json.JSONDecodeError:
                return {"detail": detail, "status": exc.code}
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def test_template_list() -> None:
    data = api("GET", "/pipeline-templates?active_only=true")
    items = data.get("items") or []
    assert len(items) >= 3, len(items)
    codes = {i["template_code"] for i in items}
    assert "FULL_OPERATION_PIPELINE" in codes, codes
    print(f"  [ok] pipeline templates ({len(items)}건)")


def test_full_template_detail() -> None:
    data = api("GET", "/pipeline-templates/PT-FULL-OPERATION")
    flow = data.get("flow") or {}
    nodes = flow.get("nodes") or []
    edges = flow.get("edges") or []
    assert len(nodes) >= 6, len(nodes)
    assert len(edges) >= 5, len(edges)
    print(f"  [ok] FULL template flow ({len(nodes)} nodes, {len(edges)} edges)")


def test_create_definition() -> str:
    body = {
        "template_id": "PT-FEATURE-BUILD",
        "pipeline_name": f"R8-test-{uuid.uuid4().hex[:6]}",
        "description": "R8 automated test",
        "node_config": {
            "DATA_SOURCE": {"data_source_id": "DS-CSV-001"},
            "DATA_MAPPING": {"mapping_id": "MAP-CSV-001"},
            "STANDARD_DATASET": {"dataset_type_id": "DST-HEAT-DEMAND-ACTUAL"},
            "FEATURE_SET": {"feature_set_id": "FS-TPL-LAG-ROLL"},
            "FEATURE_BUILD": {"feature_set_id": "FS-TPL-LAG-ROLL"},
        },
    }
    data = api("POST", "/pipeline-definitions", body)
    pid = data["pipeline_id"]
    assert pid, data
    print(f"  [ok] create definition ({pid})")
    return pid


def test_get_definition(pipeline_id: str) -> None:
    data = api("GET", f"/pipeline-definitions/{pipeline_id}")
    assert data["pipeline_id"] == pipeline_id
    assert data.get("flow"), data
    print("  [ok] get definition with flow")


def test_validate_missing_required() -> None:
    body = {
        "template_id": "PT-BATCH-PREDICTION",
        "pipeline_name": f"R8-invalid-{uuid.uuid4().hex[:6]}",
        "node_config": {},
    }
    created = api("POST", "/pipeline-definitions", body)
    pid = created["pipeline_id"]
    result = api("POST", f"/pipeline-definitions/{pid}/validate")
    assert result.get("valid") is False, result
    assert result.get("errors"), result
    print("  [ok] validation errors on missing required nodes")


def test_validate_and_activate(pipeline_id: str) -> None:
    result = api("POST", f"/pipeline-definitions/{pipeline_id}/validate")
    assert result.get("valid") is True, result
    assert result.get("runtime_params_preview"), result
    activated = api("POST", f"/pipeline-definitions/{pipeline_id}/activate")
    assert activated.get("status") == "ACTIVE", activated
    print("  [ok] validate pass + activate")


def test_runtime_preview(pipeline_id: str) -> None:
    data = api("POST", f"/pipeline-definitions/{pipeline_id}/runtime-preview")
    params = data.get("runtime_params") or {}
    assert params.get("template_code") == "FEATURE_BUILD_PIPELINE", params
    assert params.get("feature_set_id") == "FS-TPL-LAG-ROLL", params
    print("  [ok] runtime preview")


def test_node_options() -> None:
    data = api("GET", "/pipeline-node-options?component_type=DATA_SOURCE")
    fields = data.get("fields") or {}
    assert "data_source_id" in fields, fields
    assert len(fields["data_source_id"]) >= 1
    print("  [ok] node options DATA_SOURCE")


def test_planned_template_create_blocked() -> None:
    body = {
        "template_id": "PT-RETRAINING",
        "pipeline_name": f"R8-planned-{uuid.uuid4().hex[:6]}",
    }
    resp = api("POST", "/pipeline-definitions", body, expect_fail=True)
    assert resp.get("status") == 400 or "PLANNED" in str(resp), resp
    print("  [ok] PLANNED template create blocked")


def test_airflow_list_unchanged() -> None:
    data = api("GET", "/pipelines")
    items = data if isinstance(data, list) else (data.get("items") or [])
    ids = {i["pipeline_id"] for i in items}
    assert "thermops_full_pipeline_dag" in ids, ids
    print("  [ok] existing /pipelines API unchanged")


def test_archive(pipeline_id: str) -> None:
    data = api("POST", f"/pipeline-definitions/{pipeline_id}/archive")
    assert data.get("status") == "ARCHIVED", data
    print("  [ok] archive definition")


def main() -> int:
    tests = [
        test_template_list,
        test_full_template_detail,
        test_node_options,
        test_planned_template_create_blocked,
        test_airflow_list_unchanged,
    ]
    print("THERMOps pipeline builder tests (R8)")
    failed = 0
    pipeline_id: str | None = None
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {exc}", file=sys.stderr)

    try:
        pipeline_id = test_create_definition()
        test_get_definition(pipeline_id)
        test_validate_missing_required()
        test_validate_and_activate(pipeline_id)
        test_runtime_preview(pipeline_id)
        test_archive(pipeline_id)
    except Exception as exc:
        failed += 1
        print(f"  [FAIL] pipeline lifecycle: {exc}", file=sys.stderr)

    total = len(tests) + 6
    if failed:
        print(f"FAILED ({failed} errors)", file=sys.stderr)
        return 1
    print(f"PASSED ({total}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
