# THERMOps R11-S7-5 Option C Run-Worker 전환 검토

> **문서 유형**: 설계 / 검토 (구현 없음)  
> **작성 기준**: `master` @ R11-S7-4 (`cef1c6d`) 완료 시점  
> **범위**: Option B BackgroundTasks 한계 정리, Option C 별도 VP run-worker 필요성·아키텍처·DB/claim/heartbeat·배포·테스트·로드맵  
> **비범위**: run-worker 구현, DB polling 구현, queue/Redis/Celery, POST/GET `/runs` 동작 변경, DB migration, FE, Schedule Activation, due worker 연결, R10 `run_load` 변경, package 변경  
> **후속**: R11-S7-6 VP run-worker PoC (별도 승인)

관련 문서:

- `docs/md/THERMOps_R11-S7-2_Background_Run_전환_검토.md`
- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md`
- `docs/md/THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md`
- README R11-S7-3 / S7-4

---

## 1. 배경과 목적

### 1.1 S7-3 Option B 현재 상태 (구현됨)

| 항목 | 내용 |
|------|------|
| API | `POST /api/v1/visual-pipelines/{pipeline_id}/runs` → **HTTP 202** |
| Persistence | `tb_visual_pipeline_run` — `execution_mode=BACKGROUND`, 초기 `run_status=PENDING` |
| Executor | FastAPI **BackgroundTasks** (backend process 내부) |
| Task session | request-scoped DB **미전달** — task가 `async_session()`으로 새 세션 오픈 |
| 상태 전이 | PENDING → RUNNING(+`started_at`) → SUCCESS / PARTIAL / FAILED(+`finished_at`) |
| Polling | `GET .../runs/{run_id}` · `poll_url` · `GET .../runs` 목록 |
| Concurrent | 동일 pipeline에 PENDING/RUNNING 있으면 **409** `RUN_CONCURRENT_RUN_EXISTS` |
| 안전 | `schedule active_yn` 미변경 · due worker 미연결 · sync/materialization status 미변경 |
| 테스트 | `scripts/test_visual_pipeline_manual_run.py` (quick **미포함**) |

실행은 **오직** `POST /runs` 접수 후 background task에서만 발생한다.  
compile / materialize / GET / 페이지 로드는 실행을 시작하지 않는다.

### 1.2 S7-4 Studio Run UI (구현됨)

| 항목 | 내용 |
|------|------|
| Run Now | 조건부 활성화 + confirm → POST 202 |
| Polling | GET `/runs/{id}` · interval 1s · timeout 90s |
| Latest | list `limit=1` → detail · PENDING/RUNNING이면 자동 polling 재개 |
| Panel | status / visual_run_id / load_run_id / result / issues / safety |
| Schedule Activation | **disabled + Soon** 유지 |
| Known limitation UI | Option B stuck(재시작) 안내 문구 |

S7-4는 **polling / background-ready** 계약을 이미 사용한다.  
Option C로 executor만 바꿔도 UI 재작성이 최소화된다.

### 1.3 Option B 한계

| 한계 | 설명 |
|------|------|
| Process restart | backend 재시작 시 PENDING/RUNNING **stuck** · task 유실 |
| Multi-instance | uvicorn multi-worker / multi-container에서 실행 관리 취약 |
| Heartbeat 없음 | 장시간 RUNNING 생존 여부 판별 불가 |
| Claim/lock 없음 | 동일 run 이중 실행 방지 수단이 process 내부에 의존 |
| Retry/requeue 없음 | 실패·유실 후 자동 재시도 정책 없음 |
| Graceful shutdown | 진행 중 run을 안전하게 drain하기 어려움 |
| Long-running | pagination/write 장기화 시 lease/heartbeat 부재로 운영 취약 |
| Schedule Activation | 자동 실행 run을 붙이면 Option B로는 안정성 부족 |

README/S7-3 known limitation과 동일: **자동 recovery/heartbeat/claim은 Option C 후속**.

### 1.4 S7-5 목적

1. Option C **별도 VP run-worker**가 필요한 이유를 고정한다.  
2. DB claim / lock / heartbeat 후보와 S7-6 최소 migration 범위를 정한다.  
3. POST 202 + GET polling **계약을 유지**한 채 executor만 교체하는 전략을 수립한다.  
4. S7-6 PoC 범위·테스트·배포를 S7-6에서 바로 구현 가능 수준으로 구체화한다.  
5. **Schedule Activation 전에** Manual Run 실행 기반을 안정화할 기준을 남긴다.  
6. **본 단계는 docs-only** — 구현·migration·API/FE 변경 없음.

---

## 2. Option B vs Option C 비교

| 항목 | Option B BackgroundTasks | Option C 별도 run-worker |
|------|--------------------------|--------------------------|
| 실행 위치 | backend process 내부 | 별도 worker process/container |
| POST timeout 회피 | 가능 | 가능 |
| 프로세스 재시작 복구 | 약함 | 설계 가능 |
| stuck RUNNING 처리 | 수동/문서화 | heartbeat/lock TTL 가능 |
| 멀티 인스턴스 | 취약 | claim/lock으로 안전화 가능 |
| retry/requeue | 제한 | 가능 |
| Schedule Activation 대응 | 위험 | 적합 |
| 구현 복잡도 | 낮음 | 중간~높음 |
| 운영 적합성 | PoC / transitional | 운영 지향 |

### 결론

- S7-3/S7-4까지는 Option B로 **충분**했다 (non-blocking UX·polling 계약 검증).  
- **Schedule Activation 전**에 Option C 검토·PoC가 필요하다.  
- UI/API 계약은 유지하고 **executor만 바꾸는 phased migration**이 바람직하다.  
- Queue / Redis / Celery는 **도입하지 않는다** — DB polling worker로 충분하다.

---

## 3. 권장 결론

| 단계 | 내용 |
|------|------|
| **S7-5** | docs-only 검토 (본 문서) |
| **S7-6** | Option C **VP run-worker PoC** 구현 |
| **S7-7** | Schedule Activation **설계** |
| **S7-8** | Schedule Activation **PoC** |
| **S7-9** | retry / cancel / progress / audit / notification hardening |

기본 권장:

- POST `/runs`는 계속 **202 + PENDING run object + `poll_url`**.  
- GET `/runs/{id}` polling 계약 **유지**.  
- Studio Run UI(S7-4)는 **변경 최소화**.  
- S7-6에서 BackgroundTasks는 **feature flag**로 worker mode와 병행 후, 운영은 worker로 수렴.  
- Schedule Activation은 **S7-6 검증 이후** S7-7에서 설계.

단기 대안:

- S7-6을 생략하고 Activation 설계만 먼저 진행하는 것은 **가능**하나,  
  Activation **PoC 구현**은 Option C 이후를 **권장**한다.

---

## 4. 목표 아키텍처

```
Studio Run Now
  → POST /api/v1/visual-pipelines/{pipeline_id}/runs
      - precondition 검증
      - tb_visual_pipeline_run PENDING 생성 (+ commit)
      - 202 + poll_url 반환
      - (worker mode) BackgroundTasks 미등록
  → VP Run Worker (vp-run-worker)
      - PENDING run claim (FOR UPDATE SKIP LOCKED)
      - RUNNING 전이 + claim/lock/heartbeat
      - R10 run_load 호출 (기존 서비스 재사용, 대규모 리팩터 금지)
      - SUCCESS / FAILED / PARTIAL 저장
  → Studio
      - GET /runs/{run_id} polling
      - terminal 결과 표시
