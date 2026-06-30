# THERMOps: 열수요 예측 모델 운영 자동화 플랫폼

오픈소스 기반 열수요 예측 MLOps 스타터 솔루션입니다. 데이터 적재부터 Feature 구성, 모델 학습, 배치 예측, 성능 모니터링까지 전체 운영 흐름을 웹 UI에서 시연할 수 있습니다.

## 프로젝트 구조

```text
thermops/                          # 프로젝트 루트
├── backend/                       # FastAPI 백엔드 (/api/v1)
├── frontend/                      # React 프론트엔드 (Vite + TypeScript)
├── ml/                            # ML 모듈 (데이터 로딩, Feature, 학습, 평가)
├── airflow/dags/                  # Airflow DAG 템플릿
├── db/init/                       # PostgreSQL 스키마 및 시드 데이터
├── configs/                       # 파이프라인/모델 설정
├── scripts/                       # 유틸리티 스크립트
├── docs/md/                       # 설계서 (Markdown)
└── design/figma/                  # Figma UI 참조 자료
```

## 사전 요구사항

- Docker Desktop 4.x 이상
- (로컬 개발 시) Node.js 20+, Python 3.11+, PostgreSQL 15+

## 설치 및 실행 (Docker Compose)

Docker Desktop이 실행 중인지 확인한 뒤, 프로젝트 루트에서 아래 명령을 실행합니다.

```powershell
# Windows (PowerShell)
cd d:\Projects\Cursor\thermops
copy .env.example .env

# 전체 스택 빌드 및 기동
docker compose up -d --build

# 기동 상태 확인 (postgres healthy 후 backend/airflow 기동)
docker compose ps
```

```bash
# macOS / Linux
cp .env.example .env
docker compose up -d --build
docker compose ps
```

**첫 기동 시 참고:** Airflow 웹서버는 DB 마이그레이션 후 약 30~60초 후 `http://localhost:8080` 에 응답합니다. MLflow는 `psycopg2` 설치 후 기동됩니다.

**기존 DB 볼륨 사용 시:** 스키마 변경(`tb_pipeline_run.result_summary` 등)을 반영하려면 아래를 실행합니다.

```powershell
python scripts/apply_dev_migrations.py
```

## P0 전체 실행 절차

P0 MLOps 루프: **적재 → 품질 → Feature → 학습 → 예측 → 평가 → Airflow 오케스트레이션**

### 1. Docker 전체 기동

```powershell
docker compose up -d --build
python scripts/apply_dev_migrations.py   # 기존 볼륨 사용 시
docker compose ps
```

### 2. 단계별 API 검증 (순서 권장)

| 단계 | 스크립트 | 설명 |
|------|----------|------|
| P0-1 CSV 적재 | `python scripts/test_csv_ingestion.py` | 열수요·기상 CSV → DB |
| P1-3 DB Connector | `python scripts/test_db_connector.py` | PostgreSQL 적재 |
| P1-3 안정화 | `python scripts/test_connector_error_handling.py` | 오류 코드·마스킹 |
| P0-2 품질 점검 | `python scripts/test_data_quality.py` | 결측·중복·이상치 |
| P0-3 Feature | `python scripts/test_feature_build.py` | Feature Dataset 생성 |
| P0-4-1 학습 | `python scripts/test_model_training.py` | LightGBM + MLflow |
| P1-4 CatBoost | `python scripts/test_catboost_training.py` | CatBoost 학습·예측 |
| P1-4 2-Stage | `python scripts/test_two_stage_catboost.py` | 2-Stage CatBoost |
| P0-5 예측 | `python scripts/test_batch_prediction.py` | 배치 예측 DB 저장 |
| P0-6 평가 | `python scripts/test_prediction_evaluation.py` | 예측↔실적 매칭 |

### 3. Airflow 개별 DAG / Full Pipeline

```powershell
# 짧은 DAG (품질 점검, 수 초~수십 초)
python scripts/test_airflow_pipeline.py

# 전체 파이프라인 E2E (학습 포함, 5~20분 소요 가능)
python scripts/test_full_pipeline_airflow.py
```

Full Pipeline API 수동 실행:

```powershell
curl -X POST "http://localhost:8000/api/v1/pipelines/thermops_full_pipeline_dag/trigger" ^
  -H "Content-Type: application/json" ^
  -d "{\"business_date\":\"2026-06-20\",\"parameters\":{\"source_id\":\"DS-CSV-001\",\"feature_set_id\":\"FS-TPL-LAG-ROLL\",\"config_id\":\"TRC-TPL-LAG-ROLL\",\"model_name\":\"heat_demand_lightgbm\"}}"
```

### 4. P0 최종 검증 (전체 테스트)

**권장: 회귀 테스트 Runner로 일괄 실행**

