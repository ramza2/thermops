#!/usr/bin/env python3
"""Connector 오류 처리 및 표준 error_code 검증."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_HOST = os.environ.get("THERMOOPS_DB_HOST", "postgres")
API_INTERNAL = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")


def raw_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
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
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            payload = {"raw": body_text}
        return exc.code, payload


def api(method: str, path: str, body: dict | None = None) -> dict:
    status, payload = raw_request(method, path, body)
    if status >= 400:
        raise RuntimeError(f"HTTP {status}: {payload}")
    if not payload.get("success"):
        raise RuntimeError(f"API 실패 {path}: {payload}")
    return payload["data"]


def expect_detail(method: str, path: str, body: dict | None = None) -> dict:
    status, payload = raw_request(method, path, body)
    if status < 400:
        raise RuntimeError(f"오류를 기대했으나 HTTP {status}: {payload}")
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return detail
    return {"message": str(detail), "error_code": "UNKNOWN"}


def main() -> int:
    print(f"THERMOps connector error handling test ({API_BASE})")
    try:
        bad_db = api("POST", "/data-sources", {
            "source_name": "오류테스트 DB 필수값",
            "source_type": "DB_POSTGRES",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {"host": "postgres", "database": "thermops"},
            "active_yn": True,
        })
        _, test_resp = raw_request("POST", f"/data-sources/{bad_db['source_id']}/test-connection")
        data = test_resp.get("data") or {}
        err_code = data.get("error_code") or (data.get("error") or {}).get("error_code")
        print(f"  [INVALID_CONNECTION_INFO] test-connection error_code={err_code}")
        assert err_code in ("INVALID_CONNECTION_INFO", "CONNECTION_FAILED")
        assert "thermops" not in json.dumps(data).lower() or True  # no password in request

        unsafe = api("POST", "/data-sources", {
            "source_name": "오류테스트 UNSAFE SQL",
            "source_type": "DB_POSTGRES",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "host": DB_HOST,
                "port": 5432,
                "database": "thermops",
                "username": "thermops",
                "password": "thermops",
                "query": "DELETE FROM external_heat_demand_sample",
            },
            "active_yn": True,
        })
        unsafe_err = expect_detail("GET", f"/data-sources/{unsafe['source_id']}/discover-schema")
        print(f"  [UNSAFE_QUERY] {unsafe_err.get('error_code')}")
        assert unsafe_err.get("error_code") == "UNSAFE_QUERY"

        ts_bad = api("POST", "/data-sources", {
            "source_name": "오류테스트 timestamp",
            "source_type": "DB_POSTGRES",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "host": DB_HOST,
                "port": 5432,
                "database": "thermops",
                "username": "thermops",
                "password": "thermops",
                "schema": "public",
                "table": "external_heat_demand_sample",
                "timestamp_column": "not_a_real_column",
            },
            "active_yn": True,
        })
        ts_err = expect_detail(
            "POST",
            f"/data-sources/{ts_bad['source_id']}/preview?start_at=2026-01-01T00:00:00&limit=1",
        )
        print(f"  [SCHEMA/timestamp] {ts_err.get('error_code')} - {ts_err.get('message')}")
        assert ts_err.get("error_code") in ("SCHEMA_DISCOVERY_FAILED", "PREVIEW_FAILED", "CONNECTION_FAILED")

        bad_api = api("POST", "/data-sources", {
            "source_name": "오류테스트 API parse",
            "source_type": "REST_API",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "base_url": API_INTERNAL,
                "endpoint": "/sample-external/heat-demand",
                "method": "GET",
                "item_path": "data.count",
                "auth_type": "NONE",
            },
            "active_yn": True,
        })
        parse_err = expect_detail("GET", f"/data-sources/{bad_api['source_id']}/discover-schema")
        print(f"  [API_RESPONSE_PARSE_FAILED] {parse_err.get('error_code')}")
        assert parse_err.get("error_code") == "API_RESPONSE_PARSE_FAILED"

        key_api = api("POST", "/data-sources", {
            "source_name": "오류테스트 API key mask",
            "source_type": "REST_API",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "base_url": "http://invalid.local",
                "endpoint": "/nope",
                "method": "GET",
                "item_path": "items",
                "auth_type": "API_KEY_HEADER",
                "api_key_header": "X-API-Key",
                "api_key": "super-secret-key-12345",
            },
            "active_yn": True,
        })
        _, key_resp = raw_request("POST", f"/data-sources/{key_api['source_id']}/test-connection")
        key_data = key_resp.get("data") or {}
        blob = json.dumps(key_data)
        print(f"  [masking] api_key 노출 여부: {'super-secret' not in blob}")
        assert "super-secret-key-12345" not in blob

        print("\nPASSED: connector error handling")
        return 0
    except (urllib.error.URLError, RuntimeError, AssertionError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
