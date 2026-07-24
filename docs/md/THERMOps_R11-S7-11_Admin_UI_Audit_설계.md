# THERMOps R11-S7-11 Admin UI / Audit 설계

> **문서 유형**: 설계 / 검토 (구현 없음)  
> **작성 기준**: `master` @ R11-S7-10 (`4169073`) 완료 시점  
> **범위**: Visual Pipeline Admin Ops UI · Audit Log · mark-failed 확장 판단 · Auth 전 mock 권한 경계 · 후속 PoC 범위 확정  
> **비범위**: Admin UI 구현, Audit table/API 구현, mark-failed HTTP API, ops API 변경, DB/schema/migration, FE/Studio 변경, Auth/SSO/JWT, retry/interrupt/progress/notification, R10 due-worker/`active_yn`, Redis/Celery/queue, package  
> **후속**: R11-S7-12 Admin Ops UI PoC → R11-S7-13 Audit Log PoC → R11-S7-14 Admin Action PoC (각각 별도 승인)

관련 문서:

- `docs/md/THERMOps_R11-S7-7_Schedule_Activation_설계.md`
- `docs/md/THERMOps_R11-S7-5_Option_C_Run_Worker_검토.md`
- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md`
- README R11-S7-8 / S7-9 / S7-10

---

## 1. 배경 정리

### 1.1 현재 완료 상태

| 영역 | 상태 | 요약 |
|------|------|------|
| Manual Run | 완료 | `POST/GET .../runs` · PENDING cancel · Studio Run Panel |
| Schedule Activation | 완료 (S7-8/9) | activate / deactivate / pause / resume · Studio Activation Panel |
| Scheduled Run | 완료 | `vp-schedule-worker` due → `mode=SCHEDULED` PENDING enqueue · `dedup_key` |
| Run 실행 | 완료 | `vp-run-worker` claim → R10 `run_load` · R10 `active_yn=false` · due-worker 미연결 |
| Ops API | 완료 (S7-10) | read-only `GET .../visual-pipeline-ops/summary` · `stuck-runs` |
| Ops CLI | 완료 (S7-10) | `manage_visual_pipeline_ops.py` summary / stuck-runs / mark-failed (default dry-run) |
| Studio UI | 완료 | pipeline 단위 Run / Activation UX |
| Admin Ops UI | **미구현** | 전체 시스템 ops 화면 없음 |
| Audit Log | **미구현** | 운영 행위 감사 이력 없음 |
| mark-failed HTTP/UI | **미구현** | CLI-only |
| process liveness | **미구현** | DB 관찰만 · Docker health는 README 명령 |
| retry / progress / notification | **미구현** | R11-S8 후보 |
| Auth / Admin 권한 | **미구현** | `VITE_USER_ROLE` mock만 |

### 1.2 S7-11 목적

1. 운영자가 **브라우저에서** Visual Pipeline 운영 상태를 확인할 수 있는 Admin UI 범위를 정의한다.
2. 위험한 운영 액션(`mark-failed` 등)의 **UI/API 노출 시점**을 결정한다.
3. Audit가 필요한 이벤트·payload·DB/API/service 후보를 정의한다.
4. Auth 도입 전 **임시 mock role** 전략과 후속 권한 경계를 정리한다.
5. S7-12 / S7-13 / S7-14가 **바로 구현 가능**하도록 API/UI/Audit/test 범위를 구체화한다.

### 1.3 핵심 방향

1. **S7-12 Admin Ops UI는 read-only** — 기존 S7-10 ops API를 소비한다.
2. **mark-failed는 S7-12에서도 CLI-only** — Audit/Admin 권한 준비 전 UI/API 보류.
3. **Audit는 S7-13 PoC** — 별도 `tb_visual_pipeline_audit_log` + 내부 record service + read API.
4. **Admin Action(mark-failed HTTP/UI)은 S7-14** — confirm + audit required.
5. Studio Run/Activation UX는 **유지** — Admin Page와 역할 분리.

---

## 2. Admin UI 범위 후보

### A안: Studio 내 Ops Panel 추가

| | |
|--|--|
| 내용 | `VisualPipelineStudioPage`에 ops summary / stuck 패널 추가 |
| 장점 | 구현 범위 작음 · pipeline 단위 맥락 유지 |
| 단점 | 전체 시스템 상태 조망 어려움 · Studio 복잡도↑ · 향후 audit/admin action 확장에 비좁음 |

### B안: 별도 Admin Ops Page 추가 (권장)

| | |
|--|--|
| 내용 | `/visual-pipeline-ops` 또는 `/admin/visual-pipeline-ops` 전용 페이지 |
| 장점 | 전체 run/activation/worker 상태 확인에 적합 · S7-10 ops API와 자연 연결 · audit/action 확장에 유리 |
| 단점 | 메뉴/라우트/권한 기준 필요 · 화면 범위 증가 |

### C안: Studio + Admin Page 혼합

| | |
|--|--|
| 내용 | Studio = pipeline 단위 · Admin = 전체 ops/stuck/audit |
| 장점 | 장기적으로 이상적 |
| 단점 | S7-12에 동시 구현 시 범위 과다 · Studio 변경은 별도 승인 필요 |

### 권장안

| 단계 | 선택 |
|------|------|
| **S7-12** | **B안** — 별도 Admin Ops Page · **read-only** |
| Studio | 현재 Run/Activation UX **유지** (S7-12에서 Studio Ops Panel 추가 안 함) |
| 장기 | C안은 Audit/Action 안정화 후 선택적 Studio 요약 링크만 검토 |

**Route 후보 (S7-12에서 하나 선택):**

| Route | 비고 |
|-------|------|
| `/visual-pipeline-ops` | ops API prefix와 이름 정합 · **1차 권장** |
| `/admin/visual-pipeline-ops` | admin 네임스페이스 명확 · 메뉴 그룹화에 유리 |

> S7-12 PoC에서는 **`/visual-pipeline-ops` 권장**. `/admin/...`로 바꿀 경우 메뉴·E2E testid만 일괄 변경.

---

## 3. Admin Ops Page 설계 (S7-12 PoC)

### 3.1 Summary Cards

기존 `GET /api/v1/visual-pipeline-ops/summary` 응답을 표시:

- **Run Status Counts:** PENDING / RUNNING / SUCCESS / FAILED / PARTIAL / CANCELLED
- **Activation Status Counts:** ACTIVE / PAUSED / INACTIVE / ERROR
- **Stuck Summary:** `pending_older_than_threshold` · `running_lock_expired`
- **Worker Config:** `run_executor` · `run_worker_enabled` · `schedule_activation_enabled` · `schedule_worker_enabled` · lock TTL / poll interval

### 3.2 Activity Hints

- `latest_claimed_at` · `latest_heartbeat_at`
- `latest_last_triggered_at` · `latest_last_skip_at`

> process liveness 직접 확인 **아님** — DB 관찰 힌트만.

### 3.3 Stuck Runs Table

`GET .../stuck-runs` items:

| 컬럼 | 출처 |
|------|------|
| visual_run_id · pipeline_id · mode · activation_id · scheduled_for | run |
| run_status · reason · age_seconds | stuck 판정 |
| locked_until · heartbeat_at · claimed_by · attempt_count | claim/lease |
| heartbeat_stale_hint | 참고 표시만 (apply 기준 아님) |

### 3.4 Recent Failures

summary의 `recent_failures`:

- visual_run_id · pipeline_id · mode · error_message · finished_at · activation_id

### 3.5 Refresh

| | S7-12 |
|--|-------|
| Manual refresh | **포함** |
| Auto refresh (10–30s) | **제외** (후속) |

### 3.6 Actions (S7-12)

| 액션 | S7-12 |
|------|-------|
| mark-failed UI | **제외** (CLI-only 유지) |
| pause/resume/deactivate | Studio에 이미 있음 · Admin Page에 **추가하지 않음** |
| retry / cancel RUNNING | **제외** |
| Admin destructive action | **S7-14** |

**S7-12 Admin UI PoC는 read-only 우선**을 명확히 한다.  
화면에는 “stuck 정리는 CLI `manage_visual_pipeline_ops.py mark-failed` 사용” 안내 문구만 둔다.

### 3.7 FE 구성 후보 (구현은 S7-12)

| 항목 | 후보 |
|------|------|
| Page | `VisualPipelineOpsPage.tsx` |
| API client | `getVisualPipelineOpsSummary` · `getVisualPipelineOpsStuckRuns` |
| Types | summary / stuck item response |
| Nav | `VITE_USER_ROLE=ADMIN`일 때만 메뉴 표시 |
| E2E | `check-pages.mjs` + ops smoke |

---

## 4. mark-failed UI/API 확장 판단

R11-S7-10에서 mark-failed는 **CLI-only** (`--dry-run` 기본 · `--apply` 명시).

### A안: CLI-only 유지

| | |
|--|--|
| 장점 | 안전 · 실수 방지 · audit 미구현 상태에서도 통제 가능 |
| 단점 | 운영자 서버/로컬 접근 필요 |

### B안: Admin API만 추가

예: `POST /api/v1/visual-pipeline-ops/stuck-runs/{visual_run_id}/mark-failed`

| | |
|--|--|
| 장점 | UI 없이 API 운영 가능 · 자동화 연동 |
| 단점 | 권한/audit 없으면 위험 · 실수 blast radius↑ |

### C안: Admin UI 버튼까지 추가

| | |
|--|--|
| 장점 | 운영 편의성 높음 |
| 단점 | confirm / audit / role / rollback 정책 필수 |

### 권장 로드맵

| 단계 | 결정 |
|------|------|
| **S7-12** | **A안** — CLI-only 유지 + Admin UI **read-only** |
| **S7-13** | Audit Log PoC (CLI apply/dry-run 이벤트 포함) |
| **S7-14** | mark-failed Admin API/UI 검토 (B→C) · strong confirm · audit required · (가능 시) role check |
| 보류 조건 | Auth/Admin 권한·audit 준비 전까지 **mark-failed UI 보류** |

---

## 5. Audit 대상 이벤트 정의

### 5.1 Activation 이벤트

| event_type | 트리거 |
|------------|--------|
| `SCHEDULE_ACTIVATE` | Activation API activate |
| `SCHEDULE_DEACTIVATE` | deactivate |
| `SCHEDULE_PAUSE` | pause |
| `SCHEDULE_RESUME` | resume |

### 5.2 Run 이벤트

| event_type | 트리거 |
|------------|--------|
| `RUN_MANUAL_REQUESTED` | Manual `POST /runs` |
| `RUN_SCHEDULED_ENQUEUED` | schedule-worker PENDING insert 성공 |
| `RUN_CANCELLED` | PENDING cancel |
| `RUN_MARK_FAILED_BY_OPS` | ops mark-failed apply (per run) |
| `RUN_WORKER_CLAIMED` | run-worker claim |
| `RUN_COMPLETED` | terminal SUCCESS/PARTIAL |
| `RUN_FAILED` | terminal FAILED (실행 실패) |

### 5.3 Worker / Ops 이벤트

| event_type | 트리거 |
|------------|--------|
| `OPS_STUCK_QUERY` | stuck-runs 조회 (optional · 노이즈 가능) |
| `OPS_MARK_FAILED_DRY_RUN` | CLI dry-run |
| `OPS_MARK_FAILED_APPLY` | CLI/API apply 배치 요약 |
| `SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN` | skip `ACTIVE_RUN_EXISTS` |
| `SCHEDULE_WORKER_SKIPPED_STALE` | skip `STALE_OR_INVALID` |
| `SCHEDULE_WORKER_SKIPPED_DUPLICATE` | skip `DUPLICATE_DEDUP_KEY` |

### 5.4 UI / Admin 이벤트

| event_type | 트리거 |
|------------|--------|
| `ADMIN_OPS_VIEWED` | Admin Ops Page 로드 (optional) |
| `ADMIN_STUCK_RUNS_VIEWED` | stuck table 조회 (optional) |
| `ADMIN_ACTION_CONFIRMED` | S7-14 destructive confirm |

### 5.5 S7-13 PoC 최소 이벤트 (권장)

**포함:**

- `SCHEDULE_ACTIVATE`
- `SCHEDULE_DEACTIVATE`
- `SCHEDULE_PAUSE`
- `SCHEDULE_RESUME`
- `RUN_CANCELLED`
- `RUN_MARK_FAILED_BY_OPS`
- `OPS_MARK_FAILED_APPLY`
- `OPS_MARK_FAILED_DRY_RUN`
- `SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN`

**S7-13에서 제외 또는 optional:**

- `RUN_WORKER_CLAIMED` / `RUN_COMPLETED` / `RUN_FAILED` — 로그량↑ · sampling 후속
- `OPS_STUCK_QUERY` / `ADMIN_*_VIEWED` — 노이즈 · S7-14+ 선택
- `RUN_MANUAL_REQUESTED` / `RUN_SCHEDULED_ENQUEUED` — 유용하나 최소 세트 밖 (S7-13 확장 후보)

---

## 6. Audit DB 설계 후보 (S7-13)

> S7-11에서는 **migration하지 않는다.** 아래는 S7-13 PoC용 설계.

### 테이블: `tb_visual_pipeline_audit_log`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `audit_id` | VARCHAR(40) PK | 예: `VPAU-...` |
| `event_type` | VARCHAR(80) NOT NULL | §5 event_type |
| `event_source` | VARCHAR(40) NOT NULL | `API` / `WORKER` / `CLI` / `UI` |
| `pipeline_id` | VARCHAR(40) NULL | |
| `visual_run_id` | VARCHAR(40) NULL | |
| `activation_id` | VARCHAR(40) NULL | |
| `materialization_result_id` | VARCHAR(40) NULL | |
| `r10_schedule_id` | VARCHAR(40) NULL | |
| `actor_type` | VARCHAR(40) NULL | `SYSTEM` / `USER` / `CLI` / `WORKER` |
| `actor_id` | VARCHAR(120) NULL | Auth 전: `mock_admin` / `system` / `cli` / `worker_id` |
| `action_status` | VARCHAR(30) NOT NULL | `SUCCESS` / `FAILED` / `DRY_RUN` / `SKIPPED` |
| `request_id` | VARCHAR(120) NULL | 상관 ID (optional) |
| `reason` | VARCHAR(200) NULL | 운영 사유 |
| `before_json` | JSONB NULL | 최소 상태 before |
| `after_json` | JSONB NULL | 최소 상태 after |
| `metadata_json` | JSONB NULL | redacted 부가 정보 |
| `created_at` | TIMESTAMP NOT NULL DEFAULT NOW() | |

### 인덱스 후보

- `(event_type, created_at DESC)`
- `(pipeline_id, created_at DESC)`
- `(visual_run_id, created_at DESC)`
- `(activation_id, created_at DESC)`

### 저장 금지 / 최소 원칙

- **secret raw 저장 금지**
- `request_json` / `result_json` **전체 복사 금지**
- before/after는 상태 필드만 (예: `activation_status`, `run_status`, `next_due_at`, `locked_until`)
- PII/secret **redaction helper 필수**

### Secret redaction 기준

키 이름에 다음 포함 시 값 → `***REDACTED***`:

- `secret` · `token` · `password` · `credential` · `api_key` · `authorization`

(기존 Manual Run sanitize 패턴과 정합.)

---

## 7. Audit API 설계 후보 (S7-13)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/visual-pipeline-ops/audit-logs` | 목록 · filter |
| GET | `/api/v1/visual-pipeline-ops/audit-logs/{audit_id}` | 단건 |

