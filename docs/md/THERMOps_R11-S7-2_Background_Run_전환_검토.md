# THERMOps R11-S7-2 Background Run 전환 검토

> **문서 유형**: 설계 / 검토 (구현 없음)  
> **작성 기준**: `master` @ R11-S7-1 (`3f6840b`) 완료 시점  
> **범위**: S7-1 동기 Manual Run의 한계 정리, Background 전환 Option 비교, API/DB/worker/UI 계약 제안, 로드맵 갱신  
> **비범위**: Background worker, queue, POST/GET `/runs` 동작 변경, DB migration, FE/Studio Run UI, Schedule Activation, due worker, R10 `run_load` 변경, package 변경  
> **후속**: R11-S7-3 Background Run Backend PoC (별도 승인)

관련 문서:

- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md`
- `docs/md/THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md`
- README R11-S7-1 Manual Run API PoC

---

## 1. 배경과 목적

### 1.1 S7-1 현재 상태 (구현됨)

| 항목 | 내용 |
|------|------|
| API | `POST/GET /api/v1/visual-pipelines/{pipeline_id}/runs`, `GET .../runs/{run_id}` |
| 실행 | **Option A 동기** — 요청 중 R10 `run_load` 완료 후 response |
| Persistence | `tb_visual_pipeline_run` + R10 `tb_api_connector_load_run` / call_log / dedup |
| Precondition | SUCCESS compile + SUCCESS materialization + hash 일치 + `IN_SYNC` |
| 한도 | `max_pages` 상한 **1**, `limit` 상한 **100** |
| HTTP | precondition **409** (run row 없음); runtime domain failure **200** + `run_status=FAILED` |
| 안전 | `schedule active_yn` 미변경, due worker 미연결, sync/materialization status 미변경 |
| 테스트 | `scripts/test_visual_pipeline_manual_run.py` (mock/local `sample-external`, quick **미포함**) |

실행은 **오직** `POST /runs`에서만 발생한다. compile / materialize / GET / 페이지 로드는 실행하지 않는다.

### 1.2 S7-1 한계

| 한계 | 설명 |
|------|------|
| API request timeout | gateway/proxy/uvicorn 한도 내 장시간 REST·write 불가 |
| 대량 pagination / write | `max_pages=1`·`limit≤100`으로 완화했지만 한도 완화 시 취약 |
| UI blocking | Studio가 POST 완료까지 spinner 대기해야 함 |
| 진행률 부재 | step/progress를 실시간 노출하기 어려움 |
| cancel 불가 | 진행 중 중단 API·정책 없음 |
| retry / resume 어려움 | 실패 후 동일 run 재개보다 신규 run만 가능 |
| queueing 어려움 | 동시 RUNNING은 409로 거부; 대기열 없음 |
| long-running 관리 | 프로세스 재시작·멀티 인스턴스와 무관하게 “요청=실행” |

### 1.3 S7-2 목적

1. Background 방식이 **필요한지** 판단한다.  
2. 필요 시 **어떤 구조(A/B/C/D/E)** 로 갈지 권장안을 고정한다.  
3. **S7-4 Studio Run UI 전**에 polling / result 조회 계약을 확정한다.  
4. **본 단계는 docs-only** — 후속 구현안만 명확히 남긴다.

---

## 2. Option 비교

본 문서의 Option 라벨은 **실행 인프라** 관점이다.  
S7-0 §7의 Option A/B(동기/background)와 대응하되, S7-2에서는 due worker·Airflow를 별도 옵션으로 분리한다.

### Option A — 현재 동기 실행 유지

| | |
|--|--|
| **내용** | `POST /runs` 요청 중 `run_load` 수행 → 완료 후 SUCCESS/FAILED 반환 (`execution_mode=SYNC`) |
| **장점** | 구현·테스트 단순; S7-1 그대로; worker/queue 불필요 |
| **단점** | timeout·UI blocking·progress/cancel 불가; 운영 대량 실행 부적합 |
| **적합** | PoC, `max_pages=1`, `limit≤100`, 짧은 REST/load, 내부 수동 실행 |

### Option B — FastAPI BackgroundTasks / in-process background

| | |
|--|--|
| **내용** | POST에서 run row `PENDING`/`RUNNING` 생성 후 즉시 반환 → BackgroundTasks/asyncio가 별도 DB session으로 `run_load` → GET polling |
| **장점** | 구현 부담 낮음; UI polling; API timeout 회피; 별도 worker 인프라 없이 PoC |
| **단점** | 프로세스 재시작 시 작업 유실; 멀티 프로세스/컨테이너 관리 어려움; retry/resume 제한; 운영 불완전 |
| **적합** | S7-3 transitional PoC, 단일 backend 컨테이너, non-blocking UX 검증 |

### Option C — 별도 run-worker 프로세스

| | |
|--|--|
| **내용** | POST → `PENDING` row; worker가 DB claim → `RUNNING` → `run_load` → SUCCESS/FAILED; GET polling |
| **장점** | request timeout 완전 분리; 재시작 복구·claim/lock/retry 설계 가능; Compose에서 worker 분리 |
| **단점** | 구현·migration·lifecycle·테스트 복잡도 큼 |
| **적합** | 운영형 Manual Run, long-running load, background 정식화 |

### Option D — 기존 data_load_scheduler / due worker 재사용

| | |
|--|--|
| **내용** | Manual Run을 schedule/due worker 경로에 연결 |
| **장점** | 기존 worker 재사용 |
| **단점** | Manual Run ↔ Schedule Activation 경계 혼동; `active_yn` 정책과 충돌; S6/S7 boundary 파손 위험 |
| **결론** | **Manual Run에 비권장**. Scheduled Run(Activation 이후)에만 검토 |

### Option E — Airflow / DAG trigger

| | |
|--|--|
| **내용** | Visual Pipeline Run을 Airflow DAG로 trigger |
| **장점** | 관측·재시도·장기 운영 강함 |
| **단점** | Manual Run PoC에 과도; R10 `run_load`와 중복; 오케스트레이션 범위 확대 |
| **결론** | **후순위** |

### 비교 요약

| Option | timeout 회피 | UI polling | 운영 복구 | 경계 유지 | S7-3 적합성 |
|--------|-------------|------------|-----------|-----------|-------------|
| A | ✗ | ✗ | n/a | ✓ | 유지·시연만 |
| B | ✓ | ✓ | 약함 | ✓ | **transitional PoC** |
| C | ✓ | ✓ | 강함 | ✓ | **운영 목표** |
| D | ✓ | ✓ | 중 | ✗ Manual | 비권장 |
| E | ✓ | ✓ | 강함 | △ | 후순위 |

---

## 3. 권장 결론

### 3.1 선택

**운영 모드 (권장):**

| 단계 | 내용 |
|------|------|
| **S7-2 (본 문서)** | docs-only 검토 |
| **S7-3** | Background Backend PoC — **Option B transitional 우선**, 설계상 **Option C를 운영 목표**로 병행 기술 |
| **S7-4** | Studio Run UI — **polling 기반 background-ready** |

**단기 시연 모드 (비권장 기본, 예외만):**

- S7-2 문서 후 Option A 유지 + S7-4 sync UI  
- 이후 UI를 polling으로 재작성해야 하므로 비용이 큼

### 3.2 이유

1. S7-1은 PoC로 충분하나, Studio Run UI를 **blocking spinner**에 고정하면 background 전환 시 FE 재작업이 크다.  
2. Option B는 Compose 단일 backend에서도 non-blocking과 polling 계약을 검증할 수 있다.  
3. Option C는 claim/lock/heartbeat가 필요하므로 S7-3 전량 구현보다 **목표 아키텍처로 문서화**하고, B로 UX·계약을 먼저 맞춘다.  
4. Option D는 Manual↔Activation 경계를 깨므로 S6-5 / S7-0 Decision을 유지한다.  
5. Option E는 Visual Data Load Manual Run 범위에 과도하다.

### 3.3 Hybrid / Phased

권장은 **phased migration**:

```
S7-1 SYNC (완료)
  → S7-3 Option B BACKGROUND PoC (POST 202 + polling)
  → (필요 시) S7-3b / 후속 Option C worker 교체 — API 계약·UI는 유지
  → S7-4 polling UI
