# THERMOps Feature 명칭 및 계산식 정책

## 1. 목적

Feature **메타데이터**(카탈로그)와 **실제 계산·저장 키**의 명칭을 통일하고, `calc_expression`의 역할을 명확히 한다.

## 2. 공식 Feature 명칭

신규 seed, 문서, UI, Feature Set 템플릿(`FS-TPL-*`)에서는 아래 이름만 사용한다.

| feature_name | 설명 | 계산 위치 (`ml/features.py`) |
|--------------|------|------------------------------|
| `demand_lag_24h` | 24시간 전 열수요 | `shift(24)` |
| `demand_lag_168h` | 168시간 전 열수요 | `shift(168)` |
| `demand_ma_24h` | 24시간 이동평균 열수요 | `rolling(24)` |
| `demand_ma_168h` | 168시간 이동평균 열수요 | `rolling(168)` |
| `temperature_diff_24h` | 24시간 전 대비 기온 차 | `temperature.diff(24)` |
| `heating_degree_days` | 난방도일 (기준 18℃) | `(18 - temp).clip(0)` |
| `cooling_degree_days` | 냉방도일 (기준 24℃) | `(temp - 24).clip(0)` |

기타 템플릿 Feature(`temperature`, `hour`, `comfort_distance` 등)는 `ml/features.py`의 `ALL_COMPUTED_FEATURES` 및 `FEATURE_SET_TEMPLATES`를 참조한다.

## 3. 레거시·비공식 명칭 (alias)

| 비공식/레거시 | 공식 명칭 | 비고 |
|---------------|-----------|------|
| `lag_24h_demand` | `demand_lag_24h` | `tb_feature` FEAT-001, `tb_feature_dataset.lag_24h_demand` 컬럼 |
| `lag_168h_demand` | `demand_lag_168h` | FEAT-002, `lag_168h_demand` 컬럼 |
| `rolling_24h_avg` | `demand_ma_24h` | `tb_feature_dataset` 레거시 컬럼 |
| `demand_rolling_24h_avg` | `demand_ma_24h` | 문서/논문 메모용 구표현 |
| `hdd` | `heating_degree_days` | 약어, 코드·seed에 미사용 |
| `cdd` | `cooling_degree_days` | 약어, 코드·seed에 미사용 |
| `lag_24h`, `lag_168h`, `rolling_mean_24h` | (각각 위 공식명) | 구 demo Feature Set `FS-000001` 전용 |

**정책**

- 레거시 명칭은 **기존 DB 컬럼·역매핑 호환**용으로만 유지한다.
- `FS-TPL-*` Feature Set에는 **공식 명칭만** 포함한다.
- 신규 Feature Set·문서·UI에는 레거시 명칭을 추가하지 않는다.

## 4. `calc_expression` 정책

| 항목 | 내용 |
|------|------|
| 저장 위치 | `tb_feature.calc_expression` |
| UI 표시 | **계산식 메모** (설명용) |
| 실행 여부 | **실행되지 않음** |
| DSL 예시 | `LAG(heat_demand, 24)`, `MA(heat_demand, 24)` 등은 **개념 설명용**이며 파서/엔진 없음 |

`LAG(...)`, `MA(...)`, `HDD(...)`, `CDD(...)` 문법은 향후 확장 후보이며, 현재 THERMOps에서 **자동 계산에 사용할 수 없다**.

## 5. Feature 등록 → 학습/예측 반영 경로

Feature를 `/features`에서 등록하는 것은 **카탈로그 등록**이다. 등록만으로 값이 생성되거나 모델에 반영되지 않는다.

```
tb_feature (메타 등록)
  → tb_feature_set.features 에 feature_name 포함
  → ml/features.py 에 계산 로직 존재
  → Feature 생성 (tb_feature_dataset.feature_json)
  → tb_training_config.feature_set_id 로 학습
  → 배치 예측 (동일 feature_set_id)
```

신규 파생 Feature 추가 절차:

1. `tb_feature`에 메타데이터 등록 (`feature_name`, 계산식 메모 등)
2. Feature Set의 `features` 배열에 `feature_name` 포함
3. `ml/features.py`의 `build_feature_frame()`에 실제 계산 로직 추가 (또는 향후 표현식 엔진)
4. Feature 생성 API 재실행
5. 학습 설정이 해당 Feature Set을 참조하는지 확인

### 5.1 신규 Feature 등록 유형 (Registry 기준)

| 유형 | 설명 | Feature Set 포함 | Feature 생성 | 학습/예측 |
|------|------|------------------|--------------|-----------|
| **A. Registry 등록 Feature** | `ml/feature_registry.py` + `ml/features.py`에 계산 로직 존재 | 가능 | `feature_json`에 저장 가능 | 사용 가능 |
| **B. Catalog-only Feature** | `tb_feature`에만 등록, Registry·계산 로직 없음 | 가능(경고) | 값 미생성 가능 | 바로 사용 불가 |
| **C. Deprecated/Legacy** | `hdd`, `lag_24h_demand`, `rolling_24h_avg` 등 구 명칭 | TPL 금지 | 공식명으로 대체 필요 | 신규 Set 비권장 |

