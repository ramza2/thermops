"""Feature 계산 메타데이터 Registry — calc_expression은 설명용, 실행은 ml/features.py."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

REGISTRY_VERSION = "1.0"


@dataclass(frozen=True)
class FeatureSpec:
    feature_name: str
    display_name: str
    feature_group: str
    feature_type: str
    calc_method: str
    calc_expression: str
    source_tables: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    partition_keys: list[str] = field(default_factory=list)
    time_key: str = "measured_at"
    lookback_hours: int | None = None
    requires_shift: bool = False
    leakage_safe: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _spec(
    feature_name: str,
    display_name: str,
    feature_group: str,
    feature_type: str = "DERIVED",
    calc_expression: str = "",
    source_tables: list[str] | None = None,
    source_columns: list[str] | None = None,
    partition_keys: list[str] | None = None,
    time_key: str = "measured_at",
    lookback_hours: int | None = None,
    requires_shift: bool = False,
    leakage_safe: bool = True,
    description: str = "",
) -> FeatureSpec:
    return FeatureSpec(
        feature_name=feature_name,
        display_name=display_name,
        feature_group=feature_group,
        feature_type=feature_type,
        calc_method="CODE",
        calc_expression=calc_expression,
        source_tables=source_tables or [],
        source_columns=source_columns or [],
        partition_keys=partition_keys or ["site_id"],
        time_key=time_key,
        lookback_hours=lookback_hours,
        requires_shift=requires_shift,
        leakage_safe=leakage_safe,
        description=description,
    )


_HEAT_TABLE = "tb_heat_demand_actual"
_WEATHER_TABLE = "tb_weather_observation"
_CALENDAR_TABLE = "tb_calendar"
_HEAT_COLS = ["site_id", "measured_at", "heat_demand"]
_WEATHER_COLS = ["weather_area_id", "measured_at", "temperature", "humidity", "rainfall", "wind_speed"]
_CAL_COLS = ["calendar_date", "day_of_week", "is_weekend", "is_holiday", "season"]


FEATURE_REGISTRY: dict[str, FeatureSpec] = {
    "month": _spec(
        "month",
        "월",
        "시간",
        feature_type="RAW",
        calc_expression="EXTRACT(month FROM measured_at)",
        source_tables=[_HEAT_TABLE],
        source_columns=["measured_at"],
        partition_keys=[],
        description="측정 시각의 월",
    ),
    "day_of_week": _spec(
        "day_of_week",
        "요일",
        "시간",
        feature_type="RAW",
        calc_expression="COALESCE(tb_calendar.day_of_week, EXTRACT(dow FROM measured_at))",
        source_tables=[_HEAT_TABLE, _CALENDAR_TABLE],
        source_columns=["measured_at", "day_of_week"],
        description="0=월요일 기준 요일",
    ),
    "hour": _spec(
        "hour",
        "시",
        "시간",
        feature_type="RAW",
        calc_expression="EXTRACT(hour FROM measured_at)",
        source_tables=[_HEAT_TABLE],
        source_columns=["measured_at"],
        partition_keys=[],
        description="측정 시각의 시",
    ),
    "month_sin": _spec(
        "month_sin",
        "월 사인",
        "시간",
        calc_expression="sin(2*pi*month/12)",
        source_tables=[_HEAT_TABLE],
        source_columns=["measured_at"],
        partition_keys=[],
        description="월 주기성 인코딩 (sin)",
    ),
    "month_cos": _spec(
        "month_cos",
        "월 코사인",
        "시간",
        calc_expression="cos(2*pi*month/12)",
        source_tables=[_HEAT_TABLE],
        source_columns=["measured_at"],
        partition_keys=[],
        description="월 주기성 인코딩 (cos)",
    ),
    "hour_sin": _spec(
        "hour_sin",
        "시 사인",
        "시간",
        calc_expression="sin(2*pi*hour/24)",
        source_tables=[_HEAT_TABLE],
        source_columns=["measured_at"],
        partition_keys=[],
        description="시간 주기성 인코딩 (sin)",
    ),
    "hour_cos": _spec(
        "hour_cos",
        "시 코사인",
        "시간",
        calc_expression="cos(2*pi*hour/24)",
        source_tables=[_HEAT_TABLE],
        source_columns=["measured_at"],
        partition_keys=[],
        description="시간 주기성 인코딩 (cos)",
    ),
    "is_weekend": _spec(
        "is_weekend",
        "주말 여부",
        "달력",
        feature_type="RAW",
        calc_expression="tb_calendar.is_weekend",
        source_tables=[_CALENDAR_TABLE, _HEAT_TABLE],
        source_columns=_CAL_COLS,
        description="주말이면 1",
    ),
    "is_holiday": _spec(
        "is_holiday",
        "공휴일 여부",
        "달력",
        feature_type="RAW",
        calc_expression="tb_calendar.is_holiday",
        source_tables=[_CALENDAR_TABLE, _HEAT_TABLE],
        source_columns=_CAL_COLS,
        description="공휴일이면 1",
    ),
    "season_winter": _spec(
        "season_winter",
        "겨울 시즌",
        "달력",
        calc_expression="season == WINTER",
        source_tables=[_CALENDAR_TABLE, _HEAT_TABLE],
        source_columns=_CAL_COLS,
        description="겨울 시즌이면 1",
    ),
    "season_summer": _spec(
        "season_summer",
        "여름 시즌",
        "달력",
        calc_expression="season == SUMMER",
        source_tables=[_CALENDAR_TABLE, _HEAT_TABLE],
        source_columns=_CAL_COLS,
        description="여름 시즌이면 1",
    ),
    "temperature": _spec(
        "temperature",
        "기온",
        "기상",
        feature_type="RAW",
        calc_expression="JOIN tb_weather_observation ON site_weather_map",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        description="지사-기상권역 매핑 후 시간 단위 기온",
    ),
    "humidity": _spec(
        "humidity",
        "습도",
        "기상",
        feature_type="RAW",
        calc_expression="JOIN tb_weather_observation ON site_weather_map",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        description="지사-기상권역 매핑 후 습도",
    ),
    "rainfall": _spec(
        "rainfall",
        "강수량",
        "기상",
        feature_type="RAW",
        calc_expression="JOIN tb_weather_observation ON site_weather_map",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        description="지사-기상권역 매핑 후 강수량",
    ),
    "wind_speed": _spec(
        "wind_speed",
        "풍속",
        "기상",
        feature_type="RAW",
        calc_expression="JOIN tb_weather_observation ON site_weather_map",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        description="지사-기상권역 매핑 후 풍속",
    ),
    "demand_lag_24h": _spec(
        "demand_lag_24h",
        "24시간 전 열수요",
        "열수요 이력",
        calc_expression="LAG(heat_demand, 24)",
        source_tables=[_HEAT_TABLE],
        source_columns=_HEAT_COLS,
        lookback_hours=24,
        requires_shift=True,
        description="동일 지사 기준 24시간 전 열수요",
    ),
    "demand_lag_168h": _spec(
        "demand_lag_168h",
        "168시간 전 열수요",
        "열수요 이력",
        calc_expression="LAG(heat_demand, 168)",
        source_tables=[_HEAT_TABLE],
        source_columns=_HEAT_COLS,
        lookback_hours=168,
        requires_shift=True,
        description="동일 지사 기준 168시간(7일) 전 열수요",
    ),
    "demand_ma_24h": _spec(
        "demand_ma_24h",
        "24시간 이동평균 열수요",
        "열수요 이력",
        calc_expression="MA(heat_demand, 24)",
        source_tables=[_HEAT_TABLE],
        source_columns=_HEAT_COLS,
        lookback_hours=24,
        requires_shift=False,
        leakage_safe=False,
        description="동일 지사 기준 최근 24시간 열수요 이동평균 (현재 시점 포함)",
    ),
    "demand_ma_168h": _spec(
        "demand_ma_168h",
        "168시간 이동평균 열수요",
        "열수요 이력",
        calc_expression="MA(heat_demand, 168)",
        source_tables=[_HEAT_TABLE],
        source_columns=_HEAT_COLS,
        lookback_hours=168,
        requires_shift=False,
        leakage_safe=False,
        description="동일 지사 기준 최근 168시간 열수요 이동평균 (현재 시점 포함)",
    ),
    "temperature_lag_24h": _spec(
        "temperature_lag_24h",
        "24시간 전 기온",
        "기상 이력",
        calc_expression="LAG(temperature, 24)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        lookback_hours=24,
        requires_shift=True,
        description="동일 지사 기준 24시간 전 기온",
    ),
    "humidity_lag_24h": _spec(
        "humidity_lag_24h",
        "24시간 전 습도",
        "기상 이력",
        calc_expression="LAG(humidity, 24)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        lookback_hours=24,
        requires_shift=True,
        description="동일 지사 기준 24시간 전 습도",
    ),
    "temperature_ma_24h": _spec(
        "temperature_ma_24h",
        "24시간 이동평균 기온",
        "기상 이력",
        calc_expression="MA(temperature, 24)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        lookback_hours=24,
        leakage_safe=False,
        description="동일 지사 기준 최근 24시간 기온 이동평균",
    ),
    "temperature_diff_24h": _spec(
        "temperature_diff_24h",
        "24시간 전 대비 기온 차",
        "기상 이력",
        calc_expression="DIFF(temperature, 24)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=_WEATHER_COLS,
        lookback_hours=24,
        requires_shift=True,
        description="현재 기온 − 24시간 전 기온",
    ),
    "heating_degree_days": _spec(
        "heating_degree_days",
        "난방도일",
        "쾌적·도일",
        calc_expression="HDD(temperature, 18)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=["temperature"],
        description="기준 18℃ 대비 난방도일 max(18−T, 0)",
    ),
    "cooling_degree_days": _spec(
        "cooling_degree_days",
        "냉방도일",
        "쾌적·도일",
        calc_expression="CDD(temperature, 24)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=["temperature"],
        description="기준 24℃ 대비 냉방도일 max(T−24, 0)",
    ),
    "comfort_distance": _spec(
        "comfort_distance",
        "쾌적 거리",
        "쾌적·도일",
        calc_expression="max(18-T, T-24, 0)",
        source_tables=[_WEATHER_TABLE, "tb_site_weather_mapping"],
        source_columns=["temperature"],
        description="쾌적 구간(18~24℃) 이탈 거리",
    ),
}

OFFICIAL_FEATURE_NAMES = frozenset({
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_ma_24h",
    "demand_ma_168h",
    "temperature_diff_24h",
    "heating_degree_days",
    "cooling_degree_days",
})


def get_feature_spec(feature_name: str) -> FeatureSpec | None:
    return FEATURE_REGISTRY.get(feature_name)


def list_feature_specs() -> list[FeatureSpec]:
    return [FEATURE_REGISTRY[k] for k in sorted(FEATURE_REGISTRY)]


def list_feature_names() -> list[str]:
    return sorted(FEATURE_REGISTRY)


def spec_to_lineage_payload(spec: FeatureSpec) -> dict[str, Any]:
    payload = spec.to_dict()
    payload["registry_version"] = REGISTRY_VERSION
    return payload


def assert_covers_computed_features(computed_names: list[str]) -> None:
    """ml/features.py ALL_COMPUTED_FEATURES가 Registry에 모두 등록됐는지 검증."""
    missing = sorted(set(computed_names) - set(FEATURE_REGISTRY))
    if missing:
        raise ValueError(f"Feature Registry missing specs for: {missing}")
    extra = sorted(set(FEATURE_REGISTRY) - set(computed_names))
    if extra:
        raise ValueError(f"Feature Registry has specs not in ALL_COMPUTED_FEATURES: {extra}")