```powershell
# 빠른 API·적재·품질 검증 (수 분)
python scripts/run_regression_tests.py --group quick

# 전체 회귀 (20~60분+, Airflow·학습 포함)
python scripts/run_regression_tests.py --group full

# Airflow 제외 전체
python scripts/run_regression_tests.py --group full --skip-airflow

# Frontend build 제외
python scripts/run_regression_tests.py --group full --skip-frontend

# 느린 환경 (timeout 2배)
python scripts/run_regression_tests.py --group full --timeout-scale 2
```

로그·요약: `logs/regression/YYYYMMDD_HHMMSS/summary.md`

**개별 스크립트 수동 실행 (레거시)**

```powershell
python scripts/test_system_config.py
python scripts/test_performance_eval_type.py
python scripts/test_prediction_trend.py
python scripts/test_csv_ingestion.py
python scripts/test_data_quality.py
python scripts/test_feature_build.py
python scripts/test_model_training.py
python scripts/test_feature_dataset_range.py
python scripts/test_prediction_period_validation.py
python scripts/test_batch_prediction.py
python scripts/test_prediction_evaluation.py
python scripts/test_airflow_pipeline.py
python scripts/test_full_pipeline_airflow.py
python scripts/test_drift_retraining.py
python scripts/test_retraining_candidate_train.py
python scripts/test_retraining_airflow.py
python scripts/test_catboost_training.py
python scripts/test_two_stage_catboost.py
python scripts/smoke_test_api.py
cd frontend && npm run build
```

### 5. 주요 URL

| 서비스 | URL |
|--------|-----|
| Frontend | http://localhost:5173 |
| Backend Docs | http://localhost:8000/docs |
| Airflow | http://localhost:8080 (admin / admin) |
| MLflow | http://localhost:5000 |
| MinIO Console | http://localhost:9001 (minioadmin / minioadmin) |

### API 스모크 테스트

백엔드가 기동된 상태에서:

```powershell
python scripts/smoke_test_api.py
```

12개 주요 API + `/health` 의 HTTP 200 응답을 확인합니다.

### 전체 회귀 테스트 Runner

커밋·태그 전 전체 테스트를 한 번에 실행하고 결과를 요약합니다.

```powershell
python scripts/run_regression_tests.py --group quick      # API·적재·품질 (약 1~3분)
python scripts/run_regression_tests.py --group connector  # DB/API Connector
python scripts/run_regression_tests.py --group model      # Feature·학습·예측·메타데이터 정합성·Dataset range·기간 검증·평가 (9개)
python scripts/run_regression_tests.py --group retraining # Drift·재학습
python scripts/run_regression_tests.py --group airflow    # Airflow DAG
python scripts/run_regression_tests.py --group frontend   # npm build + check-pages
python scripts/run_regression_tests.py --group full       # 전체 (20~60분+)
python scripts/run_regression_tests.py --all              # full과 동일
```

**`model` 그룹 (9개):** Feature 생성 → **Feature 메타데이터·명칭 정합성** (`test_feature_metadata_consistency.py`) → LightGBM/CatBoost/2-Stage 학습 → Feature Dataset range API → 예측 기간 검증 → 배치 예측 → 예측-실적 평가. 배치 예측·기간 검증 관련 변경 후 권장:

```powershell
python scripts/run_regression_tests.py --group model --timeout-scale 2
```

**주요 옵션**

| 옵션 | 설명 |
|------|------|
| `--fail-fast` | 첫 실패 시 즉시 중단 |
| `--skip-airflow` | full 실행 시 Airflow 테스트 제외 |
| `--skip-frontend` | Frontend build/check 제외 |
| `--timeout-scale 2` | timeout 2배 (느린 환경) |
| `--log-dir PATH` | 로그 디렉터리 지정 |

**로그 구조:** `logs/regression/YYYYMMDD_HHMMSS/`

- `01_test_system_config.log` … 개별 테스트 stdout/stderr
- `summary.json` — 기계 판독용 요약
- `summary.md` — 사람이 읽기 쉬운 요약

**커밋 전 권장:** `python scripts/run_regression_tests.py --group quick` + 변경 영역 그룹 (예: `--group model`)

### Traefik 배포 서버 — 적용·검증

스택 반영:

```bash
cd ~/thermops
git pull
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend frontend
```

배포 후 API 검증 (호스트에서 backend `localhost:8000` 또는 `THERMOOPS_API_BASE` 설정):

```bash
export THERMOOPS_API_BASE=https://thermops.openlink.kr/api/v1   # Traefik 경유 시

python scripts/test_feature_dataset_range.py
python scripts/test_prediction_period_validation.py
python scripts/test_batch_prediction.py
python scripts/run_regression_tests.py --group model --timeout-scale 2
python scripts/run_regression_tests.py --group quick
```

**`/predictions/jobs` 화면 확인 체크리스트**

- Feature Set 선택 시 **사용 가능한 Feature Dataset 기간** 표시
- Feature Dataset 없음 → Feature 생성 안내·링크
- Dataset 있음 → **최신 24시간** 예측 기간 자동 설정
- 범위 밖 기간 → 경고·**예측 실행 버튼 비활성**
- 정상 범위 → 예측 실행 성공
- 실패 시 API `detail` 기반 한국어 메시지

