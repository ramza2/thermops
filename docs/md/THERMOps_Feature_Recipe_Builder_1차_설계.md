# THERMOps Feature Recipe Builder 1차 설계

> **문서 유형**: 기획·설계·영향 분석 (구현 없음)  
> **작성 기준**: `master` @ Feature Legacy 일괄 대체 완료 시점  
> **범위**: 범용 MLOps 확장을 위한 Feature Recipe Builder 1차 설계

---

## 1. 배경과 문제점

### 1.1 배경

THERMOps는 열수요 예측(Heat Demand Forecasting) 시연을 위해 구축된 MLOps 스타터이다. Feature 영역에는 이미 다음이 갖춰져 있다.

| 영역 | 현재 상태 |
|------|-----------|
| Feature Catalog | `tb_feature` — 메타데이터 등록 |
| Feature Registry | `ml/feature_registry.py` — CODE 기반 계산 메타 |
| Feature Lineage | `tb_feature_lineage` — Build 시 Registry 스펙 저장 |
| Feature Build | `ml/features.py` → `tb_feature_dataset.feature_json` |
| Feature Quality | `feature_json` 기반 null/범위/이상치 검증 |
| 등록 검증 | Registry/Catalog/Legacy 분류 API·UI |
| Legacy 대체 | Feature Set 내 alias → 공식명 일괄 치환 |

그러나 **Feature 생성 방식**은 여전히 열수요 도메인에 고정되어 있다.

- 계산 로직: `build_feature_frame(heat_df, weather_df, calendar_df, site_weather_map)` 단일 함수
- Entity/Time/Target: `site_id`, `measured_at`, `heat_demand` 하드코딩
- 신규 Feature: Python 코드 + Registry 수동 추가 → Catalog 등록 → Feature Set 수동 편집
- `calc_expression`: 설명용 텍스트이며 UI에서도 직접 입력 — **실행·검증·미리보기와 연결되지 않음**

### 1.2 문제점

1. **도메인 결합**: Feature명·소스 테이블·파티션 키가 열수요 전용이다.
2. **텍스트 의존 UI**: Feature명·계산식 메모·그룹을 사용자가 직접 타이핑한다.
3. **Recipe 부재**: “어떤 컬럼에 어떤 연산을 적용했는지”를 구조화해 저장·재현·버전관리할 수 없다.
4. **범용 Preview 불가**: 현재 Preview는 기존 CODE Feature Set에 한정되며, 사용자 정의 파생 Feature 시험 불가.
5. **컬럼 역할 미관리**: `tb_data_mapping.columns`는 `source_column`↔`target_column`만 있고 ENTITY_KEY/TIME_KEY 등 역할이 없다.

### 1.3 1차 설계 목표

- **구현하지 않고** 설계·영향 분석·로드맵만 수립한다.
- 사용자가 **계산식 문자열을 입력하지 않고**, 컬럼 선택 + 연산 템플릿 + 파라미터 + 미리보기로 Feature를 정의한다.
- 기존 열수요 Feature는 **폐기하지 않고** Domain Template Pack으로 분리하는 방향을 검토한다.
- DSL 파서·드래그드롭 Canvas·Recipe Engine **구현은 하지 않는다**.

---

## 2. 현재 Feature 구조 진단

### 2.1 현재 흐름 요약

```
[데이터 적재] tb_heat_demand_actual / tb_weather_observation / tb_calendar
       ↓
[Feature Catalog] tb_feature (메타, calc_expression=설명용)
       ↓
[Feature Set] tb_feature_set.features[] (feature_name 문자열 목록)
       ↓
[Feature Build] ml/features.py build_feature_frame() — CODE 전용
       ↓
[tb_feature_dataset] feature_json { feature_name: value, ... }
       ↓
[Lineage] tb_feature_lineage (Registry FeatureSpec 복사)
       ↓
[Quality] feature_json 검증 (열수요 RANGE_RULES)
       ↓
[Training] tb_training_config.feature_set_id → 학습/예측
```

### 2.2 범용성 진단표

| 영역 | 현재 구조 | 범용화 문제점 | 개선 방향 | 영향 범위 | 우선순위 |
|------|-----------|---------------|-----------|-----------|----------|
| Feature명 | `demand_lag_24h`, `heating_degree_days` 등 도메인 의미 내장 | 다른 도메인(매출·설비)에 그대로 쓰기 어려움 | Recipe 기반 자동 명명 규칙 + Domain Pack prefix | Catalog, Registry, UI, 학습 feature_json key | P0 |
| 계산 로직 | `ml/features.py`에 열수요·기상·달력 결합 하드코딩 | 테이블·컬럼명 변경 시 코드 수정 필수 | CODE Pack(유지) + TEMPLATE Recipe Engine(신규) 이원화 | ml/, feature_build_service | P0 |
| Entity Key | `site_id` 고정 (`groupby`, `partition_keys`) | 범용 entity(고객·설비·매장) 미지원 | Column Role `ENTITY_KEY` + Recipe `entity_keys[]` | mapping, recipe, engine | P1 |
| Time Key | `measured_at` 고정 | 비정형 시계열·일 단위 데이터 미대응 | Column Role `TIME_KEY` + granularity 메타 | mapping, recipe, engine | P1 |
| Target Column | `heat_demand` / `target_heat_demand` | 타겟 개념이 스키마·Quality에 박혀 있음 | Column Role `TARGET` + Training Config 연계 | entities, quality, training | P1 |
| 데이터소스 매핑 | `tb_data_mapping.columns`: source↔target만 | 컬럼 역할·타입·granularity 없음 | `tb_feature_column_role` 또는 mapping JSON 확장 | mapping_service, ingestion UI | P1 |
| Recipe 저장 | 없음 (`tb_feature`에 recipe 필드 없음) | 사용자 정의 파생 Feature 재현 불가 | `tb_feature_recipe` 신규 (1:N feature_name) | DB, API, UI | P2 |
| Preview/Dry-run | Feature Set 단위, `build_feature_frame` 결과 10행 | Recipe 단위·파라미터 변경 시험 불가 | `POST /feature-recipes/preview` (비저장) | API, UI, engine | P2 |
| Quality/Lineage | Registry CODE 스펙·열수요 RANGE_RULES | Recipe Feature 메타·범위 규칙 미연동 | `calc_method=TEMPLATE`, `lineage_json.recipe_params` | quality_service, lineage_service | P3 |
| 신규 Feature UI | Feature명·calc_expression 텍스트 입력 | 오타·비표준 명칭·실행 불가 식 입력 | Recipe Builder 마법사 (선택식) | FeaturesPage, 신규 페이지 | P2 |
| Feature Set 연결 | `features: string[]` 수동 추가 | Recipe→Feature명 자동 등록 없음 | publish 시 Catalog+Set 연동 API | feature API, UI | P3 |
| Training 연결 | `tb_training_config.feature_set_id` | Recipe 변경과 학습 영향 추적 없음 | feature_config_hash + recipe version | training_service | P4 |
| Domain Template | `FS-TPL-*`, `target_domain=HEAT_DEMAND` | 다른 도메인 템플릿 없음 | `tb_domain_feature_pack` + seed 분리 | seed, UI | P4 |

### 2.3 열수요 도메인에 고정된 부분

| 위치 | 고정 내용 |
|------|-----------|
| `ml/features.py` | `heat_demand`, `site_id`, `measured_at`, weather join, calendar join, HDD/CDD 기준온도 |
| `ml/feature_registry.py` | `_HEAT_TABLE`, `_WEATHER_TABLE`, `partition_keys=["site_id"]`, `time_key="measured_at"` |
| `feature_build_service.py` | `_fetch_heat`, `_fetch_weather`, `_fetch_calendar`, `MIN_HISTORY_HOURS=168` |
| `feature_quality_service.py` | `RANGE_RULES` 열수요·기상 전용, `heat_demand` 범위 |
| `tb_feature_dataset` | `target_heat_demand`, `site_id`, 레거시 lag 컬럼 |
| `FEATURE_SET_TEMPLATES` | 전부 `target_domain: HEAT_DEMAND` |
| `mapping_service.py` | `HEAT_TARGET` / `WEATHER_TARGET` 이원 표준 스키마 |

### 2.4 범용화 가능한 부분

| 위치 | 재사용 가능 요소 |
|------|------------------|
| `FeatureSpec` | `partition_keys`, `time_key`, `lookback_hours`, `requires_shift`, `leakage_safe` — Recipe 메타로 확장 가능 |
| `tb_feature_lineage` | `calc_method`, `source_tables`, `lineage_json` — TEMPLATE 연동 여지 |
| `feature_registration_service` | COMPUTABLE/CATALOG_ONLY/LEGACY 분류 → `calc_mode` 추가 확장 |
| `DataQualityRun` | FEATURE_BUILD / FEATURE_QUALITY job 패턴 — Recipe Preview Run에 재사용 |
| `feature_json` | key-value 저장 — Recipe 출력도 동일 키로 저장 가능 |
| Preview API 패턴 | `POST /feature-sets/{id}/preview` — Recipe Preview API 설계 참고 |
| UI 패턴 | 등록 유형 뱃지, 검증 패널, dry-run 모달 — Recipe Builder에 재사용 |

