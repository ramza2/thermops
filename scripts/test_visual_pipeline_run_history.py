#!/usr/bin/env python3
"""R11-S8-2 Visual Pipeline Run History — read-only list/detail tests.

No migration. Uses sample-external fixtures. Not in quick group by default.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
_BACKEND = _ROOT / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://thermops:thermops@localhost:5432/thermops",
    ),
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

from test_fixtures import ensure_test_standard_datasets, psql_run, psql_scalar  # noqa: E402
from test_visual_pipeline_materialization import archive_pipeline  # noqa: E402
from test_visual_pipeline_run_worker import setup_compiled_materialized  # noqa: E402


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def _psql_exec(sql: str) -> None:
    psql_run(sql)


def api(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    expect_fail: bool = False,
) -> dict | list:
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
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                parsed = {"detail": detail}
            if isinstance(parsed, dict):
                parsed["_http_status"] = exc.code
            return parsed
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from None
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def _snapshot_runs(pipeline_id: str) -> list[tuple[str, str, str, str, str]]:
    """(visual_run_id, run_status, finished_at, attempt_count, error_message)."""
    raw = _psql(
        "SELECT COALESCE(string_agg("
        "visual_run_id || '|' || COALESCE(run_status,'') || '|' || "
        "COALESCE(finished_at::text,'') || '|' || COALESCE(attempt_count::text,'0') || '|' || "
        "COALESCE(replace(error_message, E'\\n', ' '), ''), "
        "E'\\n' ORDER BY created_at DESC), '') "
        f"FROM tb_visual_pipeline_run WHERE pipeline_id = '{pipeline_id}'"
    )
    if not raw:
        return []
    out = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 4)
        while len(parts) < 5:
            parts.append("")
        out.append((parts[0], parts[1], parts[2], parts[3], parts[4]))
    return out


def _assert_readonly(pipeline_id: str, before: list[tuple[str, str, str, str, str]]) -> None:
    after = _snapshot_runs(pipeline_id)
    if len(before) != len(after):
        raise AssertionError(f"run count changed: {len(before)} -> {len(after)}")
    if before != after:
        raise AssertionError(f"run snapshot mutated:\n before={before}\n after={after}")


def _seed_runs(pipeline_id: str) -> list[str]:
    """Insert two synthetic terminal rows without executing run_load."""
    ids = []
    for i, (status, mode) in enumerate(
        (("FAILED", "MANUAL"), ("SUCCESS", "SCHEDULED")),
        start=1,
    ):
        vid = f"VPR-HIST{uuid4().hex[:8].upper()}"
        ids.append(vid)
        act = f"VPA-HIST{uuid4().hex[:6].upper()}" if mode == "SCHEDULED" else "NULL"
        act_sql = f"'{act}'" if act != "NULL" else "NULL"
        sched = "NOW() - INTERVAL '1 hour'" if mode == "SCHEDULED" else "NULL"
        err_sql = "NULL" if status == "SUCCESS" else f"'hist fail {i}'"
        _psql_exec(
            "INSERT INTO tb_visual_pipeline_run ("
            "visual_run_id, pipeline_id, compile_result_id, materialization_result_id, "
            "mode, execution_mode, run_status, issues_json, error_message, "
            "activation_id, scheduled_for, attempt_count, created_at, started_at, finished_at"
            ") VALUES ("
            f"'{vid}', '{pipeline_id}', 'VPC-HIST', 'VPM-HIST', "
            f"'{mode}', 'BACKGROUND', '{status}', "
            "'[{\"severity\":\"ERROR\",\"code\":\"HIST_TEST\",\"message\":\"hist\"}]'::jsonb, "
            f"{err_sql}, "
            f"{act_sql}, {sched}, {i}, "
            f"NOW() - INTERVAL '{i} minutes', NOW() - INTERVAL '{i} minutes', NOW()"
            ")"
        )
    return ids


def main() -> None:
    ensure_test_standard_datasets()
    pipeline_id = None
    try:
        setup = setup_compiled_materialized(f"S82-HIST-{uuid4().hex[:6]}")
        pipeline_id = setup["pipeline_id"]
        print(f"  [ok] fixture pipeline={pipeline_id}")

        seeded = _seed_runs(pipeline_id)
        print(f"  [ok] seeded runs={seeded}")

        # --- list default ---
        listed = api("GET", f"/visual-pipelines/{pipeline_id}/runs?limit=20")
        assert isinstance(listed, dict), listed
        assert "items" in listed and "limit" in listed, listed
        assert "offset" in listed and "total" in listed, listed
        assert listed["offset"] == 0
        assert listed["total"] >= 2
        items = listed["items"]
        assert len(items) >= 2
        # created_at desc — first seeded SUCCESS (1 min ago) then FAILED (2 min) wait:
        # we insert FAILED with i=1 (1 min), SUCCESS with i=2 (2 min) — so FAILED is newer
        assert items[0]["visual_run_id"] == seeded[0], items[0]
        assert items[0]["run_status"] == "FAILED"
        assert "issues_count" in items[0]
        assert items[0]["issues_count"] >= 1
        print("  [ok] list default sort created_at desc + issues_count")

        # --- status filter ---
        failed = api("GET", f"/visual-pipelines/{pipeline_id}/runs?run_status=FAILED&limit=10")
        assert all(i["run_status"] == "FAILED" for i in failed["items"]), failed
        assert failed["total"] >= 1
        print("  [ok] status filter FAILED")

        # --- mode filter ---
        scheduled = api("GET", f"/visual-pipelines/{pipeline_id}/runs?mode=SCHEDULED&limit=10")
        assert all(i.get("mode") == "SCHEDULED" for i in scheduled["items"]), scheduled
        assert scheduled["total"] >= 1
        print("  [ok] mode filter SCHEDULED")

        # --- limit/offset ---
        page0 = api("GET", f"/visual-pipelines/{pipeline_id}/runs?limit=1&offset=0")
        page1 = api("GET", f"/visual-pipelines/{pipeline_id}/runs?limit=1&offset=1")
        assert page0["limit"] == 1 and page0["offset"] == 0
        assert page1["offset"] == 1
        assert len(page0["items"]) == 1 and len(page1["items"]) == 1
        assert page0["items"][0]["visual_run_id"] != page1["items"][0]["visual_run_id"]
        print("  [ok] limit/offset")

        # --- invalid filter ---
        bad = api(
            "GET",
            f"/visual-pipelines/{pipeline_id}/runs?run_status=NOPE",
            expect_fail=True,
        )
        assert bad.get("_http_status") == 400, bad
        print("  [ok] invalid run_status → 400")

        # --- detail ---
        detail = api("GET", f"/visual-pipelines/{pipeline_id}/runs/{seeded[0]}")
        for key in (
            "visual_run_id",
            "pipeline_id",
            "run_status",
            "created_at",
            "attempt_count",
            "issues_count",
            "claimed_by",
            "heartbeat_at",
            "dedup_key",
        ):
            assert key in detail, f"missing {key} in {detail.keys()}"
        assert detail["run_status"] == "FAILED"
        assert detail["issues_count"] >= 1
        # no full request_json dump
        assert "request_json" not in detail
        print("  [ok] detail additive fields")

        # --- 404 wrong pipeline / missing ---
        nf = api(
            "GET",
            f"/visual-pipelines/{pipeline_id}/runs/VPR-DOES-NOT-EXIST",
            expect_fail=True,
        )
        assert nf.get("_http_status") == 404, nf
        wrong_pipe = api(
            "GET",
            f"/visual-pipelines/PIPE-DOES-NOT-EXIST/runs/{seeded[0]}",
            expect_fail=True,
        )
        assert wrong_pipe.get("_http_status") == 404, wrong_pipe
        print("  [ok] detail 404")

        # --- no mutation ---
        before = _snapshot_runs(pipeline_id)
        api("GET", f"/visual-pipelines/{pipeline_id}/runs?limit=50")
        api("GET", f"/visual-pipelines/{pipeline_id}/runs/{seeded[0]}")
        api("GET", f"/visual-pipelines/{pipeline_id}/runs?run_status=FAILED&mode=MANUAL")
        _assert_readonly(pipeline_id, before)
        print("  [ok] list/detail read-only (count/status/finished_at/attempt/error)")

        # --- scheduled provenance on summary ---
        sched_item = next(i for i in listed["items"] if i["visual_run_id"] == seeded[1])
        assert sched_item.get("mode") == "SCHEDULED"
        assert sched_item.get("activation_id")
        assert sched_item.get("scheduled_for")
        print("  [ok] scheduled provenance on list item")

        print("PASS Visual Pipeline Run History")
    finally:
        if pipeline_id:
            try:
                archive_pipeline(pipeline_id)
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] archive failed: {exc}")


if __name__ == "__main__":
    main()