**중요**: Feature 등록 화면(`/features`)에서 신규 Feature를 등록해도 **자동 계산되지 않습니다**. 학습/예측에 사용 가능하려면 코드 기반 Registry에 등록되어 있고 `build_feature_frame()`에서 값을 만들어야 합니다.

현재 단계에서는 **코드 기반 Registry 방식만** 지원합니다. `LAG(...)`, `MA(...)` 등 DSL 파서/실행 엔진은 없습니다.

**향후 확장**: 범용 Feature Recipe Builder(컬럼 선택 + 연산 템플릿 + 미리보기) 1차 설계는 [`THERMOps_Feature_Recipe_Builder_1차_설계.md`](THERMOps_Feature_Recipe_Builder_1차_설계.md)를 참고한다. 현재는 CODE Registry + Catalog/Quality/Lineage 구조이며, DSL 자동 실행은 여전히 미지원이다.

### 5.2 Feature명 검증 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/features/validate-name?feature_name=...` | Registry·카탈로그·레거시·계산 가능 여부 반환 |
| GET | `/api/v1/features` | 목록 각 행에 `registration` 객체 포함 (동적 계산, DB migration 없음) |

`status` 예: `COMPUTABLE`, `CATALOG_ONLY`, `LEGACY_ALIAS`, `DUPLICATE`, `REGISTERED_IN_REGISTRY`

### 5.3 Feature Build missing Feature 요약

Feature Set에 포함되었으나 `build_feature_frame()` 결과에 없는 Feature는 `result_summary`에 기록됩니다.

- `missing_features`, `catalog_only_features`, `legacy_alias_features`
- 공식 TPL(`FS-TPL-*`)은 전 Feature가 계산 가능하므로 `SUCCESS` 유지
- 카탈로그 전용 Feature 포함 시 `WARNING` 가능 (계산 가능 Feature만 `feature_json` 저장)

### 5.4 Legacy alias 공식명 일괄 대체

Legacy alias 자동 대체 기능은 기존 Feature Set에 남아 있는 과거 명칭을 공식 Feature명으로 정리하기 위한 기능입니다. 계산 로직을 새로 만들거나 `calc_expression`을 실행하는 기능은 아닙니다.

| API | 설명 |
|-----|------|
| `POST /api/v1/feature-sets/{id}/replace-legacy-features` | body: `{ "dry_run": true }` (기본) — 계획만 반환; `dry_run: false` 시 DB 반영 |

- 매핑 기준: `LEGACY_ALIASES` (`hdd`→`heating_degree_days`, `rolling_24h_avg`→`demand_ma_24h` 등)
- 대체 후 **중복 제거**, 순서 유지
- **Catalog-only는 대체 대상 아님**
- 공식 TPL도 Legacy **제거 목적**의 대체는 허용 (dry-run → 확인 후 적용)
- 적용 후 **Feature Build·Feature Quality 재실행 권장**

## 6. 저장 구조

| 저장소 | 키/컬럼 | 설명 |
|--------|---------|------|
| `feature_json` | Feature Set에 포함된 `feature_name` | 학습·예측이 참조하는 **주 경로** |
| `lag_24h_demand`, `lag_168h_demand`, `rolling_24h_avg` | `tb_feature_dataset` 레거시 컬럼 | 일부 값 미러링, 역매핑 지원 |

## 7. Feature Set 템플릿별 공식 Feature 포함

| Feature Set | Lag/Rolling | temperature_diff_24h | HDD/CDD |
|-------------|-------------|----------------------|---------|
| `FS-TPL-LAG-ROLL` | O | X | X |
| `FS-TPL-COMFORT` | O | X | O |
| `FS-TPL-TWO-STAGE` | O | O | O |

## 8. seed 정리 현황

| 파일 | 명칭 체계 | 비고 |
|------|-----------|------|
| `db/init/02_seed_clean.sql` | **공식** (`demand_*`, `heating_degree_days` 등) | Traefik clean 배포 기준 |
| `db/init/02_seed.sql` | **혼재** — TPL은 공식, `FS-000001`·FEAT-001/002는 레거시 | demo/시연 seed, 대규모 변경 보류 |

`02_seed.sql`의 `FS-000001`(`lag_24h`, `rolling_mean_24h` 등)은 계산 키와 불일치하는 **구 demo**이며, clean 배포 경로에서는 사용하지 않는다.

## 9. 향후 확장 (별도 과제)

| 안 | 설명 |
|----|------|
| A | 제한된 DSL 표현식 엔진 (`LAG`, `MA`, `HDD` 등) |
| B | `ml/features.py` 코드 기반 Feature 추가 (현재 방식) |
| C | SQL view / materialized table 기반 Feature 계산 |

## 10. Feature Registry·Lineage

### Registry (`ml/feature_registry.py`)

- `ALL_COMPUTED_FEATURES`와 1:1 메타데이터 (`source_tables`, `lookback_hours`, `leakage_safe` 등)
- `calc_expression`은 설명용; **실행 연결 없음** (`calc_method=CODE`)

### Lineage (`tb_feature_lineage`)

