#!/usr/bin/env python3
"""Feature Registry·Lineage API 및 저장 검증."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

OFFICIAL_FEATURES = (
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_ma_24h",
    "demand_ma_168h",
    "temperature_diff_24h",
    "heating_degree_days",
    "cooling_degree_days",
)

FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-LAG-ROLL")


def api(method: str, path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
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
            return str(row[0]).strip() if row and row[0] is not None else ""
    finally:
        conn.close()


def _load_all_computed_features() -> list[str]:
    source = (ROOT / "ml" / "features.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ALL_COMPUTED_FEATURES":
                    return list(ast.literal_eval(node.value))
    raise RuntimeError("ALL_COMPUTED_FEATURES not found in ml/features.py")


def check_registry_module() -> None:
    sys.path.insert(0, str(ROOT / "ml"))
    import feature_registry as reg  # noqa: WPS433

    computed = _load_all_computed_features()
    reg.assert_covers_computed_features(computed)
    for name in OFFICIAL_FEATURES:
        spec = reg.get_feature_spec(name)
        if not spec:
            raise RuntimeError(f"registry missing official feature: {name}")
        if spec.calc_method != "CODE":
            raise RuntimeError(f"{name}: calc_method must be CODE")
    print(f"  [ml] registry covers {len(computed)} computed features")


def check_registry_api() -> None:
    payload = api("GET", "/feature-registry")
    names = {f["feature_name"] for f in payload.get("features", [])}
    missing = [n for n in OFFICIAL_FEATURES if n not in names]
    if missing:
        raise RuntimeError(f"{API_BASE}/feature-registry missing: {missing}")

    spec = api("GET", "/feature-registry/demand_lag_24h")
    if spec.get("lookback_hours") != 24 or not spec.get("requires_shift"):
        raise RuntimeError(f"unexpected demand_lag_24h spec: {spec}")
    if "tb_heat_demand_actual" not in (spec.get("source_tables") or []):
        raise RuntimeError("demand_lag_24h source_tables missing heat table")
    print(f"  [api] {API_BASE}/feature-registry OK")


def run_feature_build() -> tuple[str, str]:
    qs = urllib.parse.urlencode({"feature_set_id": FEATURE_SET_ID})
    build = api("POST", f"/feature-build-jobs?{qs}")
    if build.get("status") not in ("SUCCESS", "WARNING"):
        raise RuntimeError(f"feature build failed: {build}")
    dsv = build.get("dataset_version_id")
    job_id = build.get("job_id")
    if not dsv or not job_id:
        raise RuntimeError("build response missing dataset_version_id or job_id")
    lineage_count = build.get("lineage_count")
    if lineage_count is None:
        raise RuntimeError("build response missing lineage_count")
    print(f"  [build] {FEATURE_SET_ID} -> {dsv} lineage_count={lineage_count}")
    return dsv, job_id


def check_lineage_api(dsv: str, job_id: str, expected_features: list[str]) -> None:
    by_dsv = api("GET", f"/feature-lineage?dataset_version_id={urllib.parse.quote(dsv)}")
    items = by_dsv.get("items") or []
    if by_dsv.get("lineage_count") != len(items):
        raise RuntimeError("lineage_count mismatch")
    names = {i["feature_name"] for i in items}
    for name in expected_features:
        if name not in names:
            raise RuntimeError(f"lineage missing feature {name} for {dsv}")

    by_job = api("GET", f"/feature-build-jobs/{job_id}/lineage")
    if by_job.get("lineage_count") != len(items):
        raise RuntimeError("job lineage count mismatch")
    if by_job.get("dataset_version_id") != dsv:
        raise RuntimeError("job lineage dataset_version_id mismatch")

    row = items[0]
    for key in ("calc_method", "calc_expression", "source_tables", "feature_set_id"):
        if key not in row:
            raise RuntimeError(f"lineage row missing {key}")
    print(f"  [api] lineage {len(items)} rows for {dsv}")


def check_lineage_db(dsv: str, job_id: str) -> None:
    count = psql_scalar(
        f"SELECT COUNT(*) FROM tb_feature_lineage WHERE dataset_version_id = '{dsv}'"
    )
    if not count or int(count) < 1:
        raise RuntimeError(f"tb_feature_lineage empty for {dsv}")
    job_match = psql_scalar(
        f"SELECT COUNT(*) FROM tb_feature_lineage WHERE feature_build_job_id = '{job_id}'"
    )
    if int(job_match) != int(count):
        raise RuntimeError("lineage job_id row count mismatch")
    print(f"  [db] tb_feature_lineage {count} rows")


def resolve_feature_set() -> list[str]:
    sets = api("GET", "/feature-sets")
    for fs in sets:
        if fs.get("feature_set_id") == FEATURE_SET_ID:
            return fs.get("features") or []
    raise RuntimeError(f"Feature Set not found: {FEATURE_SET_ID}")


def main() -> int:
    print(f"THERMOps feature lineage test ({API_BASE})")
    try:
        check_registry_module()
        check_registry_api()
        feature_names = resolve_feature_set()
        dsv, job_id = run_feature_build()
        check_lineage_api(dsv, job_id, feature_names)
        check_lineage_db(dsv, job_id)
        print("\nPASSED: feature registry & lineage")
        return 0
    except (urllib.error.URLError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
