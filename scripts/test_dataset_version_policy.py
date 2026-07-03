#!/usr/bin/env python3
"""Dataset Version(학습 데이터 버전) 운영 정책 테스트 — R9-S2."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    FS_LAG_ROLL_ID,
    FS_MINIMAL_ID,
    ensure_csv_ingested,
    ensure_feature_dataset_built,
    ensure_test_platform,
    psql_run,
    psql_scalar,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_LAG_ROLL_ID)


def api(method: str, path: str, body: dict | None = None, timeout: int = 180) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def api_expect_fail(method: str, path: str, body: dict | None = None) -> int:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
        return 0
    except urllib.error.HTTPError as exc:
        return exc.code


def cleanup_test_versions(feature_set_id: str) -> None:
    psql_run(
        f"""
        DELETE FROM tb_dataset_version
        WHERE feature_set_id = '{feature_set_id}'
          AND (
            dataset_version_id LIKE 'DSV-TEST-PARTIAL-%'
            OR dataset_version_id LIKE 'DSV-TEST-TEMP-%'
            OR dataset_version_id LIKE 'DSV-TEST-FAIL-%'
            OR dataset_version_id LIKE 'DSV-TEST-CAND2-%'
          );
        """
    )


def latest_dsv_for_fs(feature_set_id: str) -> str:
    dsv = psql_scalar(
        f"""
        SELECT dataset_version_id FROM tb_dataset_version
        WHERE feature_set_id = '{feature_set_id}'
        ORDER BY COALESCE(record_count, 0) DESC, created_at DESC
        LIMIT 1
        """
    )
    if not dsv:
        dsv = psql_scalar(
            f"""
            SELECT fd.dataset_version_id FROM tb_feature_dataset fd
            WHERE fd.feature_json->>'feature_set_id' = '{feature_set_id}'
            GROUP BY fd.dataset_version_id
            ORDER BY COUNT(*) DESC LIMIT 1
            """
        )
    if not dsv:
        raise RuntimeError(f"No dataset version for {feature_set_id}")
    return dsv


def insert_partial_shadow(full_dsv: str, feature_set_id: str) -> str:
    partial_id = f"DSV-TEST-PARTIAL-{full_dsv[-6:]}"
    psql_run(
        f"""
        DELETE FROM tb_dataset_version WHERE dataset_version_id = '{partial_id}';
        INSERT INTO tb_dataset_version (
            dataset_version_id, dataset_type, feature_set_id, record_count, feature_count,
            dataset_version_role, dataset_version_status, build_scope,
            is_primary, is_training_ready, is_serving_ready,
            created_at, created_by
        )
        SELECT
            '{partial_id}', dataset_type, '{feature_set_id}', 24, feature_count,
            'PARTIAL', 'PARTIAL', 'PARTIAL',
            false, false, false,
            NOW() + interval '1 minute', 'policy_test'
        FROM tb_dataset_version WHERE dataset_version_id = '{full_dsv}';
        """
    )
    return partial_id


def reset_roles(feature_set_id: str) -> None:
    psql_run(
        f"""
        UPDATE tb_dataset_version
        SET is_primary = false,
            dataset_version_role = CASE
                WHEN dataset_version_role = 'PRIMARY' THEN 'CANDIDATE'
                ELSE dataset_version_role
            END
        WHERE feature_set_id = '{feature_set_id}';
        """
    )


def main() -> int:
    print(f"THERMOps dataset version policy test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            count = int(psql_scalar("SELECT COUNT(*) FROM tb_dataset_version") or "0")
            items = api("GET", "/dataset-versions")
            assert count == 0, f"expected 0 dataset versions, got {count}"
            assert len(items) == 0, items
            print("  [ok] clean DB dataset-versions empty")
            print("PASS")
            return 0

        ensure_test_platform()
        ensure_csv_ingested(api)
        ensure_feature_dataset_built(api, FEATURE_SET_ID, timeout=300)
        cleanup_test_versions(FEATURE_SET_ID)

        empty_fs_items = api("GET", f"/dataset-versions?feature_set_id={FS_MINIMAL_ID}")
        assert isinstance(empty_fs_items, list)
        print(f"  [ok] minimal feature set versions={len(empty_fs_items)}")

        full_dsv = latest_dsv_for_fs(FEATURE_SET_ID)
        psql_run(
            f"""
            UPDATE tb_dataset_version dv
            SET feature_set_id = '{FEATURE_SET_ID}'
            FROM (
                SELECT DISTINCT dataset_version_id AS dsv_id
                FROM tb_feature_dataset
                WHERE feature_json->>'feature_set_id' = '{FEATURE_SET_ID}'
            ) sub
            WHERE dv.dataset_version_id = sub.dsv_id
              AND dv.feature_set_id IS NULL;
            UPDATE tb_dataset_version dv
            SET dataset_version_role = 'ARCHIVED',
                dataset_version_status = 'ARCHIVED',
                is_primary = false,
                is_training_ready = false,
                is_serving_ready = false
            WHERE dv.dataset_version_id IN (
                SELECT DISTINCT dataset_version_id
                FROM tb_feature_dataset
                WHERE feature_json->>'feature_set_id' = '{FEATURE_SET_ID}'
            )
              AND dv.dataset_version_id != '{full_dsv}'
              AND dv.dataset_version_id NOT LIKE 'DSV-TEST-PARTIAL-%'
              AND dv.dataset_version_id NOT LIKE 'DSV-TEST-TEMP-%'
              AND dv.dataset_version_id NOT LIKE 'DSV-TEST-FAIL-%'
              AND dv.dataset_version_id NOT LIKE 'DSV-TEST-CAND2-%';
            UPDATE tb_dataset_version
            SET dataset_version_role = 'CANDIDATE',
                dataset_version_status = 'TRAINING_READY',
                build_scope = 'FULL',
                is_training_ready = true,
                is_serving_ready = true,
                record_count = GREATEST(COALESCE(record_count, 0), 1000),
                is_primary = false
            WHERE dataset_version_id = '{full_dsv}';
            """
        )
        partial_id = insert_partial_shadow(full_dsv, FEATURE_SET_ID)

        preview = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        selected_id = (preview.get("selected") or {}).get("dataset_version_id")
        assert selected_id == full_dsv, f"expected full {full_dsv}, got {selected_id} ({preview})"
        assert preview["selection_reason"] in {
            "CANDIDATE_QUALITY_BEST",
            "PRIMARY_TRAINING_READY",
            "FALLBACK_RECORD_COUNT",
        }
        excluded = {e["dataset_version_id"]: e["reason"] for e in preview.get("excluded_candidates", [])}
        assert partial_id in excluded, excluded
        assert "PARTIAL" in excluded[partial_id]
        print(f"  [ok] partial excluded; full selected ({preview['selection_reason']})")

        reset_roles(FEATURE_SET_ID)
        psql_run(
            f"""
            UPDATE tb_dataset_version SET is_primary = false, dataset_version_role = 'CANDIDATE',
                dataset_version_status = 'TRAINING_READY', record_count = 5000,
                is_training_ready = true, build_scope = 'FULL', created_at = NOW() - interval '1 hour'
            WHERE dataset_version_id = '{full_dsv}';
            UPDATE tb_dataset_version SET is_primary = false, dataset_version_role = 'PARTIAL',
                dataset_version_status = 'PARTIAL', record_count = 9000,
                is_training_ready = false, build_scope = 'PARTIAL',
                created_at = NOW() + interval '5 minutes'
            WHERE dataset_version_id = '{partial_id}';
            """
        )
        preview2 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        assert preview2["selected"]["dataset_version_id"] == full_dsv, preview2
        print("  [ok] R9-S1 regression: newer high-count PARTIAL excluded; FULL CANDIDATE selected")

        psql_run(
            f"""
            UPDATE tb_dataset_version SET is_primary = true, dataset_version_role = 'PRIMARY',
                dataset_version_status = 'TRAINING_READY', record_count = 5000,
                is_training_ready = true, is_serving_ready = true, build_scope = 'FULL'
            WHERE dataset_version_id = '{full_dsv}';
            """
        )
        preview3 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        assert preview3["selected"]["dataset_version_id"] == full_dsv
        assert preview3["selection_reason"] == "PRIMARY_TRAINING_READY"
        print("  [ok] PRIMARY selected over CANDIDATE")

        temp_id = f"DSV-TEST-TEMP-{full_dsv[-6:]}"
        psql_run(
            f"""
            DELETE FROM tb_dataset_version WHERE dataset_version_id = '{temp_id}';
            INSERT INTO tb_dataset_version (
                dataset_version_id, dataset_type, feature_set_id, record_count,
                dataset_version_role, dataset_version_status, build_scope,
                is_primary, is_training_ready, is_serving_ready, created_at, created_by
            ) VALUES (
                '{temp_id}', 'FEATURE', '{FEATURE_SET_ID}', 500,
                'TEMPORARY', 'BUILD_SUCCESS', 'PARTIAL',
                false, true, true, NOW() + interval '2 minutes', 'policy_test'
            );
            """
        )
        preview4 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        assert preview4["selected"]["dataset_version_id"] == full_dsv
        print("  [ok] TEMPORARY excluded from auto selection")

        explicit_partial = insert_partial_shadow(full_dsv, FEATURE_SET_ID)
        explicit = api(
            "POST",
            "/dataset-versions/selection-preview",
            {
                "feature_set_id": FEATURE_SET_ID,
                "purpose": "TRAINING",
                "explicit_dataset_version_id": explicit_partial,
            },
        )
        assert explicit["selection_reason"] == "EXPLICIT_SELECTED"
        assert explicit.get("warnings"), explicit
        print("  [ok] explicit PARTIAL returns warning")

        api("POST", f"/dataset-versions/{partial_id}/archive", {"reason": "test archive"})
        preview5 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        excluded5 = {e["dataset_version_id"] for e in preview5.get("excluded_candidates", [])}
        assert partial_id in excluded5
        print("  [ok] ARCHIVED excluded after archive")

        failed_id = f"DSV-TEST-FAIL-{full_dsv[-6:]}"
        psql_run(
            f"""
            DELETE FROM tb_dataset_version WHERE dataset_version_id = '{failed_id}';
            INSERT INTO tb_dataset_version (
                dataset_version_id, dataset_type, feature_set_id, record_count,
                dataset_version_role, dataset_version_status, build_scope,
                is_primary, is_training_ready, is_serving_ready, created_at, created_by
            ) VALUES (
                '{failed_id}', 'FEATURE', '{FEATURE_SET_ID}', 0,
                'TEMPORARY', 'BUILD_FAILED', 'UNKNOWN',
                false, false, false, NOW() + interval '3 minutes', 'policy_test'
            );
            """
        )
        preview6 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        ex6 = {e["dataset_version_id"]: e["reason"] for e in preview6.get("excluded_candidates", [])}
        assert failed_id in ex6
        print("  [ok] BUILD_FAILED excluded")

        code = api_expect_fail(
            "POST",
            "/dataset-versions/selection-preview",
            {
                "feature_set_id": FEATURE_SET_ID,
                "purpose": "TRAINING",
                "explicit_dataset_version_id": partial_id,
            },
        )
        assert code == 400, code
        print("  [ok] explicit ARCHIVED blocked")

        reset_roles(FEATURE_SET_ID)
        psql_run(
            f"""
            UPDATE tb_dataset_version SET is_primary = false, dataset_version_role = 'CANDIDATE',
                dataset_version_status = 'TRAINING_READY', is_training_ready = true,
                quality_score = 0.9, record_count = 3000
            WHERE dataset_version_id = '{full_dsv}';
            """
        )
        cand2 = f"DSV-TEST-CAND2-{full_dsv[-6:]}"
        psql_run(
            f"""
            DELETE FROM tb_dataset_version WHERE dataset_version_id = '{cand2}';
            INSERT INTO tb_dataset_version (
                dataset_version_id, dataset_type, feature_set_id, record_count, quality_score,
                dataset_version_role, dataset_version_status, build_scope,
                is_primary, is_training_ready, is_serving_ready, created_at, created_by
            ) VALUES (
                '{cand2}', 'FEATURE', '{FEATURE_SET_ID}', 2000, 0.5,
                'CANDIDATE', 'TRAINING_READY', 'FULL',
                false, true, true, NOW(), 'policy_test'
            );
            """
        )
        preview7 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        assert preview7["selected"]["dataset_version_id"] == full_dsv
        print("  [ok] CANDIDATE quality/record_count preference")

        psql_run(
            f"""
            UPDATE tb_dataset_version SET is_primary = false,
                dataset_version_role = 'LEGACY', dataset_version_status = 'BUILD_SUCCESS',
                is_training_ready = true, is_serving_ready = true, quality_score = NULL
            WHERE dataset_version_id IN ('{full_dsv}', '{cand2}');
            UPDATE tb_dataset_version SET record_count = 8000, created_at = NOW() - interval '1 day'
            WHERE dataset_version_id = '{full_dsv}';
            UPDATE tb_dataset_version SET record_count = 100, build_scope = 'FULL', created_at = NOW()
            WHERE dataset_version_id = '{cand2}';
            """
        )
        preview8 = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "TRAINING"},
        )
        assert preview8["selected"]["dataset_version_id"] == full_dsv
        assert preview8["selection_reason"] == "FALLBACK_RECORD_COUNT"
        print("  [ok] fallback record_count DESC with PARTIAL roles excluded")

        api("POST", f"/dataset-versions/{full_dsv}/set-primary")
        detail = api("GET", f"/dataset-versions/{full_dsv}")
        assert detail["is_primary"] is True
        primaries = psql_scalar(
            f"SELECT COUNT(*) FROM tb_dataset_version WHERE feature_set_id = '{FEATURE_SET_ID}' AND is_primary"
        )
        assert int(primaries) == 1
        print("  [ok] set-primary enforces single primary")

        cleanup = api(
            "POST",
            "/dataset-versions/cleanup-preview",
            {"feature_set_id": FEATURE_SET_ID, "roles": ["TEMPORARY", "PARTIAL"], "dry_run": True},
        )
        assert cleanup.get("dry_run") is True
        assert cleanup.get("count", 0) >= 0
        print(f"  [ok] cleanup-preview dry_run count={cleanup.get('count')}")

        list_all = api("GET", f"/dataset-versions?feature_set_id={FEATURE_SET_ID}")
        assert isinstance(list_all, list) and len(list_all) > 0
        print(f"  [ok] list API rows={len(list_all)}")

        pred_preview = api(
            "POST",
            "/dataset-versions/selection-preview",
            {"feature_set_id": FEATURE_SET_ID, "purpose": "PREDICTION"},
        )
        assert pred_preview.get("selected")
        print(f"  [ok] prediction selection ({pred_preview['selection_reason']})")

        print("PASS")
        return 0
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