- Feature 생성 성공 시 `dataset_version_id` 기준 Feature별 1행 저장
- `dataset_version_id` 형식: `DSV-{feature_set_id}-{timestamp}` → Feature Set별 유일
- 유니크 키: `(dataset_version_id, feature_name)` — 동일 DSV를 여러 Set이 공유하지 않으므로 충분
- Lineage 저장 실패 시 Feature Build는 **WARNING**으로 완료 (`inserted_count` 유지, `lineage_count=0`)

### API (prefix `/api/v1`)

| 메서드 | 경로 |
|--------|------|
| GET | `/api/v1/feature-registry` |
| GET | `/api/v1/feature-registry/{feature_name}` |
| GET | `/api/v1/features/validate-name?feature_name=...` |
| POST | `/api/v1/feature-sets/{id}/replace-legacy-features` |
| GET | `/api/v1/feature-lineage?dataset_version_id=...` |
| GET | `/api/v1/feature-build-jobs?feature_set_id=...&limit=10` |
| GET | `/api/v1/feature-build-jobs/{job_id}` |
| GET | `/api/v1/feature-build-jobs/{job_id}/lineage` |

테스트·스크립트는 `THERMOOPS_API_BASE=http://localhost:8000/api/v1` (또는 Traefik 공개 URL + `/api/v1`) 기준.

### Feature Build Job 이력

- 저장소: `tb_data_quality_run` (`check_type=FEATURE_BUILD`, `source_id`=feature_set_id)
- 상태: `SUCCESS`(정상), `WARNING`(lineage_error 가능), `FAILED`, `RUNNING`
- `lineage_count` / `lineage_error`는 `result_summary`에서 조회

### UI

| 화면 | 경로 | 내용 |
|------|------|------|
| Feature 목록 | `/features` | **등록 유형** 뱃지, **신규 Feature 사용 절차** 안내, Registry 요약, **상세** 모달 |
| Feature Set 상세 | `/feature-sets/:id` | 포함 Feature **등록 유형** 뱃지·필터·TPL 보호, **Feature Build 이력** · **Lineage** · **Feature 품질 검증** |

**공식 TPL(`FS-TPL-*`) 보호**: computable이 아닌 Feature(Catalog-only·Legacy) 추가 차단. 사용자 정의 Set은 Catalog-only 실험 가능(저장 전 확인).

Lineage 조회 우선순위: 최근 Build Job 목록 → Feature 생성 직후 job → dataset-range fallback → 고급 수동 입력.

### Feature 품질 검증 (`tb_data_quality_run`, `check_type=FEATURE_QUALITY`)

- **목적**: Feature 생성 결과(`feature_json`) 값이 학습·예측에 쓸 만한지 점검 (원천 `tb_heat_demand_actual` 품질과 별도)
- **기준**: `feature_set_id` + `dataset_version_id` (미지정 시 최신 DSV)
- **Lineage와의 관계**: Lineage = 출처 추적, Feature 품질 = 값 적합성
- **registration_status**: Feature별 `COMPUTABLE` / `CATALOG_ONLY` / `LEGACY_ALIAS` 등 — missing key가 단순 누락인지, Catalog-only·Legacy 때문인지 구분
- **build_coverage**: 동일 `dataset_version_id`의 Feature Build `result_summary`에서 missing/catalog_only/legacy 목록 참조(있을 때)

Feature Quality의 `registry_status`는 해당 Feature가 실제 계산 가능한 Registry Feature인지, 카탈로그에만 등록된 Feature인지, 레거시 별칭인지 확인하기 위한 값입니다. Catalog-only 또는 Legacy Feature는 Feature 생성 결과에 값이 없을 수 있으므로 학습/예측에 사용하기 전에 반드시 Feature Build 결과와 Feature Quality 결과를 확인해야 합니다.

| 메서드 | 경로 |
|--------|------|
| POST | `/api/v1/feature-quality-runs` body: `{ feature_set_id, dataset_version_id? }` |
| GET | `/api/v1/feature-quality-runs?feature_set_id=...` |
| GET | `/api/v1/feature-quality-runs/{run_id}` |

**판정**

| 상태 | 조건 |
|------|------|
| FAILED | Dataset 없음, key 누락 row 30%+, invalid 10%+, 점수 < 70 |
| WARNING | null 1%+, 이상치 5%+, 범위 위반 일부, 점수 70~89 |
| SUCCESS | 점수 ≥ 90, 치명 오류 없음 |

**점수**: 100점에서 missing/null/invalid/range/outlier 비율로 감점 (가중치 40/25/20/10/5).

**지표**: `null_ratio`, `missing_key_count`, `invalid_count`, `range_violation_count`, `outlier_count`, 분포(min/p25/mean/p50/p75/max/std)

`/data/quality` 목록에서는 `FEATURE_QUALITY`를 **제외** (원천 데이터 품질 중심 유지).

## 11. 검증

- `python scripts/test_feature_metadata_consistency.py`
- `python scripts/test_feature_lineage.py`
- `python scripts/test_feature_build_jobs.py`
- `python scripts/test_feature_quality.py`
- 회귀: `python scripts/run_regression_tests.py --group model`
