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

```bash
# 1. 환경 변수 복사
cp .env.example .env

# 2. 전체 스택 실행
docker compose up -d --build

# 3. 서비스 기동 확인 (PostgreSQL healthcheck 후 backend 기동)
docker compose ps
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
| `feature_build_dag` | Feature 생성 |
| `model_training_dag` | Baseline/ML 모델 학습 |
| `batch_prediction_dag` | D+1/D+7 배치 예측 |
| `monitoring_dag` | 성능 평가, 드리프트, 재학습 후보 |

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
- `design/figma/THERMOps_Figma_UI_Master_Spec.md`

## 1차 구현 범위 및 제한사항

- 실제 원천 시스템 연계 대신 **시드 DB + Mock API 응답** 기반으로 전체 화면·운영 흐름 시연
- ML 모델은 Baseline/LightGBM/XGBoost **구조만** 제공 (완전한 성능 튜닝 미포함)
- 인증/SSO는 미구현 (Bearer Token 구조만 API 설계서에 정의)
- 수주 후 발주기관 환경에 맞춰 데이터 매핑, DAG 스케줄, DBMS 전환 보정 필요

## 라이선스

사전 구축형 솔루션 설계 산출물 기준 — 내부 프로젝트용