### 데이터 품질 점검 테스트 (P0-2)

CSV 적재가 완료된 상태(`P0-1`)에서 품질 점검 API를 검증합니다.

```powershell
# 열수요·기상 각각 품질 점검 + 이력 조회
python scripts/test_data_quality.py

# 도메인별 수동 호출 예시
curl -X POST "http://localhost:8000/api/v1/data-quality/checks?data_domain=HEAT_DEMAND"
curl -X POST "http://localhost:8000/api/v1/data-quality/checks?data_domain=WEATHER"
curl "http://localhost:8000/api/v1/data-quality/runs?page=1&size=20"
```

품질 점검은 `tb_heat_demand_actual`, `tb_weather_observation`의 결측·중복·시간 누락·이상치·참조 정합성을 점검하고 `tb_data_quality_run`에 결과를 저장합니다.

### Feature 생성 테스트 (P0-3)

CSV 적재·품질 점검 후 Feature Dataset 생성을 검증합니다.

```powershell
python scripts/test_feature_build.py
```

Feature Set 미리보기·생성 API:

```powershell
curl -X POST "http://localhost:8000/api/v1/feature-sets/FS-TPL-LAG-ROLL/preview"
curl -X POST "http://localhost:8000/api/v1/feature-build-jobs?feature_set_id=FS-TPL-LAG-ROLL"
```

**Feature 메타데이터·명칭 정책**

- Feature 등록(`/features`)은 **카탈로그(1단계)** 이다. 등록만으로 값이 생성되거나 학습에 반영되지 않는다.
- **Registry 등록 Feature**(유형 A)만 Feature 생성 시 값이 만들어진다. **Catalog-only**(유형 B)는 경고와 함께 등록 가능하나 계산 로직 추가 전까지 사용 불가.
- **레거시 별칭**(유형 C: `hdd`, `rolling_24h_avg` 등)은 공식명으로 대체한다. 검증 API: `GET /features/validate-name`.
- `calc_expression`(계산식 메모)은 **설명용**이며 `LAG(...)`, `MA(...)` 등은 현재 **실행되지 않는다** (코드 기반 Registry만 지원).
- 학습/예측에 쓰이려면: (1) 메타 등록 → (2) `ml/features.py` + Registry → (3) Feature Set 포함 → (4) Feature 생성 → (5) 품질 검증 → (6) 학습 설정.
- 공식 Feature명: `demand_lag_24h`, `demand_lag_168h`, `demand_ma_24h`, `demand_ma_168h`, `temperature_diff_24h`, `heating_degree_days`, `cooling_degree_days`.
- 상세: [`docs/md/THERMOps_Feature_명칭_및_계산식_정책.md`](docs/md/THERMOps_Feature_명칭_및_계산식_정책.md)

**Feature Registry·Lineage UI**

- `/features`: **등록 유형** 뱃지, **신규 Feature 사용 절차** 안내, Registry 요약, **상세** 모달에서 입력 테이블·Lookback·누수 방지 등 확인
- `/feature-sets/:id`: 포함 Feature **등록 유형** 뱃지·필터·TPL 보호, **Feature Build 이력** + **Lineage** + **Feature 품질 검증**(등록 상태 컬럼)
- Lineage 없음 → Feature Set 상세에서 **Feature 생성** 먼저 실행

**Feature 품질 검증** (`check_type=FEATURE_QUALITY`)

- Feature별 **registration_status**(계산 가능/카탈로그 전용/레거시) 표시
- **Legacy alias 일괄 공식명 대체** (`POST /feature-sets/{id}/replace-legacy-features`, dry-run 후 적용)
- Build `result_summary`의 missing/catalog_only 정보를 `build_coverage`로 참조

- 대상: `tb_feature_dataset.feature_json` (원천 데이터 품질 점검과 별도)
- Feature Set 상세에서 `dataset_version_id` 기준 실행 · 이력 조회
- API: `POST/GET /api/v1/feature-quality-runs`
- 판정: 점수 90+ SUCCESS, 70~89 WARNING, 70 미만 FAILED (null·key 누락·범위·이상치 가중 감점)

```powershell
python scripts/test_feature_metadata_consistency.py
python scripts/test_feature_lineage.py
python scripts/test_feature_build_jobs.py
python scripts/test_feature_quality.py
python scripts/test_feature_registration_validation.py
python scripts/test_feature_set_legacy_replace.py
```

### 모델 학습 테스트 (P0-4-1)

Feature 생성 완료 후 모델 학습·MLflow·DB 반영을 검증합니다. MLflow 컨테이너가 기동 중이어야 합니다.

```powershell
python scripts/test_model_training.py
```

학습 실행 API:

```powershell
curl -X POST "http://localhost:8000/api/v1/training-jobs" -H "Content-Type: application/json" -d "{\"config_id\":\"TRC-TPL-LAG-ROLL\",\"register_model_yn\":true}"
```

### CatBoost / 2-Stage CatBoost 학습 (P1-4)

