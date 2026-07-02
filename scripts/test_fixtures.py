"""회귀 테스트용 런타임 픽스처 — clean operational seed에 없는 테스트 플랫폼·CSV 데이터."""

from __future__ import annotations

import os
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any, Callable

# Standard dataset types
DST_HEAT_ID = "TEST-DST-HEAT"
DST_WEATHER_ID = "TEST-DST-WEATHER"
DST_SITE_MASTER_ID = "TEST-DST-SITE-MASTER"
DST_SWM_ID = "TEST-DST-SWM"
DST_COMMON_CODE_ID = "TEST-DST-COMMON-CODE"
DST_FACILITY_ID = "TEST-DST-FACILITY"
DST_HEAT_CODE = "TEST_HEAT_DEMAND_ACTUAL"
PT_FEATURE_BUILD_CODE = "TEST_FEATURE_BUILD_PIPELINE"
PT_FULL_CODE = "TEST_FULL_OPERATION_PIPELINE"

# Feature sets
FS_LAG_ROLL_ID = "TEST-FS-LAG-ROLL"
FS_TWO_STAGE_ID = "TEST-FS-TWO-STAGE"
FS_MINIMAL_ID = "TEST-FS-MINIMAL"
FS_COMFORT_ID = "TEST-FS-COMFORT"
TPL_FS_GUARD_ID = "FS-TPL-LAG-ROLL"

# Training configs
TRC_LGBM_ID = "TEST-TRC-LGBM"
TRC_CATBOOST_ID = "TEST-TRC-CATBOOST"
TRC_TWO_STAGE_ID = "TEST-TRC-TWO-STAGE"

# Pipeline templates
PT_FULL_ID = "TEST-PT-FULL"
PT_FEATURE_BUILD_ID = "TEST-PT-FEATURE-BUILD"
PT_BATCH_ID = "TEST-PT-BATCH"
PT_RETRAINING_ID = "TEST-PT-RETRAINING"

HEAT_SOURCE_NAME = "TEST 열수요 CSV"
WEATHER_SOURCE_NAME = "TEST 기상 CSV"
HEAT_MAPPING_NAME = "TEST 열수요 CSV 표준 매핑"
WEATHER_MAPPING_NAME = "TEST 기상 CSV 표준 매핑"

FIXTURE_SQL_PATH = Path(__file__).resolve().parent / "fixtures" / "test_platform_seed.sql"
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

_platform_loaded = False
_heat_fixture: dict[str, str] | None = None
_weather_fixture: dict[str, str] | None = None


def load_fixture_sql() -> str:
    return FIXTURE_SQL_PATH.read_text(encoding="utf-8")


def psql_run(sql: str) -> None:
    if os.environ.get("THERMOOPS_USE_DOCKER", "1") == "1":
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops"],
            input=sql,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2 required when THERMOOPS_USE_DOCKER=0") from exc
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def psql_scalar(sql: str) -> str:
    try:
        import psycopg2
    except ImportError:
        out = subprocess.check_output(
            [
                "docker", "exec", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops",
                "-t", "-A", "-c", sql,
            ],
            text=True,
        )
        return out.strip()
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return str(row[0]).strip() if row and row[0] is not None else ""
    finally:
        conn.close()


LEGACY_POC_CLEANUP_SQL = """
-- Legacy PoC/r7/r8 seed on existing volumes: deactivate so test fixtures own shared target tables.
UPDATE tb_standard_dataset_type
SET active_yn = 'N', status = 'ARCHIVED'
WHERE dataset_type_id NOT LIKE 'TEST-%'
  AND (owner = 'SEED' OR dataset_type_id LIKE 'DST-%');

UPDATE tb_pipeline_template
SET active_yn = 'N', status = 'ARCHIVED'
WHERE template_id NOT LIKE 'TEST-%'
  AND template_id LIKE 'PT-%';

UPDATE tb_feature_set
SET active_yn = 'N'
WHERE feature_set_id NOT LIKE 'TEST-%'
  AND feature_set_id LIKE 'FS-%';

DELETE FROM tb_feature
WHERE feature_id NOT LIKE 'TEST-%'
  AND feature_id LIKE 'FEAT-%';

DELETE FROM tb_training_config
WHERE config_id NOT LIKE 'TEST-%'
  AND config_id LIKE 'TRC-%';
"""