```

### 경계

| 주체 | 역할 |
|------|------|
| Backend API | enqueue만 (PENDING row + 202). compile/materialize/Run 실행 아님 |
| VP Run Worker | Manual(및 후속 Scheduled) Visual Pipeline run의 **유일한** `run_load` 실행자 (worker mode) |
| GET | 조회만 — 실행 시작 금지 |
| R10 `run-due-worker` | **data_load_schedule** due 처리만. VP Manual Run **미처리** |
| Schedule Activation | S7-7+ — Manual Run과 분리 |

---

## 5. DB / Schema 설계 후보

### 5.1 현재 `tb_visual_pipeline_run` (S7-1~S7-4)

`visual_run_id`, `pipeline_id`, `compile_result_id`, `materialization_result_id`, `graph_version_hash`, `load_run_id`, `mode`, `execution_mode`, `run_status`, `request_json`, `result_json`, `issues_json`, `error_message`, `started_at`, `finished_at`, `created_at`

인덱스(현행): `(pipeline_id, created_at DESC)`, `(pipeline_id, run_status)`

### 5.2 Option C 확장 후보 컬럼

| 컬럼 | 용도 | S7-6 PoC |
|------|------|----------|
| `claimed_at` TIMESTAMP NULL | claim 시각 | **필수 후보** |
| `claimed_by` VARCHAR NULL | worker_id | **필수 후보** |
| `locked_until` TIMESTAMP NULL | lease 만료 | **필수 후보** |
| `heartbeat_at` TIMESTAMP NULL | 생존 신호 | **필수 후보** |
| `attempt_count` INT DEFAULT 0 | claim/재시도 횟수 | **필수 후보** |
| `max_attempts` INT DEFAULT 1 | 재시도 상한 | 후속 |
| `next_retry_at` TIMESTAMP NULL | 재시도 예약 | 후속 |
| `last_error_code` VARCHAR NULL | 요약 코드 | 후속 |
| `progress_json` JSONB NULL | step progress | 후속 |
| `current_step` VARCHAR NULL | 현재 step | 후속 |
| `cancel_requested_yn` BOOLEAN DEFAULT FALSE | cancel | 후속 |
| `idempotency_key` VARCHAR NULL | 멱등 | 후속 |

### 5.3 Migration 구분

| 구분 | 내용 |
|------|------|
| **S7-5 (본 단계)** | migration **하지 않음** |
| **S7-6 PoC 필수 후보** | `claimed_at`, `claimed_by`, `locked_until`, `heartbeat_at`, `attempt_count` (+ 인덱스) |
| **후속 hardening** | retry/progress/cancel/idempotency 컬럼 |

인덱스 후보 (S7-6):

- `(run_status, created_at)` — PENDING claim 순서  
- `(run_status, locked_until)` — expired RUNNING 복구  
- 기존 `(pipeline_id, run_status)` 유지  

**S7-6에서 실제 ALTER는 별도 승인** 후에만 적용한다.

---

## 6. Claim / Lock 설계

### 6.1 권장 claim 흐름

1. Worker가 `PENDING`을 `created_at ASC`로 조회.  
2. PostgreSQL `FOR UPDATE SKIP LOCKED`로 1건(또는 batch=1) pick.  
3. Claim 시 원자적 UPDATE:
   - `run_status = 'RUNNING'`
   - `claimed_at = now`
   - `claimed_by = worker_id`
   - `locked_until = now + lock_ttl`
   - `heartbeat_at = now`
   - `attempt_count = attempt_count + 1`
   - `started_at = COALESCE(started_at, now)`
4. 다른 worker는 동일 row를 claim하지 못함.

### 6.2 Pseudo SQL

```sql
WITH picked AS (
  SELECT visual_run_id
  FROM tb_visual_pipeline_run
  WHERE run_status = 'PENDING'
    AND (next_retry_at IS NULL OR next_retry_at <= NOW())  -- S7-6에서는 next_retry_at 없이 PENDING만도 가능
  ORDER BY created_at ASC
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE tb_visual_pipeline_run r
SET run_status = 'RUNNING',
    claimed_at = NOW(),
    claimed_by = :worker_id,
    locked_until = NOW() + (:lock_ttl_seconds || ' seconds')::interval,
    heartbeat_at = NOW(),
    attempt_count = COALESCE(attempt_count, 0) + 1,
    started_at = COALESCE(started_at, NOW())
FROM picked
WHERE r.visual_run_id = picked.visual_run_id
RETURNING r.*;
```

### 6.3 구현 방식 (S7-6)

- SQLAlchemy Core/ORM 트랜잭션으로 구현 가능하면 우선.  
- `SKIP LOCKED`가 ORM로 번거로우면 **raw SQL / text()** 허용.  
- R10 `run_due_worker_lock_service` 패턴을 **참고만** 하고, 테이블·서비스는 **분리**.

---

## 7. Heartbeat / Stuck Recovery

### 7.1 Heartbeat

| 단계 | 정책 |
|------|------|
| **S7-6 PoC** | run 시작 시 `locked_until` / `heartbeat_at` 설정 · 완료 시 terminal · **별도 heartbeat coroutine 없음** (run_load blocking 가정) |
| **S7-6+ hardening** | heartbeat task로 `locked_until` 연장 · crash 감지 |

`THERMOOPS_VP_RUN_WORKER_LOCK_TTL_SECONDS` / `MAX_RUNTIME_SECONDS`로 상한을 둔다.

### 7.2 Stuck Recovery

| 상태 | 후보 처리 |
|------|-----------|
| 오래된 PENDING | 재claim (worker가 계속 poll) |
| RUNNING & `locked_until < now` | S7-6: startup 시 **FAILED mark 옵션**(default dry-run/report) 검토 · 운영 hardening에서 requeue/STALE |
| Option B 잔여 stuck | worker mode 전환 전 수동/문서 정리 |

권장: S7-6는 **minimal recovery**만. 자동 requeue·STALE 상태는 후속.

---

## 8. Worker 프로세스 설계

### 8.1 파일 후보

| 경로 | 역할 |
|------|------|
| `scripts/run_visual_pipeline_worker.py` | CLI entry (once/loop) |
| `backend/app/workers/visual_pipeline_run_worker.py` | loop/claim/run 본체 (선택) |
| `backend/app/services/visual_pipeline/run_worker_service.py` | claim + execute 오케스트레이션 (선택) |

### 8.2 환경 변수 후보

| 변수 | 예시 | 설명 |
|------|------|------|
| `THERMOOPS_VP_RUN_WORKER_ENABLED` | `false` | worker 프로세스 enable |
| `THERMOOPS_VP_RUN_WORKER_MODE` | `loop` / `once` | 실행 모드 |
| `THERMOOPS_VP_RUN_WORKER_POLL_INTERVAL_SECONDS` | `5` | loop 간격 |
| `THERMOOPS_VP_RUN_WORKER_LOCK_TTL_SECONDS` | `120` | lease |
| `THERMOOPS_VP_RUN_WORKER_MAX_BATCH_SIZE` | `1` | claim 개수 |
| `THERMOOPS_VP_RUN_WORKER_ID` | `auto` | claimed_by |
| `THERMOOPS_VP_RUN_WORKER_MAX_RUNTIME_SECONDS` | `300` | run 상한(정책) |
| `THERMOOPS_VP_RUN_EXECUTOR` | `background_tasks` \| `worker` | API enqueue 후 executor 선택 |

### 8.3 Docker Compose 서비스 후보

```yaml
# 후보 — S7-6에서 추가 (본 문서는 구현하지 않음)
vp-run-worker:
  build:
    context: ./backend
  container_name: thermops-vp-run-worker
  environment:
    DATABASE_URL: postgresql+asyncpg://thermops:thermops@postgres:5432/thermops
    THERMOOPS_VP_RUN_WORKER_ENABLED: "true"
    THERMOOPS_VP_RUN_WORKER_MODE: loop
    THERMOOPS_VP_RUN_WORKER_POLL_INTERVAL_SECONDS: "5"
    THERMOOPS_VP_RUN_WORKER_LOCK_TTL_SECONDS: "120"
    THERMOOPS_VP_RUN_WORKER_MAX_BATCH_SIZE: "1"
    THERMOOPS_VP_RUN_EXECUTOR: worker
  depends_on:
    postgres:
      condition: service_healthy
    backend:
      condition: service_started
  command: python scripts/run_visual_pipeline_worker.py --mode loop
  restart: unless-stopped
  # Traefik 노출 없음
```

배포 명령 후보:

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend frontend vp-run-worker
docker compose -f docker-compose.traefik.yml --env-file .env.deploy logs -f vp-run-worker
```

### 8.4 `run-due-worker` vs `vp-run-worker`

| | `run-due-worker` | `vp-run-worker` |
|--|------------------|-----------------|
| 대상 | R10 `tb_data_load_schedule` due | `tb_visual_pipeline_run` PENDING |
| API | `/api/v1/run-due-worker/*`, `run-due` | Visual Pipeline `/runs` enqueue 결과 소비 |
| Manual Run | **처리하지 않음** | Manual Run(및 후속 Scheduled VP run) 처리 |
| Schedule Activation | R10 schedule active와 연계 가능 | VP Activation(S7-7+)과 연계 예정 · **혼합 금지** |

두 worker를 **코드 경로·컨테이너·env·락 테이블에서 분리**한다.

---

## 9. POST `/runs` 변경 전략

| Strategy | 내용 | 평가 |
|----------|------|------|
| 1. worker 기본 전환 | BackgroundTasks 제거 · worker만 | 명확하나 worker 미기동 시 PENDING stuck |
| 2. **feature flag** | `THERMOOPS_VP_RUN_EXECUTOR=background_tasks\|worker` | **권장** — 전환기 안전 |
| 3. fallback | worker 없으면 BackgroundTasks | 경계 흐림 · **비권장** |

### 권장 (S7-6)

- **feature flag** 도입.  
- **개발 default:** `background_tasks` 가능 (worker 없이 Studio E2E/로컬 편의).  
- **운영 목표:** `worker` — Compose에 `vp-run-worker` 필수 · README에 명시.  
- worker mode에서 POST는 PENDING만 생성하고 **BackgroundTasks 미등록**.  
- 어느 모드든 응답 계약은 **202 + PENDING(+poll_url)** 유지.

---

## 10. API / UI 영향

### API 계약 유지

| API | 계약 |
|-----|------|
| POST `/runs` | **202** + BACKGROUND + PENDING + `poll_url` |
| GET `/runs/{id}` | polling · terminal 시 result/issues |
| GET `/runs` | latest / concurrent 판단 |
| Precondition | 409/400 코드 유지 |

### UI (S7-4)

- polling 로직 **유지** — worker mode에서도 동일.  
- worker 미기동 시 PENDING 장기화 → Panel 안내에 “worker 기동 확인” 문구를 **S7-6에서 소폭 보강 가능**.  
- Schedule Activation 버튼은 계속 disabled + Soon.  
- S7-6에서 FE **필수 아님** (backend worker test 중심).

---

## 11. Schedule Activation과의 관계

- Activation은 **본 문서·S7-6에서 구현하지 않는다**.  
- Option C run-worker는 Activation의 **선행 기반**이다.  
- 후속 Scheduled Run 권장 형태:
  - Activation이 `active_yn` 등을 변경하고, due/trigger가 **`tb_visual_pipeline_run` PENDING**을 생성  
  - **VP run-worker**가 `run_load` 실행  
  - R10 due worker가 VP Manual Run을 직접 실행하는 구조는 **비권장**  
- Manual vs Scheduled는 `mode` / `trigger_type`(후속 컬럼)으로 구분.  
- S7-7에서 `schedule_id`, activation status, scheduled run provenance를 별도 설계.

---

## 12. Error / Retry 정책

### S7-6 PoC

- runtime failure → `FAILED` (+ issues)  
- **자동 retry 없음**  
- 동일 pipeline PENDING/RUNNING → POST **409** 유지  
- terminal 후 신규 Manual Run으로 재실행  

### 후속

- `attempt_count` / `max_attempts` / `next_retry_at`  
- failed run clone vs 동일 row requeue 정책  
- `idempotency_key` · dead letter  

### 상태

| 상태 | S7-6 |
|------|------|
| PENDING / RUNNING / SUCCESS / FAILED / PARTIAL / CANCELLED | 유지 |
| STALE / EXPIRED | **후속 검토** — S7-6에서 추가하지 않음 |

---

## 13. 테스트 전략 (S7-6)

필수 시나리오 후보:

1. POST → PENDING only (worker mode)  
2. Worker once: PENDING → RUNNING → SUCCESS  
3. GET polling → SUCCESS  
4. Worker 부재 → PENDING 유지  
5. Concurrent worker claim — 이중 실행 없음  
6. RUNNING fixture → POST 409  
7. Expired RUNNING policy (구현 시에만)  
8. Runtime failure → FAILED  
9. `schedule active_yn` / sync / materialization **불변**  
10. due worker **미호출**  
11. quick **미포함**

테스트 파일 후보:

- `scripts/test_visual_pipeline_run_worker.py` (신규, side effect → quick 제외)  
- 기존 `test_visual_pipeline_manual_run.py` — API/polling 계약 regression 유지  

E2E: S7-4 Studio E2E는 worker mode에서 `vp-run-worker` 기동 필요. S7-6 FE E2E는 **비필수**.

---

## 14. 운영 / 배포 영향

- Compose / Traefik compose에 `vp-run-worker` 서비스 추가 후보  
- Traefik **미노출**  
- `.env.deploy` / `.env.example`에 worker·executor env 추가 후보  
- clean reset 시 worker 포함 재기동  
- **worker 미기동 + executor=worker** → POST 후 PENDING stuck — 운영 문서에 명시  

---

## 15. Observability / Admin

### S7-6 최소

- 구조화 로그: `worker_id`, `visual_run_id`, claim/finish  
- DB 컬럼으로 claim/heartbeat 확인  
- 기존 GET runs 목록으로 상태 확인  

### 후속

- worker summary API · stuck admin · retry/cancel · metrics · notification  
- R10 run-due-worker admin API를 **과도하게 복제하지 않음**

---

## 16. 로드맵 업데이트

S7-2 문서의 구 번호(S7-5=history, S7-6=Activation)를 **본 문서 기준으로 재번호화**한다.

| 단계 | 내용 |
|------|------|
| **R11-S7-5** | Option C run-worker 검토 (**본 문서**, docs-only) |
| **R11-S7-6** | VP run-worker PoC — feature flag · claim/lock 최소 · once/loop · migration(승인 후) · backend test |
| **R11-S7-7** | Schedule Activation 설계 — activation status · schedule_id · manual vs scheduled |
| **R11-S7-8** | Schedule Activation PoC |
| **R11-S7-9** | retry / cancel / progress / audit / notification hardening |

S7-6 검증 전 Activation PoC(구 “바로 Activation”)는 **권장하지 않음**.

---

## 17. Decision Log

| ID | 결정 |
|----|------|
| **D1** | Schedule Activation PoC 전 Option C run-worker를 먼저 검토한다. |
| **D2** | S7-6에서 VP run-worker PoC를 구현한다. |
| **D3** | S7-4 polling UI 계약은 유지한다 (변경 최소화). |
| **D4** | Manual Run 실행은 due worker가 아니라 **VP run-worker**가 담당한다 (worker mode). |
| **D5** | R10 `run-due-worker`와 `vp-run-worker`는 **분리**한다. |
| **D6** | S7-6 최소 migration은 `claimed_at` / `claimed_by` / `locked_until` / `heartbeat_at` / `attempt_count` 중심. |
| **D7** | Retry / cancel / progress는 S7-6 PoC에서 **제외 또는 최소화**. |
| **D8** | POST `/runs`는 계속 **202 + PENDING** run object (+ `poll_url`). |
| **D9** | worker 미기동 시 PENDING stuck 가능성을 운영 문서에 명시한다. |
| **D10** | quick group에 worker test를 **포함하지 않는다**. |
| **D11** | Queue / Redis / Celery **도입하지 않음** (DB claim worker). |
| **D12** | POST executor는 **feature flag** (`background_tasks` \| `worker`); 운영 목표는 worker. |
| **D13** | S7-5는 **docs-only** — migration/API/FE/worker 구현 없음. |
| **D14** | Activation은 **S7-6 검증 후** S7-7 설계. |

---

## 18. S7-6 구현 체크리스트 (참고, 본 단계 미구현)

- [ ] migration: claim/lock/heartbeat/attempt 컬럼 + 인덱스  
- [ ] `THERMOOPS_VP_RUN_EXECUTOR` flag  
- [ ] worker mode에서 BackgroundTasks 미등록  
- [ ] claim SQL / service  
- [ ] `scripts/run_visual_pipeline_worker.py` once/loop  
- [ ] Compose `vp-run-worker`  
- [ ] `test_visual_pipeline_run_worker.py`  
- [ ] README 운영 안내 (worker 필수·stuck)  
- [ ] (선택) Studio PENDING 장기화 안내 문구  

---

## 19. 본 문서 범위 확인

| 항목 | S7-5 |
|------|------|
| run-worker 구현 | **없음** |
| DB polling 구현 | **없음** |
| POST/GET 동작 변경 | **없음** |
| DB/schema/migration | **없음** |
| FE | **없음** |
| Schedule Activation | **없음** |
| due worker 연결 | **없음** |
| R10 `run_load` 변경 | **없음** |
| package | **없음** |

---

*문서 끝 — R11-S7-5 Option C Run-Worker 전환 검토*