### 2.5 사용자 텍스트 입력 지점 (현재)

| 화면 | 텍스트 입력 항목 | Recipe Builder 대체 방향 |
|------|------------------|--------------------------|
| FeaturesPage — 등록 | `feature_name`, `feature_group`, `calc_expression`, `description` | Recipe publish 시 자동 생성; 그룹·설명은 템플릿 기본값 |
| FeatureSetDetailPage | `feature_set_name`, `text`(설명), `featureSearch`, Feature 수동 체크 | Set 메타만 텍스트; Feature는 Recipe에서 추가 |
| FeatureSetDetailPage — 생성 | `site_id`, `start_at`, `end_at` (Preview/Build) | 드롭다운·날짜 피커 유지 (선택식) |
| Data Mapping UI | `source_column`, `target_column` | 컬럼 역할 드롭다운 추가; target은 표준 스키마 선택 |

---

## 3. 범용 Feature Recipe 개념

### 3.1 정의

**Feature Recipe**는 사용자가 UI 마법사에서 선택한 입력 컬럼·연산 유형·파라미터·출력 Feature명을 **안전한 JSON**으로 구조화한 계산 정의이다.

- 임의 문자열 계산식(DSL)이 **아니다**.
- Backend는 **지원 operation 화이트리스트**만 검증·(향후) 실행한다.
- Lineage·Quality·Feature Set·Catalog와 연결 가능해야 한다.

### 3.2 calc_mode 분류 (Feature 전체)

| calc_mode | 설명 | 저장 위치 | Build 시 처리 |
|-----------|------|-----------|---------------|
| `CODE` | `ml/features.py` + Registry | Registry + (선택) Catalog | `build_feature_frame()` |
| `TEMPLATE` | Recipe JSON 기반 | `tb_feature_recipe` | Recipe Engine (향후) |
| `RAW` | 원본 컬럼 pass-through | Recipe 또는 Catalog | RAW_COLUMN 템플릿 |
| `CATALOG_ONLY` | 메타만 있고 계산 없음 | `tb_feature` | warning, key 미생성 |

### 3.3 Recipe 기본 필드 (후보)

```json
{
  "recipe_id": "RCP-20250624-ABC123",
  "feature_name": "sales_lag_7d",
  "display_name": "7일 전 매출",
  "description": "매장별 7 step lag",
  "domain": "SALES_FORECAST",
  "task_type": "REGRESSION",
  "calc_mode": "TEMPLATE",
  "recipe_type": "LAG",
  "source_dataset_id": "DS-001",
  "source_table": "tb_sales_actual",
  "source_column": "sales_amount",
  "source_columns": ["sales_amount"],
  "entity_keys": ["store_id"],
  "time_key": "transaction_date",
  "target_column": "sales_amount",
  "params": {
    "offset_steps": 7,
    "granularity": "1d",
    "include_current_row": false,
    "sort_order": "asc"
  },
  "output_data_type": "NUMERIC",
  "unit": "KRW",
  "null_handling": "PASS",
  "leakage_policy": "SHIFT_REQUIRED",
  "preview_enabled": true,
  "status": "DRAFT",
  "owner": "user@example.com",
  "version": 1,
  "created_at": "2026-06-24T00:00:00Z",
  "updated_at": "2026-06-24T00:00:00Z"
}
```

### 3.4 저장 구조 검토

| 방안 | 장점 | 단점 | 1차 권장 |
|------|------|------|----------|
| A. `tb_feature`에 `recipe_json` 컬럼 확장 | Catalog·Recipe 일원화 | migration 필요; Catalog-only와 혼재 | Phase R5 이후 검토 |
| B. **`tb_feature_recipe` 별도 테이블** | 관심사 분리, 버전·상태 관리 용이 | feature_name 동기화 필요 | **1차 권장** |
| C. Feature Set `features`에 recipe_id embed | migration 최소 | Set만으로 Recipe 재사용 어려움 | 비권장 |

**권장 관계**

```
tb_feature_recipe (1) ──publish──> tb_feature (0..1)  [feature_name UNIQUE]
tb_feature_recipe (N) ──used by──> tb_feature_set.features[]  [feature_name 문자열]
tb_feature (Catalog)  ←──registry── ml/feature_registry.py (CODE only)
```

- `feature_name`은 Recipe publish 시 확정; 동일 이름 중복 불가.
- `recipe_id`는 내부 식별자; `feature_name`은 학습·예측·feature_json key.
- CODE Registry Feature는 `recipe_id` 없음 (`calc_method=CODE`).
- 버전: `tb_feature_recipe_version`에 스냅샷; publish 시 version 증가.

### 3.5 Registry와 Recipe 공존

| 유형 | calc_method | 관리 주체 | UI 표시 |
|------|-------------|-----------|---------|
| CODE (Heat Pack) | CODE | `ml/feature_registry.py` | Registry Panel, 읽기 전용 |
| TEMPLATE (사용자 Recipe) | TEMPLATE | `tb_feature_recipe` | Recipe Builder, 편집 가능 |
| CATALOG_ONLY | — | `tb_feature` | Catalog 등록, 경고 |

`FeatureSpec` 확장 후보 (코드 변경은 Phase R6+):

- `calc_method: CODE | TEMPLATE`
- `recipe_id: str | None`
- `recipe_type: str | None`

---

## 4. Column Role 설계

### 4.1 컬럼 역할 enum

| Role | 설명 | 필수 개수 |
|------|------|-----------|
| `ENTITY_KEY` | 시계열 그룹 키 (site, store, equipment) | ≥1 (LAG/ROLLING 시) |
| `TIME_KEY` | 시간 축 | 1 (시계열 템플릿 시) |
| `TARGET` | 예측 대상 (학습 라벨) | 0~1 |
| `NUMERIC_INPUT` | 수치형 입력 | 템플릿별 |
| `CATEGORICAL_INPUT` | 범주형 입력 | Encoding 시 |
| `BOOLEAN_INPUT` | 불리언 | 선택 |
| `JOIN_KEY` | 테이블 조인 키 | 다중 소스 시 |
| `EXCLUDE` | Feature 제외 | — |
| `ID` | 식별자(학습 미사용) | — |
| `TEXT` | 자유 텍스트(1차 미지원) | — |
| `LOCATION` | 위치(geo) | 향후 |
| `DATETIME` | TIME_KEY 보조·파생 원본 | DATE_PART 시 |
| `MEASURE` | 측정값(=NUMERIC_INPUT alias) | — |

### 4.2 매핑 단계 역할 지정

**현재** `tb_data_mapping.columns` 구조:

```json
{ "source_column": "SITE_CD", "target_column": "site_id", "required_yn": true }
```

**확장 후보** (migration 또는 JSON 확장):

```json
{
  "source_column": "SITE_CD",
  "target_column": "site_id",
  "data_type": "STRING",
  "column_role": "ENTITY_KEY",
  "required_yn": true
}
```

- 데이터소스·매핑 UI에서 컬럼별 **역할 드롭다운** 제공.
- `target_table`별 **권장 역할 프리셋** (heat_demand_actual → site_id=ENTITY_KEY, measured_at=TIME_KEY, heat_demand=TARGET).

### 4.3 Recipe Builder에서 역할 기반 템플릿 제한

| 조건 | 비활성화 템플릿 |
|------|------------------|
| TIME_KEY 없음 | LAG, ROLLING_*, DIFF, DATE_PART(시계열) |
| ENTITY_KEY 없음 | LAG, ROLLING_*, DIFF (단일 시계열 제외 옵션은 고급) |
| NUMERIC_INPUT 없음 | ROLLING_*, RATIO, BINNING, DIFF |
| CATEGORICAL_INPUT 없음 | CATEGORY_ENCODING |
| TARGET 없음 | (경고만) 학습 연결 시 TARGET 필요 안내 |

### 4.4 자동 추론 규칙 (1차)

| 신호 | 추론 역할 |
|------|-----------|
| 컬럼명 `*_at`, `*_date`, `timestamp` + datetime 타입 | TIME_KEY 후보 |
| 컬럼명 `*_id`, `site_id`, `store_id` + cardinality 높음 | ENTITY_KEY 후보 |
| `heat_demand`, `sales`, `amount` + numeric | TARGET 또는 NUMERIC_INPUT |
| cardinality < 50 + string | CATEGORICAL_INPUT 후보 |
| boolean / 0·1 | BOOLEAN_INPUT |

자동 추론은 **제안**만; 사용자 확인 후 확정.

### 4.5 Validation

- TIME_KEY 2개 이상 지정 → 오류
- ENTITY_KEY + TIME_KEY 동일 컬럼 → 오류
- LAG 템플릿 + `include_current_row=true` + TARGET 동일 컬럼 → leakage 경고
- ROLLING + `include_current_row=true` + TARGET → leakage 경고 (강등 또는 차단)