def ensure_test_platform() -> None:
    """테스트 플랫폼 SQL을 1회 idempotent 로드."""
    global _platform_loaded
    if _platform_loaded and psql_scalar(
        f"SELECT COUNT(*) FROM tb_standard_dataset_type WHERE dataset_type_id = '{DST_HEAT_ID}'"
    ) not in ("", "0"):
        return
    _platform_loaded = False
    psql_run(LEGACY_POC_CLEANUP_SQL)
    psql_run(load_fixture_sql())
    _platform_loaded = True


def ensure_test_sites() -> None:
    ensure_test_platform()


def ensure_test_calendar() -> None:
    ensure_test_platform()


def ensure_test_standard_datasets() -> None:
    ensure_test_platform()


def ensure_test_feature_sets() -> None:
    ensure_test_platform()


def ensure_test_training_configs() -> None:
    ensure_test_platform()


def ensure_test_pipeline_templates() -> None:
    ensure_test_platform()


def _env_or(default: str, *keys: str) -> str:
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val
    return default


def _list_sources(api: Callable[..., Any]) -> list[dict]:
    data = api("GET", "/data-sources?page=1&size=100")
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []


def _list_mappings(api: Callable[..., Any]) -> list[dict]:
    data = api("GET", "/mappings?page=1&size=100")
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []


