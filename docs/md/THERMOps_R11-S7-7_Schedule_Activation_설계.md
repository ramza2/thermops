# THERMOps R11-S7-7 Schedule Activation 설계

> **문서 유형**: 설계 / 검토 (구현 없음)  
> **작성 기준**: `master` @ R11-S7-6 (`40a4fe3`) 완료 시점  
> **범위**: Visual Pipeline Schedule Activation의 상태·provenance·due trigger·scheduled run 생성·worker 연계·UI/API 계약 확정  
> **비범위**: Activation API/UI 구현, DB/schema/migration, VP run-worker 변경, run-due-worker 변경, R10 `run_load` 변경, Redis/Celery/queue, package, Auth, cancel/retry/progress  
> **후속**: R11-S7-8 Schedule Activation PoC (별도 승인)

관련 문서:

- `docs/md/THERMOps_R11-S7-5_Option_C_Run_Worker_검토.md`
- `docs/md/THERMOps_R11-S7-2_Background_Run_전환_검토.md`
- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md`
- `docs/md/THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md`
- README R11-S7-3 / S7-4 / S7-5 / S7-6

---

## 1. 배경 정리

### 1.1 현재 상태

| 단계 | 상태 | 요약 |
|------|------|------|
| R11-S6 | 완료 | Visual Pipeline graph compile / materialization |
| R11-S7-1~S7-4 | 완료 | Manual Run API + Studio polling UI |
| R11-S7-5 | 완료 (docs) | Option C run-worker 전환 검토 |
| R11-S7-6 | 완료 | VP run-worker PoC (`THERMOOPS_VP_RUN_EXECUTOR`) |
| Schedule Activation UI | **미구현** | Studio 버튼 **disabled + Soon** |
| Manual Run | 구현됨 | 사용자 Run Now → `POST /runs` → PENDING → executor |
| Schedule Activation | **미구현** | CRON 기반 자동 반복 실행 허용 기능 |

### 1.2 Manual Run vs Schedule Activation

| | Manual Run | Schedule Activation |
|--|------------|---------------------|
| 트리거 | 사용자 버튼 (즉시 1회) | CRON due 시점 (자동·반복) |
| API | `POST .../runs` | Activation API (후속) + due enqueue |
| run row | `mode=MANUAL` | `mode=SCHEDULED` |
| 실행자 | BackgroundTasks 또는 **VP run-worker** | **VP run-worker만** (권장) |
| schedule active | 변경하지 않음 | activation 상태로 관리 |

### 1.3 핵심 방향

1. **Schedule Activation은 `run_load`를 직접 실행하지 않는다.**
2. Schedule trigger는 `tb_visual_pipeline_run`을 **PENDING**으로 생성한다.
3. 실제 실행은 **VP run-worker**가 claim하여 수행한다.
4. Studio UI는 scheduled run도 기존 `GET /runs` · `GET /runs/{id}`로 확인한다.
5. Manual / Scheduled는 **`mode` provenance**로 구분한다.
6. 기존 R10 **`run-due-worker`와 혼동하지 않는다.**

---

## 2. 용어와 경계 정의

| 용어 | 정의 |
|------|------|
| **Compile** | Visual Pipeline graph를 실행 가능한 R10 설정 후보로 변환 |
| **Materialization** | Compile 결과를 R10 설정 row로 생성/갱신 (`active_yn=false` 유지) |
| **Manual Run** | Studio **Run Now**로 사용자가 즉시 실행 (`mode=MANUAL`) |
| **Schedule Activation** | materialized schedule을 활성화하여 CRON 기반 자동 trigger를 허용 |
| **Scheduled Run** | 활성화된 schedule에 의해 자동 생성된 run (`mode=SCHEDULED`) |
| **VP Run Worker** | `tb_visual_pipeline_run` PENDING을 claim하고 R10 `run_load` 실행 |
| **VP Schedule Worker** | ACTIVE activation의 due를 탐지하고 PENDING scheduled run을 enqueue |
| **R10 run-due-worker** | R10 `tb_data_load_schedule` due 처리 전용. VP Scheduled Run과 **직접 혼합하지 않음** |

### 경계

| 구분 | 내용 |
|------|------|
| Activation | schedule을 **켜는** 행위 — 즉시 `run_load` 금지 |
| Scheduled Run | activation 이후 due 시점에 생성되는 **실행 이력** |
| Manual Run | activation 상태와 **독립**적으로 가능 |
| Scheduled Run 생성 | activation이 **ACTIVE**일 때만 |
| `materialization.activation` | **mirror/표시용** — 권위 상태는 activation table |

---

## 3. 권장 아키텍처

```text
Studio Schedule Activation
  → POST /api/v1/visual-pipelines/{pipeline_id}/schedule-activations
      - precondition 검증
      - tb_visual_pipeline_schedule_activation ACTIVE 저장
      - materialization.activation mirror 갱신 (표시용)
      - (선택) R10 schedule active_yn 정책 — S7-8에서 명시
      - 즉시 run_load 실행 안 함
      - 200 + activation object 반환