CatBoost 단일 모델과 2-Stage CatBoost(기본 예측 + 잔차 보정)를 학습·예측 파이프라인에 통합했습니다.

**2-Stage 구조**

- Stage 1: `CatBoostRegressor`로 `target_heat_demand` 예측
- Stage 2: train set 잔차(`actual - stage1_pred`)로 CatBoost 재학습
- 최종 예측: `final = clip(stage1 + stage2_residual, min=0)`

**학습 설정 템플릿**

| config_id | algorithm | Feature Set | 모델명 |
|-----------|-----------|-------------|--------|
| `TRC-TPL-CATBOOST` | `catboost` | `FS-TPL-LAG-ROLL` | `heat_demand_catboost` |
| `TRC-TPL-TWO-STAGE-CATBOOST` | `two_stage_catboost` | `FS-TPL-TWO-STAGE` | `heat_demand_two_stage_catboost` |

**테스트 (기존 볼륨 사용 시 먼저 `python scripts/apply_dev_migrations.py`)**

```powershell
python scripts/test_catboost_training.py
python scripts/test_two_stage_catboost.py
```

CatBoost 학습 API 예시:

```powershell
curl -X POST "http://localhost:8000/api/v1/training-jobs" -H "Content-Type: application/json" -d "{\"config_id\":\"TRC-TPL-CATBOOST\",\"register_model_yn\":true}"
curl -X POST "http://localhost:8000/api/v1/training-jobs" -H "Content-Type: application/json" -d "{\"config_id\":\"TRC-TPL-TWO-STAGE-CATBOOST\",\"register_model_yn\":true}"
```

**P1-4 제한사항**

- GPU 학습 최적화 없음 (CPU 기준)
- 하이퍼파라미터 자동 튜닝 없음
- Stage 2 잔차는 train prediction 기준 (validation OOF 미사용)
- CatBoost 미설치 환경에서 `catboost`/`two_stage_catboost` 요청 시 명시적 오류 (LightGBM처럼 sklearn fallback 없음)
- 예측값 0 미만은 `max(pred, 0)`으로 clip
- 성능 수치는 데이터·Feature 품질에 따라 달라지며 보장하지 않음

상세: `docs/md/THERMOps_P1_모델고도화_정리.md`

### 배치 예측 테스트 (P0-5)

모델 학습 완료 후 배치 예측·결과 DB 저장을 검증합니다.

```powershell
python scripts/test_batch_prediction.py
```

배치 예측 실행 API:

`model_version_id`를 명시하지 않으면 요청 `feature_set_id`와 호환되는 모델 버전 중 CHAMPION을 우선 선택하고, 없으면 최신 CANDIDATE를 사용합니다. 명시한 `model_version_id`가 다른 feature_set으로 학습된 경우 `MODEL_FEATURE_SET_MISMATCH` 오류(400)를 반환합니다.

```powershell
curl -X POST "http://localhost:8000/api/v1/prediction-jobs" -H "Content-Type: application/json" -d "{\"feature_set_id\":\"FS-TPL-LAG-ROLL\",\"model_version_id\":\"MV-heat_demand_lightgbm-1\",\"start_at\":\"2026-06-01T00:00:00\",\"end_at\":\"2026-06-20T23:00:00\"}"
```

### 시스템 설정 API 테스트 (Mock 제거 1차)

`SystemConfigPage`의 localStorage Mock을 제거하고 DB 기반 설정 API를 검증합니다.

```powershell
python scripts/test_system_config.py
```

설정 조회 API:

```powershell
curl "http://localhost:8000/api/v1/system-configs"
```

### 성능 지표 eval_type 테스트 (Mock 제거 1차 B)

학습 검증 성능과 운영 예측 성능 API 필터를 검증합니다.

```powershell
python scripts/test_performance_eval_type.py
```

### 예측 추이 API 테스트 (Mock 제거 1차 C)

대시보드·모니터링의 `prediction-trend` 차트가 **실제 매칭/예측 DB 데이터**만 사용하는지 검증합니다. 데이터가 없으면 API는 빈 배열(`data_source: EMPTY`)을 반환하며, 프론트는 가짜 차트 대신 empty state를 표시합니다.

```powershell
python scripts/test_prediction_trend.py
```

예측 추이 조회 API:

```powershell
curl "http://localhost:8000/api/v1/dashboard/prediction-trend?start_at=2026-06-01T00:00:00&end_at=2026-06-07T23:59:59"
```

### Drift 감지 및 재학습 후보 테스트 (P1-1)

예측–실적 매칭 및 Feature Dataset이 존재하는 상태에서 Drift 감지를 검증합니다.

```powershell
python scripts/test_drift_retraining.py
```

Drift 점검 API 수동 실행:

