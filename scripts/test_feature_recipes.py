#!/usr/bin/env python3
"""Feature Recipe 저장·발행 API 테스트 (Phase R5)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    TPL_FS_GUARD_ID,
    ensure_test_platform,
    resolve_heat_mapping_id,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_MAPPING_ID = ""
TPL_FS = TPL_FS_GUARD_ID


def api(method: str, path: str, body: dict | None = None, *, expect_error: bool = False) -> dict | list:
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
        if expect_error:
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                return {"http_error": detail, "status": exc.code}
            return parsed
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success") and not expect_error:
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def api_error_code(resp: dict) -> str:
    detail = resp.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("code", ""))
    return ""


def _lag_body(**overrides) -> dict:
    suffix = uuid4().hex[:6]
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "LAG",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {"offset_steps": 96, "granularity": "1h"},
        "output_feature_name": f"heat_demand_lag_96h_r5_{suffix}",
        "display_name": f"R5 LAG test {suffix}",
    }
    body.update(overrides)
    return body


def test_create_draft_lag() -> str:
    data = api("POST", "/feature-recipes", _lag_body())
    assert data["status"] in ("DRAFT", "VALIDATED"), data
    assert data["recipe_id"].startswith("RCP-"), data
    print("  [ok] create draft LAG recipe")
    return data["recipe_id"]


def test_create_raw_column() -> None:
    suffix = uuid4().hex[:6]
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["supply_temp"],
        "output_feature_name": f"supply_temp_r5_{suffix}",
        "display_name": f"supply temp r5 {suffix}",
    }
    data = api("POST", "/feature-recipes", body)
    assert data["recipe_type"] == "RAW_COLUMN", data
    print("  [ok] create draft RAW_COLUMN recipe")


def test_list_and_get(recipe_id: str) -> None:
    listed = api("GET", "/feature-recipes?limit=20")
    assert any(i["recipe_id"] == recipe_id for i in listed["items"]), listed
    detail = api("GET", f"/feature-recipes/{recipe_id}")
    assert detail["recipe_id"] == recipe_id
    print("  [ok] list/get recipe")


def test_update_draft(recipe_id: str) -> None:
    updated = api("PUT", f"/feature-recipes/{recipe_id}", {"description": "R5 test update"})
    assert updated["description"] == "R5 test update"
    print("  [ok] update DRAFT recipe")


def test_validate_saved(recipe_id: str) -> None:
    data = api("POST", f"/feature-recipes/{recipe_id}/validate")
    assert data["validation"]["valid"] is True, data
    print("  [ok] validate saved recipe")


def test_preview_saved(recipe_id: str) -> None:
    data = api("POST", f"/feature-recipes/{recipe_id}/preview", {"sample_size": 30})
    assert data["preview"]["valid"] is True, data
    assert data["preview_summary"]["row_count"] is not None
    print("  [ok] preview saved recipe (summary only)")


def test_publish(recipe_id: str) -> str:
    data = api("POST", f"/feature-recipes/{recipe_id}/publish")
    assert data["recipe"]["status"] == "PUBLISHED", data
    feature_name = data["feature"]["feature_name"]
    assert feature_name, data
    feat = api("GET", f"/features/validate-name?feature_name={feature_name}")
    assert feat["status"] in ("TEMPLATE_PUBLISHED", "TEMPLATE_BUILD_SUPPORTED"), feat
    print("  [ok] publish recipe + catalog registration")
    return feature_name


def test_published_update_blocked(recipe_id: str) -> None:
    resp = api("PUT", f"/feature-recipes/{recipe_id}", {"description": "blocked"}, expect_error=True)
    assert api_error_code(resp) == "RECIPE_NOT_EDITABLE" or resp.get("status") == 400, resp
    print("  [ok] PUBLISHED recipe update blocked")


def test_add_to_custom_feature_set(recipe_id: str) -> str:
    suffix = uuid4().hex[:6]
    fs = api("POST", "/feature-sets", {
        "feature_set_name": f"R5 Recipe FS {suffix}",
        "target_domain": "HEAT_DEMAND",
        "features": ["temperature"],
        "apply_site_scope": "ALL",
        "description": "R5 test",
    })
    fsid = fs["feature_set_id"]
    result = api("POST", f"/feature-sets/{fsid}/add-recipe-feature", {"recipe_id": recipe_id})
    assert result["added"] is True, result
    assert any("R5" in w or "R6" in w or "Recipe Engine" in w for w in result.get("warnings", [])), result
    print("  [ok] add published recipe to custom Feature Set")
    return fsid


def test_add_draft_blocked() -> None:
    rid = api("POST", "/feature-recipes", _lag_body())["recipe_id"]
    suffix = uuid4().hex[:6]
    fs = api("POST", "/feature-sets", {
        "feature_set_name": f"R5 draft block {suffix}",
        "target_domain": "HEAT_DEMAND",
        "features": ["temperature"],
        "apply_site_scope": "ALL",
    })
    resp = api(
        "POST",
        f"/feature-sets/{fs['feature_set_id']}/add-recipe-feature",
        {"recipe_id": rid},
        expect_error=True,
    )
    assert api_error_code(resp) == "RECIPE_NOT_PUBLISHED", resp
    print("  [ok] draft recipe add to Feature Set blocked")


def test_add_to_tpl_blocked(recipe_id: str) -> None:
    resp = api(
        "POST",
        f"/feature-sets/{TPL_FS}/add-recipe-feature",
        {"recipe_id": recipe_id},
        expect_error=True,
    )
    assert api_error_code(resp) == "TPL_FEATURE_SET_BLOCKED", resp
    print("  [ok] add recipe to FS-TPL blocked")


def test_duplicate_publish_blocked(recipe_id: str) -> None:
    resp = api("POST", f"/feature-recipes/{recipe_id}/publish", expect_error=True)
    assert api_error_code(resp) == "ALREADY_PUBLISHED", resp
    print("  [ok] duplicate publish blocked")


def test_archive(recipe_id: str) -> None:
    data = api("POST", f"/feature-recipes/{recipe_id}/archive")
    assert data["status"] == "ARCHIVED", data
    print("  [ok] archive recipe")


def test_template_registration(feature_name: str) -> None:
    data = api("GET", f"/features/validate-name?feature_name={feature_name}")
    assert data["status"] in ("TEMPLATE_PUBLISHED", "TEMPLATE_BUILD_SUPPORTED"), data
    assert data.get("build_supported") is True, data
    print("  [ok] TEMPLATE build_supported registration")


def test_preview_api_unchanged() -> None:
    import subprocess

    r = subprocess.run([sys.executable, "scripts/test_feature_recipe_preview.py"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    print("  [ok] existing preview tests still pass")


def main() -> int:
    global HEAT_MAPPING_ID
    print("test_feature_recipes.py")
    ensure_test_platform()
    HEAT_MAPPING_ID = resolve_heat_mapping_id(api)
    print(f"  [fixture] heat mapping={HEAT_MAPPING_ID}")
    try:
        test_create_raw_column()
        recipe_id = test_create_draft_lag()
        test_list_and_get(recipe_id)
        test_update_draft(recipe_id)
        test_validate_saved(recipe_id)
        test_preview_saved(recipe_id)
        feature_name = test_publish(recipe_id)
        test_published_update_blocked(recipe_id)
        test_template_registration(feature_name)
        test_add_to_custom_feature_set(recipe_id)
        test_add_draft_blocked()
        test_add_to_tpl_blocked(recipe_id)
        test_duplicate_publish_blocked(recipe_id)
        test_archive(recipe_id)
        test_preview_api_unchanged()
    except Exception as exc:
        print(f"  [FAIL] {exc}", file=sys.stderr)
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
