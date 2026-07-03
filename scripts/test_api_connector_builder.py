#!/usr/bin/env python3
"""R10 Generic REST API Connector Builder 테스트."""

from __future__ import annotations

import json
import os
import sys
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
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")
TEST_SECRET = "abcde12345xyzTESTKEY"


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | None:
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


def test_parser_local() -> None:
    from app.services.api_connector_parser import normalize_items, parse_response_body

    payload = {"response": {"body": {"items": {"item": [{"a": 1}, {"a": 2}]}}}}
    items = normalize_items(payload, item_path="response.body.items.item")
    assert len(items) == 2
    xml = '<?xml version="1.0"?><response><items><item><id>1</id></item></items></response>'
    parsed = parse_response_body(xml, "XML")
    xml_items = normalize_items(parsed, item_path="response.items.item")
    assert len(xml_items) == 1
    print("  [ok] JSON/XML parser")


def test_masking_local() -> None:
    from app.utils.masking import mask_params_dict, mask_secret_value, mask_url

    masked = mask_secret_value(TEST_SECRET)
    assert TEST_SECRET not in (masked or "")
    assert "****" in (masked or "") or "*" in (masked or "")
    params = mask_params_dict({"serviceKey": TEST_SECRET, "solYear": "2026"})
    assert params["serviceKey"] == "****"
    assert params["solYear"] == "2026"
    url = mask_url(f"http://api.example.com?serviceKey={TEST_SECRET}&year=2026")
    assert TEST_SECRET not in url
    print("  [ok] secret masking utilities")


def ensure_rest_source() -> str:
    sources = api("GET", "/data-sources?page=1&size=100")
    items = sources.get("items", []) if isinstance(sources, dict) else sources
    for s in items:
        if s.get("source_name") == "TEST R10 REST Connector":
            return s["source_id"]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": "TEST R10 REST Connector",
            "source_type": "REST_API",
            "data_domain": "REFERENCE",
            "connection_info": {"base_url": INTERNAL_BASE},
            "active_yn": True,
        },
    )
    return created["source_id"]


def main() -> int:
    print(f"THERMOps API connector builder test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            count = int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_operation") or "0")
            cred = int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_credential") or "0")
            logs = int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_call_log") or "0")
            assert count == 0 and cred == 0 and logs == 0
            ops = api("GET", "/api-connectors/operations")
            assert len(ops) == 0
            print("  [ok] clean DB connector tables empty")
            print("PASS")
            return 0

        test_parser_local()
        test_masking_local()

        ops = api("GET", "/api-connectors/operations")
        assert isinstance(ops, list)
        print(f"  [ok] operations list ({len(ops)} rows)")

        source_id = ensure_rest_source()
        print(f"  [ok] REST data source {source_id}")

        cred = api(
            "PUT",
            f"/api-connectors/data-sources/{source_id}/credential",
            {
                "credential_type": "API_KEY",
                "key_location": "QUERY",
                "key_name": "serviceKey",
                "secret_value": TEST_SECRET,
                "encoding_policy": "STORE_DECODED_ENCODE_ON_CALL",
            },
        )
        assert cred.get("secret_value_masked")
        assert TEST_SECRET not in json.dumps(cred)
        print(f"  [ok] credential masked ({cred.get('secret_value_masked')})")

        cred_get = api("GET", f"/api-connectors/data-sources/{source_id}/credential")
        assert TEST_SECRET not in json.dumps(cred_get)
        print("  [ok] credential GET has no plaintext secret")

        op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": "TEST 샘플 열수요 조회",
                "endpoint_path": "/sample-external/heat-demand",
                "response_item_path": "data.items",
                "response_format": "JSON",
            },
        )
        op_id = op["operation_id"]
        print(f"  [ok] operation created {op_id}")

        params = api(
            "PUT",
            f"/api-connectors/operations/{op_id}/params",
            {
                "params": [
                    {
                        "param_name": "start_at",
                        "display_name": "시작",
                        "param_location": "QUERY",
                        "param_type": "DATETIME",
                        "default_value": "2026-05-22T00:00:00",
                    },
                    {
                        "param_name": "end_at",
                        "display_name": "종료",
                        "param_location": "QUERY",
                        "param_type": "DATETIME",
                        "default_value": "2026-05-23T00:00:00",
                    },
                ]
            },
        )
        assert len(params) == 2
        print("  [ok] params saved")

        pg = api(
            "PUT",
            f"/api-connectors/operations/{op_id}/pagination",
            {"pagination_type": "NONE", "max_pages": 1},
        )
        assert pg["pagination_type"] == "NONE"
        print("  [ok] pagination saved")

        preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/request-preview",
            {"runtime_params": {}},
        )
        assert "masked_url" in preview
        assert TEST_SECRET not in json.dumps(preview)
        print("  [ok] request-preview masked")

        test_result = api(
            "POST",
            f"/api-connectors/operations/{op_id}/test-call",
            {"runtime_params": {}},
        )
        assert test_result.get("success") is True
        assert test_result.get("item_count", 0) >= 0
        print(f"  [ok] test-call items={test_result.get('item_count')}")

        resp_preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/response-preview",
            {"runtime_params": {}},
        )
        assert "sample_items" in resp_preview
        print("  [ok] response-preview")

        bad = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": "bad target",
                "endpoint_path": "/x",
                "target_table": "not_allowed_table_xyz",
            },
            expect_fail=True,
        )
        assert bad and bad.get("http_error") == 400
        print("  [ok] invalid target_table blocked")

        fail_op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": "fail call",
                "endpoint_path": "/not-exists-endpoint-404",
                "response_item_path": "data.items",
            },
        )
        fail_res = api(
            "POST",
            f"/api-connectors/operations/{fail_op['operation_id']}/test-call",
            {"runtime_params": {}},
            expect_fail=True,
        )
        assert fail_res and fail_res.get("http_error") == 400
        print("  [ok] test-call HTTP failure user-friendly 400")

        logs = api("GET", "/api-connectors/call-logs")
        assert isinstance(logs, list)
        for log in logs[:5]:
            blob = json.dumps(log)
            assert TEST_SECRET not in blob
        print(f"  [ok] call logs ({len(logs)}) no secret leak")

        if resp_preview.get("snapshot_id"):
            snap = api("GET", f"/api-connectors/snapshots/{resp_preview['snapshot_id']}")
            assert TEST_SECRET not in json.dumps(snap)
            print("  [ok] snapshot stored")

        enc_cred = api(
            "PUT",
            f"/api-connectors/data-sources/{source_id}/credential",
            {"encoding_policy": "STORE_AS_IS", "secret_value": TEST_SECRET},
        )
        assert enc_cred.get("encoding_policy") == "STORE_AS_IS"
        print("  [ok] encoding policy STORE_AS_IS")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
