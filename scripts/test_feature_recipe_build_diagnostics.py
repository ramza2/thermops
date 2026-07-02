#!/usr/bin/env python3
"""Recipe Engine Build diagnostics·이력·비교 API 테스트 (Phase R6-S1)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import resolve_heat_mapping_id

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_MAPPING_ID = ""
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)


def api(method: str, path: str, body: dict | None = None, *, expect_error: bool = False) -> dict | list:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        if expect_error:
            try:
                return json.loads(detail)
            except json.JSONDecodeError:
                return {"http_error": detail, "status": exc.code}
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success") and not expect_error:
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def create_publish_recipe(recipe_type: str, **overrides) -> tuple[str, str]:
    suffix = uuid4().hex[:6]
    body: dict = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": recipe_type,
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "display_name": f"R6S1 {recipe_type} {suffix}",
    }
    if recipe_type == "RAW_COLUMN":
        body["output_feature_name"] = f"heat_raw_s1_{suffix}"
    elif recipe_type == "LAG":
        body["params"] = {"offset_steps": 24, "granularity": "1h"}
        body["output_feature_name"] = f"heat_lag_s1_{suffix}"
    body.update(overrides)
    recipe_id = api("POST", "/feature-recipes", body)["recipe_id"]
    api("POST", f"/feature-recipes/{recipe_id}/validate")
    feature_name = api("POST", f"/feature-recipes/{recipe_id}/publish")["feature"]["feature_name"]
    return recipe_id, feature_name


def create_fs(features: list[str]) -> str:
    suffix = uuid4().hex[:6]
    return api("POST", "/feature-sets", {
        "feature_set_name": f"R6S1 FS {suffix}",
        "target_domain": "HEAT_DEMAND",
        "features": features,
        "apply_site_scope": "ALL",
    })["feature_set_id"]


def run_build(feature_set_id: str) -> dict:
    qs = urllib.parse.urlencode({"feature_set_id": feature_set_id})
    return api("POST", f"/feature-build-jobs?{qs}")


def test_template_status_by_feature() -> tuple[str, str, str, str]:
    recipe_id, fname = create_publish_recipe("RAW_COLUMN")
    fsid = create_fs([fname])
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    by_feat = rs.get("template_build_status_by_feature") or {}
    assert fname in by_feat, rs
    entry = by_feat[fname]
    assert entry.get("recipe_id") == recipe_id, entry
    assert entry.get("status") in ("GENERATED", "GENERATED_WITH_WARNING"), entry
    counts = rs.get("template_build_status_counts") or {}
    assert counts.get("generated", 0) >= 1, counts
    assert rs.get("recipe_engine_diagnostics_version") == "R6-S1", rs
    dsv = rs.get("dataset_version_id")
    assert dsv, rs
    print("  [ok] template_build_status_by_feature")
    return recipe_id, fname, dsv, fsid


def test_lag_insufficient_history_warning() -> None:
    recipe_id, fname = create_publish_recipe("LAG")
    fsid = create_fs([fname])
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    by_feat = rs.get("template_build_status_by_feature") or {}
    entry = by_feat.get(fname) or {}
    warnings = entry.get("warning_codes") or []
    diagnostics = rs.get("template_build_diagnostics") or []
    has_history_warn = "INSUFFICIENT_HISTORY" in warnings or any(
        d.get("code") == "INSUFFICIENT_HISTORY" for d in diagnostics
    )
    assert has_history_warn or entry.get("null_ratio", 0) > 0, (entry, diagnostics)
    print("  [ok] LAG insufficient history warning/null")


def psql_exec(sql: str) -> None:
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        finally:
            conn.close()
    except ImportError:
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
            check=True,
            capture_output=True,
            text=True,
        )


def test_unsupported_recipe_type() -> None:
    recipe_id, fname = create_publish_recipe("RAW_COLUMN")
    psql_exec(f"UPDATE tb_feature_recipe SET recipe_type = 'RATIO' WHERE recipe_id = '{recipe_id}'")
    fsid = create_fs(["temperature", fname])
    res = run_build(fsid)
    assert res["status"] in ("SUCCESS", "WARNING"), res
    rs = res.get("result_summary") or {}
    by_feat = rs.get("template_build_status_by_feature") or {}
    if fname in by_feat:
        assert by_feat[fname].get("status") == "UNSUPPORTED", by_feat[fname]
    else:
        assert fname in (rs.get("template_build_unsupported_features") or []), rs
    print("  [ok] unsupported recipe type UNSUPPORTED")


def test_missing_source_column_failed() -> None:
    suffix = uuid4().hex[:6]
    fname = f"supply_miss_s1_{suffix}"
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["supply_temp"],
        "output_feature_name": fname,
        "display_name": f"missing {suffix}",
    }
    recipe_id = api("POST", "/feature-recipes", body)["recipe_id"]
    api("POST", f"/feature-recipes/{recipe_id}/validate")
    api("POST", f"/feature-recipes/{recipe_id}/publish")
    fsid = create_fs(["temperature", fname])
    res = run_build(fsid)
    assert res["status"] == "WARNING", res
    rs = res.get("result_summary") or {}
    by_feat = rs.get("template_build_status_by_feature") or {}
    entry = by_feat.get(fname) or {}
    status = entry.get("status")
    failed_list = rs.get("template_build_failed_features") or []
    assert status == "FAILED" or fname in failed_list, (entry, failed_list)
    print("  [ok] missing source column FAILED")


def test_build_history_api(recipe_id: str, fname: str) -> None:
    hist = api("GET", f"/feature-recipes/{recipe_id}/build-history?limit=5")
    assert hist.get("recipe_id") == recipe_id, hist
    assert hist.get("feature_name") == fname, hist
    items = hist.get("items") or []
    assert items, hist
    item = items[0]
    for key in ("job_id", "status", "template_feature_status", "started_at"):
        assert key in item, item
    assert item.get("template_feature_status") in (
        "GENERATED", "GENERATED_WITH_WARNING", "FAILED", "UNSUPPORTED", "UNKNOWN",
    ), item
    print("  [ok] recipe build-history API")


def test_compare_preview_build(recipe_id: str, dsv: str) -> None:
    res = api(
        "POST",
        f"/feature-recipes/{recipe_id}/compare-preview-build",
        {"dataset_version_id": dsv, "sample_size": 10},
    )
    assert res.get("recipe_id") == recipe_id, res
    assert "comparable" in res, res
    assert "summary" in res, res
    if res.get("comparable"):
        summary = res["summary"]
        assert summary.get("sample_count", 0) >= 0, summary
    else:
        assert res.get("warnings"), res
    print("  [ok] compare-preview-build API")


def test_compare_without_dataset_version(recipe_id: str) -> None:
    res = api(
        "POST",
        f"/feature-recipes/{recipe_id}/compare-preview-build",
        {"sample_size": 10},
    )
    assert res.get("recipe_id") == recipe_id, res
    assert "comparable" in res, res
    assert res.get("dataset_version_id") or res.get("warnings"), res
    print("  [ok] compare-preview-build without dataset_version_id")


def test_build_history_limit_one(recipe_id: str) -> None:
    hist = api("GET", f"/feature-recipes/{recipe_id}/build-history?limit=1")
    assert len(hist.get("items") or []) <= 1, hist
    print("  [ok] build-history limit=1")


def test_build_job_recipe_filter(recipe_id: str) -> None:
    q = urllib.parse.urlencode({"recipe_id": recipe_id, "limit": 5})
    jobs = api("GET", f"/feature-build-jobs?{q}")
    items = jobs.get("items") if isinstance(jobs, dict) else jobs
    assert isinstance(items, list), jobs
    print("  [ok] feature-build-jobs recipe_id filter")


def test_quality_template_coverage(dsv: str, fsid: str) -> None:
    quality = api("POST", "/feature-quality-runs", {
        "feature_set_id": fsid,
        "dataset_version_id": dsv,
    })
    rs = quality.get("result_summary") or {}
    cov = rs.get("build_coverage") or {}
    assert cov.get("template_feature_count", 0) >= 1, cov
    print("  [ok] quality template build_coverage")


def test_lineage_template_metadata() -> None:
    recipe_id, fname = create_publish_recipe("LAG")
    fsid = create_fs([fname])
    res = run_build(fsid)
    lineage = api("GET", f"/feature-build-jobs/{res['job_id']}/lineage")
    rows = [r for r in (lineage.get("items") or []) if r.get("feature_name") == fname]
    assert rows, lineage
    lj = rows[0].get("lineage_json") or {}
    recipe_meta = lj.get("recipe") or {}
    assert recipe_meta.get("recipe_id") == recipe_id, lj
    assert recipe_meta.get("recipe_type") == "LAG", lj
    print("  [ok] lineage TEMPLATE metadata")


def test_code_only_backward_compat() -> None:
    sets = api("GET", "/feature-sets")
    fsid = "FS-TPL-TWO-STAGE"
    for fs in sets:
        if fs.get("feature_set_id") == fsid or fs.get("feature_set_name") == "Two-Stage Ready Feature Set":
            fsid = fs["feature_set_id"]
            break
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    assert rs.get("template_feature_count", 0) == 0, rs
    assert "code_feature_count" in rs, rs
    print("  [ok] CODE-only build backward compat")


def main() -> int:
    global HEAT_MAPPING_ID
    print("test_feature_recipe_build_diagnostics.py")
    HEAT_MAPPING_ID = resolve_heat_mapping_id(api)
    print(f"  [fixture] heat mapping={HEAT_MAPPING_ID}")
    try:
        recipe_id, fname, dsv, fsid = test_template_status_by_feature()
        test_lag_insufficient_history_warning()
        test_unsupported_recipe_type()
        test_missing_source_column_failed()
        test_build_history_api(recipe_id, fname)
        test_build_history_limit_one(recipe_id)
        test_compare_preview_build(recipe_id, dsv)
        test_compare_without_dataset_version(recipe_id)
        test_build_job_recipe_filter(recipe_id)
        test_quality_template_coverage(dsv, fsid)
        test_lineage_template_metadata()
        test_code_only_backward_compat()
    except Exception as exc:
        print(f"  [FAIL] {exc}", file=sys.stderr)
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