Query 후보: `event_type` · `pipeline_id` · `visual_run_id` · `activation_id` · `created_from` · `created_to` · `limit`

- **Write HTTP API 없음** — 이벤트 생성은 내부 service만
- Admin UI는 audit list **read-only**
- 기존 summary / stuck-runs API **변경하지 않음** (경로만 추가)

---

## 8. Audit service 설계 후보 (S7-13)

파일 후보: `backend/app/services/visual_pipeline/audit_service.py`

| 함수 | 역할 |
|------|------|
| `record_visual_pipeline_audit_event(...)` | 공통 insert |
| `sanitize_audit_payload(...)` | secret redaction |
| `record_activation_event(...)` | activate/deactivate/pause/resume |
| `record_run_cancel_event(...)` | PENDING cancel |
| `record_ops_mark_failed_event(...)` | dry-run / apply |
| `list_audit_logs(...)` | read API용 |

### audit write 실패 정책

| 단계 | 정책 |
|------|------|
| **S7-13 PoC** | audit write 실패 → **main action 성공 유지** · warning log (**fail-open**) |
| **S7-14+** | mark-failed 등 위험 액션은 **fail-close**(audit 필수) 검토 |

---

## 9. 권한 / Admin 경계

### 9.1 현재

- Frontend: `VITE_USER_ROLE` mock (`ADMIN` | `OPERATOR` | `VIEWER`)
- Backend: Admin 권한 검증 **없음** (1차 범위 Auth 미구현)
- 내부 PoC / 배포 전제: 네트워크·접근 통제에 의존