---

## 5. Recipe Template 1차 범위

### 5.1 템플릿 상세표

| recipe_type | 설명 | 필요 컬럼 역할 | 필요 파라미터 | 출력 Feature명 자동 생성 규칙 | 누수 위험 | 1차 난이도 | 1차 포함 | 비고 |
|-------------|------|----------------|---------------|------------------------------|-----------|------------|----------|------|
| RAW_COLUMN | 원본 컬럼을 Feature로 사용 | NUMERIC_INPUT 또는 CATEGORICAL_INPUT | `source_column` | `{column}` 또는 `{table}_{column}` | 낮음 | 낮음 | **포함** | Phase R3 |
| DATE_PART | timestamp에서 hour/dow/month/is_weekend 등 | TIME_KEY 또는 DATETIME | `parts[]`: hour, day_of_week, month, is_weekend | `{time_key}_{part}` | 낮음 | 낮음 | **포함** | Phase R3 |
| LAG | entity+time 기준 n step 이전 값 | ENTITY_KEY, TIME_KEY, NUMERIC_INPUT | `offset_steps`, `granularity`, `include_current_row=false`, `sort_order` | `{col}_lag_{n}{unit}` | **높음** (shift 누락 시) | 중간 | **포함** | Phase R4; `requires_shift=true` |
| ROLLING_MEAN | 최근 n step 평균 | ENTITY_KEY, TIME_KEY, NUMERIC_INPUT | `window_steps`, `min_periods`, `include_current_row` | `{col}_ma_{n}{unit}` | **중~높음** (현재 행 포함 시) | 중간 | **포함** | Phase R4 |
| ROLLING_SUM | 최근 n step 합계 | 동일 | `window_steps`, `min_periods`, `include_current_row` | `{col}_sum_{n}{unit}` | 중~높음 | 중간 | **포함** | Phase R4 |
| DIFF | 현재값 − n step 이전값 | ENTITY_KEY, TIME_KEY, NUMERIC_INPUT | `offset_steps`, `granularity` | `{col}_diff_{n}{unit}` | 중간 | 중간 | **포함** | Phase R4 |
| RATIO | column_a / column_b | NUMERIC_INPUT ×2 | `numerator`, `denominator`, `epsilon` | `{a}_over_{b}` | 낮음 | 낮음 | **포함** | Phase R5; div0 처리 |
| BINNING | numeric 구간화 | NUMERIC_INPUT | `bins[]` 또는 `n_bins`, `strategy` | `{col}_bin` | 낮음 | 중간 | **포함** | Phase R5 |
| FILL_NULL | 결측 처리 변환 | 임의 입력 컬럼 | `strategy`: PREV/MEAN/ZERO/DROP | `{col}_filled` | 낮음 | 낮음 | **포함** | Phase R5 |
| CATEGORY_ENCODING | 범주형 인코딩 | CATEGORICAL_INPUT | `method`: ONE_HOT/LABEL/ORDINAL | `{col}_{method}` | 낮음 | 중간 | **후보** | cardinality 제한 필요 |

### 5.2 LAG / ROLLING / DIFF 공통 시계열 개념

| 개념 | 설명 | Recipe params |
|------|------|---------------|
| `entity_keys` | groupby 키 배열 | `["site_id"]` |
| `time_key` | 정렬·shift 기준 시각 컬럼 | `"measured_at"` |
| `sort_order` | `asc` (과거→현재) | 필수 |
| `offset_steps` / `window_steps` | **row step** 수 (granularity와 곱해 실제 시간 환산) | 24, 168 등 |
| `granularity` | `1h`, `1d`, `1w` — step↔시간 변환 | `1h` |
| `include_current_row` | rolling window에 현재 행 포함 | default `false` (TARGET 시) |
| `shift` 적용 | LAG/DIFF는 항상 shift; ROLLING은 window 정의에 따름 | `requires_shift` 메타 |
| 시간 단위 vs row step | 데이터가 균등 간격이 아니면 **row step ≠ 시간** 경고 | Preview에서 gap 검사 |
| leakage 방지 | TARGET 동일 컬럼 + include_current → 경고/차단 | `leakage_policy` |

열수요 CODE 매핑 예:

- `demand_lag_24h` = LAG(heat_demand, offset=24, granularity=1h, entity=site_id)
- `demand_ma_24h` = ROLLING_MEAN(heat_demand, window=24, include_current=true) → `leakage_safe=false`

---

## 6. Feature Recipe Builder UI 흐름

### 6.1 진입점 (향후)

- `/features` → 「Recipe로 Feature 만들기」
- `/feature-sets/:id` → 「Recipe Feature 추가」
- Domain Pack 갤러리 → Pack Feature 복제

### 6.2 마법사 단계표

| 단계 | 사용자 입력 방식 | 선택지 | 자동 추천/생성 | validation | 다음 단계 조건 | 화면 안내 문구 |
|------|------------------|--------|----------------|------------|----------------|----------------|
| 1. 생성 방식 | 카드 클릭 | 원본 컬럼 / 시계열 / 집계 / 비율·수식 / 날짜·시간 / 범주형 | Domain Pack 추천 배너 | — | 1개 선택 | 「계산식을 직접 입력하지 않습니다. 템플릿을 선택하세요.」 |
| 2. 데이터 소스 | 드롭다운 | 등록된 DataSource + target_table | 최근 사용·활성 매핑 | 매핑 없으면 매핑 UI 링크 | source+table 확정 | 「Feature를 만들 데이터가 적재된 테이블을 선택하세요.」 |
| 3. 입력 컬럼 | 검색 가능 드롭다운 | 역할별 필터된 컬럼 목록 | 매핑 기반 목록 | 템플릿별 최소 컬럼 수 | 필수 컬럼 선택 완료 | 「원천 컬럼을 선택하세요. 역할이 맞지 않으면 매핑을 수정하세요.」 |
| 4. 컬럼 역할 확인 | 읽기+수정(드롭다운) | ENTITY_KEY, TIME_KEY, … | 자동 추론 제안 | TIME_KEY 1개, ENTITY≥1 | 역할 validation 통과 | 「시계열 Feature는 시간 축과 그룹 키가 필요합니다.」 |
| 5. 연산 템플릿 | 카드/라디오 | recipe_type 목록 (역할로 필터) | 1단계 선택과 연동 | 비활성 템플릿 grey-out | 1개 선택 | 「지원되는 연산만 선택할 수 있습니다.」 |
| 6. 파라미터 | 슬라이더·숫자·토글·프리셋 버튼 | offset 24/168, window, bins… | 열수요 프리셋(24h/168h) | 범위·정수·leakage 규칙 | 필수 param 입력 | 「24시간 = 24 step (1시간 간격 데이터 기준)」 |
| 7. 출력 Feature명 | 읽기 우선 텍스트 (수정 가능) | 자동 생성명 | `{col}_lag_{n}h` 규칙 | validate-name API 실시간 | COMPUTABLE/DUPLICATE 아님 | 「이름은 자동 생성됩니다. 필요 시만 수정하세요.」 |
| 8. 미리보기 | 기간·site 드롭다운 + 실행 버튼 | 최근 100행 / 기간 선택 | dataset-range API | Preview 성공 또는 경고 확인 | 사용자 「다음」 클릭 | 「저장 전 샘플 결과를 확인하세요. DB에 저장되지 않습니다.」 |
| 9. Registry/Catalog 등록 | 체크박스 (기본 on) | Catalog 등록, 설명 편집 | display_name, description | publish validation | — | 「Catalog에 등록되어 Feature Set에서 선택할 수 있습니다.」 |
| 10. Feature Set 추가 | 드롭다운 + 체크 | 현재 Set / 다른 Set | 현재 Set pre-select | TPL Set은 COMPUTABLE만 | 선택적 | 「바로 이 Feature Set에 추가할 수 있습니다.」 |
| 11. Build 안내 | 안내 패널 | 「Feature 생성 실행」링크 | — | — | 선택적 스킵 | 「값을 저장하려면 Feature 생성 작업을 실행하세요.」 |
| 12. Quality 안내 | 안내 패널 | 「품질 검증 실행」링크 | — | — | 종료 | 「학습 전 Feature 품질 검증을 권장합니다.」 |

### 6.3 UI 원칙

- 텍스트 직접 입력 최소화 (Feature명·설명만 예외적 수정)
- `calc_expression` 입력 필드 **없음** — 대신 `recipe_type` + `params` 요약 표시
- 고급 옵션(leakage override, custom granularity)은 접기 영역
- 잘못된 조합은 선택 불가 또는 경고 배너

---

## 7. Preview / Dry-run 설계

### 7.1 목적

Recipe publish **전** 샘플 결과를 확인한다. `tb_feature_dataset`에 **저장하지 않는다**.

### 7.2 Preview 요청 (후보)

`POST /api/v1/feature-recipes/preview`