VP Schedule Worker (due trigger)
  → ACTIVE activation 중 next_due_at <= now 탐지
  → tb_visual_pipeline_run row 생성
      - run_status=PENDING
      - execution_mode=BACKGROUND
      - mode=SCHEDULED
      - activation_id / r10_schedule_id / scheduled_for / dedup_key
  → next_due_at / last_triggered_at / trigger_count 갱신

VP Run Worker
  → PENDING run claim (Manual + Scheduled 동일)
  → RUNNING → R10 run_load → SUCCESS / FAILED / PARTIAL

Studio
  → Activation Panel (status / next_due / deactivate)
  → Run list/detail — Manual vs Scheduled 표시
  → GET /runs polling 계약 유지
```

### 책임 분리

| 컴포넌트 | 책임 | 비책임 |
|----------|------|--------|
| Activation API | 켜기/끄기 · precondition | `run_load` · due enqueue |
| `vp-schedule-worker` | due 감지 · PENDING enqueue | `run_load` 실행 |
| `vp-run-worker` | PENDING claim · `run_load` | due 계산 · activation 변경 |
| R10 `run-due-worker` | R10 data_load_schedule only | VP scheduled run |
| Studio Run UI | list/detail polling | Activation 로직과 분리 |
| Studio Activation UI | activate/deactivate · status | Run Now와 분리 |

---

## 4. DB / Schema 설계 후보

> **S7-7에서는 migration하지 않는다.** 아래는 S7-8 PoC용 설계 후보다.

### 4.1 기존 관련 테이블

| 테이블 | 역할 (현재) |
|--------|-------------|
| `tb_visual_pipeline_run` | Manual/Background run · `mode` 기본 `MANUAL` · claim/lock 컬럼(S7-6) |
| `tb_visual_pipeline_compile_result` | compile 이력 |
| `tb_visual_pipeline_materialization_result` | materialize 이력 · `activation=NOT_REQUESTED` (표시) |
| `tb_data_load_schedule` | R10 schedule · `cron_expression` · `timezone` · `next_run_at` · `active_yn` |
| `tb_data_load_schedule_run` | R10 scheduled load 이력 — **VP Scheduled Run 기본 경로에 강제 사용하지 않음** |

### 4.2 Activation 저장 대안

#### A안: materialization_result에 activation 상태 포함

| 장점 | 단점 |
|------|------|
| 구현 단순 | 이력/재활성 추적 약함 |
| Materialization과 직접 연결 | provenance·감사에 불리 |

#### B안: 별도 activation table (권장)

`tb_visual_pipeline_schedule_activation`

**S7-8 최소 컬럼:**

| 컬럼 | 설명 |
|------|------|
| `activation_id` | PK |
| `pipeline_id` | Visual Pipeline |
| `materialization_result_id` | 대상 materialization |
| `compile_result_id` | 참조 (optional/최소 포함 권장) |
| `r10_schedule_id` | materialized R10 schedule |
| `activation_status` | `INACTIVE` / `ACTIVE` / `PAUSED` / `ERROR` |
| `activated_at` | 활성 시각 |
| `deactivated_at` | 비활성 시각 |
| `next_due_at` | 다음 due |
| `last_triggered_at` | 마지막 enqueue 시각 |
| `trigger_count` | enqueue 횟수 |
| `created_at` / `updated_at` | 감사 최소 |
| `metadata_json` | cron snapshot · timezone · graph hash 등 |

**후속 컬럼 후보:** `created_by` · `reason` · `paused_at` · `last_due_at` · `graph_version_hash` · error detail

**권장:** **B안**. `materialization_result.activation`은 **mirror/표시용**으로만 유지·갱신.

### 4.3 `tb_visual_pipeline_run` 확장 후보

| 컬럼 | S7-8 | 설명 |
|------|------|------|
| `mode` | **확장** | 기존 `MANUAL` + **`SCHEDULED`** (별도 `trigger_type` 컬럼 우선 불필요) |
| `activation_id` | 권장 | Scheduled Run 연결 |
| `r10_schedule_id` | 권장 | SoT 참조 |
| `scheduled_for` | 권장 | due slot |
| `triggered_at` | 선택 | enqueue 시각 (없으면 `created_at`로도 가능) |
| `dedup_key` | **권장** | 중복 enqueue 방지 |
| `trigger_source` | 후속 | `VP_SCHEDULE_WORKER` 등 |

**`mode` vs `trigger_type`:**  
기존 스키마에 `mode`가 이미 있으므로 **`mode` 확장 우선**. `trigger_type` 병행은 후속 여유 시.

**`dedup_key`:**  
형식 후보 `VP-SCHEDULED:{activation_id}:{scheduled_for_iso}`  
S7-8에서 **컬럼 + UNIQUE index 권장** (service exists-check만으로는 race에 취약).

---

## 5. Activation 상태 모델

### 5.1 상태

| 상태 | 의미 |
|------|------|
| `INACTIVE` | 비활성 (기본·deactivate 후) |
| `ACTIVE` | due enqueue 허용 |
| `PAUSED` | 일시 중지 (enqueue 금지) — **S7-9** |
| `ERROR` | mismatch/invalid — enqueue 금지 |

표시/legacy mirror (`materialization.activation`):

- `NOT_REQUESTED` → 아직 activation 없음
- Activation 후 mirror: `ACTIVE` / `INACTIVE` 등 (S7-8에서 매핑 확정)

### 5.2 전이 (목표)

```text
INACTIVE → ACTIVE     : activate
ACTIVE   → PAUSED     : pause      (S7-9)
PAUSED   → ACTIVE     : resume     (S7-9)
ACTIVE|PAUSED → INACTIVE : deactivate
ACTIVE   → ERROR      : schedule/materialization mismatch 등
ERROR    → ACTIVE     : 해결 후 reactivate (후속)
```

### 5.3 S7-8 PoC 범위

- **구현:** activate / deactivate / current·history 조회
- **API shape만 설계·또는 미구현:** pause / resume
- Compile / Materialization 상태와 **분리**
- `current_sync_status=STALE` → activation **불가**
- materialization `STALE`/`FAILED` → activation **불가**
- 활성 후 graph 변경(STALE active):
  - **S7-8:** precondition으로 신규 activation만 막고, 기존 ACTIVE는 UI/API **경고** (“STALE active schedule”)
  - **자동 비활성화:** S7-9 이후

---

## 6. Precondition 설계

Activation 성공 전 검증 후보:

| # | Precondition |
|---|--------------|
| 1 | pipeline 존재 |
| 2 | graph 저장됨 · dirty 아님 |
| 3 | latest compile `SUCCESS` · persisted |
| 4 | `pipeline.current_sync_status = IN_SYNC` |
| 5 | latest materialization `SUCCESS` |
| 6 | materialization `graph_version_hash` == compile/graph hash |
| 7 | 동일 pipeline에 이미 `ACTIVE` activation 없음 |
| 8 | CRON node / cron expression 유효 |
| 9 | materialized R10 schedule row 존재 |
| 10 | secret refs는 materialization 시 검증 완료 전제 |

### HTTP 매핑

| 코드 | 상황 |
|------|------|
| 400 | request invalid |
| 404 | pipeline / materialization / schedule missing |
| 409 | precondition failed (stale, already active, cron missing 등) |
| 500 | unexpected |

**규칙:** precondition 실패 시 run row 생성 금지 · Activation 경로에서 `run_load` 호출 금지.

**Executor note:** Scheduled Run은 `THERMOOPS_VP_RUN_EXECUTOR=worker` 운영을 권장. Activation precondition으로 worker 강제할지, warning만 할지는 S7-8에서 결정 — **기본 권장: activation은 허용하되 README/UI에 worker 필수 경고**.

---

## 7. API 설계 후보

### 7.1 Activation API (S7-8)

**권장 REST (plural resource):**

| Method | Path | 역할 |
|--------|------|------|
| `POST` | `/api/v1/visual-pipelines/{pipeline_id}/schedule-activations` | activate |
| `GET` | `/api/v1/visual-pipelines/{pipeline_id}/schedule-activations` | history list |
| `GET` | `/api/v1/visual-pipelines/{pipeline_id}/schedule-activations/current` | current/latest |
| `POST` | `/api/v1/visual-pipelines/{pipeline_id}/schedule-activations/{activation_id}/deactivate` | deactivate |

대안 비교:

| 스타일 | 예 | 평가 |
|--------|-----|------|
| Singular + DELETE | `DELETE .../schedule-activation/{id}` | 가능하나 plural 일관성 약함 |
| Action suffix | `.../{id}:deactivate` | 명확하나 FastAPI 관례상 path segment 선호 |
| **Plural + deactivate action** | 위 표 | **권장** — list/current와 정합 |

Response 최소 필드: `activation_id`, `activation_status`, `r10_schedule_id`, `cron_expression`, `timezone`, `next_due_at`, `last_triggered_at`, `trigger_count`, `materialization_result_id`.

### 7.2 Scheduled Run trigger (내부)

- **Public API로 열지 않음**
- Service 후보:
  - `find_due_visual_pipeline_activations`
  - `enqueue_scheduled_visual_pipeline_run`
  - `run_schedule_activation_due_once` / `run_due_once`
- CLI 후보:
  - `python -m app.workers.visual_pipeline_schedule_worker --mode once|loop`
  - wrapper: `scripts/run_visual_pipeline_schedule_worker.py`

### 7.3 Worker 분리 권장 (상세는 §10)

- S7-8: **`vp-schedule-worker` 별도 PoC 권장**
- `vp-run-worker`는 실행만
- 구현 부담이 크면 compose 서비스는 CLI once 검증 후 S7-8에 포함하되, loop 운영 튜닝은 S7-9 가능

---

## 8. Scheduled Run 생성 정책

due 발생 시 `tb_visual_pipeline_run` 생성:

| 필드 | 값 |
|------|-----|
| `run_status` | `PENDING` |
| `execution_mode` | `BACKGROUND` |
| `mode` | `SCHEDULED` |
| `pipeline_id` | activation 대상 |
| `compile_result_id` / `materialization_result_id` | activation 스냅샷 |
| `graph_version_hash` | 스냅샷 |
| `activation_id` | FK성 참조 |
| `r10_schedule_id` | SoT |
| `scheduled_for` | due slot |
| `dedup_key` | `VP-SCHEDULED:{activation_id}:{scheduled_for}` |
| `request_json` | `trigger_type=SCHEDULED`, cron, `scheduled_for`, `activation_id`, `executor=worker` 등 |
| `result_json` | 초기 null |
| `issues_json` | `[]` |

### 중복 방지

- 동일 `activation_id` + `scheduled_for` → run **1개**
- **S7-8 권장:** `dedup_key` UNIQUE + insert 시 conflict 처리
- exists-check만: race 가능 → PoC라도 unique 권장

### Concurrent Manual Run

- 기존 Manual Run: 동일 pipeline `PENDING`/`RUNNING` → POST **409**
- Scheduled enqueue 시 Manual이 진행 중이면:
  - **S7-8 후보 A:** enqueue 스킵 + 다음 cycle 재시도 (next_due 유지/지연 정책 문서화)
  - **S7-8 후보 B:** PENDING은 허용하고 claim 직렬화에 위임
  - **권장:** S7-8은 **enqueue 허용**(PENDING 큐잉)하되, claim은 기존 worker 직렬화. Manual POST 409 정책은 Manual 경로만 유지. (동시성 세부는 S7-8 구현 시 테스트로 고정)

---

## 9. Due 계산 / CRON 기준

### 9.1 Source of truth

| 단계 | SoT |
|------|-----|
| Compile 이전 | Visual graph CRON node config (입력) |
| Materialization 이후 | **R10 `tb_data_load_schedule` + activation record** |
| Due 계산 (Activation 후) | activation.`next_due_at` + materialized schedule cron/timezone |

Graph CRON node는 compile/materialization **이전 입력**. Activation 이후 due는 **materialized schedule 기준**.

### 9.2 Timezone

- 기본: **`Asia/Seoul`** (R10 `schedule_time_service.DEFAULT_TZ`와 동일)
- schedule row의 `timezone` 우선

### 9.3 Missed / catch-up

| 정책 | S7-8 | S7-9+ |
|------|------|-------|
| Catch-up | **없음** | 검토 |
| `now >= next_due_at` | **1건** enqueue 후 `next_due_at` 갱신 | multi-miss 정책 |
| PAUSED/INACTIVE/ERROR | enqueue **금지** | 동일 |

### 9.4 Parser 재사용

- R10: `cron_schedule_service` · `schedule_time_service.compute_next_run_at` **재사용 권장**
- **신규 cron 패키지 도입 금지**
- Visual Pipeline CRON은 현재 materialization 경로에서 R10 schedule로 반영됨 — Activation은 그 row를 읽음

### 9.5 R10 `active_yn` 정책 (S7-8에서 확정 필요)

권장 방향:

- VP Scheduled Run은 **`vp-schedule-worker` → VP run row** 경로만 사용
- R10 `run-due-worker`가 동일 schedule을 **이중 실행하지 않도록**:
  - **권장:** Activation 시에도 R10 `active_yn=false` 유지하고, due는 **activation.`next_due_at`만** 사용  
  - 또는 Activation 시 `active_yn=true`로 올리되 run-due-worker가 VP-origin schedule을 **스킵**하는 플래그 — 복잡도↑ · **비권장(초기)**
- **S7-8 기본 권장:** `active_yn`은 **false 유지** · VP activation table이 due 권위

---

## 10. Worker 분리 전략

| 안 | 내용 | 평가 |
|----|------|------|
| **A** | `vp-run-worker`가 due enqueue도 수행 | 단순 · 책임 혼합 |
| **B** | `vp-schedule-worker` 별도 | **권장** · 장애/관찰성 분리 |
| **C** | R10 `run-due-worker` 재사용 | **비권장** · 경계 혼합 · provenance 약화 |

### 권장: B안

| Worker | 역할 | Traefik |
|--------|------|---------|
| `vp-schedule-worker` | due 감지 · PENDING enqueue | **미노출** |
| `vp-run-worker` | PENDING claim · `run_load` | **미노출** |
| `run-due-worker` | R10 data_load_schedule only | 기존 정책 |

S7-8 PoC:

- schedule worker CLI `once|loop` + Compose 서비스 추가
- 부담 시: service + CLI once를 필수로 두고 Compose loop는 동일 단계에서 최소 추가

---

## 11. UI 설계 후보

> S7-7에서는 UI 구현하지 않는다. S7-8 Studio 최소 변경 후보.

### Schedule Activation 버튼 enabled 조건

- `!dirty`
- latest compile SUCCESS + persisted
- `current_sync_status = IN_SYNC`
- latest materialization SUCCESS
- materialized CRON schedule 존재
- ACTIVE activation 없음
- activation request 진행 중 아님

### Confirm 문구 (후보)

> 스케줄 활성화를 수행합니다. 활성화 후 설정된 CRON 주기에 따라 자동 실행 Run이 생성될 수 있습니다. 실제 적재 실행은 VP run-worker가 처리합니다. 계속 진행하시겠습니까?

### Activation Panel

- `activation_status` · `activation_id` · `r10_schedule_id`
- cron · timezone · `next_due_at` · `last_triggered_at` · `trigger_count`
- Deactivate 버튼
- STALE active 경고 (해당 시)

### Run Panel

- Manual / Scheduled 구분 (`mode`)
- `scheduled_for` / `activation_id` 표시
- polling 계약 유지

### Materialization Panel

- `activation` mirror: `NOT_REQUESTED` → `ACTIVE` / `INACTIVE`

### S7-8 UI 범위

- Soon 배지 제거 · activate + deactivate 최소
- pause/resume UI → S7-9

---

## 12. API/UI 에러 처리

| 코드 | 예 |
|------|----|
| 400 | invalid body |
| 404 | pipeline / materialization / schedule / activation not found |
| 409 | graph stale · compile/materialization required · already active · cron missing/invalid |
| 500 | unexpected |

UI:

- 409 사유 메시지 표시
- success 후 Activation Panel refresh
- due run **즉시 생성 보장하지 않음** (다음 schedule-worker cycle)
- Scheduled run은 Run list에서 확인

---

## 13. Security / Safety

- Activation은 반복 실행 허용 → Manual Run보다 **위험도 높음**
- Confirm **필수**
- Auth 전: mock role / ADMIN UI 제한 가능 (`VITE_USER_ROLE`)
- 향후 Activation API는 admin 권한 후보
- secrets raw · request/result JSON에 secret 값 저장 금지
- schedule enable/disable은 **audit 대상 후보** (S7-9+)
- min interval / CRON 허용 범위: env `THERMOOPS_VP_SCHEDULE_MIN_INTERVAL_SECONDS` 후보
- 테스트: **운영 외부 API 호출 금지** · sample/local fixture만

---

## 14. 테스트 전략 (S7-8)

### 필수 시나리오

1. activation precondition success  
2. precondition fail: dirty/stale · compile/materialization · cron · already active  
3. activation → ACTIVE record · **`run_load` 미호출**  
4. deactivate → INACTIVE  
5. schedule worker once → scheduled PENDING enqueue  
6. duplicate due → 중복 enqueue 없음 (`dedup_key`)  
7. vp-run-worker가 scheduled run 실행  
8. provenance: `mode=SCHEDULED` · `activation_id` · `scheduled_for` · `request_json`  
9. Manual Run이 activation 상태를 바꾸지 않음  
10. scheduled run 실행이 `current_sync_status` / materialization status를 바꾸지 않음  
11. quick group **미포함**  
12. (선택) Studio E2E: 버튼 enabled · panel · due once 후 run 표시  

### 테스트 파일 후보

- `scripts/test_visual_pipeline_schedule_activation.py`
- `scripts/test_visual_pipeline_schedule_worker.py`
- 기존 `test_visual_pipeline_run_worker.py` — scheduled mode claim 보강 검토

주의: deterministic due/timezone fixture · cleanup 철저 · 외부 API 금지

---

## 15. 운영 / 배포 설계

### Compose (S7-8 이후)

- `backend` · `frontend` · `vp-run-worker` · **`vp-schedule-worker`**
- Worker: Traefik **미노출**

### Env 후보

```env
THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED=false
THERMOOPS_VP_SCHEDULE_WORKER_ENABLED=false
THERMOOPS_VP_SCHEDULE_WORKER_MODE=loop
THERMOOPS_VP_SCHEDULE_WORKER_POLL_INTERVAL_SECONDS=30
THERMOOPS_VP_SCHEDULE_WORKER_MAX_BATCH_SIZE=10
THERMOOPS_VP_SCHEDULE_WORKER_ID=
THERMOOPS_VP_SCHEDULE_MIN_INTERVAL_SECONDS=300
```

### 배포 예

```bash
python3 scripts/apply_dev_migrations.py
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build \
  backend frontend vp-run-worker vp-schedule-worker