```

API·UI는 **run object + GET polling** 기준으로 맞추면 B→C 교체 시 FE 영향이 최소화된다.

---

## 4. Background 전환 시 API 계약 (후속 구현 후보)

> S7-2에서는 **구현하지 않는다**. S7-3 승인 후 적용.

### 4.1 `POST /api/v1/visual-pipelines/{pipeline_id}/runs`

**전환 후 response 후보:**

```json
{
  "visual_run_id": "VPR-...",
  "pipeline_id": "PIPE-...",
  "mode": "MANUAL",
  "execution_mode": "BACKGROUND",
  "run_status": "PENDING",
  "compile_result_id": "VPC-...",
  "materialization_result_id": "VPM-...",
  "graph_version_hash": "...",
  "poll_url": "/api/v1/visual-pipelines/PIPE-.../runs/VPR-...",
  "load_run_id": null,
  "started_at": null,
  "finished_at": null,
  "result": null,
  "issues": [],
  "schedule_active_changed": false,
  "current_sync_status_changed": false
}
```

| 정책 | 내용 |
|------|------|
| HTTP | **202 Accepted** 권장 (즉시 수락, 완료 아님). 200도 가능하나 “완료”와 혼동 위험 |
| Precondition 실패 | 기존과 동일 **409**, run row **미생성**, R10 실행 **없음** |
| Request validation | **400** (`dry_run`, secret override, bad mode 등) |
| Runtime 실패 | POST가 아니라 **GET polling**에서 `run_status=FAILED` |
| `execution_mode` | `BACKGROUND` (S7-1의 `SYNC`와 구분) |
| S7-1 호환 | S7-3까지는 feature flag 또는 단계적 전환; **본 문서는 계약만 제안** |

### 4.2 `GET .../runs/{run_id}`

| `run_status` | 의미 |
|--------------|------|
| `PENDING` | 대기 (worker/task 미시작) |
| `RUNNING` | 실행 중 |
| `SUCCESS` | 완료 성공 |
| `FAILED` | 치명 실패 |
| `PARTIAL` | 일부 성공 (R10 WARNING 등) |
| `CANCELLED` | 취소 (후속, S7-3 기본 제외 가능) |

**권장 필드:**

- `started_at` / `finished_at` / (optional) `duration_ms`
- `load_run_id` (완료 후)
- `result` / `result_json`, `issues` / `issues_json`
- optional: `progress`, `current_step` (S7-3b+)

### 4.3 `GET .../runs` 목록

- 최신순 유지
- `PENDING`/`RUNNING` 존재 시 Studio **Run Now disabled** 근거로 사용 (S7-4)

### 4.4 Cancel

- `POST .../runs/{run_id}/cancel` — S7-3 MVP **제외**, Decision Log에 후속으로 남김

---

## 5. DB / schema 영향 검토

### 5.1 현재 `tb_visual_pipeline_run` (S7-1)

이미 존재:

- `run_status`, `request_json`, `result_json`, `issues_json`
- `started_at`, `finished_at`, `load_run_id`
- `execution_mode` (`SYNC` 기본)
- index: `(pipeline_id, created_at DESC)`, `(pipeline_id, run_status)`

### 5.2 Option B

| 판단 | 내용 |
|------|------|
| **충분성** | **현재 테이블로 PoC 가능** — `execution_mode=BACKGROUND`, status `PENDING`→`RUNNING`→terminal |
| migration | S7-3에서 **필수는 아님** (선택: `progress_json` 등) |
| 한계 | claim/heartbeat 없음 → stuck `RUNNING`은 운영 복구 약함 |

### 5.3 Option C (운영 목표 시 후보 컬럼)

| 후보 | 용도 |
|------|------|
| `claimed_at` / `claimed_by` | worker claim |
| `locked_until` / `heartbeat_at` | lease / stuck 감지 |
| `attempt_count` / `next_retry_at` | retry |
| `progress_json` / `current_step` | UI progress |
| `cancel_requested_yn` | soft cancel |
| `idempotency_key` | 중복 POST 방지 |

**인덱스 후보:** `(run_status, created_at)` claim용, partial index on `PENDING`.

### 5.4 S7-2에서의 결정

- **본 단계 migration 없음**
- S7-3 Option B: 기존 스키마로 시작 권장
- Option C 전환 시 **별도 migration 승인** 후 claim/lock 컬럼 추가

---

## 6. Worker 설계 후보

### 6.1 Option B — in-process

```
1. API precondition (동기, run row 없음)
2. run row PENDING (또는 즉시 RUNNING) 생성 + commit
3. BackgroundTasks / asyncio task 등록 → 즉시 202
4. task: 새 AsyncSession으로 run_load
5. SUCCESS / FAILED / PARTIAL update
```

주의:

- **request DB session 재사용 금지**
- process crash → `PENDING`/`RUNNING` stuck 가능
- startup recovery는 후속 (Option C 또는 B hardening)
- uvicorn multi-worker 시 중복 실행 위험 → PoC는 single worker 가정

### 6.2 Option C — DB polling worker

```
1. API precondition → PENDING row → 202
2. worker loop: SELECT ... FOR UPDATE SKIP LOCKED (또는 equivalent) claim
3. RUNNING + claimed_by / heartbeat
4. run_load (새 session)
5. terminal status update
6. stuck RUNNING: heartbeat timeout → FAILED 또는 requeue
```

주의:

- PostgreSQL lock 전략, polling interval, graceful shutdown
- max concurrency, Docker Compose service명 (`thermops-vp-run-worker` 후보)
- **due worker / `run_due_schedules`와 코드 경로 분리** — Manual Run 전용 claim

### 6.3 공통 불변 (B/C)

- schedule `active_yn` **미변경**
- due worker **미호출**
- `current_sync_status` / `materialization_status` **미변경**
- 실행은 worker/task 경로에서만; compile/materialize/GET은 실행 없음

---

## 7. UI 영향 검토 (S7-4)

### 7.1 동기 UI (Option A 유지 시)

- Run Now click → blocking spinner → result panel
- 페이지 reload 시 latest run GET으로 복원 가능하나 UX는 “요청=완료”

### 7.2 Background-ready UI (권장)

| 단계 | 동작 |
|------|------|
| Click + confirm | “실제 REST 호출 및 target write 발생” 경고 (S7-0 D12) |
| POST | `visual_run_id` + `PENDING`/`RUNNING` 수신 |
| Panel | RUNNING 표시 + `GET .../runs/{id}` polling |
| Complete | SUCCESS/FAILED/PARTIAL → result / issues |
| Reload | latest run 또는 RUNNING run 조회 |
| Concurrent | RUNNING 존재 시 Run Now **disabled** |
| Cancel | 후속 |

### 7.3 권장

- **S7-4는 background-ready UI로 설계**한다.  
- backend가 일시적으로 SYNC여도 response를 **run object**로 맞추면, FE는 “POST 후 결과 표시”와 “POST 후 polling”을 같은 panel로 흡수할 수 있다.  
- Materialize UI(S6-6)와 Run UI는 분리 유지.

---

## 8. 상태 / 실패 / 재시도 정책

| 전이 | 정책 |
|------|------|
| `PENDING` → `RUNNING` → `SUCCESS` | 정상 |
| `PENDING`/`RUNNING` → `FAILED` | runtime / worker 실패 |
| stuck `RUNNING` | Option B: 문서화·수동 정리; Option C: heartbeat timeout |
| retry | **S7-3 MVP 미구현** — 완료 후 신규 Manual Run만 (S7-1과 동일) |
| runtime failure | `run_status=FAILED` + issues; sync/materialization **불변** |
| schedule | `active_yn` **불변**; due worker **미사용** |
| concurrent | 동일 pipeline `PENDING`/`RUNNING` 존재 시 **409** `RUN_CONCURRENT_RUN_EXISTS` (확장) |

**Run 실패 ≠ `COMPILE_FAILED`.** (S7-0 D4 / S6-5 유지)

---

## 9. 테스트 전략 (S7-3+ 후속)

| 분류 | 항목 |
|------|------|
| Latency | POST가 빠르게 반환 (background) |
| Polling | GET이 SUCCESS / FAILED에 도달 |
| Precondition | 409 시 run row·load_run·call_log·target write 증가 없음 |
| Concurrent | RUNNING fixture → 409 |
| Safety | schedule active 불변, sync/materialization 불변 |
| Isolation | mock/local source only; 운영 외부 API 금지 |
| Crash | Option C에서 stuck recovery; Option B는 한계 문서화 |
| Regression | `test_visual_pipeline_manual_run.py` 계열 **quick 미포함** 유지 |

---

## 10. 로드맵 업데이트

### 10.1 권장 (운영 모드)

| 단계 | 내용 |
|------|------|
| **R11-S7-0** | Run 설계 (완료) |
| **R11-S7-1** | Manual Run API PoC Option A (완료, `3f6840b`) |
| **R11-S7-2** | Background Run 전환 검토 (**본 문서**) |
| **R11-S7-3** | Background Run Backend PoC — Option B 우선, C 설계 병행; POST **202** + polling |
| **R11-S7-4** | Studio Run UI — confirm + polling result panel |
| **R11-S7-5** | Run history / step log / progress 강화 |
| **R11-S7-6** | Schedule Activation 설계 |
| **R11-S7-7** | Schedule Activation PoC |
| **R11-S7-8** | audit / retry / cancel 안정화 |

### 10.2 단기 시연 모드 (예외)

`S7-2 → S7-4 sync UI` — 가능하나 background 전환 시 UI 재작업. **기본 권장 아님.**

### 10.3 S7-0 Decision D13과의 관계

S7-0: `S7-0→S7-1(A)→S7-2→S7-3→S7-4`.  
본 문서는 S7-2를 **동기→background 검토**로 구체화하고, S7-3을 **Background Backend PoC**로 명명한다. Activation은 S7-6+로 번호만 정리(내용 동일).

---

## 11. Decision Log

| ID | 결정 | 선택 |
|----|------|------|
| **D1** | S7-4 전 background 여부 | **먼저 검토** (본 문서). UI 전 API/polling 계약 확정 |
| **D2** | Manual Run vs Activation | **계속 분리**. Manual은 schedule activate하지 않음 |
| **D3** | due worker 재사용 | Manual Run에 **비권장** (Option D) |
| **D4** | S7-3 우선순위 | **Background Backend PoC** (Option B transitional) |
| **D5** | POST HTTP | Background 전환 시 **202 Accepted** 권장 |
| **D6** | GET polling | UI 기준 계약 확정 (`PENDING`/`RUNNING`/terminal + result/issues) |
| **D7** | B vs C | **B = transitional**, **C = 운영 지향** |
| **D8** | sync status | Background run도 `current_sync_status` **미변경** |
| **D9** | schedule | Background run도 `active_yn` **미변경**, due worker 미사용 |
| **D10** | regression | Background/manual run 테스트 **quick 미포함** (당분간) |
| **D11** | S7-4 UI | **polling / background-ready** 설계 |
| **D12** | S7-2 범위 | **docs-only**. migration/API/FE/worker **없음** |
| **D13** | R10 adapter | 계속 `run_load` 래핑; runtime 대규모 리팩토링 금지 |
| **D14** | Airflow | Manual Run **후순위** (Option E) |

---

## 12. Side-effect 표 (Background 포함 예정)

| 이벤트 | sync | materialization | R10 config | load/call | target write | schedule active |
|--------|------|-----------------|------------|-----------|--------------|-----------------|
| Preview/Compile/Materialize | S6-5 | S6-5 | materialize만 | 없음 | 없음 | false |
| Manual Run SYNC (S7-1) | 불변 | 불변 | 불변 | POST 중 증가 | POST 중 | 불변 |
| Manual Run BACKGROUND (S7-3+) | 불변 | 불변 | 불변 | **worker에서** 증가 | **worker에서** | 불변 |
| Activation (후속) | 불변 | 불변 | schedule update | — | — | **true** |

---

## 13. 참조

- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md` — D1–D15, Option A/B
- `docs/md/THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md` — no-run/no-activation 경계
- `backend/app/services/visual_pipeline/manual_run_service.py` — S7-1 동기 구현
- `backend/app/api/v1/visual_pipelines.py` — POST/GET runs
- `scripts/r11s7_visual_pipeline_run.sql` — `tb_visual_pipeline_run`
- `scripts/test_visual_pipeline_manual_run.py`
- `backend/app/services/api_connector_service.py` — `run_load`
- `backend/app/services/data_load_scheduler_service.py` — `run_due_schedules` (active only; Manual 미사용)
