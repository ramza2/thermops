#!/usr/bin/env python3
"""Feature Recipe Engine Build 테스트 (Phase R6)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_MAPPING_ID = os.environ.get("THERMOOPS_HEAT_MAPPING_ID", "MAP-CSV-001")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)
TPL_FS = "FS-TPL-LAG-ROLL"
CODE_ONLY_FS = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-TWO-STAGE")


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


def psql_scalar(sql: str) -> str:
    try:
        import psycopg2
    except ImportError:
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
            return str(row[0]) if row and row[0] is not None else ""
    finally:
        conn.close()


def ensure_calendar_seed() -> None:
    sql = """
    INSERT INTO tb_calendar (calendar_date, day_of_week, is_weekend, is_holiday, holiday_name, season)
    SELECT d::date, EXTRACT(DOW FROM d)::int,
      CASE WHEN EXTRACT(DOW FROM d) IN (0,6) THEN 'Y' ELSE 'N' END, 'N', NULL, 'SHOULDER'
    FROM generate_series('2026-05-01'::date, '2026-07-31'::date, '1 day') d
    ON CONFLICT (calendar_date) DO NOTHING;
    """
    try:
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def create_publish_recipe(recipe_type: str, **overrides) -> tuple[str, str]:
    suffix = uuid4().hex[:6]
    body: dict = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": recipe_type,
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "display_name": f"R6 {recipe_type} {suffix}",
    }
    if recipe_type == "RAW_COLUMN":
        body["output_feature_name"] = f"heat_raw_r6_{suffix}"
    elif recipe_type == "DATE_PART":
        body["source_columns"] = ["measured_at"]
        body["params"] = {"parts": ["hour"]}
        body["output_feature_name"] = f"heat_hour_r6_{suffix}"
    elif recipe_type == "LAG":
        body["params"] = {"offset_steps": 24, "granularity": "1h"}
        body["output_feature_name"] = f"heat_lag_r6_{suffix}"
    elif recipe_type == "ROLLING_MEAN":
        body["params"] = {"window_steps": 24, "min_periods": 24, "granularity": "1h", "include_current_row": False}
        body["output_feature_name"] = f"heat_ma_r6_{suffix}"
    elif recipe_type == "ROLLING_SUM":
        body["params"] = {"window_steps": 12, "min_periods": 12, "granularity": "1h", "include_current_row": False}
        body["output_feature_name"] = f"heat_sum_r6_{suffix}"
    elif recipe_type == "RATIO":
        body["source_columns"] = ["heat_demand", "supply_temp"]
        body["params"] = {"numerator": "heat_demand", "denominator": "supply_temp"}
        body["output_feature_name"] = f"heat_ratio_r6_{suffix}"
    body.update(overrides)
    recipe_id = api("POST", "/feature-recipes", body)["recipe_id"]
    api("POST", f"/feature-recipes/{recipe_id}/validate")
    feature_name = api("POST", f"/feature-recipes/{recipe_id}/publish")["feature"]["feature_name"]
    return recipe_id, feature_name


def create_fs_with_features(features: list[str]) -> str:
    suffix = uuid4().hex[:6]
    fs = api("POST", "/feature-sets", {
        "feature_set_name": f"R6 Build FS {suffix}",
        "target_domain": "HEAT_DEMAND",
        "features": features,
        "apply_site_scope": "ALL",
    })
    return fs["feature_set_id"]


def run_build(feature_set_id: str) -> dict:
    qs = urllib.parse.urlencode({"feature_set_id": feature_set_id})
    return api("POST", f"/feature-build-jobs?{qs}")


def test_registration_build_supported() -> str:
    _, feature_name = create_publish_recipe("LAG")
    reg = api("GET", f"/features/validate-name?feature_name={feature_name}")
    assert reg.get("build_supported") is True, reg
    assert reg.get("registration_status") in ("TEMPLATE_BUILD_SUPPORTED", "TEMPLATE_PUBLISHED"), reg
    print("  [ok] registration build_supported=true")
    return feature_name


def test_raw_column_build() -> None:
    _, fname = create_publish_recipe("RAW_COLUMN")
    fsid = create_fs_with_features(["temperature", fname])
    res = run_build(fsid)
    assert res["status"] in ("SUCCESS", "WARNING"), res
    rs = res.get("result_summary") or {}
    assert rs.get("template_generated_feature_count", 0) >= 1, rs
    dsv = rs.get("dataset_version_id")
    assert dsv, rs
    sample = psql_scalar(
        f"SELECT feature_json::text FROM tb_feature_dataset WHERE dataset_version_id = '{dsv}' "
        f"AND feature_json ? '{fname}' LIMIT 1"
    )
    assert sample, f"feature_json missing key {fname}"
    print("  [ok] RAW_COLUMN recipe build")


def test_date_part_build() -> None:
    _, fname = create_publish_recipe("DATE_PART")
    fsid = create_fs_with_features([fname])
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    assert fname in (rs.get("template_recipe_features") or []), rs
    dsv = rs.get("dataset_version_id")
    sample = psql_scalar(
        f"SELECT (feature_json->>'{fname}') FROM tb_feature_dataset WHERE dataset_version_id = '{dsv}' LIMIT 1"
    )
    assert sample != "", f"DATE_PART value missing for {fname}"
    print("  [ok] DATE_PART recipe build")


def test_lag_build() -> None:
    _, fname = create_publish_recipe("LAG")
    fsid = create_fs_with_features(["demand_lag_24h", fname])
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    assert rs.get("template_generated_feature_count", 0) >= 1, rs
    print("  [ok] LAG recipe build")


def test_rolling_mean_build() -> None:
    _, fname = create_publish_recipe("ROLLING_MEAN")
    fsid = create_fs_with_features([fname])
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    assert rs.get("recipe_engine_version") == "R6", rs
    print("  [ok] ROLLING_MEAN recipe build")


def test_rolling_sum_build() -> None:
    _, fname = create_publish_recipe("ROLLING_SUM")
    fsid = create_fs_with_features([fname])
    res = run_build(fsid)
    assert res["status"] in ("SUCCESS", "WARNING"), res
    print("  [ok] ROLLING_SUM recipe build")


def test_lineage_template() -> None:
    _, fname = create_publish_recipe("LAG")
    fsid = create_fs_with_features([fname])
    res = run_build(fsid)
    job_id = res["job_id"]
    lineage = api("GET", f"/feature-build-jobs/{job_id}/lineage")
    items = lineage.get("items") or []
    rows = [r for r in items if r.get("feature_name") == fname]
    assert rows, items
    assert rows[0].get("calc_method") == "TEMPLATE", rows[0]
    print("  [ok] lineage calc_method=TEMPLATE")


def test_missing_source_column_warning() -> None:
    suffix = uuid4().hex[:6]
    fname = f"supply_missing_r6_{suffix}"
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["supply_temp"],
        "output_feature_name": fname,
        "display_name": f"missing source {suffix}",
    }
    recipe_id = api("POST", "/feature-recipes", body)["recipe_id"]
    api("POST", f"/feature-recipes/{recipe_id}/validate")
    api("POST", f"/feature-recipes/{recipe_id}/publish")
    fsid = create_fs_with_features(["temperature", fname])
    res = run_build(fsid)
    assert res["status"] == "WARNING", res
    rs = res.get("result_summary") or {}
    failed = rs.get("template_build_failed_features") or []
    assert fname in failed, rs
    print("  [ok] missing source column WARNING")


def test_code_only_unchanged() -> None:
    sets = api("GET", "/feature-sets")
    fsid = CODE_ONLY_FS
    for fs in sets:
        if fs.get("feature_set_id") == CODE_ONLY_FS or fs.get("feature_set_name") == "Two-Stage Ready Feature Set":
            fsid = fs["feature_set_id"]
            break
    res = run_build(fsid)
    assert res["status"] in ("SUCCESS", "WARNING"), res
    assert res.get("inserted_count", 0) > 0, res
    rs = res.get("result_summary") or {}
    assert rs.get("template_feature_count", 0) == 0, rs
    sample = psql_scalar(
        f"SELECT feature_json::text FROM tb_feature_dataset WHERE dataset_version_id = '{rs.get('dataset_version_id')}' "
        "AND feature_json->>'demand_lag_24h' IS NOT NULL LIMIT 1"
    )
    assert sample, "CODE feature demand_lag_24h missing"
    print("  [ok] CODE-only Feature Set build unchanged")


def test_result_summary_fields() -> None:
    _, fname = create_publish_recipe("RAW_COLUMN")
    fsid = create_fs_with_features([fname])
    res = run_build(fsid)
    rs = res.get("result_summary") or {}
    for key in (
        "code_feature_count",
        "template_feature_count",
        "template_generated_feature_count",
        "recipe_engine_version",
    ):
        assert key in rs, rs
    print("  [ok] result_summary template fields")


def main() -> int:
    print("test_feature_recipe_build.py")
    ensure_calendar_seed()
    try:
        test_registration_build_supported()
        test_raw_column_build()
        test_date_part_build()
        test_lag_build()
        test_rolling_mean_build()
        test_rolling_sum_build()
        test_lineage_template()
        test_missing_source_column_warning()
        test_code_only_unchanged()
        test_result_summary_fields()
    except Exception as exc:
        print(f"  [FAIL] {exc}", file=sys.stderr)
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