```powershell
curl -X POST "http://localhost:8000/api/v1/drift-checks" -H "Content-Type: application/json" -d "{\"model_version_id\":\"MV-heat_demand_lightgbm-1\",\"feature_set_id\":\"FS-TPL-LAG-ROLL\",\"baseline_start_at\":\"2026-05-22T00:00:00\",\"baseline_end_at\":\"2026-06-05T23:00:00\",\"current_start_at\":\"2026-06-06T00:00:00\",\"current_end_at\":\"2026-06-20T23:00:00\"}"
```

**Drift 감지 기준 (요약)**

| 유형 | 판단 |
|------|------|
| 성능 Drift | 최근 운영 MAPE ≥ `mape_warning_threshold` → WARNING, ≥ `retraining_mape_threshold` → CRITICAL |
| 예측 오차 Drift | current MAPE가 baseline 대비 1.2배 → WARNING, 1.5배 → CRITICAL |
| Feature Drift | mean/std shift + KS-test, `drift_warning_threshold` 기준 |

**재학습 후보:** WARNING/CRITICAL Drift 시 `tb_retraining_candidate`에 PENDING 후보 자동 생성. 승인 후 `POST /retraining-candidates/{id}/train`으로 재학습 실행.

**실행 모드 (P1-2 안정화):**

| mode | 설명 |
|------|------|
| `AIRFLOW` (기본) | `retraining_dag` 비동기 트리거. 즉시 `TRAINING` 반환 후 DAG 완료 시 `TRAINED`/`FAILED` |
| `SYNC` | 기존 동기 API. 요청이 끝날 때까지 학습 완료 대기 (`?execution_mode=SYNC`) |

**후보 상태 흐름:**

```
PENDING → APPROVED → TRAINING → TRAINED
PENDING → REJECTED
TRAINING → FAILED
```

- SEED / MANUAL 후보는 재학습 실행 불가 (`400`)
- 운영 기본 흐름은 **AIRFLOW 비동기** (`retraining_dag`)
- 재학습으로 생성된 모델은 Model Registry(`/models`)에서 확인
- 내부 API: `POST /retraining-candidates/{id}/train-sync-internal` (Airflow DAG 전용, service token TODO)

```powershell
# 1) COMPUTED + PENDING 후보 ID 확인
curl "http://localhost:8000/api/v1/retraining-candidates?computed_only=true&status=PENDING"

# 2) 승인 후 Airflow 비동기 재학습 (기본)
curl -X POST "http://localhost:8000/api/v1/retraining-candidates/RTC-20260629-42F5/approve"
curl -X POST "http://localhost:8000/api/v1/retraining-candidates/RTC-20260629-42F5/train"
# 또는 명시: ?execution_mode=AIRFLOW

# 3) 동기 재학습 (테스트/디버그)
curl -X POST "http://localhost:8000/api/v1/retraining-candidates/RTC-20260629-42F5/train?execution_mode=SYNC"

python scripts/test_retraining_candidate_train.py
python scripts/test_retraining_airflow.py
```

**source_type 구분 (P1-1 안정화)**

| source_type | 의미 |
|-------------|------|
| `COMPUTED` | `POST /drift-checks` 또는 Drift 파이프라인으로 **실제 계산**된 리포트/후보 |
| `SEED` | `db/init/02_seed.sql` 시드·시연용 샘플 데이터 |
| `MANUAL` | 향후 수동 등록 후보 (예약) |

화면 기본 조회는 `computed_only=true` (계산 결과만). 시드 데이터는 운영 Drift 결과가 아닙니다.

```powershell
# 계산된 Drift 리포트만
curl "http://localhost:8000/api/v1/drift-reports?computed_only=true"

# 자동 산출 재학습 후보만
curl "http://localhost:8000/api/v1/retraining-candidates?computed_only=true"
```

대시보드 `retraining_candidate_count`는 **COMPUTED + PENDING/REVIEW** 후보만 집계합니다.

기존 DB 볼륨 사용 시 P1-1 컬럼 반영:

```powershell
python scripts/apply_dev_migrations.py
```

### DB/API 데이터소스 Connector (P1-3)

CSV 외에 **PostgreSQL(`DB_POSTGRES`)** 및 **REST JSON API(`REST_API`)** 데이터소스를 등록·연결 테스트·스키마 탐색·미리보기·적재할 수 있습니다. 기존 CSV 적재(`FILE_CSV`/`CSV`)는 그대로 동작합니다.

**지원 source_type**

| source_type | 설명 |
|-------------|------|
| `CSV` / `FILE_CSV` | 로컬 CSV 파일 |
| `DB_POSTGRES` | PostgreSQL 테이블 또는 SELECT 쿼리 |
| `REST_API` | REST JSON GET API |

**Connector 공통 흐름:** 연결 테스트 → 스키마 탐색 → 매핑 → 미리보기 → `POST /ingestion-jobs`

**PostgreSQL connection_info 예시** (backend 컨테이너 기준 `host=postgres`):

```json
{
  "host": "postgres",
  "port": 5432,
  "database": "thermops",
  "schema": "public",
  "table": "external_heat_demand_sample",
  "username": "thermops",
  "password": "thermops",
  "query": null,
  "timestamp_column": "measured_at"
}
```