### 9.2 S7-12 Admin UI

| 항목 | 정책 |
|------|------|
| 메뉴 표시 | `VITE_USER_ROLE=ADMIN`일 때만 Admin Ops 메뉴 |
| 비ADMIN 직접 URL | 페이지에서 “ADMIN mock role 필요” 안내 또는 list로 redirect (S7-12에서 택1 · **권장: 안내 + 빈 상태**) |
| Backend ops API | read-only이므로 **권한 미적용 가능** (현행 유지) |
| README | **“임시 mock role — 운영 권한 아님”** 명시 필수 |

### 9.3 S7-13 Audit actor

| source | actor_type | actor_id 예 |
|--------|------------|-------------|
| API | USER | `mock_admin` (또는 후속 header) |
| CLI | CLI | `cli` |
| WORKER | WORKER | `worker_id` |
| SYSTEM | SYSTEM | `system` |

실제 Auth 도입 시 `actor_id`를 인증 subject로 교체.

### 9.4 S7-14 Admin Actions

- mark-failed API/UI는 **최소 backend admin check** 또는 동등 통제가 생긴 뒤 권장
- Auth 전: UI action **보류** · CLI + audit로 운영

---

## 10. Test 전략

### 10.1 S7-12 Admin Ops UI

**Frontend**

