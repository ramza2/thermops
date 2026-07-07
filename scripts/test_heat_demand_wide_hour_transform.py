#!/usr/bin/env python3
"""R10-S3 열수요 API wide-hour → long format 변환 적재 테스트."""

from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_fixtures import psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_BASE = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")


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


def make_wide_item(nd_id: str, nd_name: str, bas_ymd: str = "20260101", *, blank_hour: int | None = None) -> dict:
    item = {"ND_ID": nd_id, "ND_KORN_NM": nd_name, "BAS_YMD": bas_ymd}
    for h in range(1, 25):
        key = f"HTDND_AMNT_{h}HR"
        if blank_hour == h:
            item[key] = ""
        else:
            item[key] = f"{100 + h}.5" if h != 3 else "1,203.4"
    return item


def test_service_local() -> None:
    from datetime import date, datetime, timedelta, time

    def parse_date_value(value, date_format: str) -> date:
        text = str(value).strip()
        if date_format == "YYYYMMDD" and len(text) == 8 and text.isdigit():
            return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
        raise ValueError(f"bad date {value}")

    def build_measured_at(base_date: date, hour: int, config: dict) -> datetime:
        policy = config.get("timestamp_policy") or "HOUR_LABEL_AS_END"
        h24 = config.get("hour_24_policy") or "NEXT_DAY_00"
        if policy == "HOUR_LABEL_AS_END":
            if hour == 24:
                if h24 == "NEXT_DAY_00":
                    return datetime.combine(base_date + timedelta(days=1), time(0, 0))
                return datetime.combine(base_date, time(23, 0))
            return datetime.combine(base_date, time(hour, 0))
        if hour == 24:
            return datetime.combine(base_date, time(23, 0))
        return datetime.combine(base_date, time(hour - 1, 0))

    def parse_numeric_value(value, config: dict):
        if value is None:
            return None, None
        text = str(value).strip().replace(",", "")
        try:
            return float(text), None
        except ValueError:
            return None, "invalid"

    cfg = {"timestamp_policy": "HOUR_LABEL_AS_END", "hour_24_policy": "NEXT_DAY_00", "numeric_parse_policy": "ALLOW_COMMA"}
    d = parse_date_value("20260101", "YYYYMMDD")
    assert build_measured_at(d, 1, cfg) == datetime(2026, 1, 1, 1, 0)
    assert build_measured_at(d, 24, cfg) == datetime(2026, 1, 2, 0, 0)
    cfg2 = {**cfg, "timestamp_policy": "HOUR_LABEL_AS_START", "hour_24_policy": "SAME_DAY_23"}
    assert build_measured_at(d, 1, cfg2) == datetime(2026, 1, 1, 0, 0)
    assert build_measured_at(d, 24, cfg2) == datetime(2026, 1, 1, 23, 0)
    val, err = parse_numeric_value("1,203.4", cfg)
    assert val == 1203.4 and err is None
    print("  [ok] local timestamp/numeric helpers")


def create_heat_target_table(suffix: str) -> tuple[str, str]:
    table = f"std_wh_transform_{suffix}"
    code = f"WH_TR_{suffix.upper()}"
    created = api(
        "POST",
        "/standard-dataset-types",
        {
            "dataset_type_code": code,
            "dataset_type_name": f"Wide Hour Test {suffix}",
            "target_table": table,
            "status": "DRAFT",
            "managed_table": True,
            "mapping_supported": True,
            "columns": [
                {"column_name": "measured_at", "data_type": "TIMESTAMP", "required": True, "default_column_role": "TIME_KEY"},
                {"column_name": "heat_demand", "data_type": "NUMERIC", "numeric_precision": 18, "numeric_scale": 4, "default_column_role": "TARGET"},
                {"column_name": "entity_id", "data_type": "VARCHAR", "data_length": 64, "default_column_role": "ENTITY_KEY"},
                {"column_name": "site_id", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "external_node_id", "data_type": "VARCHAR", "data_length": 64},
                {"column_name": "external_node_name", "data_type": "VARCHAR", "data_length": 200},
                {"column_name": "raw_hour", "data_type": "INTEGER"},
                {"column_name": "raw_date", "data_type": "VARCHAR", "data_length": 16},
            ],
        },
    )
    ds_id = created["dataset_type_id"]
    api("POST", f"/standard-dataset-types/{ds_id}/validate")
    api("POST", f"/standard-dataset-types/{ds_id}/create-physical-table", {"confirm": True})
    api("POST", f"/standard-dataset-types/{ds_id}/activate")
    return ds_id, table


