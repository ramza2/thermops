#!/usr/bin/env python3
"""Pipeline Definition 기반 Airflow 실행 연계 테스트 (Phase R9)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    ensure_test_pipeline_templates,
    heat_pipeline_node_config,
    resolve_batch_pipeline_template_id,
    resolve_feature_build_template_id,
)

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
    return payload.get("data", payload)


def _create_runnable_pipeline() -> str:
    body = {
        "template_id": resolve_feature_build_template_id(),
        "pipeline_name": f"R9-exec-{uuid.uuid4().hex[:6]}",
        "node_config": heat_pipeline_node_config(api),
    }
    created = api("POST", "/pipeline-definitions", body)
    pid = created["pipeline_id"]
    api("POST", f"/pipeline-definitions/{pid}/validate")
    api("POST", f"/pipeline-definitions/{pid}/activate")
    return pid


def test_dry_run_success() -> str:
    pid = _create_runnable_pipeline()
    result = api("POST", f"/pipeline-definitions/{pid}/run", {"dry_run": True, "requested_by": "test"})
    assert result.get("dry_run") is True, result
    assert result.get("run_status") == "DRY_RUN", result
    conf = result.get("airflow_conf") or {}
    ctx = conf.get("thermops_context") or {}
    assert ctx.get("run_source") == "PIPELINE_DEFINITION", ctx
    assert ctx.get("pipeline_id") == pid, ctx
    assert conf.get("node_config"), conf
    assert conf.get("runtime_params"), conf
    assert conf.get("schedule_config") is not None, conf
    assert conf.get("validation_snapshot"), conf
    print(f"  [ok] dry_run conf ({pid})")
    return pid


def test_draft_run_blocked() -> None:
    body = {
        "template_id": resolve_feature_build_template_id(),
        "pipeline_name": f"R9-draft-{uuid.uuid4().hex[:6]}",
        "node_config": heat_pipeline_node_config(api),
    }
    created = api("POST", "/pipeline-definitions", body)
    pid = created["pipeline_id"]
    resp = api("POST", f"/pipeline-definitions/{pid}/run", {"dry_run": True}, expect_fail=True)
    assert resp.get("status") == 400 or "detail" in resp, resp
    assert "DRAFT" in str(resp), resp
    print("  [ok] DRAFT run blocked")


def test_archived_run_blocked(pid: str) -> None:
    api("POST", f"/pipeline-definitions/{pid}/archive")
    resp = api("POST", f"/pipeline-definitions/{pid}/run", {"dry_run": True}, expect_fail=True)
    assert resp.get("status") == 400 or "보관" in str(resp) or "ARCHIVED" in str(resp), resp
    print("  [ok] ARCHIVED run blocked")


def test_validation_error_blocks_run() -> None:
    body = {
        "template_id": resolve_batch_pipeline_template_id(),
        "pipeline_name": f"R9-invalid-{uuid.uuid4().hex[:6]}",
        "node_config": {},
    }
    created = api("POST", "/pipeline-definitions", body)
    pid = created["pipeline_id"]
    api("POST", f"/pipeline-definitions/{pid}/validate")
    resp = api("POST", f"/pipeline-definitions/{pid}/run", {"dry_run": True}, expect_fail=True)
    assert resp.get("status") == 400 or "detail" in resp, resp
    assert "누락" in str(resp) or "필수" in str(resp) or "detail" in resp, resp
    print("  [ok] validation error blocks run")


def test_actual_run_and_link() -> None:
    pid = _create_runnable_pipeline()
    result = api("POST", f"/pipeline-definitions/{pid}/run", {"requested_by": "test"})
    assert result.get("pipeline_run_id"), result
    assert result.get("run_source") == "PIPELINE_DEFINITION", result
    assert result.get("runtime_params_snapshot"), result
    link_id = result.get("link_id")
    assert link_id, result

    defn = api("GET", f"/pipeline-definitions/{pid}")
    assert defn.get("last_run_id") == result["pipeline_run_id"], defn

    runs = api("GET", f"/pipeline-definitions/{pid}/runs?limit=5")
    items = runs.get("items") or []
    assert any(i.get("link_id") == link_id for i in items), items

    links = api("GET", f"/pipeline-run-links?pipeline_id={pid}&limit=5")
    assert links.get("total", 0) >= 1, links
    print(f"  [ok] run link created ({result['pipeline_run_id']}, status={result.get('run_status')})")


def test_pipeline_runs_metadata_merge() -> None:
    runs = api("GET", "/pipeline-runs?page=1&size=50&sync_airflow=false")
    items = runs.get("items") or []
    assert isinstance(items, list), runs
    has_source = any(i.get("run_source") for i in items)
    assert has_source or len(items) == 0, items[:3]
    print("  [ok] pipeline-runs metadata merge")


def test_direct_dag_trigger_unchanged() -> None:
    result = api(
        "POST",
        "/pipelines/feature_build_dag/trigger",
        {"business_date": "2026-07-01"},
    )
    assert result.get("pipeline_run_id"), result
    print("  [ok] direct DAG trigger unchanged")


def main() -> int:
    print("THERMOps pipeline execution tests (R9)")
    ensure_test_pipeline_templates()
    failed = 0
    pid: str | None = None
    tests = [
        test_draft_run_blocked,
        test_validation_error_blocks_run,
        test_pipeline_runs_metadata_merge,
        test_direct_dag_trigger_unchanged,
    ]
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {exc}", file=sys.stderr)

    try:
        pid = test_dry_run_success()
        test_archived_run_blocked(pid)
        test_actual_run_and_link()
    except Exception as exc:
        failed += 1
        print(f"  [FAIL] pipeline run lifecycle: {exc}", file=sys.stderr)

    total = len(tests) + 3
    if failed:
        print(f"FAILED ({failed} errors)", file=sys.stderr)
        return 1
    print(f"PASSED ({total}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