**REST API connection_info 예시** (개발용 sample endpoint, `item_path`는 API 응답 래퍼 `data.items`):

```json
{
  "base_url": "http://127.0.0.1:8000/api/v1",
  "endpoint": "/sample-external/heat-demand",
  "method": "GET",
  "query_params": { "start_at": "{start_at}", "end_at": "{end_at}" },
  "auth_type": "NONE",
  "item_path": "data.items"
}
```

**개발용 테스트 리소스 (운영 기능 아님)**

- DB: `external_heat_demand_sample`, `external_weather_sample` (`apply_dev_migrations.py`로 생성)
- API: `GET /api/v1/sample-external/heat-demand`, `/sample-external/weather`

**API**

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/data-sources/{id}/test-connection` | 연결 테스트 |
| GET | `/data-sources/{id}/discover-schema` | 컬럼/JSON 필드 탐색 |
| POST | `/data-sources/{id}/preview` | 원천 데이터 미리보기 |
| POST | `/ingestion-jobs?source_id=...&start_at=...&end_at=...&limit=...&load_mode=...&mapping_id=...` | 적재 실행 |

**Ingestion 쿼리 파라미터**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `source_id` | 데이터 소스 ID | 필수 |
| `mapping_id` | 매핑 ID (미지정 시 활성 매핑) | optional |
| `data_domain` | 소스 도메인 일치 검증 | optional |
| `start_at` / `end_at` | 기간 필터 (DB: timestamp_column, API: query_params template) | optional |
| `limit` | 최대 fetch 행 수 | optional (미지정 시 전체) |
| `load_mode` | `UPSERT` 또는 `INSERT_ONLY` | `UPSERT` |

**적재 결과 summary**

| 필드 | 의미 |
|------|------|
| `inserted_count` | 신규 key 적재 건수 |
| `updated_count` | 기존 key upsert 갱신 건수 |
| `failed_count` | 매핑/파싱 실패 건수 |
| `skipped_count` | 파일 내 중복·INSERT_ONLY 스킵 건수 |
| `total_success_count` | inserted + updated |

**Connector error_code (요약)**

`CONNECTOR_NOT_FOUND`, `CONNECTION_FAILED`, `INVALID_CONNECTION_INFO`, `UNSAFE_QUERY`, `SCHEMA_DISCOVERY_FAILED`, `PREVIEW_FAILED`, `INGESTION_FAILED`, `API_REQUEST_FAILED`, `API_RESPONSE_PARSE_FAILED`, `MAPPING_VALIDATION_FAILED`

### P1-3 Connector 안정화

- UI: 데이터 소스 **적재 실행** modal에서 `start_at`/`end_at`/`limit`/`load_mode` 지정
- `inserted_count` / `updated_count` 분리 집계 (upsert 전 기존 key 조회)
- Connector 오류 `error_code` + 사용자 메시지 표준화, credential 응답 마스킹
- Airflow `data_ingestion_dag` conf에 `limit`, `load_mode`, `mapping_id` 전달 지원

**Airflow `data_ingestion_dag` conf 예시** (DB/API source_id 사용):

```json
{
  "source_id": "DS-XXXXXXXX",
  "data_domain": "HEAT_DEMAND",
  "start_at": "2026-05-22T00:00:00",
  "end_at": "2026-05-23T23:00:00",
  "limit": 1000,
  "load_mode": "UPSERT"
}
```

**테스트**

```powershell
python scripts/apply_dev_migrations.py   # external_* 샘플 테이블
python scripts/test_db_connector.py
python scripts/test_api_connector.py
python scripts/test_connector_error_handling.py
```

**보안·제한 (TODO)**

- `connection_info`에 credential이 평문 저장될 수 있음 → 운영 시 secret manager/암호화 필요
- DB `query`는 **SELECT만** 허용
- REST API: OAuth/BASIC 미지원, 복잡한 pagination 미지원
- SCADA/PI, Kafka/MQTT, 대용량 incremental loading은 후속 과제

### Airflow DAG 연동 테스트 (P0-7)

파이프라인 수동 실행 시 **Backend → Airflow REST trigger → DAG → Backend API** 흐름을 검증합니다.

**Airflow UI:** http://localhost:8080 (admin / admin)

기동 직후 DAG 목록 반영까지 **30~60초** 걸릴 수 있습니다. DAG가 보이지 않으면:

```powershell
docker compose restart airflow
docker compose logs airflow --tail 50
```

파이프라인 수동 실행 (API):

```powershell
curl -X POST "http://localhost:8000/api/v1/pipelines/data_quality_dag/trigger" -H "Content-Type: application/json" -d "{\"business_date\":\"2026-06-20\"}"
```

통합 테스트 (짧은 DAG `data_quality_dag` 권장):

```powershell
python scripts/test_airflow_pipeline.py
```

전체 파이프라인 E2E (`thermops_full_pipeline_dag`, **5~20분** 소요 가능):

```powershell
python scripts/test_full_pipeline_airflow.py
```

환경 변수로 polling timeout 조정: `FULL_PIPELINE_POLL_TIMEOUT=1200` (초)

### CSV 적재 테스트 (P0-1)

```powershell
python scripts/test_csv_ingestion.py
```

## 인증/권한 (1차 범위 — Mock)

**1차 구현 범위에서는 로그인, 인증, SSO, JWT, 세션, 사용자 관리 기능을 구현하지 않습니다.**

현재 프론트엔드의 권한 처리는 **실제 보안 인증이 아니라**, Figma/화면 설계서에 정의된 **버튼 노출·Disabled·권한 없음 Modal** 등 UI 권한 표현을 확인하기 위한 **Mock** 입니다. 백엔드 API는 인증·권한 검증 없이 호출 가능합니다.

| 구분 | 1차 범위 | 사업 적용 시 (추후) |
|------|----------|-------------------|
| 로그인 화면 | 없음 | 발주기관 SSO/포털 연계 |
| API 인증 | 없음 | JWT / API Gateway / Bearer Token |
| 사용자·역할 관리 | 없음 | IAM, 메뉴·기능 권한 매트릭스 |
| 프론트 권한 | `VITE_USER_ROLE` Mock | Auth Provider, 토큰 클레임 기반 |

설계서(`docs/md/THERMOps_API_설계서.md`)에는 Bearer Token 구조가 정의되어 있으나, **코드에는 미연동** 상태입니다.

### Mock 권한값 (`VITE_USER_ROLE`)

`frontend/src/hooks/useRole.ts` 가 읽는 **개발·시연·화면 검증용** 환경 변수입니다. 값을 바꿔도 서버 권한이 바뀌지 않으며, **UI 상태만** 바뀝니다.

| Mock 값 | 저장/실행 | 삭제 | 파이프라인 수동 실행 |
|---------|-----------|------|---------------------|
| `ADMIN` | 가능 | 가능 | 가능 |
| `OPERATOR` | 가능 | 불가 | 가능 |
| `VIEWER` | 불가 (Disabled + 권한 Modal) | 불가 | 불가 |

**Docker Compose (권장):** `docker-compose.yml` frontend 서비스 기본값은 `ADMIN` (`${VITE_USER_ROLE:-ADMIN}`). `.env`에서 변경할 수 있습니다.

```env
# .env — Mock 권한 (실제 인증 아님)
VITE_USER_ROLE=ADMIN
```

변경 후 프론트엔드 컨테이너를 재기동합니다.

```powershell
docker compose up -d --build frontend
```

### ADMIN / VIEWER UI 상태 확인 방법

| 확인 항목 | ADMIN | VIEWER |
|-----------|-------|--------|
| 설정 | `.env` → `VITE_USER_ROLE=ADMIN` 후 frontend 재기동 | `.env` → `VITE_USER_ROLE=VIEWER` 후 frontend 재기동 |
| 헤더 표시 | 권한 라벨 `(ADMIN)` | 권한 라벨 `(VIEWER)` |
| Feature Set 관리 | `신규 Feature Set` 버튼 **활성** | 버튼 **비활성**, 클릭 시 **권한 없음 Modal** |
| 파이프라인 실행 이력 | `수동 실행` 버튼 **활성** | 클릭 시 **권한 없음 Modal** |

코드 기본값(`useRole.ts`)은 Mock 미설정 시 **VIEWER** 입니다. Docker 없이 `npm run dev`만 사용할 때는 프로젝트 루트 `.env` 또는 `frontend/.env.local`에 `VITE_USER_ROLE=ADMIN`을 설정하세요.

### 자주 발생하는 오류와 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| 모든 화면에서 "데이터를 불러오지 못했습니다" | backend 또는 postgres 미기동 | `docker compose ps` 로 상태 확인 후 `docker compose up -d postgres backend` |
| `port is already allocated` (5432, 8000 등) | 포트 충돌 | 해당 포트를 사용 중인 프로세스 종료 또는 `docker-compose.yml` 의 `ports` 매핑 변경 |
| MLflow 컨테이너 `Exited (1)` | PostgreSQL 백엔드용 `psycopg2` 미포함 | `docker compose up -d --build mlflow` 재기동 (이미지 entrypoint에서 자동 설치) |
| Airflow `Exited (1)` — db init 오류 | `thermops_airflow` DB 마이그레이션 실패 | `docker compose up -d --build airflow` 재시도. 지속 시 `docker compose down -v` 후 재기동(DB 초기화) |
| Airflow UI 접속 불가 (연결 거부) | 웹서버 기동 대기 중 | 1분 정도 대기 후 `http://localhost:8080` 재접속 |
| 프론트 변경이 반영되지 않음 | Vite env는 빌드/기동 시점에 주입 | `docker compose up -d --build frontend` |
| pipeline_run result_summary 오류 | 기존 DB 볼륨에 컬럼 없음 | `python scripts/apply_dev_migrations.py` |
| `thermops_airflow` DB 없음 | postgres 볼륨이 init 스크립트 이전에 생성됨 | `docker compose down -v` 후 `docker compose up -d --build` |