- `check-pages.mjs`에 Admin Ops route 추가
- smoke:
  - ops summary 로드
  - run / activation status counts 표시
  - stuck runs table 표시
  - recent failures 표시
  - refresh 동작
  - **action 버튼 없음** 확인
- `VITE_USER_ROLE=ADMIN` → 메뉴 표시 · 비ADMIN → 숨김/제한

**Backend**

- 기존 `test_visual_pipeline_ops.py` 유지
- read-only API가 DB를 변경하지 않음 확인 (현행)

### 10.2 S7-13 Audit Log

**Backend**

1. migration re-run PASS  
2. activate → audit row  
3. pause / resume / deactivate → audit row  
4. run cancel → audit row  
5. mark-failed dry-run / apply CLI → audit row  
6. secret redaction  
7. list filter (pipeline / event / run)  
8. audit failure가 main action을 막지 않음 (fail-open)  
9. quick regression **미포함** 권장  

**Frontend (optional in S7-13)**

- Admin Audit tab/list smoke · event_type filter  
- detail modal은 optional  

---

## 11. Roadmap

### 권장 순서

| 단계 | 내용 | 성격 |
|------|------|------|
| **R11-S7-11** | Admin UI / Audit 설계 (본 문서) | docs-only |
| **R11-S7-12** | Admin Ops UI PoC — read-only page · summary/stuck/failures · no mark-failed UI | FE + API client |
| **R11-S7-13** | Audit Log PoC — table/service/API · 최소 이벤트 · Admin Audit list | DB + BE (+ FE list) |
| **R11-S7-14** | Admin Action PoC — mark-failed HTTP/UI · confirm · audit required | BE + FE |
| **R11-S8** | Run History / Progress / Retry 설계 — retry · RUNNING cancel · progress · catch-up · notification | docs → 이후 PoC |