```

### Worker 미기동 영향

| 미기동 | 영향 |
|--------|------|
| `vp-schedule-worker` | scheduled PENDING **미생성** |
| `vp-run-worker` | PENDING **미실행** (stuck) |
| `backend` | Activation API/UI 불가 |

---

## 16. Observability / Admin

### S7-8 최소

- activation record · `next_due_at` / `last_triggered_at` / `trigger_count`
- schedule/run worker 로그
- Run list에서 `mode=SCHEDULED` provenance

### S7-9+

- activation history UI · schedule worker summary API  
- missed run report · dedup dashboard  
- pause/resume · manual scheduled trigger  
- retry/cancel/progress · audit · notification  

---

## 17. Roadmap

| 단계 | 내용 |
|------|------|
| **R11-S7-7** | Schedule Activation **설계** (본 문서, docs-only) |
| **R11-S7-8** | Schedule Activation **PoC** — activation table · API · `vp-schedule-worker` · scheduled enqueue · Studio 최소 UI · `dedup_key`+unique |
| **R11-S7-9** | Hardening — catch-up · pause/resume · retry/cancel/progress · audit/notification · missed run |
| **R11-S7-10** | 운영 배포 안정화 — monitoring · recovery · production defaults |

### S7-8 PoC 포함

- [ ] `tb_visual_pipeline_schedule_activation` migration  
- [ ] run 확장: `mode=SCHEDULED` · `activation_id` · `scheduled_for` · `r10_schedule_id` · `dedup_key`(+unique)  
- [ ] Activation API (activate/deactivate/list/current)  
- [ ] `materialization.activation` mirror 갱신  
- [ ] schedule due service + CLI/`vp-schedule-worker`  
- [ ] Studio Activation UI 최소 (Soon 제거)  
- [ ] 전용 테스트 스크립트  
- [ ] README/env/compose  

### S7-9로 미룸

- catch-up / missed multi-slot  
- pause/resume  
- retry/cancel/progress  
- 자동 STALE 비활성화  
- audit/notification  
- R10 `active_yn` 고급 연동  
- Redis/Celery  

---

## 18. Decision Log

| ID | 결정 |
|----|------|
| **D1** | Schedule Activation은 `run_load`를 **직접 실행하지 않는다**. |
| **D2** | Scheduled trigger는 `tb_visual_pipeline_run` **PENDING** row를 생성한다. |
| **D3** | 실제 실행은 **VP run-worker**가 담당한다. |
| **D4** | R10 `run-due-worker`는 VP Scheduled Run에 **재사용하지 않는다**. |
| **D5** | activation 상태는 별도 **`tb_visual_pipeline_schedule_activation`** 으로 관리한다. |
| **D6** | `materialization.activation`은 **mirror/표시용**이다. |
| **D7** | Scheduled Run은 기존 **`mode` 확장** (`MANUAL` / `SCHEDULED`)을 우선한다. |
| **D8** | Provenance: `activation_id` · `scheduled_for` · `r10_schedule_id` · `dedup_key`. |
| **D9** | Due SoT는 **materialized R10 schedule + activation record**다. |
| **D10** | S7-8은 **`vp-schedule-worker`(enqueue) + `vp-run-worker`(실행)** 분리를 권장한다. |
| **D11** | Catch-up / missed run은 S7-8 **제외**, S7-9 검토. |
| **D12** | pause/resume은 S7-9 · S7-8은 activate/deactivate 중심. |
| **D13** | `dedup_key` + UNIQUE를 S7-8에서 **권장**. |
| **D14** | STALE active는 S7-8에서 **경고**, 자동 비활성은 후속. |
| **D15** | S7-8 기본: R10 `active_yn=false` 유지 · due 권위는 activation table. |
| **D16** | GET `/runs` polling 계약 유지 · Run Now UI와 Activation UI 분리. |
| **D17** | Worker는 Traefik **미노출**. |
| **D18** | S7-7은 **docs-only** — code/DB/API/FE/package 변경 없음. |
| **D19** | Queue / Redis / Celery **도입하지 않음**. |
| **D20** | Activation은 admin/audit 대상 후보. |

---

## 19. 본 문서 범위 확인

| 항목 | S7-7 |
|------|------|
| Activation 구현 | **없음** |
| API endpoint 추가/수정 | **없음** |
| DB/schema/migration | **없음** |
| FE/Studio UI | **없음** |
| VP run-worker 변경 | **없음** |
| run-due-worker 변경 | **없음** |
| R10 `run_load` 변경 | **없음** |
| package | **없음** |

---

## 20. 참고 코드 / 문서 (구현 시)

- `backend/app/services/visual_pipeline/manual_run_service.py`
- `backend/app/services/visual_pipeline/run_worker_service.py`
- `backend/app/api/v1/visual_pipelines.py` — `/runs` only (현재)
- `backend/app/models/entities.py` — `VisualPipelineRun` · `VisualPipelineMaterializationResult` · `DataLoadSchedule`
- `backend/app/services/cron_schedule_service.py` · `schedule_time_service.py`
- `backend/app/workers/run_due_worker.py` · `run_due_worker_service.py` (참고만, 혼합 금지)
- `frontend/src/pages/VisualPipelineStudioPage.tsx` — Activation Soon
- `frontend/src/components/visualPipeline/VpRunPanel.tsx`
- `scripts/r11s7_visual_pipeline_run_worker.sql`
- `scripts/test_visual_pipeline_run_worker.py`
- README R11-S7-3 ~ S7-6
