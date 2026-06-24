# THERMOps 열수요 예측 논문 반영 메모

| 항목 | 내용 |
|------|------|
| 문서명 | THERMOps 열수요 예측 논문 반영 메모 |
| 작성 목적 | Feature 생성·모델 학습·모델 평가 고도화를 위한 참고 설계 메모 |
| 현재 구현 기준 | **P0-1** CSV 기반 실제 데이터 적재 완료 (`tb_heat_demand_actual`, `tb_weather_observation`) |
| 참고 PDF | `docs/pdf/우수상.pdf`, `docs/pdf/KCI_FI002432660.pdf` |
| PDF 추출본 | `docs/pdf/extracted/우수상.md`, `docs/pdf/extracted/KCI_FI002432660.md` |
| 코드/설계서 변경 | 없음 (본 문서만 신규 작성) |

> **주의:** 논문·대회 보고서에 기재된 R², MAPE, RMSE 등은 **특정 데이터·기간·지역 기준의 참고 지표**이며, THERMOps에서 동일 성능을 보장하지 않는다. 구현 시에는 **후보 모델/참고 지표**로만 활용한다.

---

## 목차

1. [문서 목적](#1-문서-목적)
2. [참고 PDF별 핵심 요약](#2-참고-pdf별-핵심-요약)
3. [THERMOps Feature 후보](#3-thermops-feature-후보)
4. [Feature Set 템플릿 제안](#4-feature-set-템플릿-제안)
5. [모델 알고리즘 후보](#5-모델-알고리즘-후보)
6. [2-Stage 모델 적용 방안](#6-2-stage-모델-적용-방안)
7. [구현 단계별 반영 위치](#7-구현-단계별-반영-위치)
8. [지금 바로 구현하지 않을 항목](#8-지금-바로-구현하지-않을-항목)
9. [THERMOps 구현 권장 순서](#9-thermops-구현-권장-순서)
10. [부록: 논문 참고 지표 요약](#10-부록-논문-참고-지표-요약)

---

## 1. 문서 목적

- THERMOps의 **다음 구현 단계**(P0-2~P0-6, P1)에서 Cursor·개발자가 **구현 프롬프트·설계 결정**을 내릴 때 바로 참고할 수 있는 **논문 기반 설계 메모**이다.
- 대상 범위:
  - **Feature 생성** (`ml/features.py`, `DAG-005`, `tb_feature_dataset`)
  - **모델 학습·평가** (`DAG-006`, MLflow, Training Job API)
  - **모델 성능 비교·Registry** (Champion 후보, 성능 화면)
- 본 문서는 기존 `docs/md/THERMOps_*_설계서.md`를 **대체하지 않으며**, 논문·대회 자료에서 도출한 **후보 Feature·알고리즘·2-Stage 구조**를 THERMOps 용어로 정리한 **보조 자료**이다.

---

## 2. 참고 PDF별 핵심 요약

### 2.1 `우수상.pdf` 핵심 요약

| 구분 | 내용 |
|------|------|
| 제목 | 2-Stage CatBoost를 활용한 열수요 예측 모델 개발 (따숩조) |
| 데이터 | `train_heat.csv`, `test_heat.csv`; 지사(`branch_id`)별 열수요·기상 시계열 |
| 핵심 아이디어 | Stage 1 예측 후 **잔차(residual)** 를 Stage 2에서 보정 → `final = stage1 + stage2` |
| Feature 범주 | 시간, 기상, 공휴일/코로나 시기, 쾌적도(HDD/CDD/comfort_distance), Lag, 이동평균 |
| 전처리 | 결측 보완(RandomForest, ffill), 체감온도 수식, sin/cos 주기 변수, Min-Max Scaling(학습 기준) |
| 단일 모델 비교 | CatBoost, XGBoost, LightGBM, RNN, LSTM (검증 RMSE 비교) |
| 2-Stage 조합 | CatBoost + CatBoost 등 (Stage1 잔차를 Stage2 타깃으로 학습) |
| 튜닝 | Bayesian Optimization 기반 AutoML (CatBoost 하이퍼파라미터) |
| 참고 RMSE (해당 데이터) | CatBoost 단일 15.12 → 2-Stage 14.72 → 튜닝 후 검증 **13.17** (보장 아님) |

**주요 파생변수 (논문 표 1 기준)**

| 분류 | 변수 예시 |
|------|-----------|
| 시간 | `month`, `day_of_week`, `hour`, `month_sin/cos`, `hour_sin/cos`, `weekend`, `winter`, `summer` |
| 사회적 | `is_holiday`, `is_covid_period` |
| 쾌적도 | `comfort_distance`, `heating_degree_days`, `cooling_degree_days` |
| Lag | `ta_chi_lag_k`, `hm_lag_k`, `si_lag_k` (k: 1~24h, 2~4d, 1~2주, 1개월) |
| 이동평균 | `ta_chi_ma_k`, `si_ma_k` |

---

### 2.2 `KCI_FI002432660.pdf` 핵심 요약

| 구분 | 내용 |
|------|------|
| 제목 | 딥러닝을 이용한 열 수요예측 모델 개발 (서한석·신광섭, 2018) |
| 핵심 아이디어 | **실시간 확보 가능한 제한 변수**(외기온도 + 날짜)만으로 MLP 학습 → 범용성 확보 |
| 모델 구조 | TensorFlow MLP (Hidden 128-256-128-64, relu, Adam, Epoch 2000) |
| 3단계 변수 확장 | ① 외기온도만 → ② + 주중/주말(공휴일 포함) → ③ + **전일 온도차** |
| 대조군 | MLR(다중선형회귀) |
| 평가 지표 | R², MAPE |
| 데이터 | 2012-01-01 ~ 2015-01-31 (train 3년, test 2015년 1월 동절기) |

**3가지 모형 비교 (해당 지역·기간 참고 지표, 보장 아님)**

| 모형 | 입력 | MLP R² (참고) | MLP MAPE% (참고) |
|------|------|---------------|------------------|
| 외기온도 모형 | 외기온도 | 0.76 | 3.76 |
| 행동 패턴 모형 | 외기온도 + 주중/주말 | 0.78 | 3.48 |
| 심리 모형 | 외기온도 + 주중/주말 + 전일 온도차 | 0.80 | 3.13 |

- 같은 온도에서 수요가 다른 현상 → **행동 패턴·심리 요인** Feature로 설명 시도
- 향후 연구 제안: RNN, 타 지역 검증

---

### 2.3 THERMOps 반영 구분

| 항목 | 직접 반영 (P0-2~P0-6) | 참고만 (후순위/사업 확장) |
|------|----------------------|---------------------------|
| 시간 Feature (hour, DOW, sin/cos) | ✅ P0-3 | — |
| 기상 Feature (temperature, humidity, rainfall, wind) | ✅ P0-3 (`tb_weather_observation` 조인) | 일사량(`si`) — 데이터 확보 후 |
| 공휴일/주말 | ✅ P0-3 (`tb_calendar` 연계) | 코로나 시기 이진 변수 — 운영 정책 결정 후 |
| 전일 온도차 | ✅ P0-3 | — |
| Lag / 이동평균 (열수요·기상) | ✅ P0-3 (`ml/features.py` 확장) | Lag k 다단계(1개월) — 점진 확장 |
| 쾌적도 / HDD / CDD / comfort_distance | ✅ P0-3 (템플릿) | 체감온도 수식·실내 가이드 상수는 설정화 |
| 지사/권역 (`site_id`, `weather_area_id`) | ✅ 이미 스키마·샘플 존재 | `branch_id` Label Encoding — CatBoost 시 |
| CatBoost / LightGBM / XGBoost | ✅ P0-4 | — |
| Baseline (MLR/seasonal naive) | ✅ P0-4 | — |
| 2-Stage 잔차 보정 | ⏳ P0-4 확장 | — |
| MLP | ⏳ P0-4 후순위 후보 | — |
| LSTM / RNN | ❌ P1 이후 검토 | 논문에서 CatBoost 대비 RMSE 열위(참고) |
| Bayesian Optimization / Optuna | ❌ 기본 학습 안정화 후 | 우수상.pdf에서 사용 |
| Min-Max Scaling + 720h 패딩 | 참고 (누수 방지 패턴) | 구현 시 train-only fit 원칙 적용 |
| 인구통계·공간정보·경제지표 | ❌ | 우수상.pdf 향후 연구·KCI 타지역 검증 |
| 지사 클러스터링·지사별 특화 모델 | ❌ P1+ | — |

---

## 3. THERMOps Feature 후보

> **공통 키:** `site_id` + `measured_at`(또는 `feature_at`). 기상은 `tb_site_weather_map` → `weather_area_id` 조인.

### 3.1 시간 기반 Feature

| Feature ID (후보) | 설명 | 논문 출처 | THERMOps 소스 |
|-------------------|------|-----------|---------------|
| `hour_of_day` | 0~23 | 우수상, KCI(날짜 파생) | `measured_at` |
| `day_of_week` | 0~6 | 우수상 | `measured_at` / `tb_calendar` |
| `month` | 1~12 | 우수상 | `measured_at` |
| `hour_sin`, `hour_cos` | 시간 주기성 | 우수상 | 파생 |
| `month_sin`, `month_cos` | 월 주기성 | 우수상 | 파생 |
| `is_weekend` | 주말 여부 | 우수상, KCI | `tb_calendar.is_weekend` |
| `is_winter`, `is_summer` | 계절 구분 | 우수상 | `tb_calendar` 또는 month 규칙 |
| `day_of_year` | 연중 일자 | 우수상(전처리) | 파생 |

### 3.2 기상 기반 Feature

| Feature ID (후보) | 설명 | 논문 출처 | THERMOps 소스 |
|-------------------|------|-----------|---------------|
| `temperature` | 외기/대기 온도 (`ta`) | 양쪽 | `tb_weather_observation.temperature` |
| `humidity` | 습도 (`hm`) | 우수상 | `tb_weather_observation.humidity` |
| `rainfall` | 강수 (`rn_hr1`) | 우수상 | `tb_weather_observation.rainfall` |
| `wind_speed` | 풍속 (`ws`) | 우수상 | `tb_weather_observation.wind_speed` |
| `apparent_temp` | 체감온도 (`ta_chi`) | 우수상 | 컬럼 있으면 사용, 없으면 수식 파생 |
| `solar_irradiance` | 일사량 (`si`) | 우수상 | **데이터 미보유 시 보류** |

### 3.3 공휴일/사회적 요인 Feature

| Feature ID (후보) | 설명 | 논문 출처 | THERMOps 소스 |
|-------------------|------|-----------|---------------|
| `is_holiday` | 공휴일 | 우수상 | `tb_calendar.is_holiday` |
| `is_weekday_vs_weekend_holiday` | 주중 vs 주말·공휴일 | KCI | `tb_calendar` 조합 |
| `is_covid_period` | 팬데믹 기간 | 우수상 | **설정 YAML** (기본 비활성) |
| `behavior_pattern_flag` | KCI 행동패턴 이진 | KCI | `is_weekend OR is_holiday` 등 |

### 3.4 전일 온도차/심리 요인 Feature

| Feature ID (후보) | 설명 | 논문 출처 | THERMOps 소스 |
|-------------------|------|-----------|---------------|
| `temp_diff_prev_day` | 전일 동시각(또는 전일 평균) 대비 온도차 | KCI | `temperature` 시계열 shift |
| `temp_diff_prev_24h` | 24시간 전 대비 온도차 | KCI 확장 | 파생 |
| `demand_psychology_proxy` | 온도 변화 대비 수요 변화 잔차 | KCI | Stage2 또는 Feature로 분리 검토 |

### 3.5 Lag Feature

| Feature ID (후보) | 설명 | Lag | 논문 출처 |
|-------------------|------|-----|-----------|
| `lag_1h_demand` ~ `lag_24h_demand` | 과거 열수요 | 1~24h | 우수상(열수요 lag 확장) |
| `lag_168h_demand` | 주간 주기 | 168h | `ml/features.py` 기존 |
| `lag_k_temperature` | 기온 lag | k∈{1,24,48,168,…} | 우수상 |
| `lag_k_humidity`, `lag_k_rainfall` | 기상 lag | k 가변 | 우수상 |

- **지사별 그룹:** `group_col=site_id`로 `shift` (현재 `ml/features.py` 패턴 유지)

### 3.6 이동평균 Feature

| Feature ID (후보) | 설명 | 윈도우 | 논문 출처 |
|-------------------|------|--------|-----------|
| `rolling_24h_avg_demand` | 열수요 24h 평균 | 24 | `ml/features.py` 기존 |
| `rolling_168h_avg_demand` | 열수요 7d 평균 | 168 | 우수상 확장 |
| `rolling_k_avg_temperature` | 기온 이동평균 | k∈{24,48,168,…} | 우수상 (`ta_chi_ma_k`) |
| `rolling_k_avg_humidity` | 습도 이동평균 | k 가변 | 우수상 |

### 3.7 쾌적도 기반 Feature

| Feature ID (후보) | 설명 | 논문 출처 | 비고 |
|-------------------|------|-----------|------|
| `heating_degree_days` | 난방도일 (기준 18~21℃) | 우수상 | 기준온도는 `configs/` 상수화 |
| `cooling_degree_days` | 냉방도일 (기준 24~27℃) | 우수상 | 동절기 중심이면 우선순위 낮음 |
| `comfort_distance` | 쾌적온도 범위와 체감온도 최소 거리 | 우수상 | `apparent_temp` 또는 `temperature` 사용 |
| `temp_below_comfort` | 쾌적 하한 이하 거리 | 우수상 파생 | HDD와 유사 |

### 3.8 지사/권역 기반 Feature

| Feature ID (후보) | 설명 | THERMOps 소스 |
|-------------------|------|---------------|
| `site_id` | 지사 식별자 | `tb_heat_demand_actual.site_id` |
| `site_id_encoded` | CatBoost용 범주 인코딩 | 학습 파이프라인 |
| `weather_area_id` | 기상 권역 | `tb_site_weather_map` |
| `parent_site_id` | 상위 조직 | `tb_site` (있을 경우) |
| `site_cluster_id` | 유사 지사 군집 | **P1+** (우수상 향후 연구) |

---

## 4. Feature Set 템플릿 제안

> UI `Feature Set`(`FEAT-002`) 및 `tb_feature_set.features` JSON에 등록할 **템플릿 초안**.  
> `description` 메타 또는 별도 문서로 템플릿 ID를 관리한다.

### 4.1 Minimal Weather Feature Set

| 항목 | 내용 |
|------|------|
| 목적 | KCI 외기온도 모형에 대응하는 **최소 기상 Baseline** |
| Feature | `temperature`, `hour_of_day`, `day_of_week`, `month` |
| 입력 테이블 | `tb_heat_demand_actual` + `tb_weather_observation` |
| 적합 단계 | P0-3 초기 스모크 |

### 4.2 Behavior Pattern Feature Set

| 항목 | 내용 |
|------|------|
| 목적 | KCI 행동 패턴 모형 (주중/주말·공휴일) |
| Feature | Minimal + `is_weekend`, `is_holiday`, `behavior_pattern_flag` |
| 입력 테이블 | + `tb_calendar` |
| 적합 단계 | P0-3 |

### 4.3 Weather Extended Feature Set

| 항목 | 내용 |
|------|------|
| 목적 | 우수상.pdf 기상 변수 확장 |
| Feature | Behavior + `humidity`, `rainfall`, `wind_speed`, `apparent_temp` |
| 입력 테이블 | `tb_weather_observation` 전 컬럼 |
| 적합 단계 | P0-3 |

### 4.4 Lag/Rolling Feature Set

| 항목 | 내용 |
|------|------|
| 목적 | 시계열 메모리 반영 (우수상 Lag/MA) |
| Feature | Weather Extended + `lag_24h_demand`, `lag_168h_demand`, `rolling_24h_avg_demand`, `lag_24h_temperature`, `rolling_24h_avg_temperature` |
| 구현 참고 | `ml/features.py`의 `build_lag_features` 확장 |
| 주의 | 예측 시 **미래 누수 방지** (train fit scaler, lag는 과거만) |
| 적합 단계 | P0-3 |

### 4.5 Comfort Index Feature Set

| 항목 | 내용 |
|------|------|
| 목적 | 쾌적도·난방도일 기반 비선형 기온 효과 |
| Feature | Lag/Rolling + `heating_degree_days`, `cooling_degree_days`, `comfort_distance` |
| 설정 | HDD/CDD 기준온도 → `configs/model.yml` 또는 `configs/pipeline.yml` |
| 적합 단계 | P0-3 후반 |

### 4.6 Two-Stage Ready Feature Set

| 항목 | 내용 |
|------|------|
| 목적 | Stage 1 CatBoost용 **풀 Feature** + Stage 2에서 `stage1_prediction` 추가 |
| Feature | Comfort Index + `month_sin/cos`, `hour_sin/cos`, `is_winter`, `is_summer`, `temp_diff_prev_day`, `site_id_encoded` |
| Stage 2 추가 | `stage1_prediction` (학습 시 OOF 예측값 권장) |
| 적합 단계 | P0-4 확장 |

**템플릿 의존 관계**

```text
Minimal Weather
  └─ Behavior Pattern
       └─ Weather Extended
            └─ Lag/Rolling
                 └─ Comfort Index
                      └─ Two-Stage Ready (+ stage1_prediction)
```

---

## 5. 모델 알고리즘 후보

| 알고리즘 | 분류 | 논문 근거 | THERMOps 우선순위 | 비고 |
|----------|------|-----------|-------------------|------|
| **Baseline (MLR)** | 통계 | KCI 대조군 | **P0-4 필수** | 해석 용이, 성능 하한선 |
| **Baseline (seasonal naive)** | 통계 | MLOps 관례 | **P0-4 필수** | 전주 동시각 등 |
| **LightGBM** | GBDT | 우수상 비교 | **P0-4 필수** | `configs/pipeline.yml` 기존 |
| **XGBoost** | GBDT | 우수상 RMSE 17.43 (참고) | **P0-4 필수** | 기존 설정 |
| **CatBoost** | GBDT | 우수상 최우수 단일 15.12 (참고) | **P0-4 필수** | 범주형·`site_id` 처리 유리 |
| **2-Stage CatBoost** | GBDT 2단 | 우수상 핵심 | **P0-4 확장** | 잔차 보정 |
| **MLP** | 딥러닝 | KCI 핵심 | **P0-4 후순위** | 제한 변수 실험용 |
| **LSTM** | 딥러닝 | 우수상 RMSE 15.89 (참고) | **후순위 검토** | 운영·데이터 복잡도 |
| **RNN** | 딥러닝 | 우수상 RMSE 35.91 (참고) | **후순위 검토** | 성능·운영 모두 열위 참고 |

**평가 지표 (THERMOps 표준)**

| 지표 | 용도 | 논문 사용 |
|------|------|-----------|
| MAPE | Primary (`configs/pipeline.yml`) | KCI |
| RMSE | 보조 | 우수상 |
| MAE | 보조 | — |
| R² | 보조 | KCI |

---

## 6. 2-Stage 모델 적용 방안

### 6.1 학습·예측 흐름

```text
[Stage 1]
  X (Feature Set) ──► CatBoost ──► ŷ₁

[잔차]
  residual = y_actual - ŷ₁   (학습/검증 구간)

[Stage 2]
  X₂ = X + ŷ₁ ──► CatBoost ──► r̂₂

[최종]
  ŷ_final = ŷ₁ + r̂₂
```

| 단계 | 설명 | 구현 시 주의 |
|------|------|--------------|
| Stage 1 학습 | Two-Stage Ready Feature Set으로 CatBoost 학습 | 시계열 split (우수상: 2021~2022 train, 2023 val) |
| Stage 1 예측 | train/val/test에 ŷ₁ 생성 | **OOF 예측**으로 Stage2 입력 시 누수 방지 |
| residual 계산 | `actual - stage1_prediction` | 지사·시각 키 정렬 |
| Stage 2 학습 | 입력 = 기존 Feature + `stage1_prediction`, 타깃 = residual | 동일 split |
| 최종 예측 | `stage1_prediction + stage2_residual_prediction` | 배치 예측(P0-5)에 동일 파이프라인 |

### 6.2 MLflow 기록 방식

| 기록 항목 | Stage 1 | Stage 2 | Parent Run |
|-----------|---------|---------|------------|
| Run name | `{job_id}_stage1` | `{job_id}_stage2` | `{job_id}` |
| Parameters | algorithm, feature_set_id, train_period | + `stage1_model_uri` | `pipeline=two_stage` |
| Metrics | mape, rmse, mae, r2 | 동일 | **final_mape**, **final_rmse** |
| Artifacts | model.pkl, feature_importance | model.pkl | pipeline diagram, residual plot |
| Tags | `stage=1`, `model_family=catboost` | `stage=2` | `thermops.training_job_id` |

### 6.3 모델 Registry 저장 방식

| Registry 항목 | 제안 |
|---------------|------|
| 모델명 | `heat_demand_lgbm` → **`heat_demand_catboost_2stage`** (별도 이름) |
| 버전 구성 | Stage1 artifact + Stage2 artifact **번들** (MLflow logged model 또는 custom artifact folder) |
| `tb_model_version` | `metric_summary_json`에 `stage1_mape`, `stage2_mape`, `final_mape` |
| Champion 정책 | **final_mape** 기준 Champion 후보 (검증 구간) |
| 예측 서빙 | 로더가 stage1 → stage2 순차 호출 |

### 6.4 THERMOps 화면 표현 항목

| 화면 | 표현 항목 |
|------|-----------|
| Training Config (`ML-001`) | `algorithm=two_stage_catboost`, Stage1/2 알고리즘 선택(초기는 CatBoost 고정) |
| Training Job (`ML-002`) | 상태: `RUNNING_STAGE1` → `RUNNING_STAGE2` → `SUCCESS`; 로그에 잔차 통계 |
| 모델 성능 비교 (`ML-003`) | 단일 vs 2-Stage **참고 MAPE/RMSE** 나란히 |
| Model Registry (`ML-004`) | 버전 태그 `two_stage`, Champion 사유 |
| Prediction Job (`PRED-001`) | 사용 모델이 2-Stage일 경우 파이프라인 단계 표시 |

---

## 7. 구현 단계별 반영 위치

| 단계 | 목표 | 논문 반영 핵심 | THERMOps 반영 위치 |
|------|------|----------------|-------------------|
| **P0-1** ✅ | CSV 적재 | 원천 데이터 | `tb_heat_demand_actual`, `tb_weather_observation`, CSV 서비스 — **완료** |
| **P0-2** | 데이터 품질 점검 | 결측·이상 패턴 사전 탐지 (우수상 EDA) | `DAG-004`, `/data-quality/*`, `tb_data_quality_run`; 기상·열수요 **시간 누락·중복·범위** 검사 |
| **P0-3** | Feature 생성 실제화 | 시간/기상/행동/심리/Lag/MA/쾌적도 | `ml/features.py`, `DAG-005`, `tb_feature_dataset`, Feature Set 템플릿 §4 |
| **P0-4** | 모델 학습 + MLflow | CatBoost/LGBM/XGB + Baseline; 2-Stage 확장 | `ml/train*.py`, `DAG-006`, Training Job API, MLflow experiment |
| **P0-5** | 배치 예측 실제화 | 동일 Feature 파이프라인, 2-Stage 순차 추론 | `DAG-008`, `tb_heat_demand_prediction`, Champion 모델 로드 |
| **P0-6** | 성능 평가/모니터링 | MAPE/RMSE 추이, 잔차 패턴 모니터링 | `DAG-009`, `tb_model_performance_metric`, 대시보드 `DASH-001` |
| **P1** | 드리프트/재학습 후보 | 입력 분포 변화(기온·행동 패턴) | `DAG-010`, `tb_drift_report`, `tb_retraining_candidate` |

### P0-2 품질 점검 체크리스트 (논문 연계)

| 검사 | 근거 | 임계 예시 (`configs/pipeline.yml`) |
|------|------|-------------------------------------|
| `temperature` 결측률 | 우수상 결측 보완 전제 | `max_missing_rate: 0.05` |
| `measured_at` 시간 연속성 | Lag/MA 생성 전제 | 시간 단위 gap 탐지 |
| 동일 `site_id+measured_at` 중복 | upsert 품질 | duplicate count |
| 기온 범위 이상치 | EDA | `max_outlier_rate: 0.03` |
| `site_id` ↔ `weather_area_id` 정합 | 기상 조인 | FK/매핑 누락 |

### P0-3 Feature 생성 모듈 구조 (제안)

```text
ml/
  features/
    time.py          # §3.1
    weather.py       # §3.2, join_weather
    calendar.py      # §3.3
    psychology.py    # §3.4
    lag_rolling.py   # §3.5, §3.6
    comfort.py       # §3.7
    pipeline.py      # Feature Set ID → transform chain
```

### P0-4 학습 실험 매트릭스 (제안)

| 실험 ID | Feature Set | 모델 | 목적 |
|---------|-------------|------|------|
| EXP-01 | Minimal Weather | MLR | KCI 대응 Baseline |
| EXP-02 | Behavior Pattern | LightGBM | 행동 패턴 효과 |
| EXP-03 | Weather Extended | XGBoost | 기상 확장 |
| EXP-04 | Lag/Rolling | CatBoost | 시계열 GBDT |
| EXP-05 | Comfort Index | CatBoost | 쾌적도 |
| EXP-06 | Two-Stage Ready | 2-Stage CatBoost | 우수상 재현 |

---

## 8. 지금 바로 구현하지 않을 항목

| 항목 | 분류 | 사유 |
|------|------|------|
| 2-Stage CatBoost | P0-4 **확장** | 단일 GBDT·MLflow 안정화 선행 |
| LSTM / RNN | 후순위 | 우수상 참고 RMSE 열위, GPU·시계열 운영 복잡 |
| MLP | P0-4 후순위 | KCI 참고용 소규모 실험 후 결정 |
| Bayesian Optimization / Optuna | 학습 안정화 후 | 우수상 CatBoost 튜닝 참고 |
| `is_covid_period` | 설정 옵션 | 운영 기간 정책 필요 |
| 일사량(`si`) Feature | 데이터 확보 후 | 샘플 CSV 미포함 |
| 인구통계·공간정보 | 사업 데이터 후 | 우수상 향후 연구 |
| 경제지표(GDP, 요금 등) | 사업 데이터 후 | 우수상 향후 연구 |
| 지사 클러스터링·지사별 특화 모델 | P1+ | |
| KCI 제안 RNN | P1+ | |
| 전국 단일 vs 지사별 모델 A/B | P1+ | |

---

## 9. THERMOps 구현 권장 순서

**전제:** P0-1 CSV 적재 완료, `DS-CSV-001/002`, `MAP-CSV-001/002` 시드 사용 가능

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 1 | **품질 점검 (P0-2)** | 품질 run, 결측/중복/범위 리포트 |
| 2 | **달력/공휴일 시드 정비** | `tb_calendar` — Behavior Feature 전제 |
| 3 | **Feature 생성 (P0-3)** | `tb_feature_dataset`, Feature Set 템플릿 §4.1~4.5 |
| 4 | **Baseline 학습** | MLR / seasonal naive, MLflow 기록 |
| 5 | **LightGBM / XGBoost / CatBoost** | 단일 모델 3종, 성능 비교表 |
| 6 | **MLflow 실험·Registry 연동** | `tb_training_job`, artifact URI |
| 7 | **모델 성능 비교 UI** | ML-003 차트 (참고 지표) |
| 8 | **2-Stage 잔차 보정 (P0-4 확장)** | §6 파이프라인 |
| 9 | **배치 예측 (P0-5)** | Champion 모델, D+1 예측 |
| 10 | **성능 모니터링 (P0-6)** | 실적 매칭, MAPE 추이 |
| 11 | **드리프트/재학습 후보 (P1)** | 기온·행동 분포 변화 탐지 |

---

## 10. 부록: 논문 참고 지표 요약

> 아래 수치는 **해당 논문·대회 데이터 기준 참고값**이며 THERMOps 성능 보장 아님.

### 10.1 우수상.pdf — 단일 모델 RMSE (참고)

| 모델 | RMSE (참고) |
|------|-------------|
| CatBoost | 15.1249 |
| LSTM | 15.8938 |
| XGBoost | 17.4313 |
| LightGBM | 17.5197 |
| RNN | 35.9074 |

### 10.2 우수상.pdf — 2-Stage RMSE (참고)

| Stage1 + Stage2 | RMSE (참고) |
|-----------------|-------------|
| CatBoost + CatBoost | 14.7179 → 튜닝 후 검증 **13.17** |
| CatBoost + XGBoost | 14.9249 |
| CatBoost + LightGBM | 15.0650 |

### 10.3 KCI — MLP vs MLR (참고)

| 모형 | MLP R² | MLP MAPE% | MLR MAPE% |
|------|--------|-----------|-----------|
| 외기온도 | 0.76 | 3.76 | 6.11 |
| 행동 패턴 | 0.78 | 3.48 | 6.11 |
| 심리(전일 온도차) | 0.80 | 3.13 | 5.96 |

---

## 변경 이력

| 일자 | 내용 |
|------|------|
| 2026-06-24 | 최초 작성 (PDF 추출본 기반) |
