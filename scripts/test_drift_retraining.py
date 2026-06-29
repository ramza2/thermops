#!/usr/bin/env python3
"""Drift 감지 및 재학습 후보 자동화 테스트 (P1-1)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

ORIGINAL_THRESHOLD = "10.0"
TEST_THRESHOLD = "0.01"


def api(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict:
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
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def set_config(key: str, value: str) -> None:
    api("PUT", f"/system-configs/{key}", {"config_value": value})


def main() -> int:
    print(f"THERMOps drift/retraining test ({API_BASE})")
    restored = False
    try:
        versions = api("GET", "/models/heat_demand_lightgbm/versions")
        mv_id = versions[0]["model_version_id"] if versions else None
        if not mv_id:
            versions = api("GET", "/models/heat_demand_lgbm/versions")
            mv_id = versions[0]["model_version_id"] if versions else None
        if not mv_id:
            raise RuntimeError("model_version_id를 찾을 수 없습니다. P0 학습을 먼저 실행하세요.")

        body = {
            "model_version_id": mv_id,
            "feature_set_id": "FS-TPL-LAG-ROLL",
            "baseline_start_at": "2026-05-22T00:00:00",
            "baseline_end_at": "2026-06-05T23:00:00",
            "current_start_at": "2026-06-06T00:00:00",
            "current_end_at": "2026-06-20T23:00:00",
        }

        result = api("POST", "/drift-checks", body)
        report_id = result.get("drift_report_id")
        if not report_id:
            raise RuntimeError(f"drift_report_id missing: {result}")
        print(f"  [drift-check] report_id={report_id} overall={result.get('overall_drift_status')}")

        if not result.get("metric_summary"):
            raise RuntimeError("metric_summary missing in drift-check response")

        reports_page = api("GET", "/drift-reports?page=1&size=50")
        found = any(r.get("drift_report_id") == report_id for r in reports_page.get("items", []))
        if not found:
            raise RuntimeError("drift report not found in list")
        print("  [drift-reports] list OK")

        detail = api("GET", f"/drift-reports/{report_id}")
        if not detail.get("metric_summary_json") and not detail.get("drift_score_json"):
            raise RuntimeError("drift report detail missing summary")
        print("  [drift-reports] detail OK")

        candidate_id = result.get("retraining_candidate_id")
        if not candidate_id:
            print("  [candidate] none from normal thresholds — lowering retraining_mape_threshold for test")
            set_config("retraining_mape_threshold", TEST_THRESHOLD)
            restored = True
            forced = api("POST", "/drift-checks", {**body, "force_candidate": True})
            candidate_id = forced.get("retraining_candidate_id")
            if not candidate_id and forced.get("created_retraining_candidates", 0) < 1:
                candidates_before = api("GET", "/retraining-candidates")
                pending = [c for c in candidates_before if c.get("status") in ("PENDING", "REVIEW")]
                if pending:
                    candidate_id = pending[0]["candidate_id"]
            if not candidate_id:
                raise RuntimeError("retraining candidate was not created even with force_candidate")

        candidates = api("GET", "/retraining-candidates")
        match = next((c for c in candidates if c["candidate_id"] == candidate_id), None)
        if not match:
            raise RuntimeError(f"candidate {candidate_id} not in list")
        print(f"  [candidates] found {candidate_id} status={match.get('status')}")

        if match.get("status") in ("PENDING", "REVIEW"):
            approved = api("POST", f"/retraining-candidates/{candidate_id}/approve", {})
            if approved.get("status") != "APPROVED":
                raise RuntimeError(f"approve failed: {approved}")
            print("  [approve] OK")

            rejected_id = candidate_id
            api("POST", f"/retraining-candidates/{rejected_id}/reject", {})
            rej = api("GET", "/retraining-candidates")
            rej_row = next(c for c in rej if c["candidate_id"] == rejected_id)
            if rej_row.get("status") != "REJECTED":
                raise RuntimeError("reject failed")
            print("  [reject] OK")
        else:
            print(f"  [approve/reject] skip (status={match.get('status')})")

        print("PASSED")
        return 0
    except urllib.error.URLError as exc:
        print(f"FAILED: cannot reach API ({exc})", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if restored:
            try:
                set_config("retraining_mape_threshold", ORIGINAL_THRESHOLD)
                print("  [cleanup] retraining_mape_threshold restored")
            except Exception as exc:
                print(f"  [WARN] failed to restore threshold: {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