```powershell
# 전체 재시작 (코드 변경 반영)
docker compose up -d --build

# 로그 확인
docker compose logs -f backend
docker compose logs -f airflow

# 전체 중지
docker compose down

# DB 포함 초기화 (스키마/시드 재적용)
docker compose down -v
docker compose up -d --build
```

### 서비스 접속 URL

| 서비스 | URL | 비고 |
|--------|-----|------|
| **Frontend** | http://localhost:5173 | 관리 UI |
| **Backend API** | http://localhost:8000 | REST API |
| **API 문서 (Swagger)** | http://localhost:8000/docs | OpenAPI |
| **Airflow** | http://localhost:8080 | admin / admin |
| **MLflow** | http://localhost:5000 | 실험/모델 추적 |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **PostgreSQL** | localhost:5432 | thermops / thermops |

## 로컬 개발 (Docker 없이)

### 1. PostgreSQL

```bash
# Docker로 DB만 실행
docker compose up -d postgres

# 또는 scripts/init_db.sh 로 스키마/시드 적용
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 접속

## API 확인 방법

```bash
# 헬스체크
curl http://localhost:8000/health

# 대시보드 요약
curl http://localhost:8000/api/v1/dashboard/overview

# 지사 목록
curl http://localhost:8000/api/v1/sites

