#!/usr/bin/env python3
"""Feature 메타데이터·명칭·Feature Set·feature_json 정합성 검증."""

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
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    FS_COMFORT_ID,
    FS_LAG_ROLL_ID,
    FS_TWO_STAGE_ID,
    ensure_test_platform,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

OFFICIAL_FEATURES = frozenset({
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_ma_24h",
    "demand_ma_168h",
    "temperature_diff_24h",
    "heating_degree_days",
    "cooling_degree_days",
})

LEGACY_ALIASES = frozenset({
    "lag_24h_demand",
    "lag_168h_demand",
    "rolling_24h_avg",
})

FORBIDDEN_IN_TPL = frozenset({
    "demand_rolling_24h_avg",
    "hdd",
    "cdd",
    "rolling_mean_24h",
    "lag_24h",
    "lag_168h",
})

TPL_SETS = (
    FS_LAG_ROLL_ID,
    FS_COMFORT_ID,
    FS_TWO_STAGE_ID,
)


def api(method: str, path: str) -> dict | list:
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


def _load_all_computed_features() -> set[str]:
    source = (ROOT / "ml" / "features.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ALL_COMPUTED_FEATURES":
                    return set(ast.literal_eval(node.value))
    raise RuntimeError("ALL_COMPUTED_FEATURES not found in ml/features.py")


def check_ml_computed_features() -> None:
    computed = _load_all_computed_features()
    missing = sorted(OFFICIAL_FEATURES - computed)
    if missing:
        raise RuntimeError(f"ml/features.py ALL_COMPUTED_FEATURES missing: {missing}")
    print(f"  [ml] ALL_COMPUTED_FEATURES includes {len(OFFICIAL_FEATURES)} official names")


def check_tpl_feature_sets(sets: list[dict]) -> dict[str, list[str]]:
    by_id = {s["feature_set_id"]: s.get("features") or [] for s in sets}
    for fs_id in TPL_SETS:
        if fs_id not in by_id:
            raise RuntimeError(f"Feature Set not found: {fs_id}")
        names = by_id[fs_id]
        bad = [n for n in names if n in FORBIDDEN_IN_TPL]
        if bad:
            raise RuntimeError(f"{fs_id} contains forbidden names: {bad}")
        print(f"  [set] {fs_id}: {len(names)} features, no forbidden names")
    return by_id


def ensure_feature_build(feature_set_id: str) -> str:
    """Feature build 실행 후 dataset_version_id 반환."""
    qs = urllib.parse.urlencode({"feature_set_id": feature_set_id})
    build = api("POST", f"/feature-build-jobs?{qs}")
    if build.get("status") not in ("SUCCESS", "WARNING"):
        raise RuntimeError(f"feature build failed for {feature_set_id}: {build}")
    dsv = build.get("dataset_version_id")
    if not dsv:
        raise RuntimeError(f"dataset_version_id missing for {feature_set_id}")
    print(f"  [build] {feature_set_id} -> {dsv} inserted={build.get('inserted_count')}")
    return dsv


def sample_feature_json(feature_set_id: str, dataset_version_id: str | None = None) -> dict:
    where = f"feature_json->>'feature_set_id' = '{feature_set_id}'"
    if dataset_version_id:
        where += f" AND dataset_version_id = '{dataset_version_id}'"
    sql = f"""
    SELECT feature_json::text FROM tb_feature_dataset
    WHERE {where}
    ORDER BY feature_id DESC
    LIMIT 1
    """
    text = psql_scalar(sql)
    if not text:
        return {}
    return json.loads(text)


def assert_keys_in_json(sample: dict, keys: list[str], context: str) -> None:
    missing = [k for k in keys if k not in sample]
    nulls = [k for k in keys if k in sample and sample[k] is None]
    if missing:
        raise RuntimeError(f"{context}: missing keys {missing}")
    if nulls:
        raise RuntimeError(f"{context}: null values for {nulls}")
    print(f"  [json] {context}: OK {keys}")


def verify_feature_json_samples(by_id: dict[str, list[str]]) -> None:
    # LAG-ROLL: build or reuse
    lag_roll = FS_LAG_ROLL_ID
    sample = sample_feature_json(lag_roll)
    if not sample or not all(k in sample for k in ("demand_lag_24h", "demand_ma_168h")):
        dsv = ensure_feature_build(lag_roll)
        sample = sample_feature_json(lag_roll, dsv)
    assert_keys_in_json(
        sample,
        ["demand_lag_24h", "demand_lag_168h", "demand_ma_24h", "demand_ma_168h"],
        lag_roll,
    )

    # TWO-STAGE: temperature_diff + comfort
    two_stage = FS_TWO_STAGE_ID
    sample_ts = sample_feature_json(two_stage)
    if not sample_ts or "temperature_diff_24h" not in sample_ts:
        dsv = ensure_feature_build(two_stage)
        sample_ts = sample_feature_json(two_stage, dsv)
    assert_keys_in_json(sample_ts, ["temperature_diff_24h"], two_stage)
    assert_keys_in_json(
        sample_ts,
        ["heating_degree_days", "cooling_degree_days"],
        f"{two_stage} (comfort)",
    )

    # COMFORT set list includes HDD/CDD even if TWO-STAGE already built
    comfort_names = by_id.get(FS_COMFORT_ID, [])
    for name in ("heating_degree_days", "cooling_degree_days"):
        if name not in comfort_names:
            raise RuntimeError(f"{FS_COMFORT_ID} missing {name} in features list")
    print(f"  [set] {FS_COMFORT_ID} includes heating_degree_days, cooling_degree_days")


def main() -> int:
    print(f"THERMOps feature metadata consistency test ({API_BASE})")
    try:
        ensure_test_platform()
        check_ml_computed_features()

        sets = api("GET", "/feature-sets")
        if not isinstance(sets, list):
            raise RuntimeError("unexpected /feature-sets response")
        by_id = check_tpl_feature_sets(sets)

        # Feature Set 멤버는 공식명 또는 (TPL 외) 허용 — TPL에는 forbidden 검사 완료
        for fs_id in TPL_SETS:
            for name in by_id[fs_id]:
                if name in FORBIDDEN_IN_TPL:
                    raise RuntimeError(f"forbidden name in {fs_id}: {name}")

        verify_feature_json_samples(by_id)

        print("\nPASSED: feature metadata consistency")
        return 0
    except (urllib.error.URLError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