```json
{
  "recipe": { "...": "Recipe JSON (DRAFT 가능)" },
  "sample_size": 100,
  "site_id": "SITE-001",
  "start_at": "2025-01-01T00:00:00",
  "end_at": "2025-01-07T00:00:00",
  "entity_keys": ["site_id"],
  "time_key": "measured_at"
}
```

### 7.3 Preview 응답 (후보)

```json
{
  "feature_name": "demand_lag_24h",
  "preview_rows": [ { "site_id": "...", "measured_at": "...", "demand_lag_24h": 123.4 } ],
  "stats": {
    "row_count": 100,
    "null_ratio": 0.02,
    "invalid_ratio": 0.0,
    "outlier_count": 1
  },
  "leakage_warnings": ["TARGET(heat_demand)에 include_current_row=true 시 누수 위험"],
  "feature_json_key_preview": "demand_lag_24h",
  "lineage_preview": {
    "calc_method": "TEMPLATE",
    "recipe_type": "LAG",
    "source_columns": ["heat_demand"],
    "params": { "offset_steps": 24 }
  },
  "quality_preview": {
    "estimated_status": "WARNING",
    "null_ratio": 0.02
  },
  "warnings": ["site SITE-002: 이력 120h — lag 168 일부 결측"],
  "errors": []
}
```

### 7.4 구현 원칙

| 항목 | 정책 |
|------|------|
| 저장 | Preview 결과 DB 미저장; `tb_feature_recipe_preview_run`에 선택적 이력 |
| 샘플링 | 기본 100행; 대용량은 entity·기간 필터 + `LIMIT` |
| 데이터 소스 | 적재된 표준 테이블에서 pandas 로드 (Recipe Engine) |
| 실패 | 사용자 친화 메시지 (컬럼 없음, 역할 누락, step>이력) |
| CODE Feature | 기존 `preview_features` 유지; Recipe Preview는 TEMPLATE 전용 |

### 7.5 Validate API

`POST /api/v1/feature-recipes/validate` — DB·실행 없이 스키마·역할·이름·leakage만 검증.

---

## 8. Recipe Engine 설계

### 8.1 이원화 아키텍처

```
Feature Build 요청
       │
       ├─ feature_name ∈ CODE Registry (ALL_COMPUTED_FEATURES)
       │       └─ build_feature_frame()  [기존 유지, 수정 금지 1차]
       │
       ├─ feature_name ∈ TEMPLATE Recipe (tb_feature_recipe)
       │       └─ feature_recipe_engine.apply(recipe, base_df)
       │
       ├─ CATALOG_ONLY → warning, key skip
       │
       └─ LEGACY_ALIAS → 공식명 대체 유도 (기존 로직)
```

### 8.2 모듈 구조 (향후)

```
ml/
  features.py                    # CODE Heat Pack (유지)
  feature_registry.py            # CODE specs (유지)
  feature_recipe_engine.py       # 신규: orchestrator
  feature_templates/
    raw_column.py
    datetime_features.py
    lag.py
    rolling.py
    diff.py
    ratio.py
    binning.py
    encoding.py
```

### 8.3 Recipe Engine 책임

| 책임 | 설명 |
|------|------|
| Load base frame | entity_keys, time_key, 소스 테이블에서 DataFrame 구성 |
| Apply template | recipe_type별 함수 디스패치 |
| Output column | `feature_name` 컬럼 1개 생성 |
| Merge to build | Feature Build 시 CODE 결과 DF에 left join 또는 column append |
| feature_json | `{ feature_name: value }` — 기존과 동일 key |

### 8.4 Lineage 연동

`save_feature_lineage` 확장:

- `calc_method = "TEMPLATE"`
- `calc_expression` = human-readable 요약 (자동 생성, 예: `LAG(heat_demand, 24, entity=site_id)`)
- `lineage_json.recipe_id`, `recipe_version`, `recipe_params`

### 8.5 Quality 연동

- Recipe publish 시 `output_data_type`, 선택적 `range_rule` 저장
- TEMPLATE Feature는 Registry `RANGE_RULES` 대신 recipe 메타 또는 domain pack defaults
- missing key는 기존과 동일 검사

### 8.6 Template Registry

| 방안 | 설명 |
|------|------|
| 코드 상수 | `ml/feature_templates/__init__.py`에 recipe_type 목록 — 1차 권장 |
| DB `tb_feature_recipe_template` | UI에서 템플릿 설명·아이콘 관리 — Phase R2 |

---

## 9. Domain Template Pack 분리

### 9.1 구조

```
Core (범용)
  ├── Recipe Engine
  ├── Column Role
  ├── RAW / DATE_PART / LAG / ROLLING / …
  └── Preview / Validate API

Domain Pack: Heat Demand Forecasting
  ├── CODE: ml/features.py + feature_registry.py (현행)
  ├── FS-TPL-* 템플릿
  ├── RANGE_RULES (quality)
  └── HDD/CDD/comfort_distance 등 도메인 전용 템플릿 (향후 TEMPLATE화)

Domain Pack: Sales Forecasting (예시)
  └── store_id, sales_amount, promotion_flag …

Domain Pack: Equipment Anomaly (예시)
  └── equipment_id, sensor_reading, …
```

### 9.2 Feature 분류

| 분류 | Feature 예 | 위치 |
|------|-----------|------|
| **Core TEMPLATE** | RAW_COLUMN, DATE_PART(hour/dow), LAG, ROLLING | Recipe Engine |
| **Heat CODE** | demand_lag_24h, heating_degree_days, comfort_distance | ml/features.py |
| **Heat-adjacent CODE** | temperature, humidity (기상 join) | ml/features.py |
| **Universal time CODE** | hour, month, is_weekend | Core로 이전 가능 (TEMPLATE DATE_PART로 대체 가능) |

### 9.3 Domain Pack metadata (후보)

```json
{
  "pack_id": "DP-HEAT-DEMAND",
  "pack_name": "Heat Demand Forecasting",
  "domain": "HEAT_DEMAND",
  "default_entity_key": "site_id",
  "default_time_key": "measured_at",
  "default_target": "heat_demand",
  "source_tables": ["tb_heat_demand_actual", "tb_weather_observation", "tb_calendar"],
  "feature_set_templates": ["FS-TPL-MINIMAL", "..."],
  "code_registry_module": "ml.feature_registry",
  "range_rules_ref": "heat_demand_quality"
}
```

### 9.4 seed 분리 전략

| 단계 | 작업 |
|------|------|
| 현재 | 단일 seed에 Heat Feature·Set·Config |
| Phase R8 | `db/init/domain_packs/heat_demand.sql` 분리 |
| clean 배포 | Core + Heat Pack 기본 포함; Sales는 optional seed |

### 9.5 UI 도메인 선택

- Feature Set 생성 시 `target_domain` 드롭다운 → Pack 필터
- Recipe Builder 1단계에서 Pack 선택 시 프리셋·컬럼 역할 자동 채움

---

## 10. DB/API 설계 초안

### 10.1 DB 테이블

| 테이블 | 목적 | 주요 컬럼 | 기존 관계 | migration | 1차 포함 |
|--------|------|-----------|-----------|-----------|----------|
| `tb_feature_recipe` | Recipe 정의 저장 | recipe_id PK, feature_name UNIQUE, recipe_type, calc_mode, source_table, entity_keys JSONB, time_key, params JSONB, status, version, owner | → tb_feature (publish) | **필요** | R5 |
| `tb_feature_recipe_version` | Recipe 버전 스냅샷 | version_id, recipe_id, version_no, recipe_snapshot JSONB, published_at | recipe_id FK | 필요 | R5 |
| `tb_feature_recipe_template` | 템플릿 카탈로그(메타) | template_id, recipe_type, display_name, param_schema JSONB, required_roles JSONB | — | 선택 | R2 |
| `tb_feature_recipe_preview_run` | Preview 이력(선택) | run_id, recipe_id, sample_size, result_summary JSONB | recipe_id FK | 선택 | R3 |
| `tb_feature_column_role` | 테이블별 컬럼 역할 | role_id, source_table, column_name, column_role, data_type | mapping 보완 | 필요 | R1 |
| `tb_domain_feature_pack` | Domain Pack 메타 | pack_id, domain, metadata JSONB | feature_set.target_domain | 선택 | R8 |

**`tb_feature` 확장 (대안, R5 검토)**

- `recipe_id` FK nullable
- `calc_mode` VARCHAR(20)

### 10.2 API