def ensure_rest_source() -> str:
    sources = api("GET", "/data-sources?page=1&size=100")
    items = sources.get("items", []) if isinstance(sources, dict) else sources
    for s in items:
        if s.get("source_name") == "TEST R10 WH Transform":
            return s["source_id"]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": "TEST R10 WH Transform",
            "source_type": "REST_API",
            "data_domain": "REFERENCE",
            "connection_info": {"base_url": INTERNAL_BASE},
            "active_yn": True,
        },
    )
    return created["source_id"]


def main() -> int:
    print(f"THERMOps wide-hour transform test ({API_BASE})")
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            count = int(psql_scalar("SELECT COUNT(*) FROM tb_api_connector_transform_config") or "0")
            assert count == 0
            print("  [ok] clean DB transform config empty")
            print("PASS")
            return 0

        test_service_local()

        suffix = uuid.uuid4().hex[:8]
        nd_code = f"ND-{suffix}"
        ent = api(
            "POST",
            "/prediction-entities",
            {
                "entity_code": f"SITE-WH-{suffix}",
                "entity_name": f"테스트 지점 {suffix}",
                "entity_type": "SITE",
            },
        )
        entity_id = ent["entity_id"]
        print(f"  [ok] fixture entity {entity_id}")

        api(
            "POST",
            "/external-code-mappings",
            {
                "source_system": "HEAT_DEMAND_API",
                "external_code_group": "NODE",
                "external_code": nd_code,
                "external_code_name": "테스트 노드",
                "target_type": "PREDICTION_ENTITY",
                "target_id": entity_id,
            },
        )
        print("  [ok] external code mapping")

        _, target_table = create_heat_target_table(suffix)
        print(f"  [ok] target table {target_table}")

        source_id = ensure_rest_source()
        op = api(
            "POST",
            "/api-connectors/operations",
            {
                "data_source_id": source_id,
                "operation_name": f"TEST wide-hour {suffix}",
                "endpoint_path": "/sample-external/heat-demand-wide",
                "response_item_path": "data.items",
                "target_table": target_table,
            },
        )
        op_id = op["operation_id"]
        print(f"  [ok] operation {op_id}")

        cfg = api(
            "PUT",
            f"/api-connectors/operations/{op_id}/transform-config",
            {"transform_type": "WIDE_HOUR_TO_LONG", "unmapped_policy": "FAIL_LOAD"},
        )
        assert cfg.get("transform_type") == "WIDE_HOUR_TO_LONG"
        got = api("GET", f"/api-connectors/operations/{op_id}/transform-config")
        assert got and got.get("hour_column_prefix") == "HTDND_AMNT_"
        print("  [ok] transform config save/get")

        raw_items = [make_wide_item(nd_code, "테스트노드"), make_wide_item(nd_code, "테스트노드", "20260102")]
        preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/transform-preview",
            {"raw_items": raw_items},
        )
        assert preview.get("raw_item_count") == 2
        assert preview.get("transformed_row_count") == 48
        sample = preview.get("sample_rows") or []
        assert sample[0].get("entity_id") == entity_id
        assert sample[0].get("site_id") == ent["entity_code"]
        assert sample[0].get("heat_demand") == 101.5
        assert "2026-01-01T01:00:00" in str(sample[0].get("measured_at"))
        api("PUT", f"/api-connectors/operations/{op_id}/transform-config", {"hour_start": 24, "hour_end": 24})
        h24_preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/transform-preview",
            {"raw_items": [make_wide_item(nd_code, "테스트노드")]},
        )
        h24_row = (h24_preview.get("sample_rows") or [])[0]
        assert "2026-01-02T00:00:00" in str(h24_row.get("measured_at"))
        api("PUT", f"/api-connectors/operations/{op_id}/transform-config", {"hour_start": 1, "hour_end": 24})
        print("  [ok] transform preview 2x24 rows")

        blank_preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/transform-preview",
            {"raw_items": [make_wide_item(nd_code, "테스트", blank_hour=5)]},
        )
        assert blank_preview.get("transformed_row_count") == 23
        print("  [ok] SKIP_NULL blank hour")

        unmapped_nd = f"UNMAP-{suffix}"
        fail_preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/transform-preview",
            {"raw_items": [make_wide_item(unmapped_nd, "미매핑")]},
        )
        assert fail_preview.get("blocked") is True
        assert len(fail_preview.get("unmapped_codes") or []) >= 1
        print("  [ok] unmapped FAIL_LOAD preview blocked")

        api(
            "PUT",
            f"/api-connectors/operations/{op_id}/transform-config",
            {"unmapped_policy": "SKIP_UNMAPPED"},
        )
        skip_preview = api(
            "POST",
            f"/api-connectors/operations/{op_id}/transform-preview",
            {
                "raw_items": [
                    make_wide_item(nd_code, "매핑됨"),
                    make_wide_item(unmapped_nd, "미매핑"),
                ],
            },
        )
        assert skip_preview.get("transformed_row_count") == 24
        print("  [ok] SKIP_UNMAPPED policy")

        api(
            "PUT",
            f"/api-connectors/operations/{op_id}/transform-config",
            {"unmapped_policy": "FAIL_LOAD"},
        )
        api(
            "PUT",
            f"/api-connectors/operations/{op_id}/params",
            {
                "params": [
                    {"param_name": "nd_id", "param_location": "QUERY", "param_type": "STRING", "default_value": nd_code},
                    {"param_name": "nd_name", "param_location": "QUERY", "param_type": "STRING", "default_value": "테스트노드"},
                    {"param_name": "bas_ymd", "param_location": "QUERY", "param_type": "STRING", "default_value": "20260101"},
                ]
            },
        )
        load_preview = api("POST", f"/api-connectors/operations/{op_id}/load-preview", {"runtime_params": {}})
        assert load_preview.get("transform_applied") is True
        assert load_preview.get("transformed_row_count") == 24
        print("  [ok] load-preview with transform")

        before = int(psql_scalar(f'SELECT COUNT(*) FROM "{target_table}"') or "0")
        load_run = api(
            "POST",
            f"/api-connectors/operations/{op_id}/load-run",
            {"runtime_params": {}},
        )
        after = int(psql_scalar(f'SELECT COUNT(*) FROM "{target_table}"') or "0")
        assert load_run.get("inserted_count", 0) >= 24
        assert after >= before + 24
        run_detail = api("GET", f"/api-connectors/load-runs/{load_run['load_run_id']}")
        ts = (run_detail.get("result_summary") or {}).get("transform_summary") or {}
        assert ts.get("transform_type") == "WIDE_HOUR_TO_LONG"
        print(f"  [ok] load-run inserted {load_run.get('inserted_count')}")

        fail_run = api(
            "POST",
            f"/api-connectors/operations/{op_id}/load-run",
            {
                "runtime_params": {
                    "nd_id": unmapped_nd,
                    "nd_name": "미매핑",
                    "bas_ymd": "20260103",
                },
            },
            expect_fail=True,
        )
        assert fail_run and fail_run.get("http_error") == 400
        print("  [ok] unmapped load-run blocked")

        unmapped_cnt = int(
            psql_scalar(
                f"SELECT COUNT(*) FROM tb_unmapped_external_code WHERE external_code = '{unmapped_nd}'"
            )
            or "0"
        )
        assert unmapped_cnt >= 1
        print("  [ok] tb_unmapped_external_code upsert")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
