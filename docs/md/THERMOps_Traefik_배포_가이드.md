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

### 6.3 Clean seed에 포함되는 것

| 유지 | 비움 (clean seed에 없음) |
|------|--------------------------|
| 지사·기상권역·공통코드 | 적재 데이터 (`tb_heat_demand_actual`, `tb_weather_observation`) |
| CSV 소스 등록 (`DS-CSV-001/002`)·매핑 | Feature 생성 결과 (`tb_feature_dataset`) |
| Feature 정의·Feature Set 템플릿 | 학습·모델·Registry |
| Training Config 템플릿 (LGBM/CatBoost/2-Stage) | 예측·매칭·성능 지표 |
| 시스템 설정·캘린더 | 파이프라인·Drift·재학습 후보·품질 이력 |

Demo 데이터가 필요하면 `db/init/02_seed.sql` 내용을 별도 스크립트로 적용 (운영 배포 기본 아님).

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

1. **데이터 소스**: `DS-CSV-001`, `DS-CSV-002` 등록됨, **최근 적재 없음**
2. **Feature Set**: `FS-TPL-LAG-ROLL` 등 템플릿 존재, Feature 생성 이력 없음
3. **학습 설정**: `TRC-TPL-LAG-ROLL`, `TRC-TPL-CATBOOST`, `TRC-TPL-TWO-STAGE-CATBOOST` 존재, 학습 작업 없음
4. **Registry / 예측 / Drift / 파이프라인**: 빈 목록
5. **대시보드**: 예측 이력 없음, Champion 모델 없음

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
```

---

## 14. 관련 파일

| 파일 | 설명 |
|------|------|
| `docker-compose.traefik.yml` | Traefik 배포 스택 (기본) |
| `docker-compose.traefik.admin.yml` | Optional CNAME admin exposure |
| `.env.deploy.example` | 환경 변수 템플릿 |
| `db/init/02_seed_clean.sql` | Clean 마스터/템플릿 seed |
| `db/init/02_seed.sql` | Demo seed (개발·시연용, traefik init 미사용) |
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