| API | 목적 | request | response | validation | 우선순위 | 1차 포함 |
|-----|------|---------|----------|------------|----------|----------|
| GET `/feature-recipe-templates` | 템플릿 목록·param 스키마 | — | `{ items: TemplateMeta[] }` | — | P1 | R2 |
| POST `/feature-recipes/validate` | Recipe JSON 검증 | `{ recipe }` | `{ valid, errors, warnings }` | 역할·params·이름 | P1 | R2 |
| POST `/feature-recipes/preview` | 샘플 Preview | `{ recipe, sample_size, ... }` | PreviewResponse | 동일 + 데이터 존재 | P1 | R3 |
| POST `/feature-recipes` | Recipe 저장 (DRAFT) | RecipeCreate | `{ recipe_id }` | validate | P2 | R5 |
| GET `/feature-recipes` | 목록 | filter status, domain | paged items | — | P2 | R5 |
| GET `/feature-recipes/{id}` | 상세 | — | Recipe | — | P2 | R5 |
| PUT `/feature-recipes/{id}` | 수정 | RecipeUpdate | ok | DRAFT only | P2 | R5 |
| POST `/feature-recipes/{id}/publish` | Catalog+버전 확정 | — | feature_name, version | 이름 중복·preview 권장 | P2 | R5 |
| POST `/feature-sets/{id}/add-recipe-feature` | Set에 feature_name 추가 | `{ recipe_id \| feature_name }` | updated features[] | TPL/Legacy 규칙 | P2 | R5 |
| GET `/feature-column-roles` | 테이블 컬럼 역할 조회 | `source_table` | roles[] | — | P1 | R1 |
| PUT `/feature-column-roles` | 역할 저장 | `{ table, roles[] }` | ok | 역할 규칙 | P1 | R1 |

---

## 11. 단계별 구현 로드맵

