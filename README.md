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

**초기 DB seed (운영):** `docker compose up` 시 `02_seed_clean.sql`만 적용됩니다. **공통코드·시스템 설정만** 포함되며, 데이터 소스·매핑·표준 데이터셋·Feature Set·모델·Pipeline Definition 등은 **비어 있는 상태**로 시작합니다. UI에서 직접 등록하세요. 회귀 테스트는 `scripts/test_fixtures.py`가 런타임에 `scripts/fixtures/test_platform_seed.sql`을 적용합니다.

**완전 초기화 (clean reset, DB volume 삭제):** 환경에 따라 아래 중 하나를 사용합니다. 상세는 [Docker 완전 초기화](#docker-완전-초기화-clean-reset) 참고.

| 환경 | 명령 |
|------|------|
| **로컬 개발** (`docker-compose.yml`) | `docker compose down -v` 후 `docker compose up -d --build` |
| **서버 Traefik 배포** | `docker compose -f docker-compose.traefik.yml --env-file .env.deploy down -v` 후 `docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build` |

**데모/test seed 없음:** `02_seed_demo.sql`은 제거되었습니다. `data/samples/` CSV는 테스트 fixture용 파일이며 DB init에 사용되지 않습니다.

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
| P0-1 CSV 적재 | `python scripts/test_csv_ingestion.py` | 테스트용 CSV 소스 등록 후 열수요·기상 적재 |
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

Full Pipeline API 수동 실행 (`source_id`·`weather_source_id`는 UI에서 등록한 데이터 소스 ID로 교체):

```powershell
curl -X POST "http://localhost:8000/api/v1/pipelines/thermops_full_pipeline_dag/trigger" ^
  -H "Content-Type: application/json" ^
  -d "{\"business_date\":\"2026-06-20\",\"parameters\":{\"source_id\":\"<HEAT_SOURCE_ID>\",\"weather_source_id\":\"<WEATHER_SOURCE_ID>\",\"feature_set_id\":\"<feature_set_id>\",\"config_id\":\"<training_config_id>\",\"model_name\":\"heat_demand_lightgbm\"}}"
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

스택 반영 (코드만 갱신, DB volume 유지):

```bash
cd ~/thermops
git pull
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend frontend
python3 scripts/apply_dev_migrations.py   # 기존 DB volume 유지 시 필수 (스키마 보완)
```

**기존 volume을 유지한 채 `git pull`만 한 경우** 백엔드 코드는 갱신되어도 Postgres init 스크립트는 재실행되지 않습니다. R9-S2-1 이후 표준 데이터셋 API 등이 `500 Internal Server Error`로 실패하면 위 마이그레이션을 실행하세요.

**완전 초기화가 필요할 때** (PoC 잔여 데이터·clean seed 재적용·volume 초기화):

```bash
# 서버 (Traefik 배포)
docker compose -f docker-compose.traefik.yml --env-file .env.deploy down -v
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build

# 로컬 개발 (참고)
# docker compose down -v
# docker compose up -d --build
```

상세: [Docker 완전 초기화](#docker-완전-초기화-clean-reset) · `docs/md/THERMOps_Traefik_배포_가이드.md` §6

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
curl -X POST "http://localhost:8000/api/v1/feature-sets/<feature_set_id>/preview"
curl -X POST "http://localhost:8000/api/v1/feature-build-jobs?feature_set_id=<feature_set_id>"
```

**Feature 메타데이터·명칭 정책**

- Feature 등록(`/features`)은 **카탈로그(1단계)** 이다. 등록만으로 값이 생성되거나 학습에 반영되지 않는다.
- **Registry 등록 Feature**(유형 A)만 Feature 생성 시 값이 만들어진다. **Catalog-only**(유형 B)는 경고와 함께 등록 가능하나 계산 로직 추가 전까지 사용 불가.
- **레거시 별칭**(유형 C: `hdd`, `rolling_24h_avg` 등)은 공식명으로 대체한다. 검증 API: `GET /features/validate-name`.
- `calc_expression`(계산식 메모)은 **설명용**이며 `LAG(...)`, `MA(...)` 등은 현재 **실행되지 않는다** (코드 기반 Registry만 지원).
- 학습/예측에 쓰이려면: (1) 메타 등록 → (2) `ml/features.py` + Registry → (3) Feature Set 포함 → (4) Feature 생성 → (5) 품질 검증 → (6) 학습 설정.
- 공식 Feature명: `demand_lag_24h`, `demand_lag_168h`, `demand_ma_24h`, `demand_ma_168h`, `temperature_diff_24h`, `heating_degree_days`, `cooling_degree_days`.
- 상세: [`docs/md/THERMOps_Feature_명칭_및_계산식_정책.md`](docs/md/THERMOps_Feature_명칭_및_계산식_정책.md)
- **향후**: 범용 Feature Recipe Builder 1차 설계 — [`docs/md/THERMOps_Feature_Recipe_Builder_1차_설계.md`](docs/md/THERMOps_Feature_Recipe_Builder_1차_설계.md) (현재는 CODE Registry + Catalog/Quality/Lineage; DSL 자동 실행 미지원)
- **R1 Column Role**: `/data/mappings`에서 컬럼 역할 지정 — [`docs/md/THERMOps_Feature_Recipe_Builder_1차_설계.md`](docs/md/THERMOps_Feature_Recipe_Builder_1차_설계.md) 부록 C
- **R2 Recipe Template Catalog**: 템플릿 목록·validate API — 동일 설계서 부록 D
- **R3 Recipe Preview**: RAW_COLUMN·DATE_PART 샘플 Preview — 동일 설계서 부록 E
- **R4 Recipe Preview**: LAG·ROLLING_MEAN·ROLLING_SUM row step 기반 Preview — 동일 설계서 부록 F (저장·Build 미연동)
- **R5 Recipe 저장·Builder**: `tb_feature_recipe` 저장·발행·Feature Set 연동 — 동일 설계서 부록 G
- **R6 Recipe Engine Build**: PUBLISHED TEMPLATE Recipe를 Feature Build에 연결 — 설계서 부록 H (`RAW_COLUMN`/`DATE_PART`/`LAG`/`ROLLING_*` 지원)
- **R6-S1 Build 안정화**: Build 진단·Recipe별 이력·Preview/Build 비교·운영 UI 보강 — 설계서 부록 I (신규 Recipe Type 없음)
- **R6-S2 운영 UI 마감**: Recipe 목록 Build 상태·Builder Preview/Build 비교 UI — 설계서 부록 J
- **R7 표준 데이터셋 Builder**: 표준 대상 테이블 allowlist·학습 데이터셋 유형 관리·매핑 드롭다운 전환 — 설계서 부록 K (`/standard-datasets`, `/data/mappings`)
- **R8 Pipeline Builder**: Pipeline Template Flow Chart·노드 설정·실행 파라미터 저장·Runtime Preview — 설계서 부록 L (`/pipeline-builder`)
- **R9 Pipeline 실행 연계**: Pipeline Definition 기반 Airflow trigger·Run Link·이력 metadata — 설계서 부록 M. DAG 동적 생성·스케줄 등록은 후속
- **R9-S1 model regression 복구**: 부분 Feature Build가 최신 dataset_version으로 선택되며 학습/예측 HTTP 400이 발생하던 문제 수정 (`record_count` 최대 버전 우선, R9-S2에서 운영 정책으로 구조화). model regression **27/27 PASS** (2026-07-03)

**Pipeline Builder (R8/R9)**

- `/pipeline-builder`: Template 기반 Pipeline Definition 목록·생성·Flow Chart·노드 설정
- 검증(DRAFT/VALIDATED/ACTIVE), Runtime Preview, **R9: 실행(dry-run/실제 trigger)**
- `/ops/pipeline-runs`: DAG 수동 실행 유지 + Pipeline Definition 실행 이력 metadata 표시
- DB: `tb_pipeline_template`, `tb_pipeline_definition`, `tb_pipeline_definition_version`, `tb_pipeline_run_link` (R9)
- API: `/pipeline-definitions/.../run`, `/pipeline-run-links`, 기존 `/pipelines/{id}/trigger` 유지
- 테스트: `scripts/test_pipeline_builder.py`, `scripts/test_pipeline_execution.py`

**표준 데이터셋·매핑 (R7)**

- `/standard-datasets`: 학습 데이터셋 유형·표준 컬럼·Recipe/Build 연결 가능성 관리 (DRAFT/ACTIVE/PLANNED, 물리 테이블 자동 생성 없음)
- `/data/mappings`: 대상 테이블 **자유 입력 제거** → 표준 대상 테이블 선택 + Backend allowlist 검증
- API: `GET /standard-target-tables`, `POST /standard-dataset-types/validate-target-table`, mapping create/update 시 `INVALID_TARGET_TABLE` 검증


- `/features`: **등록 유형** 뱃지, **신규 Feature 사용 절차** 안내, Registry 요약, **상세** 모달에서 입력 테이블·Lookback·누수 방지 등 확인
- `/feature-sets/:id`: 포함 Feature **등록 유형** 뱃지·필터·TPL 보호, **Feature Build 이력** + **Recipe Engine Build 상세** + **Lineage** + **Feature 품질 검증**(TEMPLATE coverage·등록 상태)
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
curl -X POST "http://localhost:8000/api/v1/training-jobs" -H "Content-Type: application/json" -d "{\"config_id\":\"<training_config_id>\",\"register_model_yn\":true}"
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
| `TRC-TPL-CATBOOST` | `catboost` | `<feature_set_id>` | `heat_demand_catboost` |
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
curl -X POST "http://localhost:8000/api/v1/prediction-jobs" -H "Content-Type: application/json" -d "{\"feature_set_id\":\"<feature_set_id>\",\"model_version_id\":\"MV-heat_demand_lightgbm-1\",\"start_at\":\"2026-06-01T00:00:00\",\"end_at\":\"2026-06-20T23:00:00\"}"
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
curl -X POST "http://localhost:8000/api/v1/drift-checks" -H "Content-Type: application/json" -d "{\"model_version_id\":\"MV-heat_demand_lightgbm-1\",\"feature_set_id\":\"<feature_set_id>\",\"baseline_start_at\":\"2026-05-22T00:00:00\",\"baseline_end_at\":\"2026-06-05T23:00:00\",\"current_start_at\":\"2026-06-06T00:00:00\",\"current_end_at\":\"2026-06-20T23:00:00\"}"
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
| `SEED` | (레거시) 시연용 샘플 — **운영 seed에 미포함**, 자동 적용 없음 |
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
| 표준 데이터셋 목록 로드 실패 (서버만) | R9-S2-1 마이그레이션 미적용 → API 500 | Traefik 서버에서 `python3 scripts/apply_dev_migrations.py` 후 `/api/v1/standard-dataset-types` 재확인 |
| `thermops_airflow` DB 없음 | postgres 볼륨이 init 스크립트 이전에 생성됨 | [Docker 완전 초기화](#docker-완전-초기화-clean-reset) (로컬 또는 Traefik) |

### Docker 완전 초기화 (clean reset)

DB volume을 삭제하고 `02_seed_clean.sql`만 다시 적용합니다. **운영/테스트에서 쌓인 데이터가 모두 사라집니다.**

**로컬 개발** (`docker-compose.yml`, 포트 5173/8000 등):

```bash
docker compose down -v
docker compose up -d --build
python scripts/apply_dev_migrations.py   # 기존 볼륨 마이그레이션 패턴과 동일
```

**서버 Traefik 배포** (`docker-compose.traefik.yml`, `.env.deploy` 필수):

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy down -v
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build
python scripts/apply_dev_migrations.py   # 호스트에서 DB 접근 가능 시
```

검증 예 (표준 데이터셋·데이터소스 0건):

```bash
docker compose exec postgres psql -U thermops -d thermops -c \
  "SELECT 'tb_standard_dataset_type' t, COUNT(*) FROM tb_standard_dataset_type UNION ALL SELECT 'tb_data_source', COUNT(*) FROM tb_data_source;"
```

Traefik 스택에서는 `docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec postgres ...` 형태로 동일하게 실행합니다.

```powershell
# 일상 재시작 (volume 유지, 코드만 반영)
docker compose up -d --build

# 로그 확인
docker compose logs -f backend
docker compose logs -f airflow

# 전체 중지 (volume 유지)
docker compose down
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

## 초기 seed 데이터 (운영)

`db/init/02_seed_clean.sql`에 다음만 포함됩니다 (Docker 첫 기동 시 자동 적용):

- 공통코드 (`SOURCE_TYPE`, `MODEL_STAGE`, `RUN_STATUS` 등)
- 시스템 설정 (MAPE/Drift 임계치, `system_version` 등)

**포함되지 않음:** 지사·기상권역, 표준 데이터셋, Pipeline Template, Feature·Feature Set, 학습 설정, 데이터 소스·매핑, 적재 데이터, 모델·예측·Drift 결과. 모두 UI/API에서 등록합니다.

`data/samples/` CSV는 **테스트 fixture**(`scripts/test_fixtures.py`) 전용이며 DB init에 사용되지 않습니다.

### R9-S2-1 표준 데이터셋 물리 테이블 Wizard

clean 설치 후 **표준 데이터셋 0건**으로 시작합니다. UI **표준 데이터셋** 메뉴에서 Wizard로:

1. 논리 데이터셋 기본 정보·`std_` 물리 테이블명 정의
2. 표준 컬럼(타입·PK·Role) 정의
3. Backend 검증 → SQL Preview(읽기 전용) → 물리 테이블 생성

**보안 정책:** 사용자가 SQL을 직접 입력·수정해 실행하지 않습니다. `CREATE TABLE`만 metadata 기반으로 생성하며 `DROP`/`ALTER`/삭제는 지원하지 않습니다. Data Mapping 대상 테이블은 **ACTIVE + 물리 테이블 존재**한 Wizard 생성 테이블(`std_*`)입니다.

**후속 Phase:** R9-S2 Dataset Version 정책 · R10 Generic REST API Connector · 외부 코드 매핑 · 데이터 적재 스케줄러

**clean 설치 검증 시:** [Docker 완전 초기화](#docker-완전-초기화-clean-reset) 후 `/standard-datasets`·`/data/mappings` 빈 화면 확인 (`frontend/scripts/check-pages.mjs`).

### R9-S2-2 Dataset Metadata 분류 체계

R9-S2-2부터 표준 데이터셋의 업무 도메인은 **시스템 고정값이 아니라** 사용자가 선택적으로 입력하는 메타데이터(`business_domain`)로 관리합니다.

| 필드 | 의미 | 필수 |
|------|------|------|
| `dataset_category` | 데이터 구조/성격 (MASTER, FACT, TIMESERIES, …) | 권장 (기본 CUSTOM) |
| `business_domain` | 업무 영역 (예: 품질, 고객, 설비 — **사용자 입력**) | 선택 |
| `tags` | 검색·보조 분류 태그 배열 | 선택 |

- clean 설치 시 업무 도메인 seed **0건** — 필터는 `전체 업무 영역`만 표시
- `열수요`, `기상`, `설비`, `기준정보`는 **예시일 뿐** UI/운영 seed 기본값이 아님
- API: `GET /standard-datasets/metadata-options` (categories=시스템 allowlist, domains/tags=등록 데이터 distinct)

**후속 Phase:** R9-S2 Dataset Version 정책 · R10 Generic REST API Connector

### R9-S2-3 사용자 친화 용어·메뉴·안내문구

R9-S2-3에서는 **내부 개발 용어(API path, DB 컬럼, enum)는 유지**하면서 사용자 화면의 메뉴명·페이지 제목·버튼·빈 화면 안내·도움말을 **일반 운영자가 이해하기 쉬운 한글 업무 용어**로 정리했습니다.

- 공통 표시 문구: `frontend/src/constants/displayLabels.ts` (`PAGE_TITLES`, `MENU_GROUPS`, `EMPTY_MESSAGES`, `HELP_TEXTS` 등)
- 메뉴 그룹: 데이터 준비 → 학습 변수 관리 → 모델 학습·예측 → 운영 모니터링 → 시스템 관리
- URL route·API·DB 식별자는 변경하지 않음

| 내부 용어 | 화면 표시 예 |
|-----------|-------------|
| Feature | 학습 변수 |
| Feature Set | 변수 구성 |
| Feature Recipe | 변수 생성 규칙 |
| Dataset Version | 학습 데이터 버전 |
| Pipeline / Pipeline Run | 작업 흐름 / 작업 실행 이력 |
| Drift | 데이터 변화 감지·리포트 |
| Model Registry | 모델 등록 목록 |
| Target Table | 적재 대상 테이블 |
| Physical Table | 내부 테이블 |

**clean 설치 후 권장 흐름:** 표준 데이터셋(내부 테이블 생성) → 데이터 소스 등록 → 데이터 매핑 → 데이터 품질 점검 → 변수 구성·변수 생성 규칙 → 모델 학습 → 예측 실행 → 작업 흐름·실행 이력 모니터링

### R9-S2-3A 데이터 준비 메뉴 순서 정렬

데이터 준비 Sidebar 순서를 **표준 데이터셋 → 데이터 소스 → 데이터 매핑 → 데이터 품질**로 정렬했습니다. 적재 대상(내부 구조)을 먼저 정의한 뒤 원천 소스·매핑을 연결하는 업무 흐름에 맞춥니다.

**후속 Phase:** R10 Generic REST API Connector Builder · R10-S1 Prediction Entity/Location/Weather Mapping · R10-S5 Forecast On-demand Input Provider · R14 System Settings / Tenant Branding

### R9-S2 Dataset Version(학습 데이터 버전) 운영 정책

R9-S2에서는 Feature Build 결과로 생성되는 **학습 데이터 버전**에 역할·상태·생성 범위를 부여하고, 학습/예측 시 자동 선택 정책을 운영합니다.

- **역할(`dataset_version_role`)**: `PRIMARY`(대표), `CANDIDATE`(후보), `PARTIAL`(일부 생성), `TEMPORARY`(임시), `ARCHIVED`(보관)
- **상태(`dataset_version_status`)**: `BUILD_SUCCESS`, `BUILD_WARNING`, `BUILD_FAILED`, `PARTIAL`, `TRAINING_READY`, `SERVING_READY`, `ARCHIVED`
- **생성 범위(`build_scope`)**: `FULL`, `PARTIAL`, `PREVIEW`, `UNKNOWN`
- **자동 선택 순서**: 명시 `dataset_version_id` → `PRIMARY` + 학습/예측 가능 상태 → `CANDIDATE` 품질 최우선 → (후보 없을 때만) `record_count DESC` fallback. `PARTIAL`/`TEMPORARY`/`ARCHIVED`/`BUILD_FAILED`는 자동 선택에서 제외.
- **R9-S1 회귀 방지**: 최신 `created_at`의 소량 partial build가 전체 full build보다 우선 선택되던 문제를 구조적으로 방지. R9-S1 임시 복구(`record_count DESC`)는 명시적 운영 정책 후보가 없을 때만 fallback으로 유지.
- **API**: `GET /dataset-versions`, `POST .../set-primary`, `POST .../archive`, `POST .../selection-preview`, `POST .../cleanup-preview`
- **화면**: `/dataset-versions` — 목록·대표 지정·보관·선택 정책 미리보기 (표시명 **학습 데이터 버전**)
- **운영 seed**: Dataset Version 샘플 추가 없음 (clean 설치 0건 유지). 테스트는 runtime fixture만 사용.
- **검증**: `scripts/test_dataset_version_policy.py`, model regression 그룹 등록

**후속 Phase:** R10-S1 Prediction Entity/Location/Weather Mapping · R10-S2 외부 코드 매핑 · R10-S3 실제 열수요 API wide-hour 변환 · R10-S4 ASOS/Calendar · R10-S5 Forecast On-demand Input Provider · R10-S6 데이터 적재 스케줄러

### R10 Generic REST API Connector Builder

R10에서는 외부 REST API를 **데이터 소스 + API 작업(Operation)** 단위로 등록하고, 요청 파라미터·인증·페이징·응답 데이터 경로·적재 대상을 설정할 수 있습니다.

- **화면:** 데이터 소스 페이지 하단 **REST API 연결** 섹션 (API 작업 / 호출 이력 / 적재 이력)
- **API:** `/api/v1/api-connectors/*` — operation CRUD, credential, params, pagination, request-preview, test-call, load-preview, load-run
- **인증:** serviceKey 등 secret는 마스킹 저장·조회, 로그/미리보기 URL에 원문 미노출
- **serviceKey 정책:** Decoding 키 입력 권장 (`STORE_DECODED_ENCODE_ON_CALL`), Encoding 키 이중 인코딩 위험 안내
- **적재:** ACTIVE 표준 데이터셋 물리 테이블(`std_*`) 검증 후 기본 INSERT (매핑 있으면 적용)
- **운영 seed:** API connector 샘플 없음 (clean 0건)
- **검증:** `scripts/test_api_connector_builder.py`, model regression 그룹 등록

**이번 Phase 범위 외 (후속):** 열수요 wide-hour transform(R10-S3), ASOS/Calendar(R10-S4), 단기예보 Provider(R10-S5), 스케줄러(R10-S6)

### R10-S0 REST API Connector UI 고도화

R10 Backend를 기반으로 **데이터 소스** 화면 **REST API 연결** 패널 UI를 고도화했습니다.

- **8단계 Wizard:** 기본 정보 → 인증 정보 → 요청 파라미터 → 페이징 → 응답 데이터 경로 → 적재 대상 → 테스트 호출 → 검토 및 저장
- **탭:** API 작업 / 호출 이력 / 적재 이력 / 원본 응답 스냅샷
- **작업 목록:** 요청 미리보기, 테스트 호출, 적재 미리보기, 적재 실행 (target_table 미설정 시 적재 버튼 비활성)
- **secret:** `safeJsonStringify`로 UI 표시 시 serviceKey 등 마스킹, password 입력 후 저장 즉시 state 초기화
- **검증:** `frontend/scripts/check-pages.mjs` Wizard 라벨·버튼 문구 확인

### R10-S1 Prediction Entity / Location / Weather Mapping

열수요·설비·지역 등 **예측 대상(Entity)** 기준정보와 **위치 정보**, **기상 매핑**을 관리합니다.

- **예측 대상:** 범용 Entity (`SITE` / `BRANCH` / `FACILITY` / `REGION` / `ZONE` / `CUSTOM`). 열수요에서는 `site_id`·`branch_id` 등이 예측 대상이 될 수 있습니다.
- **위치 정보:** 주소, 위도/경도. 위경도 입력 후 **nx/ny 계산**으로 기상청 단기예보 격자 좌표를 제안합니다(저장 전 검토).
- **단기예보 격자 매핑:** 예측 대상 → KMA DFS 격자(`nx`, `ny`). 예측 시점 on-demand 단기예보 API 호출(R10-S5)에 사용됩니다.
- **ASOS 관측소 매핑:** 과거 학습용 관측 기상 연결(R10-S4). 단기예보와 기준이 다르므로 **별도 매핑**합니다.
- **준비 상태:** `location_ready` / `forecast_ready` / `observation_ready` — 화면에서 “위치 정보”, “단기예보 준비”, “관측 기상 준비”로 표시
- **메뉴:** 데이터 준비 → **표준 데이터셋 → 데이터 소스 → 예측 대상 → 데이터 매핑 → 데이터 품질**
- **API:** `/api/v1/prediction-entities/*`, `/api/v1/weather/forecast-grids`, `/api/v1/weather/observation-stations`, `/api/v1/weather/convert-latlon-to-grid`
- **DB:** `tb_prediction_entity`, `tb_prediction_entity_location`, `tb_weather_forecast_grid`, `tb_weather_observation_station`, `tb_prediction_entity_weather_mapping`
- **운영 seed:** 예측 대상·격자·관측소 샘플 없음 (clean 0건)
- **검증:** `scripts/test_prediction_entity_weather_mapping.py`, model regression 그룹 등록

### R10-S2 External Code / Common Code Mapping

외부 API·파일·DB의 **코드값**을 THERMOps **내부 기준정보**와 안전하게 연결합니다.

- **외부 코드 매핑:** `source_system` + `external_code_group` + `external_code` → `target_type` + `target_id`
- **내부 연결 대상:** `PREDICTION_ENTITY`, `FORECAST_GRID`, `OBSERVATION_STATION`, `STANDARD_DATASET`, `COMMON_CODE`, `CUSTOM`
- **미매핑 코드:** 변환 실패 시 `tb_unmapped_external_code`에 수집 — **내부 기준정보 자동 생성 없음**
- **코드 변환(resolve):** `POST /api/v1/external-code-mappings/resolve`, `resolve-batch`
- **예시:** 열수요 API `ND_ID` → 예측 대상 `entity_id`
- **메뉴:** 데이터 준비 → **표준 데이터셋 → 데이터 소스 → 예측 대상 → 외부 코드 매핑 → 데이터 매핑 → 데이터 품질**
- **API Connector 연계:** operation `metadata_json.code_mappings` 설정 시 load-preview/load-run에서 미매핑 코드 수집(optional)
- **운영 seed:** 외부 코드·매핑 샘플 없음 (clean 0건)
- **검증:** `scripts/test_external_code_mapping.py`, model regression 그룹 등록

### R10-S3 실제 열수요 API wide-hour 변환 적재

열수요 API 응답의 **시간대별 컬럼**(예: `HTDND_AMNT_1HR`~`HTDND_AMNT_24HR`)을 학습/예측용 **long format** 시계열(`measured_at`, `heat_demand`)로 변환해 적재합니다.

- **변환 유형:** `WIDE_HOUR_TO_LONG` (`tb_api_connector_transform_config`)
- **외부 지점 코드:** `ND_ID` → R10-S2 외부 코드 매핑으로 `PREDICTION_ENTITY` resolve (미매핑 시 자동 예측 대상 생성 **없음**)
- **시간 해석:** `timestamp_policy` (`HOUR_LABEL_AS_END` / `HOUR_LABEL_AS_START`), `hour_24_policy` (`NEXT_DAY_00` / `SAME_DAY_23`) — API 정의 확인 필요
- **미매핑 정책:** `FAIL_LOAD`(기본), `SKIP_UNMAPPED`, `LOG_ONLY`
- **API:** `GET/PUT .../transform-config`, `POST .../transform-preview`, load-preview/load-run 변환 진단 보강
- **UI:** REST API 작업 Wizard → **변환 설정** 단계 (열수요 wide-hour 변환)
- **적재:** 기본 INSERT (upsert/중복 제거는 후속)
- **운영 seed:** transform config·열수요 API 샘플 없음 (clean 0건)
- **검증:** `scripts/test_heat_demand_wide_hour_transform.py`, model/connector regression 등록

### R10-S4 ASOS 관측 기상 / Calendar·특일 적재

과거 학습용 **ASOS 관측 기상**과 **달력·공휴일·특일** 기준정보를 REST API Connector 변환 파이프라인으로 표준 데이터셋에 적재합니다.

- **과거 vs 미래 기상:** ASOS 관측값은 학습용 과거 데이터. 미래 예측 시점 기상은 **R10-S5 Forecast On-demand Input Provider**에서 예측 실행 시 on-demand 호출
- **변환 유형:** `ASOS_HOURLY_TO_CANONICAL`, `CALENDAR_SPECIAL_DAY_TO_DATE`, `CALENDAR_DATE_TO_HOUR` (`tb_api_connector_transform_config` 확장 컬럼)
- **ASOS 표준 컬럼 권장:** `std_weather_observation_hourly` — `station_code`, `observed_at`, `temperature`, `humidity`, `wind_speed`, `precipitation`, `pressure`, `sunshine_duration`, `solar_radiation`, `source_system`, `raw_json` 등
- **Calendar date 권장:** `std_calendar_date` — `calendar_date`, `year`~`day`, `day_of_week`, `day_name`, `is_weekend`, `is_holiday`, `is_public_holiday`, `is_workday`, `holiday_name`, `special_day_type`, `special_day_name`, `solar_term_name` 등
- **Calendar hour 권장:** `std_calendar_hour` — `measured_at`, `calendar_date`, `hour`, `season`, 휴일/근무일 플래그 등
- **Calendar mode:** `SPECIAL_DAYS_ONLY`(특일만), `FULL_CALENDAR_WITH_OVERLAY`(연·월 전체 달력 + 특일 오버레이, 기본 권장)
- **ASOS 관측소 검증:** R10-S1 `tb_weather_observation_station` 등록 코드 기준 (`WARN_ONLY` / `LOG_UNMAPPED` / `FAIL_LOAD`)
- **API:** 기존 `transform-config` / `transform-preview` / `load-preview` / `load-run` — `transform_summary`에 `date_row_count`, `hour_row_count` 등 진단 포함
- **개발용 mock:** `GET /sample-external/asos-hourly`, `GET /sample-external/special-days` (실제 외부 API 호출 테스트 없음)
- **운영 seed:** ASOS/Calendar transform config·표준 데이터셋·API 작업 샘플 **없음** (clean 0건)
- **검증:** `scripts/test_asos_calendar_ingestion.py`, model/connector regression 등록

**후속 Phase:** R10-S6 데이터 적재 스케줄러 · upsert/중복 제거 고도화

**이번 Phase 범위 외 (후속):** 스케줄러(R10-S6), upsert 고도화

### R10-S5 Forecast On-demand Input Provider

예측 실행 시점에 선택된 예측 대상의 **단기예보 격자(nx/ny)**로 기상청 단기예보 API를 on-demand 호출하고, 응답을 **예측용 표준 기상 입력**으로 정규화합니다. 장기 archive가 아니라 **예측 작업 단위 snapshot/cache**로 재현성을 확보합니다.

- **과거 vs 미래:** 과거 학습용 기상은 R10-S4 **ASOS 관측**. 미래 예측용은 **단기예보 API** (이번 Phase Provider)
- **Readiness:** 예측 대상 `forecast_ready`(nx/ny 매핑) 필수 — R10-S1 기상 매핑 연계
- **REST API 연계:** R10 Connector에 등록한 **기상청 단기예보 API 작업**을 `tb_forecast_provider_config.source_operation_id`로 참조. `nx`/`ny`/`base_date`/`base_time` 등은 runtime override
- **base_time 정책:** 수동 지정 없으면 KST 기준 `resolve_latest_kma_base_time(now - delay_minutes)` — 후보 `0200,0500,0800,1100,1400,1700,2000,2300`, 기본 `delay_minutes=60`
- **표준 feature:** `forecast_temperature`, `forecast_humidity`, `forecast_wind_speed`, `forecast_precipitation`, `forecast_precipitation_probability`, `forecast_sky_condition`, `forecast_precipitation_type`, `forecast_base_at`, `forecast_target_at`, `forecast_horizon_hours`
- **DB:** `tb_forecast_provider_config`, `tb_forecast_input_snapshot`, `tb_prediction_weather_input` (`scripts/r10s5_forecast_input_provider_schema.sql`)
- **캐시:** `cache_key = source|nx|ny|base_date|base_time|operation` — `USE_CACHE` / `REFRESH` / `DISABLED`
- **Prediction 연계:** `forecast_provider_enabled=true` 시 `result_summary.forecast_input_summary` 저장, `tb_prediction_weather_input` 적재
- **API:** `/api/v1/forecast-provider/*`, `GET /api/v1/prediction-jobs/{id}/weather-inputs`
- **UI:** `/predictions/jobs` — 단기예보 입력 섹션, 미리보기, Provider 설정(REST API 작업 선택)
- **개발용 mock:** `GET /sample-external/kma-short-forecast` (실제 기상청 API 호출 테스트 없음)
- **운영 seed:** Forecast Provider config·snapshot·weather input 샘플 **없음** (clean 0건)
- **검증:** `scripts/test_forecast_on_demand_provider.py`, model regression 등록

**후속 Phase:** 장기 forecast archive · upsert/중복 제거 고도화 · worker/cron/Airflow run-due 연동 고도화

**이번 Phase 범위 외 (후속):** 장기 forecast archive, upsert 고도화, OS cron/Airflow DAG 동적 생성

### R10-S6 데이터 적재 스케줄러

REST API Connector **load-run/load-preview**를 정기 일정으로 실행하기 위한 **DB 기반 스케줄 정의·실행 이력·due 조회·run-due API**입니다. 이번 Phase에서는 THERMOps 내부 API/서비스/UI만 구현하며, **상시 background daemon·OS cron 직접 등록·Airflow DAG 동적 생성은 하지 않습니다.**

- **대상:** `tb_api_connector_operation`에 등록된 REST API 작업. transform config가 있으면 기존 load-run과 동일하게 적용
- **스케줄 구성:** `operation_id` + `runtime_params_template` + `schedule_type`(MANUAL/HOURLY/DAILY/WEEKLY/MONTHLY/CRON) + `load_window_type` + 재시도 정책
- **실행 흐름:** due schedules 조회 → `POST /api/v1/data-load-schedules/run-due` → 기존 `run_load`/`load_preview` 호출 → `tb_data_load_schedule_run`에 이력·`api_load_run_id` 연결
- **운영 연계:** 외부 cron/worker/Airflow에서 **run-due API를 주기 호출**하는 방식으로 후속 연결 가능 (`metadata_json`에 Airflow 연계 힌트만 저장 가능)
- **next_run_at:** `schedule_time_service.compute_next_run_at` — CRON은 저장만 하고 due 자동 실행 제외
- **Runtime params template:** `{{today:YYYYMMDD}}`, `{{yesterday:...}}`, `{{now:...}}`, `{{last_success_at}}`, `{{window_start}}`, `{{window_end}}` — 마스킹된 snapshot만 이력 저장
- **재시도:** `retry_enabled_yn` + `POST /api/v1/data-load-schedule-runs/{id}/retry` (수동 재시도)
- **DB:** `tb_data_load_schedule`, `tb_data_load_schedule_run`, `tb_data_load_schedule_event` (`scripts/r10s6_data_load_scheduler_schema.sql`)
- **API:** `/api/v1/data-load-schedules/*`, `/api/v1/data-load-schedule-runs/*`
- **UI:** `/data-load-schedules` — 일정 목록·실행 이력·실행 대상 일정·도움말
- **Forecast on-demand(R10-S5)는 스케줄 대상 아님** — 예측 실행 시점 Provider 유지
- **운영 seed:** 스케줄·실행 이력 샘플 **없음** (clean 0건)
- **검증:** `scripts/test_data_load_scheduler.py`, model regression 등록

**후속 Phase:** 실제 worker/cron/Airflow 운영 구성 · upsert/중복 제거 고도화 · CRON parser · 알림/장애 통보

### R10-S7 운영 점검 / 통합 시나리오 검증

R10 계열(Connector, 표준 데이터셋, 예측 대상/기상 매핑, 외부 코드 매핑, Transform, Forecast Provider, 데이터 적재 일정)이 실제 운영 흐름에서 함께 동작하는지 **통합 시나리오 A~F**로 점검합니다. 이번 Phase는 신규 대규모 기능 개발이 아니라 **운영 검증·회귀 방지·문서 정합성** 단계입니다.

- **시나리오 A:** clean 설치/빈 화면/주요 R10 테이블 0건 확인
- **시나리오 B:** 표준 데이터셋 4종(열수요 long, ASOS, Calendar date/hour) Wizard/물리 테이블 준비
- **시나리오 C:** 열수요 wide-hour 변환(load-preview/load-run) + 미매핑 코드 수집 검증
- **시나리오 D:** ASOS/Calendar 변환 적재 + 월 단위 hour_generation 검증
- **시나리오 E:** 데이터 적재 일정 run-now/run-due/retry/event + masking 검증
- **시나리오 F:** Forecast on-demand preview/cache + prediction 연계(summary/weather input) 검증
- **통합 테스트:** `scripts/test_r10_operational_integration.py` (mock/sample endpoint만 사용, 외부 공공 API 의존 없음)
- **API 점검:** OpenAPI(`/openapi.json`) 기준 R10 핵심 endpoint 노출 확인
- **Secret 정책:** serviceKey/API Key 원문 미노출(요청 미리보기, snapshot, schedule run, summary)
- **운영 seed:** 업무 샘플 데이터 추가 없음 (clean 0건 정책 유지)

### R10-S8 Upsert / 중복 제거 고도화

REST API Connector 적재(`load-preview`/`load-run`)에 **적재 방식(신규 행 추가/중복 제외/있으면 갱신, 없으면 추가)**을 도입해 재실행 시 동일 키 데이터가 중복 누적되지 않도록 고도화했습니다.

- **적재 방식:** `INSERT_ONLY`, `DEDUPLICATE`, `UPSERT`
- **중복 판단 키(업무 키):** target table별 `conflict_key_columns_json` 설정
- **batch 내부 중복 정책:** `KEEP_FIRST`, `KEEP_LAST`, `ERROR`
- **null 값 갱신 정책:** `KEEP_EXISTING`, `OVERWRITE_WITH_NULL`
- **DB:** `tb_api_connector_write_policy`, `tb_api_connector_load_dedup_summary` (`scripts/r10s8_upsert_dedup_schema.sql`)
- **API:** `/api/v1/api-connectors/operations/{operation_id}/write-policy*`, `/api/v1/api-connectors/dedup-summaries*`, `/api/v1/api-connectors/target-table-columns`
- **미리보기/실행 결과:** 예상/실제 insert-update-skip, batch 중복 수, 기존 매칭 수, sample conflicts 노출
- **스케줄러 연계:** run 결과에 `write_mode`, `updated_count`, `skipped_count` 포함
- **운영 seed:** write policy/summary 샘플 데이터 추가 없음 (clean 0건 정책 유지)
- **제한:** unique index 자동 생성/대용량 temp table·COPY·MERGE 최적화는 후속 단계

### R10-S9 알림 / 장애 통보

R10 운영 기능(스케줄러, API Connector, Forecast Provider, Prediction Job 등)에서 발생하는 실패·경고를 **이벤트 → 알림 규칙 → 장애 → 발송 이력** 흐름으로 수집·통보합니다.

- **흐름:** `Notification Event` 기록 → 활성 `Alert Rule` 매칭 → `Incident` 생성/갱신 → `Notification Delivery` 생성 → MOCK(또는 설정된 채널) 발송
- **심각도:** INFO / WARNING / ERROR / CRITICAL (`min_severity` 조건)
- **중복 알림 억제:** `dedup_key` + `dedup_window_minutes`로 반복 알림 SUPPRESSED 또는 장애 `occurrence_count` 증가
- **장애 상태:** OPEN → ACKNOWLEDGED → RESOLVED / CLOSED
- **채널:** MOCK(테스트 확정), WEBHOOK(설정 시), EMAIL/SLACK/SMS는 설정 구조만(SKIPPED)
- **DB:** `tb_notification_channel`, `tb_notification_recipient`, `tb_alert_rule`, `tb_notification_event`, `tb_incident`, `tb_notification_delivery` (`scripts/r10s9_alert_notification_schema.sql`)
- **API:** `/api/v1/notifications/*` (channels, recipients, alert-rules, events, incidents, deliveries, summary)
- **UI:** `/notifications` — 장애 현황, 알림 이벤트, 알림 규칙, 알림 채널, 수신 대상, 발송 이력
- **연계:** schedule run 실패, API load-run warning/failure, forecast provider failure, prediction job failure, unmapped code detected
- **운영 seed:** channel/rule/recipient 샘플 없음 (clean 0건). 테스트는 fixture/MOCK만 사용
- **제한:** 실제 SMS/메일/Slack 외부 발송 테스트 금지, CRON parser 정식 지원은 후속

### R10-S10 Run Due Worker / Cron 운영 구성

R10-S6 `POST /api/v1/data-load-schedules/run-due`를 **운영 환경에서 주기적으로 자동 실행**할 수 있게 합니다.

- **Worker 모드:** `loop`(Docker 상시 서비스) / `once`(cron·외부 스케줄러 1회 호출)
- **중복 실행 방지:** row 기반 `tb_run_due_worker_lock` + `expires_at` TTL
- **상태 기록:** `tb_run_due_worker_instance`(heartbeat·연속 실패), `tb_run_due_worker_run`(실행 이력)
- **알림 연계:** RUN_DUE_WORKER_FAILED, CONSECUTIVE_FAILURE, STALE, RECOVERED, RUN_WARNING (R10-S9, 실패 시 worker 본동작 유지)
- **API:** `/api/v1/run-due-worker/*` (instances, runs, locks, summary, run-once, mark-stale)
- **UI:** 데이터 적재 일정 → **Worker 상태** 탭
- **DB:** `scripts/r10s10_run_due_worker_schema.sql`
- **운영 seed:** worker instance/schedule 샘플 없음 (clean 0건)
- **제한:** CRON parser 정식 지원·OS cron 자동 등록·Airflow schedule 동적 생성 금지

**환경 변수** (`.env.example` / `.env.deploy`):

| 변수 | 기본 | 설명 |
|------|------|------|
| `THERMOOPS_RUN_DUE_WORKER_ENABLED` | false | Worker CLI 동작 여부 |
| `THERMOOPS_RUN_DUE_WORKER_MODE` | loop | loop / once |
| `THERMOOPS_RUN_DUE_POLL_INTERVAL_SECONDS` | 60 | loop polling 주기 |
| `THERMOOPS_RUN_DUE_LOCK_TTL_SECONDS` | 120 | 잠금 TTL |
| `THERMOOPS_RUN_DUE_MAX_BATCH_SIZE` | 20 | run-due 배치 상한 |

**Traefik 배포 (worker 포함):**

```bash
python3 scripts/apply_dev_migrations.py
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend frontend run-due-worker
```

**cron 대안 (예시만, 자동 등록 없음):**

```bash
./scripts/run_due_once.sh
# crontab 예: * * * * * cd /opt/thermops && ./scripts/run_due_once.sh >> /var/log/thermops-run-due.log 2>&1
```

**배포 전 체크리스트 (R10):**
1. `python scripts/apply_dev_migrations.py`
2. `python scripts/test_cron_schedule_parser.py`
3. `python scripts/test_notification_alerting.py`
4. `python scripts/test_run_due_worker.py`
5. `python scripts/test_r10_operational_integration.py`
6. `python scripts/run_regression_tests.py --group model --timeout-scale 2`
7. `python scripts/run_regression_tests.py --group quick --timeout-scale 2`
8. `cd frontend && npm run build && node scripts/check-pages.mjs`
9. (Traefik) `docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend frontend run-due-worker`

### R10-S11 CRON parser 정식 지원

R10-S6에서 저장만 가능하던 `schedule_type=CRON`을 **due 계산·next_run_at·Worker 자동 실행**까지 정식 지원합니다.

- **지원:** 5-field CRON (`분 시 일 월 요일`) — `*`, `N`, `A-B`, `A,B,C`, `*/N`, `A-B/N`
- **예:** `*/5 * * * *`, `0 * * * *`, `30 2 * * *`, `0 9 * * 1-5`, `0 0 1 * *`
- **미지원:** 6-field(초), Quartz(`?`, `L`, `W`, `#`), `@hourly`/`@daily` alias
- **요일:** `0`과 `7` 모두 일요일
- **시간대:** 기본 `Asia/Seoul` (`timezone` 컬럼)
- **due/missed:** `next_run_at <= now`이면 1회 due 후 다음 future fire로 이동 (catch-up 전체 실행 없음)
- **DB:** 기존 `cron_expression`/`timezone`/`next_run_at` 재사용, `cron_expression` VARCHAR(120) (`scripts/r10s11_cron_schedule_schema.sql`)
- **API:** `/data-load-schedules/cron/validate`, `/cron/preview`, `preview-next-run` CRON 확장
- **UI:** CRON 표현식 입력·예시·검증·다음 실행 예정 미리보기
- **운영 seed:** CRON 샘플 일정 추가 없음 (clean 0건)
- **제한:** OS cron 자동 등록·Airflow schedule 동적 생성·catch-up 전체 실행 금지

### R11-S1 Visual Pipeline Component Catalog

Visual Pipeline Studio용 **code-based** 컴포넌트 계약/카탈로그 API입니다. DB migration·graph·compile·UI는 포함하지 않습니다.

- **ACTIVE 4종:** `VP_REST_API_SOURCE`, `VP_TRANSFORM`, `VP_UPSERT_LOAD`, `VP_CRON_SCHEDULE`
- **DISABLED:** Notification / Data Quality / Feature·Training·Prediction / Forecast·DB·CSV Source
- **API:** `GET /api/v1/visual-pipelines/components`, `.../components/{component_type}`, `.../connection-rules`
- **테스트:** `python scripts/test_visual_pipeline_component_catalog.py` (service direct + optional HTTP smoke)

### R11-S2 Visual Pipeline Graph 저장 / CRUD

기존 `tb_pipeline_*`를 확장해 Visual Pipeline Graph를 저장합니다. (`tb_visual_pipeline_*` 신설 없음)

- **구분:** `pipeline_kind=VISUAL_DATA_LOAD`, `pipeline_type=DATA_LOAD`
- **컬럼:** `current_graph_json`, `current_sync_status`(기본 `NOT_COMPILED`)
- **Template:** `PT-VISUAL-DATA-LOAD` skeleton (`02_seed_clean` + migration)
- **API:** `/api/v1/visual-pipelines` CRUD, archive, versions (`snapshot_json.graph`)
- **격리:** `/pipeline-definitions` 목록에서 VISUAL 제외
- **미포함:** React Flow UI, compile, run-now, semantic validation
- **테스트:** `python scripts/test_visual_pipeline_graph_storage.py`
- **Migration:** `python scripts/apply_dev_migrations.py` (`r11s2_visual_pipeline_graph_schema.sql`)

### R11-S3 / R11-S4-0 Visual Pipeline Studio UX

- **S3:** React Flow Canvas PoC (`/visual-pipelines`, Studio), `@xyflow/react`
- **S4-0:** 저장과 버전 저장 UX 분리
  - `PUT /visual-pipelines/{id}`: 기본 `create_version=false` → graph만 저장, version 미생성
  - `create_version=true`일 때만 PUT에서 version 생성
  - `POST .../versions`: 명시적 snapshot
  - Studio **저장** = graph만 저장 / **버전 저장** = dirty면 PUT(false) 후 POST → version +1

### R11-S4-1 Visual Pipeline Graph Validation

- **API:** `POST /api/v1/visual-pipelines/validate-graph`, `POST /api/v1/visual-pipelines/{id}/validate`
- **검증:** node/edge/component/port/topology/cycle (DB write 없음)
- **level:** BASIC(기본) / STRICT
- **Studio:** `Graph 검증` 버튼 + Validation Panel (저장 차단 없음)
- **테스트:** `python scripts/test_visual_pipeline_graph_validation.py`

### R11-S4-2 Port Handle 저장 / 검증 정확도

- Handle id: `output:{port}` / `input:{port}` (catalog `port_id`)
- edge에 `sourceHandle` / `targetHandle` / `data.source_port` / `data.target_port` / `data_type` 보존
- Validation은 handle 우선, legacy label-only는 `EDGE_PORT_UNSPECIFIED` fallback 유지

### R11-S4-3 Studio 상세 route E2E

- 목록 route(`/visual-pipelines`)는 기존 `frontend/scripts/check-pages.mjs`에서 검증
- Studio 상세(`/visual-pipelines/:pipelineId`)는 별도 smoke: `frontend/scripts/check-visual-pipeline-studio.mjs`
- API로 E2E fixture(4-node + handle metadata) 생성 → browser 검증 → `archive` cleanup
- env: `CHECK_PAGES_BASE`(frontend), `THERMOOPS_API_BASE`(API, `/api/v1` 포함)
- 회귀 그룹: `frontend` / `full` (`quick` 미포함)

```bash
# Docker 예시
docker run --rm --network thermops_default \
  -v "$PWD/frontend:/app" -w /app \
  -e CHECK_PAGES_BASE=http://thermops-frontend:5173 \
  -e THERMOOPS_API_BASE=http://thermops-backend:8000/api/v1 \
  node:20-bookworm bash -lc "npx playwright install --with-deps chromium && node scripts/check-visual-pipeline-studio.mjs"

# 로컬 예시 (frontend :5173 + backend :8000)
cd frontend && node scripts/check-visual-pipeline-studio.mjs
```

### R11-S5-0 Inspector Config Form 설계

- **문서:** [`docs/md/THERMOps_R11-S5-0_Visual_Pipeline_Inspector_Config_Form_설계.md`](docs/md/THERMOps_R11-S5-0_Visual_Pipeline_Inspector_Config_Form_설계.md)
- **범위:** 설계만 (Form/API/DB 구현 없음). S5-1~에서 단계적 구현.
- **config 저장:** `node.data.config` — `{ schema_version, values, validation }`; `values` 키는 S1 catalog `config_schema`와 1:1.
- **secret:** graph에 원문 저장 금지, `credential_ref` 등 참조만 허용.
- **validation:** BASIC=저장 차단 없음(WARNING 중심); STRICT=S6 compile gate; `validation.status`는 UI cache, authoritative=validation API.
- **legacy:** config 없는 graph도 load 가능 (`values: {}` normalize).

### R11-S5-1 Config schema registry + normalize

- **범위:** frontend only — Form UI·backend API·DB 변경 없음.
- **파일:**
  - `frontend/src/types/visualPipeline.ts` — `VisualPipelineNodeConfig`, field/section schema types
  - `frontend/src/utils/visualPipelineConfigRegistry.ts` — MVP 4종 local registry (S1 catalog `config_schema.name` 1:1)
  - `frontend/src/utils/visualPipelineNodeConfig.ts` — `normalizeNodeConfig`, `createDefaultNodeConfig`, `sanitizeConfigValuesForGraph`(준비만)
- **normalize:** `graphToFlow` / `flowToGraph`에서 `node.data.config`를 `{ schema_version, values, validation }`로 호환 변환. legacy flat config는 `values`로 감싸 보존, unknown key 삭제 없음.
- **Inspector:** `VpNodeInspector` placeholder JSON → registry/catalog 정렬 preview (Form은 S5-2).
- **E2E:** `check-visual-pipeline-studio.mjs` fixture에 S5-0 config sample + legacy flat CRON 포함.
- **제외:** secret 자동 삭제, config validation API, compile/저장 UX 변경.

### R11-S5-2 REST API Source Inspector Form UI

- **범위:** frontend only — `VP_REST_API_SOURCE` 노드만 editable Form. Transform/Upsert/CRON은 JSON preview 유지.
- **파일:**
  - `frontend/src/components/visualPipeline/config/VpRestApiSourceConfigForm.tsx` — REST 8 fields (connection/request/response sections)
  - `frontend/src/components/visualPipeline/config/VpConfigFieldShell.tsx`, `VpJsonTextareaField.tsx` — 소형 재사용 field helpers
  - `VpNodeInspector.tsx`, `VisualPipelineStudioPage.tsx` — Form 연동, `applyNodeConfigPatch`
- **동작:** Form 변경 → `node.data.config.values` patch → validation cache `NOT_VALIDATED` → graph dirty → 기존 `저장`/`버전 저장` UX.
- **JSON fields:** `request_params`/`pagination` — local draft, valid JSON일 때만 object 반영, invalid JSON은 warning만.
- **E2E:** Studio script — REST Form 표시, 입력, dirty, 저장 toast, Graph 검증 OK/errors 0.
- **제외:** backend/config validation API, Transform/Upsert/CRON Form, secret 원문 입력 UI.

## 설계 문서 참조

- `docs/md/THERMOps_R11-S5-0_Visual_Pipeline_Inspector_Config_Form_설계.md`
- `docs/md/THERMOps_API_설계서.md`
- `docs/md/THERMOps_DB_설계서.md`
- `docs/md/THERMOps_배치_파이프라인_설계서.md`
- `docs/md/THERMOps_화면_설계서.md`
- `docs/md/THERMOps_P1_모델고도화_정리.md`
- `design/figma/THERMOps_Figma_UI_Master_Spec.md`

## 1차 구현 범위 및 제한사항

- 실제 원천 시스템 연계: **초기 설치 시 CSV 샘플 소스 없음** — UI/API로 데이터 소스·매핑 등록 후 적재·학습
- ML 모델: Baseline, LightGBM, sklearn GBDT fallback, **CatBoost**, **2-Stage CatBoost** (완전한 성능 튜닝·GPU 최적화 미포함)
- **인증/권한:** 로그인·SSO·JWT·세션·사용자 관리 **미구현**. `VITE_USER_ROLE`은 UI Mock 권한만 제공 (상세: [인증/권한 (1차 범위 — Mock)](#인증권한-1차-범위--mock)). 실제 사업 적용 시 발주기관 SSO/JWT/기관 인증체계 연계 필요
- 수주 후 발주기관 환경에 맞춰 데이터 매핑, DAG 스케줄, DBMS 전환 보정 필요

## 라이선스

사전 구축형 솔루션 설계 산출물 기준 — 내부 프로젝트용
