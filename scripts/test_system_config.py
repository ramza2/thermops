#!/usr/bin/env python3
"""시스템 설정 API 통합 테스트."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)


def api(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
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


def api_raw(method: str, path: str, body: dict | None = None, timeout: int = 60) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode())
        return exc.code, payload


def psql_exec(sql: str) -> None:
    try:
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def ensure_schema() -> None:
    psql_exec("""
    ALTER TABLE tb_system_config ADD COLUMN IF NOT EXISTS config_name VARCHAR(200);
    ALTER TABLE tb_system_config ADD COLUMN IF NOT EXISTS editable_yn CHAR(1) NOT NULL DEFAULT 'Y';
    UPDATE tb_system_config SET editable_yn = 'Y' WHERE editable_yn IS NULL;
    INSERT INTO tb_system_config (config_key, config_name, config_value, config_type, scope, description, editable_yn) VALUES
    ('default_model_name', '기본 모델명', 'heat_demand_lightgbm', 'STRING', 'GLOBAL', 'Champion 미지정 시 사용할 기본 모델명', 'Y'),
    ('mape_warning_threshold', 'MAPE 경고 임계치', '8.0', 'NUMBER', 'GLOBAL', '운영 MAPE 경고 알림 임계치(%)', 'Y'),
    ('drift_warning_threshold', '드리프트 경고 임계치', '0.40', 'NUMBER', 'GLOBAL', 'Feature 드리프트 경고 점수 임계치', 'Y'),
    ('retraining_mape_threshold', '재학습 MAPE 임계치', '10.0', 'NUMBER', 'GLOBAL', '재학습 후보 산출 MAPE 임계치(%)', 'Y'),
    ('batch_prediction_default_horizon', '배치 예측 기본 범위', '24', 'NUMBER', 'GLOBAL', '배치 예측 기본 시간 범위(시간)', 'Y'),
    ('system_version', '시스템 버전', '0.1.0', 'STRING', 'GLOBAL', 'THERMOps 릴리스 버전', 'N')
    ON CONFLICT (config_key) DO NOTHING;
    UPDATE tb_system_config SET config_name = config_key WHERE config_name IS NULL;
    UPDATE tb_system_config SET editable_yn = 'N' WHERE config_key = 'system_version';
    """)


def main() -> int:
    print(f"THERMOps system config test ({API_BASE})")
    try:
        ensure_schema()

        configs = api("GET", "/system-configs")
        if not isinstance(configs, list) or len(configs) < 1:
            raise RuntimeError("GET /system-configs returned empty")
        print(f"  [list] configs={len(configs)}")

        editable = next((c for c in configs if c.get("editable_yn")), None)
        if not editable:
            raise RuntimeError("editable config not found")
        key = editable["config_key"]
        original = editable["config_value"]
        new_value = "9.9" if original != "9.9" else "8.1"

        updated = api("PUT", f"/system-configs/{key}", {"config_value": new_value})
        if updated.get("config_value") != new_value:
            raise RuntimeError(f"PUT response mismatch: {updated}")
        print(f"  [put] {key}={new_value}")

        again = api("GET", f"/system-configs/{key}")
        if again.get("config_value") != new_value:
            raise RuntimeError(f"GET after PUT mismatch: {again}")
        print(f"  [get] verified {key}={again.get('config_value')}")

        readonly = next((c for c in configs if not c.get("editable_yn")), None)
        if readonly:
            status, payload = api_raw(
                "PUT",
                f"/system-configs/{readonly['config_key']}",
                {"config_value": "x"},
            )
            if status != 403:
                raise RuntimeError(f"expected 403 for readonly, got {status}: {payload}")
            print(f"  [readonly] {readonly['config_key']} blocked (403)")
        else:
            print("  [WARN] no readonly config to test")

        api("PUT", f"/system-configs/{key}", {"config_value": original})

        print("\nPASSED: system config flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