### 왜 UI를 Audit보다 먼저 하는가

- S7-10 read-only ops API가 **이미 존재** → S7-12로 사용성·운영 가시성을 빠르게 확인 가능
- Audit는 이벤트 계측 포인트가 넓어 **설계 확정 후** 한 번에 붙이는 편이 안전
- 대안(Audit 선구현)도 가능하나, 본 문서는 **S7-12 → S7-13 → S7-14**를 권장한다

### S7-12 / S7-13에서 제외할 항목

| 제외 | 사유 |
|------|------|
| mark-failed HTTP/UI | S7-14 · audit/권한 선행 |
| Studio Ops Panel 대규모 추가 | B안 우선 · Studio 안정 |
| process liveness probe | Docker/README 영역 |
| retry / RUNNING interrupt / progress / catch-up / notification | R11-S8 |
| Auth/SSO/JWT | 1차 범위 밖 |
| R10 due-worker 연결 · `active_yn=true` | 기존 경계 유지 |
| Redis/Celery/queue · 신규 package | 금지 |

---

## 12. Decision Log

| ID | 결정 |
|----|------|
| **D1** | S7-12 Admin Ops UI는 **read-only**로 시작한다. |
| **D2** | mark-failed UI/API는 audit/admin 권한 준비 전까지 **보류**한다. |
| **D3** | mark-failed는 S7-12에서도 **CLI-only** 유지한다. |
| **D4** | Admin Ops Page는 Studio 내부가 아닌 **별도 route**를 권장한다 (`/visual-pipeline-ops` 1차). |
| **D5** | Audit table은 별도 **`tb_visual_pipeline_audit_log`** 를 권장한다. |
| **D6** | Audit payload는 **secret redaction** 후 **최소 상태값**만 저장한다. |
| **D7** | Auth 전 actor는 **`mock_admin` / `system` / `cli` / `worker_id`** 로 기록한다. |
| **D8** | S7-13 PoC에서 audit write 실패는 **main action을 막지 않는다** (fail-open). |
| **D9** | worker high-volume events(`CLAIMED`/`COMPLETED`/`FAILED`)는 S7-13 최소 범위에서 **제외 또는 optional**. |
| **D10** | Admin destructive action은 **S7-14 이후**로 분리한다. |
| **D11** | Roadmap은 **S7-12 UI → S7-13 Audit → S7-14 Action** 순을 권장한다. |
| **D12** | S7-11은 **docs-only** — code/DB/API/FE/package 변경 없음. |
| **D13** | Frontend Admin 메뉴는 `VITE_USER_ROLE=ADMIN` mock 표시만 · **운영 권한 아님**. |
| **D14** | 기존 S7-10 ops summary/stuck-runs API는 S7-12에서 **변경 없이 소비**한다. |

---

## 13. 본 문서 범위 확인

| 항목 | S7-11 |
|------|------|
| Admin UI 구현 | **없음** |
| Audit table/API 구현 | **없음** |
| mark-failed HTTP API | **없음** |
| ops API 변경 | **없음** |
| DB/schema/migration | **없음** |
| FE/Studio UI | **없음** |
| Auth/Login/SSO/JWT | **없음** |
| R10 due-worker / `active_yn` | **없음** |
| retry/interrupt/progress/notification | **없음** |
| package | **없음** |

---

## 14. 참고 코드 / 문서 (후속 구현 시)

- `backend/app/api/v1/visual_pipeline_ops.py`
- `backend/app/services/visual_pipeline/ops_service.py`
- `scripts/manage_visual_pipeline_ops.py`
- `backend/app/services/visual_pipeline/schedule_activation_service.py`
- `backend/app/services/visual_pipeline/manual_run_service.py` (cancel · sanitize)
- `frontend/src/pages/VisualPipelineStudioPage.tsx`
- `frontend/src/App.tsx` (route/menu 패턴)
- `docs/md/THERMOps_R11-S7-7_Schedule_Activation_설계.md`
- README R11-S7-8 / S7-9 / S7-10
