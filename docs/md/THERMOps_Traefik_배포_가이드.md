# THERMOps Traefik 배포 가이드

> **목적**: DNS A레코드 **1개**만으로 THERMOps를 Traefik 서버에 clean deployment  
> **공개 도메인**: `https://thermops.openlink.kr`  
> **개발용** `docker-compose.yml` 은 변경하지 않음

---

## 1. 배포 목적

- Traefik이 이미 동작하는 서버에 THERMOps 스택을 격리 배포
- **깨끗한 DB**(마스터·템플릿만)에서 Word 사용자 가이드 실습을 처음부터 진행
- Frontend + Backend API만 HTTPS 공개
- Airflow / MLflow / MinIO는 **내부 Docker network** 전용 (기본 외부 비공개)

---

## 2. DNS 설정 (A레코드 최소화)

### 2.1 필수 (1개만)

| 타입 | 이름 | 값 |
|------|------|-----|
| **A** | `thermops.openlink.kr` | 서버 공인 IP |

이 한 개로 Frontend·API·TLS 인증서(Let's Encrypt)가 동작합니다.

### 2.2 추가 A레코드 불필요

다음은 **기본 구성에서 사용하지 않습니다**:

- `thermops-api.openlink.kr`
- `thermops-airflow.openlink.kr`
- `thermops-mlflow.openlink.kr`
- `thermops-minio.openlink.kr`

### 2.3 Optional admin exposure (CNAME)

관리 도구를 나중에 외부 공개할 때도 **A레코드를 추가하지 않고** CNAME을 사용합니다.

| 타입 | 이름 | 값 |
|------|------|-----|
| CNAME | `airflow.thermops.openlink.kr` | `thermops.openlink.kr` |
| CNAME | `mlflow.thermops.openlink.kr` | `thermops.openlink.kr` |
| CNAME | `minio.thermops.openlink.kr` | `thermops.openlink.kr` |

DNS 제공자가 지원하면:

| 타입 | 이름 | 값 |
|------|------|-----|
| CNAME | `*.thermops.openlink.kr` | `thermops.openlink.kr` |

→ [§10 Optional admin exposure](#10-optional-admin-exposure) 참고

---

## 3. Traefik 라우팅 구조

```
                    thermops.openlink.kr (A → 서버 IP)
                              │
                         [ Traefik :443 ]
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
   PathPrefix `/api`    Path `/docs` 등      Host `/` (priority 낮음)
   priority 100         priority 100                │
         │                    │                    │
         └────────┬───────────┘                    │
                  ▼                                ▼
            backend:8000                    frontend:80 (nginx)
            /api/v1/* (prefix strip 없음)     SPA 정적 파일
```

| URL | 대상 | 비고 |
|-----|------|------|
| `https://thermops.openlink.kr/` | Frontend (nginx) | React SPA |
| `https://thermops.openlink.kr/api/v1/...` | Backend | prefix strip **하지 않음** |
| `https://thermops.openlink.kr/docs` | Backend FastAPI | Swagger UI (선택 공개) |
| `https://thermops.openlink.kr/openapi.json` | Backend | OpenAPI 스펙 |

**하지 않는 것** (의도적):

- `/airflow`, `/mlflow`, `/minio` path prefix 라우팅 — redirect·static resource 문제

---

## 4. 전제 조건

| 항목 | 요구사항 |
|------|----------|
| Docker / Compose | v2 이상 |
| Traefik | 서버에서 이미 기동, `websecure` entrypoint + Let's Encrypt resolver |
| External network | `traefik` (또는 `.env.deploy`의 `TRAEFIK_NETWORK`) |
| 포트 | **80/443은 Traefik이 사용** — THERMOps 컨테이너는 host port 미노출 |
| Git | 저장소 clone, `data/samples/*.csv` 포함 |
| 리소스 | 학습·Feature 생성 시 CPU/메모리 여유 권장 |

Traefik external network 생성 (최초 1회):

```bash
docker network create traefik
```

---

## 5. 배포 절차

### 5.1 환경 파일 준비

```bash
cp .env.deploy.example .env.deploy
# .env.deploy 편집 — POSTGRES_PASSWORD, AIRFLOW_PASSWORD, MINIO_ROOT_PASSWORD 등 변경
```

필수 변경 항목:

- `THERMOPS_HOST=thermops.openlink.kr`
- `POSTGRES_PASSWORD`, `AIRFLOW_PASSWORD`, `MINIO_ROOT_PASSWORD`
- `BACKEND_CORS_ORIGINS=https://thermops.openlink.kr`

### 5.2 Compose 검증

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy config
```

### 5.3 빌드 및 기동

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build
```

### 5.4 기동 확인

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy ps
curl -sS https://thermops.openlink.kr/api/v1/sites | head
```

---

## 6. Clean 초기화

### 6.1 새 volume으로 시작 (권장)

`docker-compose.traefik.yml`은 Postgres init 시 **demo seed 대신** `02_seed_clean.sql`을 사용합니다.

```bash
# 최초 clean 배포 (volume 없을 때)
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build
```

완전 초기화(모든 데이터·MLflow artifact·Airflow 이력 삭제):

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy down -v
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build
```

### 6.2 결과성 데이터만 TRUNCATE (volume 유지)

```bash
export THERMOPS_DEPLOY_ENV=clean
export DATABASE_URL=postgresql+asyncpg://thermops:<PASSWORD>@localhost:5432/thermops
# Postgres port-forward 또는 compose exec 후:
docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec postgres \
  psql -U thermops -d thermops -c "SELECT 1"

# 호스트에서 (postgres 포트가 내부만이면 exec 사용):
docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec backend \
  python /workspace/scripts/reset_clean_deploy.py --yes --database-url "postgresql+asyncpg://thermops:${POSTGRES_PASSWORD}@postgres:5432/thermops" --skip-env-check
```

또는 호스트에서 `THERMOPS_DEPLOY_ENV=clean python scripts/reset_clean_deploy.py --yes` (DB 접근 가능 시)

### 6.3 Clean seed에 포함되는 것 (R9-S2-0)

| 유지 (운영 seed) | 비움 (사용자 등록) |
|------|--------------------------|
| 공통코드 (`tb_common_code`) | 데이터 소스·매핑 |
| 시스템 설정 (`tb_system_config`) | 표준 데이터셋·표준 컬럼 |
| | Feature·Feature Set·Feature Recipe |
| | Dataset Version·Feature Build 결과 |
| | 학습 설정·모델·Registry·예측·Drift |
| | Pipeline Template·Pipeline Definition |
| | 지사·기상권역·캘린더·적재 데이터 |

**데모/test seed 없음:** `02_seed_demo.sql`은 제거되었습니다. `data/samples/` CSV는 테스트 fixture용이며 DB init에 사용되지 않습니다.

기존 볼륨에 PoC seed가 남아 있으면 `docker compose down -v` 후 재기동하거나, `scripts/reset_clean_deploy.py`로 정리합니다.

---

## 7. 접속 URL

| 용도 | URL |
|------|-----|
| **Frontend** | https://thermops.openlink.kr |
| **API** | https://thermops.openlink.kr/api/v1 |
| **API Docs** | https://thermops.openlink.kr/docs |
| Airflow UI | 기본 **비공개** — SSH 터널 (§9) |
| MLflow UI | 기본 **비공개** |
| MinIO Console | 기본 **비공개** |

---

## 8. 사용자 가이드 실습 시작 상태

Clean 배포 직후 UI에서 확인할 수 있는 상태:

1. **데이터 소스**: 등록된 소스 없음 — `/data/sources`에서 CSV·API·DB 소스 등록 후 매핑·적재
2. **표준 데이터셋**: 등록된 유형 없음 — `/standard-datasets`에서 등록 (물리 테이블 생성 Wizard는 R9-S2-1 후속)
3. **Feature Set / Recipe**: 빈 목록 — 사용자가 구성
4. **학습 / Registry / 예측 / Drift / 파이프라인**: 빈 목록
5. **대시보드**: 예측 이력 없음, Champion 모델 없음

회귀 테스트·로컬 검증 시에는 `scripts/test_fixtures.py`가 `TEST-*` ID로 테스트 플랫폼 데이터를 런타임 생성합니다.

→ [THERMOps_사용자가이드_근거자료.md](./THERMOps_사용자가이드_근거자료.md) §3 실습 시나리오대로 진행

---

## 9. 내부 서비스 접근 (운영자)

Postgres·Airflow·MLflow·MinIO는 host port를 열지 않습니다. 운영자 접근 예:

```bash
# Airflow UI → localhost:18080
ssh -L 18080:localhost:8080 user@<서버IP>
docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec airflow curl -s localhost:8080/health

# 서버에서 port-forward (SSH 없이 서버 쉘만 있는 경우)
docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec -it airflow bash
# 컨테이너 내부: curl localhost:8080

# MLflow
ssh -L 15000:mlflow:5000 user@<서버IP>  # 서버에서 docker network 접근 필요 시
# 또는 서버에서: docker compose exec backend curl http://mlflow:5000/health
```

---

## 10. Optional admin exposure

**기본 배포에 포함하지 않음.** 필요 시에만:

1. DNS CNAME 설정 (§2.3)
2. `.env.deploy` 수정:

```env
ENABLE_ADMIN_PUBLIC=true
AIRFLOW_HOST=airflow.thermops.openlink.kr
MLFLOW_HOST=mlflow.thermops.openlink.kr
MINIO_HOST=minio.thermops.openlink.kr
TRAEFIK_BASIC_AUTH_USERS=admin:$$apr1$$...   # htpasswd -nb admin 'password'
```

3. 기동:

```bash
docker compose -f docker-compose.traefik.yml -f docker-compose.traefik.admin.yml \
  --env-file .env.deploy up -d
```

| URL | 서비스 |
|-----|--------|
| https://airflow.thermops.openlink.kr | Airflow Web UI |
| https://mlflow.thermops.openlink.kr | MLflow |
| https://minio.thermops.openlink.kr | MinIO Console (:9001) |

**필수**: Basic Auth (`TRAEFIK_BASIC_AUTH_USERS`) 또는 Traefik IP allowlist middleware 추가.

---

## 11. 보안 주의사항

| 항목 | 현재 상태 |
|------|-----------|
| Frontend 권한 | `VITE_USER_ROLE` Mock (실제 인증 없음) |
| Backend API | JWT/SSO **미구현** — 공개 URL은 사내망·VPN 뒤 권장 |
| Postgres | internal network only |
| Airflow/MLflow/MinIO | 기본 외부 비공개 |
| 비밀번호 | `.env.deploy`는 git 제외, placeholder만 example에 포함 |
| Connector credential | DB/API 비밀번호 암호화 — 후속 과제 |

---

## 12. 문제 해결

### 12.1 Frontend 502 / blank

- `docker compose ... logs frontend`
- Traefik이 `thermops_internal` + `traefik` 네트워크에 frontend 연결됐는지 확인
- `THERMOPS_HOST`가 실제 DNS와 일치하는지 확인

### 12.2 API 호출 실패 (404)

- 브라우저 요청 URL이 `https://thermops.openlink.kr/api/v1/...` 인지 확인
- Traefik router `PathPrefix(/api)` — **strip prefix 사용 금지**
- `VITE_API_BASE_URL=/api/v1` 로 **재빌드** 필요 (`--build`)

### 12.3 CORS 오류

- `BACKEND_CORS_ORIGINS=https://thermops.openlink.kr` (프로토콜·호스트 정확히)
- backend 컨테이너 재시작

### 12.4 TLS 인증서 실패

- DNS A레코드 전파 확인
- Traefik `certresolver` 이름이 `.env.deploy`의 `TRAEFIK_CERT_RESOLVER`와 일치하는지
- 80 포트 HTTP challenge 가능 여부

### 12.5 Airflow/MLflow URL이 없는 이유

- **의도된 동작** — path prefix 없이 내부 전용
- DAG·학습은 `AIRFLOW_BASE_URL=http://airflow:8080` (컨테이너 간)으로 동작

### 12.6 CSV 적재 실패

- backend에 `/workspace` 마운트 확인 (`THERMOPS_PROJECT_ROOT=/workspace`)
- `data/samples/heat_demand_sample.csv` 파일 존재 확인

### 12.7 API 500 / `Name or service not known` (DB 연결)

증상: UI는 뜨지만 대시보드·목록 API가 500, backend 로그에 `socket.gaierror: Name or service not known`.

원인: `POSTGRES_PASSWORD`에 `@` 등이 포함되면 compose가 조합한 `DATABASE_URL`이 깨집니다.

```text
# 잘못된 예 (비밀번호 Open1234!@)
postgresql+asyncpg://thermops:Open1234!@@postgres:5432/thermops
                                      ↑ 호스트가 postgres가 아님
```

확인:

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec backend printenv DATABASE_URL
docker compose -f docker-compose.traefik.yml --env-file .env.deploy exec backend getent hosts postgres
```

조치 (최신 compose/backend 사용 시 특수문자 비밀번호도 지원):

```bash
git pull
python3 scripts/apply_dev_migrations.py
docker compose -f docker-compose.traefik.yml --env-file .env.deploy restart backend
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend airflow mlflow
```

`apply_dev_migrations.py`는 **호스트**에서 실행합니다. Ubuntu 등 Linux 서버는 `python` 대신 **`python3`** 를 사용하세요. 스크립트가 `docker exec`로 postgres 컨테이너에 SQL을 적용합니다 (`THERMOOPS_USE_DOCKER=1` 기본). backend 컨테이너에는 `scripts/`가 `/workspace/scripts`로 마운트되지만 Docker CLI가 없어 컨테이너 내부 실행은 권장하지 않습니다.

구버전이거나 급한 경우: 비밀번호에서 `@` 제거 후 `down -v`로 DB volume 재생성.

---

## 13. 배포·초기화 명령 요약

```bash
# 배포
cp .env.deploy.example .env.deploy   # 편집
docker compose -f docker-compose.traefik.yml --env-file .env.deploy config
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build

# 로그
docker compose -f docker-compose.traefik.yml --env-file .env.deploy logs -f backend frontend

# 완전 clean 재시작
docker compose -f docker-compose.traefik.yml --env-file .env.deploy down -v
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build

# 결과 데이터만 reset
THERMOPS_DEPLOY_ENV=clean python scripts/reset_clean_deploy.py --yes

# 기존 DB 볼륨 스키마 보완 (신규 테이블·컬럼, 예: tb_feature_lineage)
python3 scripts/apply_dev_migrations.py
docker compose -f docker-compose.traefik.yml --env-file .env.deploy restart backend
```

### 배포 후 회귀·API 검증 (선택)

배치 예측·Feature Dataset 기간 검증 변경 반영 후:

```bash
# API base — Traefik 공개 URL 또는 compose exec backend 환경
export THERMOOPS_API_BASE=https://thermops.openlink.kr/api/v1

python scripts/test_feature_dataset_range.py
python scripts/test_prediction_period_validation.py
python scripts/test_feature_metadata_consistency.py
python scripts/test_feature_lineage.py
python scripts/test_batch_prediction.py
python scripts/run_regression_tests.py --group model --timeout-scale 2
python scripts/run_regression_tests.py --group quick
```

`/predictions/jobs` UI: Feature Set별 Dataset 기간 표시, 최신 24시간 자동 설정, 범위 이탈 시 실행 차단.

`/features` UI: `calc_expression`은 **계산식 메모**(설명용). 등록만으로 학습에 반영되지 않음. 명칭 정책은 `docs/md/THERMOps_Feature_명칭_및_계산식_정책.md`.

---

## 14. 관련 파일

| 파일 | 설명 |
|------|------|
| `docker-compose.traefik.yml` | Traefik 배포 스택 (기본) |
| `docker-compose.traefik.admin.yml` | Optional CNAME admin exposure |
| `.env.deploy.example` | 환경 변수 템플릿 |
| `docs/md/THERMOps_Feature_명칭_및_계산식_정책.md` | Feature 공식 명칭·calc_expression·레거시 alias |
| `db/init/02_seed_clean.sql` | Clean 마스터/템플릿 seed |
| `db/init/02_seed_demo.sql` | Demo seed (개발·시연용, init 미사용) |
| `scripts/reset_clean_deploy.py` | 결과 테이블 TRUNCATE |
| `frontend/Dockerfile.prod` | Production nginx 이미지 |

---

## 15. 남은 보완 항목

- Backend API 인증·SSO 연동
- Connector credential 암호화
- Traefik IP allowlist middleware 운영 표준화
- MLflow/Airflow 이력 자동 purge 스크립트
- Health check 엔드포인트 및 모니터링 연동
- `ENABLE_ADMIN_PUBLIC` 시 MinIO API(:9000) vs Console(:9001) 분리 검토
