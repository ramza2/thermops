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
| GET | `/api/v1/feature-lineage?dataset_version_id=...` |
| GET | `/api/v1/feature-build-jobs/{job_id}/lineage` |

테스트·스크립트는 `THERMOOPS_API_BASE=http://localhost:8000/api/v1` (또는 Traefik 공개 URL + `/api/v1`) 기준.

## 11. 검증

- `python scripts/test_feature_metadata_consistency.py`
- `python scripts/test_feature_lineage.py`
- 회귀: `python scripts/run_regression_tests.py --group model`
