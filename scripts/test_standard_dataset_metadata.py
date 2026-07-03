#!/usr/bin/env python3
"""표준 데이터셋 메타데이터 분류 테스트 (Phase R9-S2-2)."""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from test_fixtures import ensure_test_standard_datasets

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
ROOT = _SCRIPTS.parent
CLEAN_SEED = ROOT / "db" / "init" / "02_seed_clean.sql"

ALLOWED_CATEGORIES = {
    "MASTER", "FACT", "TIMESERIES", "EVENT", "TRANSACTION", "LOG", "MAPPING", "CUSTOM",
}


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list:
    import urllib.error
    import urllib.request

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
                return json.loads(detail)
            except json.JSONDecodeError:
                return {"detail": detail, "status": exc.code}
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def test_clean_seed_no_domain_or_dataset_seed() -> None:
    text = CLEAN_SEED.read_text(encoding="utf-8")
    assert not re.search(r"insert\s+into\s+tb_standard_dataset_type", text, re.IGNORECASE)
    assert "HEAT_DEMAND" not in text
    assert "열수요" not in text
    print("  [ok] 운영 seed에 표준 데이터셋/도메인 insert 없음")


def test_metadata_options_clean_or_dynamic() -> None:
    data = api("GET", "/standard-datasets/metadata-options")
    categories = data.get("dataset_categories") or []
    codes = {c["code"] for c in categories}
    assert codes == ALLOWED_CATEGORIES, codes
    assert isinstance(data.get("business_domains"), list), data
    assert isinstance(data.get("tags"), list), data
    # clean DB: empty dynamic lists; fixture DB: populated from registrations only
    for fixed in ("열수요", "기상", "기준정보", "설비"):
        assert fixed not in (data.get("business_domains") or []), data
    print(f"  [ok] metadata-options categories={len(categories)} business_domains={len(data.get('business_domains') or [])}")


def test_create_without_business_domain_and_tags() -> None:
    suffix = uuid.uuid4().hex[:8]
    table = f"std_meta_min_{suffix}"
    created = api("POST", "/standard-dataset-types", {
        "dataset_type_code": f"META_MIN_{suffix.upper()}",
        "dataset_type_name": f"Metadata Min {suffix}",
        "dataset_category": "CUSTOM",
        "target_table": table,
        "status": "DRAFT",
        "managed_table": True,
        "columns": [{"column_name": "id_col", "data_type": "INTEGER", "primary_key": True, "required": True}],
    })
    assert created.get("business_domain") in (None, ""), created
    assert not created.get("tags"), created
    assert created.get("dataset_category") == "CUSTOM", created
    print("  [ok] business_domain/tags 없이 생성 가능")


def test_create_with_business_domain_and_tags() -> None:
    suffix = uuid.uuid4().hex[:8]
    table = f"std_meta_full_{suffix}"
    domain = f"테스트영역_{suffix[:4]}"
    tags = ["예측", "센서", "예측"]
    created = api("POST", "/standard-dataset-types", {
        "dataset_type_code": f"META_FULL_{suffix.upper()}",
        "dataset_type_name": f"Metadata Full {suffix}",
        "dataset_category": "TIMESERIES",
        "business_domain": domain,
        "tags": tags,
        "target_table": table,
        "status": "DRAFT",
        "managed_table": True,
        "columns": [{"column_name": "id_col", "data_type": "INTEGER", "primary_key": True, "required": True}],
    })
    assert created.get("business_domain") == domain, created
    assert created.get("tags") == ["예측", "센서"], created
    detail = api("GET", f"/standard-dataset-types/{created['dataset_type_id']}")
    assert detail.get("business_domain") == domain, detail
    assert detail.get("tags") == ["예측", "센서"], detail

    opts = api("GET", "/standard-datasets/metadata-options")
    assert domain in (opts.get("business_domains") or []), opts
    assert "예측" in (opts.get("tags") or []), opts
    print("  [ok] business_domain/tags 저장·distinct 반영")


def test_invalid_dataset_category_rejected() -> None:
    suffix = uuid.uuid4().hex[:8]
    try:
        api("POST", "/standard-dataset-types", {
            "dataset_type_code": f"META_BAD_{suffix.upper()}",
            "dataset_type_name": "bad category",
            "dataset_category": "NOT_A_REAL_CATEGORY",
            "target_table": f"std_meta_bad_{suffix}",
            "status": "DRAFT",
            "managed_table": True,
            "columns": [{"column_name": "id_col", "data_type": "INTEGER", "primary_key": True, "required": True}],
        })
        raise AssertionError("invalid category should fail")
    except RuntimeError as exc:
        assert "400" in str(exc) or "dataset_category" in str(exc).lower(), exc
    print("  [ok] invalid dataset_category reject")


def test_tags_whitespace_dedup() -> None:
    suffix = uuid.uuid4().hex[:8]
    created = api("POST", "/standard-dataset-types", {
        "dataset_type_code": f"META_TAG_{suffix.upper()}",
        "dataset_type_name": f"Tag norm {suffix}",
        "dataset_category": "CUSTOM",
        "tags": " batch , 실시간 , batch ,  ",
        "target_table": f"std_meta_tag_{suffix}",
        "status": "DRAFT",
        "managed_table": True,
        "columns": [{"column_name": "id_col", "data_type": "INTEGER", "primary_key": True, "required": True}],
    })
    assert created.get("tags") == ["batch", "실시간"], created
    print("  [ok] tags 공백/중복 제거")


def test_list_filters() -> None:
    ensure_test_standard_datasets()
    listed = api("GET", "/standard-dataset-types?dataset_category=FACT&include_planned=true")
    items = listed.get("items") or []
    assert items, "fixture FACT datasets expected"
    for item in items:
        cat = item.get("dataset_category") or item.get("category")
        assert cat == "FACT", item
    print(f"  [ok] dataset_category filter ({len(items)}건)")


def main() -> int:
    print("THERMOps standard dataset metadata tests (R9-S2-2)")
    tests = [
        test_clean_seed_no_domain_or_dataset_seed,
        test_metadata_options_clean_or_dynamic,
        test_create_without_business_domain_and_tags,
        test_create_with_business_domain_and_tags,
        test_invalid_dataset_category_rejected,
        test_tags_whitespace_dedup,
        test_list_filters,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {exc}", file=sys.stderr)
    if failed:
        print(f"FAILED ({failed}/{len(tests)})", file=sys.stderr)
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
