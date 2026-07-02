"""회귀 테스트용 런타임 픽스처 — clean seed에 없는 데이터 소스·매핑을 테스트 시 생성."""

from __future__ import annotations

from typing import Any, Callable

HEAT_SOURCE_NAME = "TEST 열수요 CSV"
WEATHER_SOURCE_NAME = "TEST 기상 CSV"
HEAT_MAPPING_NAME = "TEST 열수요 CSV 표준 매핑"
WEATHER_MAPPING_NAME = "TEST 기상 CSV 표준 매핑"

_heat_fixture: dict[str, str] | None = None
_weather_fixture: dict[str, str] | None = None


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


def heat_pipeline_node_config(api: Callable[..., Any]) -> dict[str, dict[str, str]]:
    """Pipeline Builder/Execution 테스트용 노드 설정."""
    fx = ensure_heat_csv_fixture(api)
    return {
        "DATA_SOURCE": {"data_source_id": fx["source_id"]},
        "DATA_MAPPING": {"mapping_id": fx["mapping_id"]},
        "STANDARD_DATASET": {"dataset_type_id": "DST-HEAT-DEMAND-ACTUAL"},
        "FEATURE_SET": {"feature_set_id": "FS-TPL-LAG-ROLL"},
        "FEATURE_BUILD": {"feature_set_id": "FS-TPL-LAG-ROLL"},
    }


def resolve_heat_mapping_id(api: Callable[..., Any]) -> str:
    import os
    env = os.environ.get("THERMOOPS_HEAT_MAPPING_ID")
    if env:
        return env
    return ensure_heat_csv_fixture(api)["mapping_id"]


def resolve_weather_mapping_id(api: Callable[..., Any]) -> str:
    import os
    env = os.environ.get("THERMOOPS_WEATHER_MAPPING_ID")
    if env:
        return env
    return ensure_weather_csv_fixture(api)["mapping_id"]


def resolve_heat_source_id(api: Callable[..., Any]) -> str:
    import os
    env = os.environ.get("THERMOOPS_HEAT_SOURCE_ID")
    if env:
        return env
    return ensure_heat_csv_fixture(api)["source_id"]


def resolve_weather_source_id(api: Callable[..., Any]) -> str:
    import os
    env = os.environ.get("THERMOOPS_WEATHER_SOURCE_ID")
    if env:
        return env
    return ensure_weather_csv_fixture(api)["source_id"]