# 데이터 소스 목록
curl http://localhost:8000/api/v1/data-sources
```

Swagger UI: http://localhost:8000/docs

## 주요 화면 (MLOps 운영 흐름)

1. **대시보드** — 예측 현황, 오차 추이, 모델 상태
2. **데이터 관리** — 소스 등록, 매핑 설정, 품질 점검
3. **Feature 관리** — Feature 목록, Feature Set 구성
4. **모델 관리** — 학습 설정/실행, 성능 비교, Registry (Champion 지정)
5. **예측 관리** — 배치 예측 실행, 결과 조회, 오차 분석
6. **운영 관리** — 파이프라인 이력, 성능 모니터링, 드리프트, 재학습 후보

## Airflow DAG 목록

| DAG ID | 설명 |
|--------|------|
| `data_ingestion_dag` | 열수요/기상 데이터 적재 |
| `data_quality_dag` | 데이터 품질 점검 |
| `feature_build_dag` | Feature 생성 |
| `model_training_dag` | Baseline/ML 모델 학습 |
| `batch_prediction_dag` | 배치 예측 |
| `monitoring_dag` | 예측-실적 매칭 및 성능 평가 |
| `drift_detection_dag` | Drift 감지 및 재학습 후보 자동 생성 (P1-1) |
| `thermops_full_pipeline_dag` | 전체 MLOps 파이프라인 |

Airflow UI에서 DAG를 활성화( unpause )한 뒤 수동 실행하거나 스케줄에 따라 자동 실행됩니다.

## MLflow

학습 파이프라인 실행 시 MLflow에 실험 파라미터, 지표(MAE, RMSE, MAPE), 모델 아티팩트가 기록됩니다.

- Tracking URI: `http://localhost:5000`
- Artifact Storage: MinIO (`s3://mlflow/`)

## 샘플 데이터

`db/init/02_seed.sql`에 다음이 포함됩니다:

- 지사 5개 (중앙, 강남, 분당, 고양, 대전)
- 시간별 열수요/기상 샘플
- Feature, Feature Set, 학습 설정
- 모델 버전 (Champion: heat_demand_lgbm v12)
- 예측 결과, 성능 지표, 드리프트 리포트
- 파이프라인 실행 이력, 재학습 후보

## 설계 문서 참조

- `docs/md/THERMOps_API_설계서.md`
- `docs/md/THERMOps_DB_설계서.md`
- `docs/md/THERMOps_배치_파이프라인_설계서.md`
- `docs/md/THERMOps_화면_설계서.md`
- `docs/md/THERMOps_P1_모델고도화_정리.md`
- `design/figma/THERMOps_Figma_UI_Master_Spec.md`

## 1차 구현 범위 및 제한사항

- 실제 원천 시스템 연계 대신 **시드 DB + Mock API 응답** 기반으로 전체 화면·운영 흐름 시연
- ML 모델: Baseline, LightGBM, sklearn GBDT fallback, **CatBoost**, **2-Stage CatBoost** (완전한 성능 튜닝·GPU 최적화 미포함)
- **인증/권한:** 로그인·SSO·JWT·세션·사용자 관리 **미구현**. `VITE_USER_ROLE`은 UI Mock 권한만 제공 (상세: [인증/권한 (1차 범위 — Mock)](#인증권한-1차-범위--mock)). 실제 사업 적용 시 발주기관 SSO/JWT/기관 인증체계 연계 필요
- 수주 후 발주기관 환경에 맞춰 데이터 매핑, DAG 스케줄, DBMS 전환 보정 필요

## 라이선스

사전 구축형 솔루션 설계 산출물 기준 — 내부 프로젝트용