def ensure_heat_csv_fixture(api: Callable[..., Any]) -> dict[str, str]:
    """열수요 CSV 소스·매핑 확보. {source_id, mapping_id} 반환."""
    global _heat_fixture
    if _heat_fixture:
        return _heat_fixture

    sources = _list_sources(api)
    source = next((s for s in sources if s.get("source_name") == HEAT_SOURCE_NAME), None)
    if not source:
        created = api("POST", "/data-sources", {
            "source_name": HEAT_SOURCE_NAME,
            "source_type": "CSV",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "file_path": "data/samples/heat_demand_sample.csv",
                "encoding": "utf-8",
                "delimiter": ",",
            },
            "active_yn": True,
        })
        source_id = created.get("source_id") or created.get("data_source_id")
        if not source_id:
            raise RuntimeError(f"heat CSV source create failed: {created}")
    else:
        source_id = source["source_id"]

    mappings = _list_mappings(api)
    mapping = next(
        (m for m in mappings if m.get("mapping_name") == HEAT_MAPPING_NAME and m.get("source_id") == source_id),
        None,
    )
    if not mapping:
        created = api("POST", "/mappings", {
            "source_id": source_id,
            "mapping_name": HEAT_MAPPING_NAME,
            "target_table": "heat_demand_actual",
            "columns": [
                {"source_column": "site_id", "target_column": "site_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "heat_demand", "target_column": "heat_demand", "required_yn": True},
                {"source_column": "supply_temp", "target_column": "supply_temp", "required_yn": False},
            ],
        })
        mapping_id = created["mapping_id"]
    else:
        mapping_id = mapping["mapping_id"]

    _heat_fixture = {"source_id": source_id, "mapping_id": mapping_id}
    return _heat_fixture


def ensure_weather_csv_fixture(api: Callable[..., Any]) -> dict[str, str]:
    """기상 CSV 소스·매핑 확보. {source_id, mapping_id} 반환."""
    global _weather_fixture
    if _weather_fixture:
        return _weather_fixture

    sources = _list_sources(api)
    source = next((s for s in sources if s.get("source_name") == WEATHER_SOURCE_NAME), None)
    if not source:
        created = api("POST", "/data-sources", {
            "source_name": WEATHER_SOURCE_NAME,
            "source_type": "CSV",
            "data_domain": "WEATHER",
            "connection_info": {
                "file_path": "data/samples/weather_observation_sample.csv",
                "encoding": "utf-8",
                "delimiter": ",",
            },
            "active_yn": True,
        })
        source_id = created.get("source_id") or created.get("data_source_id")
        if not source_id:
            raise RuntimeError(f"weather CSV source create failed: {created}")
    else:
        source_id = source["source_id"]

    mappings = _list_mappings(api)
    mapping = next(
        (m for m in mappings if m.get("mapping_name") == WEATHER_MAPPING_NAME and m.get("source_id") == source_id),
        None,
    )
    if not mapping:
        created = api("POST", "/mappings", {
            "source_id": source_id,
            "mapping_name": WEATHER_MAPPING_NAME,
            "target_table": "weather_observation",
            "columns": [
                {"source_column": "weather_area_id", "target_column": "weather_area_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "data_type", "target_column": "data_type", "required_yn": False},
                {"source_column": "temperature", "target_column": "temperature", "required_yn": False},
                {"source_column": "humidity", "target_column": "humidity", "required_yn": False},
                {"source_column": "rainfall", "target_column": "rainfall", "required_yn": False},
                {"source_column": "wind_speed", "target_column": "wind_speed", "required_yn": False},
            ],
        })
        mapping_id = created["mapping_id"]
    else:
        mapping_id = mapping["mapping_id"]

    _weather_fixture = {"source_id": source_id, "mapping_id": mapping_id}
    return _weather_fixture


def resolve_heat_mapping_id(api: Callable[..., Any]) -> str:
    env = os.environ.get("THERMOOPS_HEAT_MAPPING_ID")
    if env:
        return env
    return ensure_heat_csv_fixture(api)["mapping_id"]


def resolve_weather_mapping_id(api: Callable[..., Any]) -> str:
    env = os.environ.get("THERMOOPS_WEATHER_MAPPING_ID")
    if env:
        return env
    return ensure_weather_csv_fixture(api)["mapping_id"]


def resolve_heat_source_id(api: Callable[..., Any]) -> str:
    env = os.environ.get("THERMOOPS_HEAT_SOURCE_ID")
    if env:
        return env
    return ensure_heat_csv_fixture(api)["source_id"]


def resolve_weather_source_id(api: Callable[..., Any]) -> str:
    env = os.environ.get("THERMOOPS_WEATHER_SOURCE_ID")
    if env:
        return env
    return ensure_weather_csv_fixture(api)["source_id"]


def resolve_heat_dataset_type_id() -> str:
    ensure_test_standard_datasets()
    return _env_or(DST_HEAT_ID, "THERMOOPS_HEAT_DATASET_TYPE_ID")


def resolve_lag_roll_feature_set_id() -> str:
    ensure_test_feature_sets()
    return _env_or(FS_LAG_ROLL_ID, "THERMOOPS_FEATURE_SET_ID", "THERMOOPS_LAG_ROLL_FEATURE_SET_ID")


def resolve_two_stage_feature_set_id() -> str:
    ensure_test_feature_sets()
    return _env_or(FS_TWO_STAGE_ID, "THERMOOPS_TWO_STAGE_FEATURE_SET_ID")


def resolve_minimal_feature_set_id() -> str:
    ensure_test_feature_sets()
    return _env_or(FS_MINIMAL_ID, "THERMOOPS_EMPTY_FEATURE_SET_ID", "THERMOOPS_MINIMAL_FEATURE_SET_ID")


def resolve_comfort_feature_set_id() -> str:
    ensure_test_feature_sets()
    return _env_or(FS_COMFORT_ID, "THERMOOPS_COMFORT_FEATURE_SET_ID")


def resolve_lgbm_training_config_id() -> str:
    ensure_test_training_configs()
    return _env_or(TRC_LGBM_ID, "THERMOOPS_TRAINING_CONFIG_ID", "THERMOOPS_LGBM_TRAINING_CONFIG_ID")


def resolve_catboost_training_config_id() -> str:
    ensure_test_training_configs()
    return _env_or(TRC_CATBOOST_ID, "THERMOOPS_TRAINING_CONFIG_ID", "THERMOOPS_CATBOOST_TRAINING_CONFIG_ID")


def resolve_two_stage_training_config_id() -> str:
    ensure_test_training_configs()
    return _env_or(TRC_TWO_STAGE_ID, "THERMOOPS_TRAINING_CONFIG_ID", "THERMOOPS_TWO_STAGE_TRAINING_CONFIG_ID")


def resolve_feature_build_template_id() -> str:
    ensure_test_pipeline_templates()
    return _env_or(PT_FEATURE_BUILD_ID, "THERMOOPS_FEATURE_BUILD_TEMPLATE_ID")


def resolve_full_pipeline_template_id() -> str:
    ensure_test_pipeline_templates()
    return _env_or(PT_FULL_ID, "THERMOOPS_FULL_PIPELINE_TEMPLATE_ID")


def resolve_batch_pipeline_template_id() -> str:
    ensure_test_pipeline_templates()
    return _env_or(PT_BATCH_ID, "THERMOOPS_BATCH_PIPELINE_TEMPLATE_ID")


def heat_pipeline_node_config(api: Callable[..., Any]) -> dict[str, dict[str, str]]:
    """Pipeline Builder/Execution 테스트용 노드 설정."""
    fx = ensure_heat_csv_fixture(api)
    fs_id = resolve_lag_roll_feature_set_id()
    return {
        "DATA_SOURCE": {"data_source_id": fx["source_id"]},
        "DATA_MAPPING": {"mapping_id": fx["mapping_id"]},
        "STANDARD_DATASET": {"dataset_type_id": resolve_heat_dataset_type_id()},
        "FEATURE_SET": {"feature_set_id": fs_id},
        "FEATURE_BUILD": {"feature_set_id": fs_id},
    }


def ensure_feature_dataset_built(api: Callable[..., Any], feature_set_id: str, *, timeout: int = 180) -> None:
    """Feature dataset이 비어 있으면 feature build 실행."""
    count = psql_scalar(
        f"SELECT COUNT(*) FROM tb_feature_dataset WHERE feature_json->>'feature_set_id' = '{feature_set_id}'"
    )
    if count and int(count) > 0:
        return
    api("POST", f"/feature-build-jobs?feature_set_id={feature_set_id}", timeout=timeout)
    count = psql_scalar(
        f"SELECT COUNT(*) FROM tb_feature_dataset WHERE feature_json->>'feature_set_id' = '{feature_set_id}'"
    )
    if not count or int(count) <= 0:
        raise RuntimeError(f"Feature dataset empty after build: {feature_set_id}")


def ensure_csv_ingested(api: Callable[..., Any], *, limit: str = "10000") -> None:
    """heat·weather CSV 테이블이 비어 있으면 적재."""
    heat_count = int(psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_actual") or "0")
    if heat_count <= 0:
        heat = ensure_heat_csv_fixture(api)
        params = urllib.parse.urlencode({
            "source_id": heat["source_id"],
            "load_mode": "UPSERT",
            "limit": limit,
        })
        result = api("POST", f"/ingestion-jobs?{params}")
        if result.get("status") != "SUCCESS":
            raise RuntimeError(f"heat CSV ingest failed: {result}")

    weather_count = int(psql_scalar("SELECT COUNT(*) FROM tb_weather_observation") or "0")
    if weather_count <= 0:
        weather = ensure_weather_csv_fixture(api)
        params = urllib.parse.urlencode({
            "source_id": weather["source_id"],
            "load_mode": "UPSERT",
            "limit": limit,
        })
        result = api("POST", f"/ingestion-jobs?{params}")
        if result.get("status") != "SUCCESS":
            raise RuntimeError(f"weather CSV ingest failed: {result}")
