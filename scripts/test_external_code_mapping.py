#!/usr/bin/env python3
"""R10-S2 External Code / Common Code Mapping 테스트."""

from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_fixtures import psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list | None:
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
        if expect_fail:
            return {"http_error": exc.code, "body": exc.read().decode()}
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success") and not expect_fail:
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload.get("data")


def main() -> int:
    print(f"THERMOps external code mapping test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            for t in ("tb_external_code_mapping", "tb_unmapped_external_code"):
                assert int(psql_scalar(f"SELECT COUNT(*) FROM {t}") or "0") == 0
            assert len(api("GET", "/external-code-mappings") or []) == 0
            assert len(api("GET", "/external-code-mappings/unmapped") or []) == 0
            print("  [ok] clean DB external code tables empty")
            print("PASS")
            return 0

        suffix = uuid.uuid4().hex[:8].upper()
        ent = api(
            "POST",
            "/prediction-entities",
            {
                "entity_code": f"TEST-ECM-{suffix}",
                "entity_name": f"테스트 지점 {suffix}",
                "entity_type": "SITE",
            },
        )
        entity_id = ent["entity_id"]
        print(f"  [ok] fixture entity {entity_id}")

        bad = api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"ND-{suffix}",
                "target_type": "PREDICTION_ENTITY",
                "target_id": "PE-NOT-EXISTS",
            },
            expect_fail=True,
        )
        assert bad and bad.get("http_error") == 400
        print("  [ok] invalid target_id rejected")

        mapping = api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"ND-{suffix}",
                "external_code_name": "테스트 노드",
                "target_type": "PREDICTION_ENTITY",
                "target_id": entity_id,
                "priority": 1,
            },
        )
        mapping_id = mapping["mapping_id"]
        print(f"  [ok] mapping created {mapping_id}")

        dup = api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"ND-{suffix}",
                "target_type": "PREDICTION_ENTITY",
                "target_id": entity_id,
            },
            expect_fail=True,
        )
        assert dup and dup.get("http_error") == 400
        print("  [ok] duplicate active mapping blocked")

        resolved = api(
            "POST",
            "/external-code-mappings/resolve",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"ND-{suffix}",
                "target_type": "PREDICTION_ENTITY",
            },
        )
        assert resolved.get("resolved") is True
        assert resolved.get("target_id") == entity_id
        print("  [ok] resolve single success")

        missing = api(
            "POST",
            "/external-code-mappings/resolve",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"UNKNOWN-{suffix}",
            },
        )
        assert missing.get("resolved") is False
        print("  [ok] resolve failure")

        unmapped_list = api("GET", "/external-code-mappings/unmapped")
        unmapped = next(u for u in unmapped_list if u["external_code"] == f"UNKNOWN-{suffix}")
        unmapped_id = unmapped["unmapped_id"]
        assert unmapped.get("seen_count") == 1
        print(f"  [ok] unmapped upsert {unmapped_id}")

        api(
            "POST",
            "/external-code-mappings/resolve",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"UNKNOWN-{suffix}",
            },
        )
        unmapped2 = api("GET", f"/external-code-mappings/unmapped/{unmapped_id}")
        assert unmapped2.get("seen_count") >= 2
        print("  [ok] unmapped seen_count increased")

        suffix2 = uuid.uuid4().hex[:6].upper()
        ent2 = api(
            "POST",
            "/prediction-entities",
            {"entity_code": f"TEST-ECM2-{suffix2}", "entity_name": "후보2", "entity_type": "SITE"},
        )
        low_pri = api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"PRI-{suffix}",
                "target_type": "PREDICTION_ENTITY",
                "target_id": entity_id,
                "priority": 2,
            },
        )
        api("POST", f"/external-code-mappings/{low_pri['mapping_id']}/deactivate")
        high_pri = api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"PRI-{suffix}",
                "target_type": "PREDICTION_ENTITY",
                "target_id": ent2["entity_id"],
                "priority": 1,
            },
        )
        pri_res = api(
            "POST",
            "/external-code-mappings/resolve",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"PRI-{suffix}",
            },
        )
        assert pri_res.get("target_id") == ent2["entity_id"]
        print("  [ok] priority selection")

        api("POST", f"/external-code-mappings/{high_pri['mapping_id']}/archive")
        archived_res = api(
            "POST",
            "/external-code-mappings/resolve",
            {"source_system": "HEAT_DEMAND_API", "external_code_group": "NODE", "external_code": f"PRI-{suffix}"},
        )
        assert archived_res.get("resolved") is False
        print("  [ok] archived mapping excluded from resolve")

        assign = api(
            "POST",
            f"/external-code-mappings/unmapped/{unmapped_id}/assign",
            {"target_type": "PREDICTION_ENTITY", "target_id": entity_id},
        )
        assert assign["mapping"]["mapping_id"]
        assert assign["unmapped"]["review_status"] == "MAPPED"
        print("  [ok] unmapped assign")

        suffix3 = uuid.uuid4().hex[:6].upper()
        api(
            "POST",
            "/external-code-mappings/resolve",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": f"IGN-{suffix3}",
            },
        )
        rows = api("GET", "/external-code-mappings/unmapped")
        ign_row = next(r for r in rows if r["external_code"] == f"IGN-{suffix3}")
        api("POST", f"/external-code-mappings/unmapped/{ign_row['unmapped_id']}/ignore", {"ignored_reason": "테스트"})
        print("  [ok] unmapped ignore")

        batch = api(
            "POST",
            "/external-code-mappings/resolve-batch",
            {
                "items": [
                    {
                        "source_system": "HEAT_DEMAND_API",
                        "external_code_group": "NODE",
                        "external_code": f"ND-{suffix}",
                    },
                    {
                        "source_system": "HEAT_DEMAND_API",
                        "external_code_group": "NODE",
                        "external_code": f"BATCH-MISS-{suffix}",
                    },
                ]
            },
        )
        assert len(batch) == 2
        assert batch[0].get("resolved") is True
        assert batch[1].get("resolved") is False
        print("  [ok] resolve batch mixed")

        opts = api("GET", "/external-code-mappings/options")
        assert "HEAT_DEMAND_API" in opts.get("source_systems", [])
        assert "PREDICTION_ENTITY" in opts.get("target_types", [])
        print("  [ok] options")

        candidates = api(
            "GET",
            f"/external-code-mappings/target-candidates?target_type=PREDICTION_ENTITY&keyword={suffix}",
        )
        assert any(c["target_id"] == entity_id for c in candidates)
        print("  [ok] target candidate search")

        api("PUT", f"/external-code-mappings/{mapping_id}", {"external_code_name": "수정명"})
        detail = api("GET", f"/external-code-mappings/{mapping_id}")
        assert detail.get("external_code_name") == "수정명"
        print("  [ok] mapping update")

        api("POST", f"/external-code-mappings/{mapping_id}/deactivate")
        api("POST", f"/external-code-mappings/{mapping_id}/activate")
        print("  [ok] deactivate/activate")

        bad_msg = api("POST", "/external-code-mappings", {"source_system": "", "external_code_group": "X", "external_code": "Y", "target_type": "CUSTOM", "target_id": "Z"}, expect_fail=True)
        assert bad_msg and bad_msg.get("http_error") == 400
        assert "외부 시스템" in bad_msg.get("body", "") or "필수" in bad_msg.get("body", "")
        print("  [ok] user-friendly validation message")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