| Phase | 목표 | 주요 작업 | 수정 파일 예상 | DB migration | 테스트 | 위험도 | 산출물 | 난이도 |
|-------|------|-----------|----------------|--------------|--------|--------|--------|--------|
| **R0** | 설계 확정 | 본 문서, 와이어프레임, 정책 링크 | docs/ | 없음 | — | 낮음 | 설계서 | 낮음 |
| **R1** | Column Role | role API, mapping UI 확장, 추론 heuristic | mapping_service, entities, ingestion UI | **있음** (role 테이블 또는 JSON) | role validation test | 중 | Role API·UI | 중 |
| **R2** | Template Catalog | template 메타 API, validate API | feature_recipe_service, api/v1 | 선택 | validate test | 낮음 | Template 목록 API | 낮음 |
| **R3** | RAW/DATE Preview | recipe_engine scaffold, preview API | ml/feature_recipe_engine.py, api | preview_run 선택 | preview test | 중 | Preview API | 중 |
| **R4** | LAG/ROLLING Preview | 시계열 템플릿 + leakage 검사 | feature_templates/*, engine | 없음 | lag/rolling test | **높음** | 시계열 Preview | 높음 |
| **R5** | Recipe 저장·Set 연결 | tb_feature_recipe, publish, add to set | entities, feature API, UI 마법사 | **있음** | recipe CRUD test | 중 | Recipe Builder v1 | 높음 |
| **R6** | Recipe Build | build 시 TEMPLATE 실행·feature_json | feature_build_service, engine | 없음 | build integration | **높음** | E2E Build | 높음 |
| **R7** | Quality/Lineage | TEMPLATE lineage, quality rules | lineage/quality service | lineage_json 확장 | quality+lineage test | 중 | 통합 검증 | 중 |
| **R8** | Domain Pack | pack 메타, seed 분리, UI 갤러리 | seed, ml/registry 구조 | pack 테이블 | pack load test | 중 | Pack 분리 | 중 |
| **R9** | Drag&Drop Canvas | 노드 기반 UI (선택) | frontend 신규 | 없음 | UI test | 높음 | Canvas prototype | 매우 높음 |
| **R10** | 제한적 DSL | 안전 subset parser (선택) | ml/dsl/ | 없음 | dsl test | **매우 높음** | DSL spec | 매우 높음 |

---

## 12. 구현 우선순위

| 순위 | 항목 | 이유 |
|------|------|------|
| 1 | Column Role (R1) | Recipe·Preview·Engine 공통 전제 |
| 2 | Template Catalog + Validate (R2) | UI·API 계약 조기 고정 |
| 3 | RAW/DATE Preview (R3) | 낮은 위험으로 Preview 패턴 검증 |
| 4 | LAG/ROLLING Preview (R4) | 핵심 가치·누수 검증 |
| 5 | Recipe 저장 + Builder UI (R5) | 사용자 가시 성과 |
| 6 | Recipe Build (R6) | 학습 연결 전 필수 |
| 7 | Quality/Lineage (R7) | 운영 신뢰 |
| 8 | Domain Pack (R8) | 열수요 분리·범용화 |
| 9 | Canvas / DSL (R9–R10) | 장기 |

---

## 13. 리스크와 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| row step ≠ 실제 시간 간격 | LAG/ROLLING 오류 | Preview gap 검사; granularity 메타; UI 경고 |
| CODE·TEMPLATE 결과 불일치 | 동일 feature_name 충돌 | CODE 우선 정책; 이름 네임스페이스 (pack prefix) |
| tb_feature_dataset 스키마 열수요 고정 | 범용 entity 저장 | 1차: feature_json만 사용; 물리 컬럼 확장은 별도 Phase |
| migration 부담 | 배포 복잡도 | Role·Recipe 테이블만 최소 migration; 나머지 JSONB |
| 누수 | 모델 신뢰도 붕괴 | include_current 기본 false; TARGET 동일 시 차단 |
| 성능 | Preview/Build 느림 | 샘플링·entity 필터·비동기 job (Build는 기존 패턴) |

---

## 14. 이번 단계에서 하지 않는 것

- 기능 코드 구현 (Backend/Frontend/ML)
- DB migration
- DSL 파서 구현
- `calc_expression` 실행 연결
- Recipe Engine 구현
- `ml/features.py` 리팩토링
- Feature Build 로직 수정
- 테스트 코드 수정
- Traefik / design/figma 수정

---

## 부록 A. 영향 받는 영역 맵

| 영역 | 현재 파일 | Recipe Builder 영향 |
|------|-----------|---------------------|
| ML | `ml/features.py`, `ml/feature_registry.py` | Engine 추가; CODE 유지 |
| Backend Service | `feature_build_service.py`, `feature_registration_service.py`, `feature_quality_service.py`, `feature_lineage_service.py` | Build 분기, Quality 규칙, Lineage TEMPLATE |
| Backend API | `api/v1/feature.py` | recipe 엔드포인트 추가 |
| Backend Model | `entities.py` | 신규 테이블 |
| Mapping | `mapping_service.py` | column role |
| Frontend | `FeaturesPage`, `FeatureSetDetailPage`, 신규 `FeatureRecipeBuilderPage` | 마법사 UI |
| Docs | 정책 문서, README | 링크·calc_mode 정책 |
| Training | `training_service.py`, `tb_training_config` | feature_set_id 연결 유지; recipe version 추적은 후속 |

## 부록 B. Training Config 연결 (현재)

```
tb_training_config.feature_set_id
  → tb_feature_set.features[] (feature_name 목록)
  → Feature Build → tb_feature_dataset.feature_json
  → training_service: feature_json keys를 학습 행렬로 사용
  → prediction: 동일 feature_set_id
```

Recipe 도입 후에도 **학습은 feature_name 목록 기준**을 유지한다. Recipe 변경 시 `feature_config_hash` 변경 → 재학습 권장.

---

*문서 끝*

---

## 부록 C. Phase R1 구현 완료 (Column Role 관리)

> **구현 완료**: Column Role 저장·조회·자동 추론·검증·Data Mapping UI

### DB

- 테이블: `tb_feature_column_role`
- migration: `scripts/apply_dev_migrations.py` (기존 볼륨) + `db/init/01_schema.sql` (clean deploy)
- seed: `02_seed_clean.sql` — 마스터·템플릿만 (데이터 소스·매핑·Column Role seed 없음)

### API

| 메서드 | 경로 |
|--------|------|
| GET | `/api/v1/feature-column-role-codes` |
| GET | `/api/v1/feature-column-roles?mapping_id=...&include_inferred=true` |
| POST | `/api/v1/feature-column-roles/infer` |
| POST | `/api/v1/feature-column-roles/validate` |
| PUT | `/api/v1/feature-column-roles` |

### UI

- `/data/mappings` — 매핑 수정 모달에 컬럼 역할 드롭다운, 추천 역할 적용, 역할 검증, 컬럼 역할 저장, Recipe 준비도

### 정책

- 자동 추론은 **제안**이며 사용자가 저장해야 확정된다.
- Column Role은 **현재 Feature Build/학습/예측에 직접 영향 없음** (Recipe Builder 전제).

### 테스트

```bash
python scripts/apply_dev_migrations.py
python scripts/test_feature_column_roles.py
```

---

## 부록 D. Phase R2 구현 완료 (Recipe Template Catalog + Validate)

> **구현 완료**: Template Catalog 메타데이터·availability·Recipe draft validate (저장/실행/Preview 없음)

### 구현 방식

- **코드 상수** (`feature_recipe_template_service.py`) — DB migration 없음
- `tb_feature_recipe` 저장 테이블 미사용

### 지원 recipe_type

`RAW_COLUMN`, `DATE_PART`, `LAG`, `ROLLING_MEAN`, `ROLLING_SUM`, `DIFF`, `RATIO`, `BINNING`, `FILL_NULL`, `CATEGORY_ENCODING` (EXPERIMENTAL)

### API

| 메서드 | 경로 |
|--------|------|
| GET | `/api/v1/feature-recipe-templates` |
| GET | `/api/v1/feature-recipe-templates/{recipe_type}` |
| POST | `/api/v1/feature-recipes/validate` |

### UI

- `/data/mappings` — 매핑 수정 시 **사용 가능한 Recipe 템플릿** 카드 (availability 표시)

### 정책

- Validate API는 **저장·실행·Preview·Recipe ID 발급 없음**
- DSL 자동 실행은 여전히 미지원

### 테스트

```bash
python scripts/test_feature_recipe_templates.py
```

### 후속 단계

- R4: LAG/ROLLING Preview
- R5: Recipe 저장 + Builder UI

---

## 부록 E. Phase R3 구현 완료 (RAW_COLUMN / DATE_PART Preview)

> **구현 완료**: Recipe draft를 샘플 데이터에 적용해 결과만 반환 (저장·Build 없음)

### Preview 지원 범위

- **지원**: `RAW_COLUMN`, `DATE_PART`
- **미지원**: LAG, ROLLING, DIFF, RATIO, BINNING, FILL_NULL, CATEGORY_ENCODING (R4 이후)

### API

| 메서드 | 경로 |
|--------|------|
| POST | `/api/v1/feature-recipes/preview` |

### DATE_PART 기존 Feature 재사용 정책

- `hour`, `day_of_week`, `month`, `is_weekend` 등 **표준 DATE_PART** 이름이 Catalog/Registry에 이미 있으면 `reusable_existing_feature=true`로 안내
- Validate/Preview는 **통과**하며 duplicate error가 아님
- 사용자 지정 `output_feature_name`이 기존 다른 Feature와 충돌하면 error

### UI

- `/data/mappings` — RAW_COLUMN·DATE_PART 템플릿 **Preview** 버튼 및 모달

### 정책

- Preview 결과는 `tb_feature_dataset`·`tb_feature_recipe`에 **저장하지 않음**
- `preview_id`는 로컬 식별용이며 영속 ID 아님
- DSL 자동 실행은 여전히 미지원

### 테스트

```bash
python scripts/test_feature_recipe_preview.py
```

### 후속 단계 (R3 시점)

- R4: LAG/ROLLING Preview
- R5: Recipe 저장 + Builder UI

---

## 부록 F. Phase R4 구현 완료 (LAG / ROLLING Preview)

### 지원 범위

- **Preview 지원**: `LAG`, `ROLLING_MEAN`, `ROLLING_SUM` (기존 `RAW_COLUMN`, `DATE_PART` 유지)
- **Preview 미지원(후속)**: `DIFF`, `RATIO`, `BINNING`, `FILL_NULL`, `CATEGORY_ENCODING`
- Validate API는 DIFF 등 기존 정책 유지 (DIFF Preview만 미구현)

### 계산 정책

R4의 LAG/ROLLING Preview는 `entity_keys`와 `time_key` 기준으로 데이터를 정렬한 뒤 row step 기반으로 계산합니다. `offset_steps=24`, `granularity=1h`는 1시간 간격 데이터에서 24행 전 값을 의미하며, 원천 데이터의 시간 간격이 불규칙하면 실제 24시간 전 값과 다를 수 있습니다.

- ROLLING 기본: `include_current_row=false`; Preview에서 `min_periods` 미지정 시 `window_steps`
- `include_current_row=true` + `source_column == target_column` → leakage warning
- 이력 부족 → `insufficient_history_count`, `history_warnings`

### API·UI

- `POST /api/v1/feature-recipes/preview` — `time_series_preview`, `time_gap_warnings`, `leakage_warnings` 등 선택 필드
- Data Mappings → LAG/ROLLING **Preview** 버튼, row step·저장 안내 문구
- Preview 결과 **저장하지 않음**

### 후속 단계

- **R5**: Recipe 저장 + Builder UI
- **R6**: Recipe Engine 기반 Feature Build

---

## 부록 G. Phase R5 구현 완료 (Recipe 저장 + Builder UI)

### DB

- `tb_feature_recipe` — Recipe draft/validated/published 상태, validation/preview summary JSONB
- `tb_feature_recipe_version` — Publish 시점 snapshot

### API

- `POST/GET/PUT /feature-recipes`, `GET /feature-recipes/{id}`
- `POST /feature-recipes/{id}/validate|preview|publish|archive`
- `POST /feature-sets/{id}/add-recipe-feature`

### 정책

- Publish = Catalog 등록 + `feature_name` 확정 (`feature_type=TEMPLATE`)
- R5 Publish: output 1개만 허용
- PUBLISHED Recipe 수정 차단
- 사용자 정의 Feature Set에만 Recipe Feature 추가 (`FS-TPL-*` 차단)
- **Feature Build 계산 미연동** (R6)

### UI

- `/feature-recipes`, `/feature-recipes/new`, `/feature-recipes/:id`
- Features → Recipe로 Feature 만들기
- Feature Set 상세 → Recipe Feature 추가

### 후속

- **R6**: Recipe Engine 기반 Feature Build — 부록 H 참고

---

## 부록 H. Phase R6 구현 완료 (Recipe Engine Feature Build)

R6에서는 발행된 TEMPLATE Recipe Feature를 Recipe Engine으로 계산하여 기존 CODE Feature와 함께 Feature Dataset의 `feature_json`에 저장합니다. 단, 지원 범위는 `RAW_COLUMN`, `DATE_PART`, `LAG`, `ROLLING_MEAN`, `ROLLING_SUM`으로 제한하며, DSL 실행이나 임의 수식 실행은 지원하지 않습니다.

### Build 지원 recipe_type

- `RAW_COLUMN`, `DATE_PART`, `LAG`, `ROLLING_MEAN`, `ROLLING_SUM`

### Build 미지원

- `DIFF`, `RATIO`, `BINNING`, `FILL_NULL`, `CATEGORY_ENCODING` — `template_build_unsupported_features` 또는 WARNING 처리

### 처리 흐름

1. Feature Set `features` 분류 (CODE vs PUBLISHED TEMPLATE Recipe)
2. `ml/features.py`로 CODE Feature 계산 (기존 유지)
3. `feature_recipe_engine_service`로 TEMPLATE Recipe 계산·컬럼 병합
4. `tb_feature_dataset.feature_json`에 CODE + TEMPLATE 저장
5. Lineage: TEMPLATE는 `calc_method=TEMPLATE`, recipe 메타데이터 포함
6. Feature Quality: TEMPLATE key가 Build되면 missing key 아님

### result_summary 추가 필드

- `code_feature_count`, `template_feature_count`, `template_generated_feature_count`
- `template_recipe_features`, `template_build_unsupported_features`, `template_build_failed_features`
- `template_build_warnings`, `recipe_engine_version` (`R6`)

### 정책

- PUBLISHED + `active_yn=Y` Recipe만 Build
- row step 기반 LAG/ROLLING; time gap warning은 `result_summary`에만 기록
- `FS-TPL-*`에 TEMPLATE Feature 포함 시 Build WARNING
- 학습/예측 로직·`ml/features.py` CODE 계산 결과 변경 없음

### 테스트

```bash
python scripts/test_feature_recipe_build.py
```

### 후속 (R7+)

- DIFF/RATIO/BINNING/FILL_NULL Build 확장, Recipe version 고도화, Domain Pack

---

## 부록 I. Phase R6-S1 구현 완료 (Recipe Engine Build 안정화·운영 검증)

R6-S1은 **새로운 Recipe 계산 Type을 추가하지 않고**, R6에서 생성된 TEMPLATE Feature Build 결과를 운영자가 검증할 수 있도록 Build 상태·진단 코드·Recipe별 최근 Build 이력·Lineage/Quality 표시를 보강하는 안정화 단계입니다.

### result_summary 추가 필드 (optional, 하위 호환)

- `template_build_status_by_feature`: Feature별 `status`, `recipe_id`, `recipe_type`, `warning_codes`, `error_codes`, `null_ratio` 등
- `template_build_status_counts`: `generated`, `warning`, `failed`, `unsupported`
- `template_build_diagnostics`: severity·code·message 목록 (상위 N건)
- `recipe_engine_diagnostics_version` (`R6-S1`)

### status 값

- `GENERATED`, `GENERATED_WITH_WARNING`, `FAILED`, `UNSUPPORTED`, `SKIPPED`

### 진단 코드 (일부는 warning)

- `RECIPE_NOT_PUBLISHED`, `RECIPE_ARCHIVED`, `UNSUPPORTED_RECIPE_TYPE`
- `SOURCE_COLUMN_MISSING`, `ENTITY_KEY_MISSING`, `TIME_KEY_MISSING`, `INVALID_PARAM`
- `NUMERIC_CONVERSION_FAILED`, `DATETIME_CONVERSION_FAILED`
- `INSUFFICIENT_HISTORY`, `TIME_GAP_DETECTED`, `LEAKAGE_RISK` (warning 가능)
- `UNKNOWN_BUILD_ERROR`

### API

- `GET /api/v1/feature-recipes/{recipe_id}/build-history` — Recipe별 최근 Build 이력 (`result_summary` 검색)
- `POST /api/v1/feature-recipes/{recipe_id}/compare-preview-build` — Preview vs Build 샘플 비교 (`SAMPLE_BY_ENTITY_TIME`)
- `GET /api/v1/feature-build-jobs` — `recipe_id`, `feature_name` 필터

### UI

- Feature Set 상세: **Recipe Engine Build 상세** 패널, 진단·Feature별 상태 테이블
- Feature Recipe Builder: PUBLISHED Recipe **최근 Build 이력**
- Lineage: TEMPLATE badge, recipe_id/type/params, Recipe 상세 링크
- Feature Quality: TEMPLATE `build_coverage`, registration_status 표시

### 운영자 Build 실패 진단 절차

1. Feature Set 상세 Build 결과·**Recipe Engine Build 상세**에서 `status`·`error_codes` 확인
2. 실패 Feature의 Recipe 상세 → Validate·Preview 재실행
3. Lineage에서 `calc_method=TEMPLATE` 메타데이터 확인
4. Feature Quality에서 TEMPLATE coverage·null 비율 확인
5. 필요 시 `compare-preview-build`로 Preview·Build 샘플 비교

### 테스트

```bash
python scripts/test_feature_recipe_build_diagnostics.py
```

### 후속 (R7+)

- DIFF/RATIO/BINNING/FILL_NULL/CATEGORY_ENCODING Build 확장
- Domain Pack, Preview/Build 이력 비교 고도화, mapping별 외부 테이블 join 확장

---

## 부록 J. Phase R6-S2 구현 완료 (Recipe Build 운영 UI 마감)

R6-S2는 Recipe Engine Build의 **계산 범위를 확장하지 않고**, 운영자가 Recipe별 최근 Build 상태와 Preview/Build 샘플 비교 결과를 UI에서 확인할 수 있도록 마감하는 단계입니다.

### UI 보강

- **Feature Recipe 목록**: PUBLISHED Recipe 행별 최근 Build 상태·null%·경고/실패 요약, Preview/Build 비교 링크
- **Recipe Builder**: Build Job 선택, **Preview/Build 비교** 버튼·결과 모달
- **Feature Set 상세**: Recipe Engine Build 상세 패널 개선(진단 코드 도움말, Recipe/비교 링크)
- **Feature Quality**: TEMPLATE coverage·높은 null 비율 안내, 이슈 샘플 Recipe 링크
- **Lineage**: TEMPLATE recipe 메타데이터·source_columns 강조

### Preview/Build 비교

- `POST /api/v1/feature-recipes/{recipe_id}/compare-preview-build`
- `dataset_version_id` 생략 시 최근 Build Job 1건의 dataset_version 자동 사용
- 응답: `comparable`, `comparison_policy`, `summary`(matched/mismatch/max_abs_diff), `items`, `warnings`

### R6 이전 Job 제한

- `template_build_status_by_feature` 없는 Job은 build-history·진단 표시가 **제한**될 수 있음 (UI 안내)

### 테스트

```bash
python scripts/test_feature_recipe_build_diagnostics.py
```

---

## 부록 K. Phase R7 구현 완료 (표준 대상 테이블 / 학습 데이터셋 유형 관리)

R9-S2-1부터 표준 데이터셋 Wizard로 `std_` prefix 내부 물리 테이블을 metadata 기반 `CREATE TABLE`로 생성합니다. SQL Preview는 Backend만 생성하며 사용자 수정·raw SQL 실행은 금지합니다. Data Mapping 대상은 ACTIVE + 물리 테이블이 존재하는 표준 데이터셋입니다.

R9-S2-3부터 사용자 화면 표시명은 일반 운영자용 한글 업무 용어를 우선합니다(내부 코드명은 상세·툴팁에 병기). Feature Recipe Builder 화면 제목은 **변수 생성 규칙 작성**입니다.

R9-S2-2부터 `dataset_category`(구조/성격), `business_domain`·`tags`(선택 메타데이터)로 분류합니다. 업무 영역은 시스템 고정값이 아니며 `열수요`·`기상` 등은 입력 예시일 뿐입니다.

- DB: `tb_standard_dataset_type`, `tb_standard_dataset_column`
- API: `/standard-dataset-types`, `/standard-target-tables`, mapping allowlist 검증
- UI: `/standard-datasets`, `/data/mappings` 드롭다운·표준 역할 적용
- 테스트: `scripts/test_standard_datasets.py`

---

## 부록 L. Phase R8 구현 완료 (Pipeline Builder — Flow Chart·노드 설정·실행 파라미터 저장)

R8은 고정 Airflow DAG 버튼 중심의 운영 화면을 확장하여, THERMOps 내부에서 **Pipeline Template**을 Flow Chart 형태로 확인하고 노드별 실행 파라미터를 저장할 수 있도록 하는 단계이다. R8에서는 **Airflow DAG를 동적으로 생성하지 않으며**, 저장된 Pipeline Definition을 향후 공통 실행 DAG와 연계할 수 있는 기반을 마련한다.

### 용어

| 용어 | 설명 |
|------|------|
| Pipeline Template | 미리 정의된 노드·엣지 구조 (예: FULL_OPERATION, FEATURE_BUILD) |
| Pipeline Definition | 사용자가 Template 기반으로 저장한 실제 실행 설정 |
| Node Config | 각 노드의 실행 파라미터 (data_source_id, feature_set_id 등) |
| Airflow DAG Mapping | Definition 실행 시 참조할 기존 DAG ID (`thermops_full_pipeline_dag` 등) |

### R8 범위

- Flow Chart 시각화 (CSS 기반, 외부 라이브러리 없음)
- 노드별 설정 패널·저장
- Pipeline Definition 검증·활성화·보관
- Runtime Params Preview (`POST .../runtime-preview`)
- `/ops/pipeline-runs`에 Pipeline Builder 안내·Template 뱃지

### R8에서 하지 않는 것

- 완전 Drag & Drop 노드 편집
- Airflow DAG Python 파일 동적 생성·수정
- 실제 스케줄러 등록·Definition 기반 trigger (R9+)

### DB

- `tb_pipeline_template`, `tb_pipeline_definition`, `tb_pipeline_definition_version`
- Seed: `FULL_OPERATION_PIPELINE`, `FEATURE_BUILD_PIPELINE`, `BATCH_PREDICTION_PIPELINE`, `RETRAINING_PIPELINE`(PLANNED)

### API

- `GET /pipeline-templates`, `GET /pipeline-definitions`
- `POST/PUT /pipeline-definitions`, `POST .../validate`, `.../activate`, `.../archive`
- `GET /pipeline-node-options`, `POST .../runtime-preview`

### 기존 Airflow DAG와의 관계

| Template | airflow_dag_id |
|----------|----------------|
| FULL_OPERATION_PIPELINE | `thermops_full_pipeline_dag` |
| FEATURE_BUILD_PIPELINE | `feature_build_dag` |
| BATCH_PREDICTION_PIPELINE | `batch_prediction_dag` |
| RETRAINING_PIPELINE (PLANNED) | `retraining_dag` |

`/ops/pipeline-runs`의 수동 실행 버튼은 기존 `GET /pipelines` 기반이며 R8에서 제거하지 않는다.

### 검증 정책

- DRAFT: warning 있어도 저장 가능
- ACTIVE: error 없을 때만 (`POST .../activate`)
- PLANNED 템플릿으로 Definition 생성 차단

### Runtime Params Preview 예시 (API 문서용 — 운영 seed 아님)

```json
{
  "pipeline_id": "PIPE-001",
  "template_code": "TEST_FULL_OPERATION_PIPELINE",
  "airflow_dag_id": "thermops_full_pipeline_dag",
  "data_source_id": "<등록한 데이터소스 ID>",
  "mapping_id": "<등록한 매핑 ID>",
  "dataset_type_id": "TEST-DST-HEAT",
  "feature_set_id": "TEST-FS-LAG-ROLL"
}
```

> 위 ID는 회귀 테스트 fixture(`scripts/fixtures/test_platform_seed.sql`) 기준 예시입니다. clean Docker 설치 직후에는 비어 있으며, 사용자가 UI/API로 리소스를 등록한 뒤 해당 ID로 교체합니다.

### 테스트

```bash
python scripts/apply_dev_migrations.py
python scripts/test_pipeline_builder.py
```

### 향후 (R9/R10)

- ~~Definition 기반 Airflow trigger·run history 연결~~ → **R9 완료 (부록 M)**
- Drag & Drop 노드 편집·조건부 분기
- 스케줄 등록

---

## 부록 M. Phase R9 구현 완료 (Pipeline Definition 기반 Airflow 실행 연계)

R9부터 Pipeline Definition은 저장된 노드 설정과 실행 파라미터를 기반으로 **기존 Airflow DAG**를 trigger할 수 있다. THERMOps는 Airflow DAG 코드를 동적으로 생성하지 않고, runtime params snapshot을 Airflow conf로 전달하여 실행 이력과 Pipeline Definition을 연결한다.

### 실행 정책

| 상태 | 실행 |
|------|------|
| DRAFT | 불가 (검증 필요) |
| VALIDATED / ACTIVE | 가능 |
| ARCHIVED | 불가 |
| PLANNED Template | 불가 |

실행 전 `validate_pipeline_definition` 재실행. error 시 trigger 차단, warning은 허용.

### DB

- `tb_pipeline_run_link`: pipeline_id, template_id, pipeline_run_id, airflow_run_id, snapshot JSON

### API

- `POST /pipeline-definitions/{id}/run` (`dry_run` 지원)
- `GET /pipeline-definitions/{id}/runs`
- `GET /pipeline-run-links`, `GET /pipeline-run-links/{id}`, `POST .../sync-status`
- `GET /pipeline-runs` 응답에 optional pipeline metadata (`run_source`, `template_code` 등)

### Airflow conf 구조

`thermops_context`, `node_config`, `runtime_params`, `schedule_config`, `validation_snapshot` + legacy flat keys (`feature_set_id` 등)

### R9에서 하지 않는 것

- DAG 동적 생성, Drag & Drop 편집, 실제 Airflow schedule 등록

### 테스트

```bash
python scripts/apply_dev_migrations.py
python scripts/test_pipeline_execution.py
```

## 부록 N. Phase R9-S1 model regression 복구 (학습/예측 dataset_version 선택)

### 증상

R9 이후 model regression 3건(`test_catboost_training`, `test_prediction_period_validation`, `test_batch_prediction`)이 HTTP 400으로 실패.

### 원인

`latest_dataset_version_id`가 `MAX(created_at)`만으로 최신 dataset_version을 선택하여, 짧은 기간만 재빌드한 소량 버전(예: 24행)이 전체 빌드(수천 행)보다 우선되었다. Lag Feature null이 많은 소량 버전에서는 `build_feature_matrix`/`build_prediction_matrix`가 모든 행을 제외하여 `학습 데이터가 없습니다.` / `예측 입력 행이 없습니다.` 400이 발생했다.

### 조치

`feature_dataset_service.latest_dataset_version_id`를 `tb_dataset_version.record_count` 내림차순·`created_at` 보조 정렬로 변경. `training_service`는 동일 함수를 공유한다.

### R9 영향

R9 Pipeline 실행 연계와 무관. R7 이후 부분 Feature Build가 누적되면서 기존 선택 정책의 부작용이 드러난 회귀.

### 테스트

```bash
python scripts/run_regression_tests.py --group model --timeout-scale 2
```

기대: **23/23 PASS**

---

## 부록 O. Phase R9-S2 Dataset Version 운영 정책 (학습 데이터 버전)

R9-S2에서는 Feature Build 결과로 생성되는 학습 데이터 버전에 **역할·상태·생성 범위**를 부여하고 `dataset_version_policy_service`로 학습/예측 자동 선택을 수행한다.

### 정책 요약

| 구분 | 값 | 자동 선택 |
|------|-----|-----------|
| 역할 | PRIMARY, CANDIDATE | 가능(상태 조건 충족 시) |
| 역할 | PARTIAL, TEMPORARY, ARCHIVED | 제외 |
| 상태 | TRAINING_READY, SERVING_READY, BUILD_SUCCESS, BUILD_WARNING | 목적에 따라 가능 |
| 상태 | BUILD_FAILED, ARCHIVED, PARTIAL | 제외 |
| fallback | record_count DESC, created_at DESC | 명시적 후보 없을 때만, PARTIAL 등 제외 |

### R9-S1 대비

R9-S1 임시 복구(`record_count DESC`)는 **fallback**으로 `dataset_version_policy_service` 내부에 유지한다. PRIMARY·CANDIDATE 운영 정책이 우선 적용되어 최신 partial build가 자동 선택되는 회귀를 구조적으로 방지한다.

### API·화면

- `GET /api/v1/dataset-versions`, `POST .../set-primary`, `POST .../archive`, `POST .../selection-preview`
- Frontend `/dataset-versions` (표시명: 학습 데이터 버전)

### 테스트

```bash
python scripts/test_dataset_version_policy.py
python scripts/run_regression_tests.py --group model --timeout-scale 2
```

---

## 부록 P. Phase R10 Generic REST API Connector Builder

R10에서 **데이터 준비** 흐름에 REST API 연결(API 작업)이 추가되었습니다. 외부 API 응답을 표준 데이터셋 물리 테이블에 적재할 수 있는 기반이 마련되었으나, **Feature Recipe 계산 로직·Recipe Type·ml/features.py는 변경하지 않습니다.**

- Feature Build는 기존과 동일하게 학습 데이터 버전(Dataset Version)과 Feature Set/Recipe를 사용합니다.
- API 적재 데이터는 Data Mapping·표준 데이터셋 경로를 통해 Feature Build 입력 테이블로 연결됩니다.
- 열수요 wide-hour 변환·ASOS/Calendar 특화 적재는 R10-S3/S4에서 별도 구현 예정입니다.

---

## 부록 Q. Phase R10-S0 REST API Connector UI 고도화

R10-S0은 **REST API 연결 화면(UI)** 고도화이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`는 변경하지 않습니다.

- 8단계 Operation Builder Wizard, 호출/적재 이력·스냅샷 상세 UI 추가
- Backend `/api/v1/api-connectors/*` API를 그대로 활용

---

## 부록 R. Phase R10-S1 Prediction Entity / Weather Mapping

R10-S1은 **예측 대상·위치·기상 매핑 기준정보** 관리이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`는 변경하지 않습니다.

- 예측 대상 Entity, 위치(위도/경도), 단기예보 격자(nx/ny), ASOS 관측소 매핑을 DB/API/UI로 관리
- 단기예보 on-demand 호출(R10-S5)·ASOS 적재(R10-S4)는 후속 Phase에서 이 매핑을 참조
- KMA 격자 변환 유틸(`latlon_to_kma_grid`)은 제안용이며 최종 저장은 사용자 확인 후 수행

---

## 부록 S. Phase R10-S2 External Code / Common Code Mapping

R10-S2는 **외부 코드 매핑·미매핑 코드 수집·코드 변환(resolve)** 기준정보이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`는 변경하지 않습니다.

## 부록 T. Phase R10-S3 Heat Demand wide-hour Transform

R10-S3는 **열수요 API wide-hour → long format 적재 변환**이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`는 변경하지 않습니다. 변환된 `measured_at`·`heat_demand`·`entity_id`/`site_id`는 기존 Feature Build·학습 파이프라인의 입력 데이터로 사용됩니다.

## 부록 U. Phase R10-S4 ASOS / Calendar Ingestion

R10-S4는 **ASOS 관측 기상·Calendar/특일 데이터 적재·정규화** 단계이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`는 변경하지 않습니다. `std_weather_observation_hourly`·`std_calendar_date`·`std_calendar_hour` 등 표준 테이블에 적재된 값은 후속 Feature Build에서 기존과 동일한 방식으로 조인·사용됩니다.

## 부록 V. Phase R10-S5 Forecast On-demand Input Provider

R10-S5는 **예측 실행 시점 단기예보 on-demand 입력 생성·snapshot 저장** 단계이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`·학습/예측 알고리즘은 변경하지 않습니다. `tb_prediction_weather_input`에 저장된 표준 기상 행은 후속 Phase에서 Feature Build 입력과 연계할 수 있으나, 이번 Phase에서는 Provider·정규화·재현성 저장까지가 범위입니다.

## 부록 VI. Phase R10-S6 데이터 적재 스케줄러

R10-S6은 **REST API Connector load-run 정기 실행·실행 이력 관리** 단계이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`·학습/예측 알고리즘은 변경하지 않습니다. 스케줄러는 기존 transform/load-run 파이프라인을 재사용하며, Forecast on-demand Provider(R10-S5)는 스케줄 대상에서 제외합니다.

## 부록 VII. Phase R10-S7 운영 점검 / 통합 시나리오 검증

R10-S7은 **운영 점검·통합 검증·회귀 방지** 단계이며 Feature Recipe 계산 로직·Recipe Type·`ml/features.py`·학습/예측 알고리즘은 변경하지 않습니다.  
검증 범위는 Connector/Transform/Forecast Provider/데이터 적재 일정의 연계 동작과 masking·clean seed 정책 준수이며, 신규 Feature 계산 방식이나 모델 알고리즘 확장은 이번 Phase 범위가 아닙니다.

## 부록 VIII. Phase R10-S8 Upsert / 중복 제거 고도화

R10-S8은 REST API Connector 적재 안정화 단계로, `INSERT_ONLY` 외에 `DEDUPLICATE`/`UPSERT` 정책과 `중복 판단 키`를 도입합니다. 이 단계는 적재 결과의 중복 누적 방지 목적이며, **Feature Recipe 계산 로직·Recipe Type·`ml/features.py`·학습/예측 알고리즘은 변경하지 않습니다.**
