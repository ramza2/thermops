# THERMOps R11-S7-15 Visual Pipeline 운영 기능 마감 정리

> **단계:** R11-S7-15  
> **성격:** docs-only 마감 정리 (code / DB / API / FE / worker / package 변경 없음)  
> **기준 커밋:** `65e2884` — `feat(R11-S7-14): Admin mark-failed action PoC 추가`  
> **범위:** R11-S7-0 ~ R11-S7-14 Visual Pipeline 운영 기능 1차 완성 단위 정리

---

## 1. 문서 개요

본 문서는 Visual Pipeline의 **Manual Run · Background/Worker 실행 · Schedule Activation · Ops/Admin · Audit · mark-failed Action**까지 R11-S7에서 구현된 운영 기능을 한 번에 정리한다.

목적:

1. S7-0~S7-14 산출물과 운영 경계를 한 문서에서 조망한다.
2. 배포·점검·장애 대응 체크리스트를 운영자가 바로 쓸 수 있게 한다.
3. Known Limitation과 R11-S8 backlog를 분리한다.
4. UI 용어 정리(「R10 설정 반영」→「실행 설정 반영」)와 열수요 예측 Full Scenario 이용가이드를 후속으로 남긴다.

비범위:

- production code / schema / migration / API / FE / worker / compose / env / package 변경
- Auth/SSO/JWT, retry, RUNNING interrupt, progress streaming, notification 구현
- R10 `run-due-worker` 연결, R10 `active_yn=true` 전환

---

## 2. R11-S7 전체 목표와 완료 범위

### 2.1 목표

Visual Pipeline Studio에서 **Compile → 실행 설정 반영(materialization) → Manual/Scheduled Run → 운영 조회/정리**까지를 PoC 수준으로 닫는다.

### 2.2 완료 범위 (요약)

| 영역 | 완료 |
|------|------|
| Manual Run | API + Studio Run Now + polling |
| 실행기 | BackgroundTasks(transitional) + `vp-run-worker`(운영 권장) |
| Schedule | Activation API/UI + `vp-schedule-worker` enqueue |
| Hardening | pause/resume · skip/missed · PENDING cancel |
| Ops | summary/stuck API · mark-failed CLI · Admin Ops UI |
| Audit/Action | audit log + Admin mark-failed (fail-close apply) |

### 2.3 의도적 비완료 (S8+)

retry · detailed progress · RUNNING interrupt · notification · catch-up multi-slot · 실 Auth/Admin ACL · Full Scenario 이용가이드 · Studio 용어 polish

---

## 3. S7-0 ~ S7-14 단계별 기능 요약

| 단계 | 주제 | 완료 내용 | 핵심 산출물 | 상태 |
|------|------|----------|------------|------|
| S7-0 | Run 설계 | Manual/Scheduled 경계, status/이력/보안 방향 | `THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md` | docs |
| S7-1 | Manual Run API | `POST/GET .../runs`, `tb_visual_pipeline_run`, R10 `run_load` 동기 래핑 | `manual_run_service.py`, migration run table | 완료(PoC) |
| S7-2 | Background 검토 | Option B transitional / Option C 운영 목표 | `THERMOps_R11-S7-2_Background_Run_전환_검토.md` | docs |
| S7-3 | Background Backend | POST 202 · PENDING→RUNNING→terminal · BackgroundTasks | `manual_run_service.py` | 완료(PoC) |
| S7-4 | Studio Run UI | Run Now · polling · Run Panel | `VisualPipelineStudioPage`, `VpRunPanel` | 완료(PoC) |
| S7-5 | Option C 검토 | claim/lock/heartbeat · `vp-run-worker` 필요성 | `THERMOps_R11-S7-5_Option_C_Run_Worker_검토.md` | docs |
| S7-6 | VP run-worker | executor flag · claim 컬럼 · compose `vp-run-worker` | `run_worker_service.py`, `visual_pipeline_run_worker` | 완료(PoC) |
| S7-7 | Activation 설계 | Activation ≠ R10 due-worker · R10 `active_yn=false` | `THERMOps_R11-S7-7_Schedule_Activation_설계.md` | docs |
| S7-8 | Activation PoC | activation API/UI · `vp-schedule-worker` · SCHEDULED PENDING | `schedule_activation_service.py`, `schedule_worker_service.py` | 완료(PoC) |
| S7-9 | Hardening | pause/resume · skip/missed · PENDING cancel | activation/run services · Studio panels | 완료(PoC) |
| S7-10 | 운영 안정화 | ops summary/stuck API · mark-failed CLI · 배포 절차 | `ops_service.py`, `manage_visual_pipeline_ops.py` | 완료(PoC) |
| S7-11 | Admin/Audit 설계 | read-only Ops UI · audit/action roadmap | `THERMOps_R11-S7-11_Admin_UI_Audit_설계.md` | docs |
| S7-12 | Admin Ops UI | `/visual-pipeline-ops` · mock ADMIN | `VisualPipelineOpsPage.tsx` | 완료(PoC) |
| S7-13 | Audit Log | `tb_visual_pipeline_audit_log` · read API · UI list · fail-open 기본 | `audit_service.py` | 완료(PoC) |
| S7-14 | Admin Action | mark-failed API/UI · strong confirm · apply fail-close | `ops_service` mark-single · Ops UI modal | 완료(PoC) |
| S7-15 | 마감 정리 | 본 문서 + README 요약 | 본 파일 | docs-only |

---

## 4. 최종 기능 아키텍처

### 4.1 구성 요소

| 구성요소 | 역할 |
|----------|------|
| Visual Pipeline Studio (`/visual-pipelines/:id`) | Compile · materialize · Run Now · Activation · Run Panel |
| Admin Ops UI (`/visual-pipeline-ops`) | 운영 조회 · stuck 한정 mark-failed · Audit list |
| `backend` | Visual Pipeline / Ops / Audit API |
| `vp-run-worker` | PENDING claim → R10 `run_load` |
| `vp-schedule-worker` | due ACTIVE activation → SCHEDULED PENDING enqueue |
| `run-due-worker` | R10 전용 due (Visual Pipeline schedule과 **분리**) |
| PostgreSQL | run / activation / audit / materialization |

### 4.2 운영 env (핵심)

| 변수 | 의미 | 운영 권장 |
|------|------|-----------|
| `THERMOOPS_VP_RUN_EXECUTOR` | `background_tasks` \| `worker` | `worker` |
| `THERMOOPS_VP_RUN_WORKER_ENABLED` | run-worker 기동 | `true` |
| `THERMOOPS_VP_RUN_WORKER_LOCK_TTL_SECONDS` | claim lock TTL | `300` (배포 예시) |
| `THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED` | Activation API | `true` |
| `THERMOOPS_VP_SCHEDULE_WORKER_ENABLED` | schedule-worker | `true` |
| `THERMOOPS_VP_ADMIN_ACTIONS_ENABLED` | Admin mark-failed HTTP/UI | 기본 `false` |
| `VITE_USER_ROLE` | FE mock 표시 제어 | `ADMIN`일 때만 Ops 메뉴/액션 |

---

## 5. Manual Run 흐름

```text
Visual Pipeline Studio (/visual-pipelines/:id)
  → (선택) Compile → 실행 설정 반영(materialize)
  → Run Now
  → POST /api/v1/visual-pipelines/{pipeline_id}/runs
  → HTTP 202 + tb_visual_pipeline_run(mode=MANUAL, PENDING)
  → [worker] vp-run-worker claim
      또는 [local] BackgroundTasks in-process
  → R10 run_load
  → SUCCESS / PARTIAL / FAILED
  → Run Panel GET polling
```

주의:

- Studio에서 `run_load`를 직접 호출하지 않는다.
- 운영은 `THERMOOPS_VP_RUN_EXECUTOR=worker` + `vp-run-worker` 기동을 권장한다.
- worker 미기동 + worker mode면 PENDING stuck 가능.

---

## 6. Background Run / VP Run Worker 흐름

```text
POST /runs (executor=worker)
  → PENDING enqueue only (BackgroundTasks 미등록)
  → vp-run-worker loop/once
  → FOR UPDATE SKIP LOCKED claim
  → claimed_at / claimed_by / locked_until / heartbeat_at / attempt_count
  → R10 run_load
  → terminal + lease clear
```

관련 스크립트:

- `scripts/run_visual_pipeline_worker.py`
- `python -m app.workers.visual_pipeline_run_worker`

Known limitation (S7-6~): 자동 retry · cancel interrupt · detailed progress · process liveness probe 없음.

---

## 7. Schedule Activation / Schedule Worker 흐름

```text
Compile SUCCESS
  → materialize SUCCESS (schedule row upsert, active_yn=false)
  → Schedule Activation ACTIVE
  → vp-schedule-worker due scan (next_due_at <= now)
  → tb_visual_pipeline_run(mode=SCHEDULED, PENDING)
       + activation_id / scheduled_for / r10_schedule_id / dedup_key
  → vp-run-worker claim → run_load → terminal
```

주의:

- R10 `active_yn=false` 유지 (D5).
- R10 `run-due-worker`는 Visual Pipeline schedule enqueue에 **사용하지 않는다**.
- `vp-schedule-worker`는 enqueue만, 실행은 `vp-run-worker`.

---

## 8. Pause / Resume / Deactivate / Cancel 정책

| 액션 | 대상 | 효과 | Audit (상태 변경 시) |
|------|------|------|----------------------|
| Pause | ACTIVE activation | PAUSED · due enqueue 중지 | `SCHEDULE_PAUSE` |
| Resume | PAUSED | ACTIVE · `next_due_at` 재계산 | `SCHEDULE_RESUME` |
| Deactivate | ACTIVE/PAUSED | INACTIVE | `SCHEDULE_DEACTIVATE` |
| Activate | — | 신규 ACTIVE row | `SCHEDULE_ACTIVATE` |
| Cancel | PENDING run only | CANCELLED | `RUN_CANCELLED` |

정책:

- idempotent no-op은 audit 제외.
- RUNNING cancel **미지원** (409).
- terminal cancel 409.
- Activation API는 `run_load`를 호출하지 않는다.
- Admin Ops Page에는 pause/resume/deactivate/cancel 버튼을 **두지 않는다** (Studio 담당).

---

## 9. Ops API / Admin Ops UI 흐름

```text
Admin Ops UI /visual-pipeline-ops  (VITE_USER_ROLE=ADMIN)
  → GET /api/v1/visual-pipeline-ops/summary
  → GET /api/v1/visual-pipeline-ops/stuck-runs
  → GET /api/v1/visual-pipeline-ops/audit-logs
  → (optional) POST .../stuck-runs/{visual_run_id}/mark-failed
        require THERMOOPS_VP_ADMIN_ACTIONS_ENABLED=true
        strong confirm + reason
        audit required fail-close
        → run_status=FAILED
```

CLI (flag 비연동, apply는 fail-close):

```bash
python scripts/manage_visual_pipeline_ops.py summary
python scripts/manage_visual_pipeline_ops.py stuck-runs --pending-age-seconds 600
python scripts/manage_visual_pipeline_ops.py mark-failed --dry-run --pending-age-seconds 600
python scripts/manage_visual_pipeline_ops.py mark-failed --apply --reason "manual ops cleanup"
```

Stuck 기준:

- `PENDING_TOO_OLD`: PENDING + created_at 초과
- `RUNNING_LOCK_EXPIRED`: RUNNING + locked_until not null + expired (grace)

---

## 10. Audit Log / Admin Action 흐름

```text
API / CLI / WORKER action
  → audit_service.record_...
  → tb_visual_pipeline_audit_log
  → Admin Ops UI Audit Logs (list)
```

### 10.1 최소 이벤트 (S7-13+)

| event_type | 트리거 |
|------------|--------|
| `SCHEDULE_ACTIVATE` / `DEACTIVATE` / `PAUSE` / `RESUME` | Activation API 실변경 |
| `RUN_CANCELLED` | PENDING→CANCELLED |
| `OPS_MARK_FAILED_DRY_RUN` | CLI dry-run |
| `OPS_MARK_FAILED_APPLY` | CLI apply 배치 요약 (fail-open) |
| `RUN_MARK_FAILED_BY_OPS` | per-run mark-failed (apply fail-close) |
| `SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN` | ACTIVE_RUN_EXISTS skip |

### 10.2 Fail-open vs Fail-close

| 경로 | 정책 |
|------|------|
| activate/deactivate/pause/resume · cancel · worker skip · dry-run · audit read | **fail-open** |
| mark-failed **apply** (CLI / Admin API / Admin UI) | **fail-close** (audit 실패 시 run 변경 금지) |

### 10.3 Actor

| source | actor_type | actor_id |
|--------|------------|----------|
| API/UI | USER | mock_admin |
| CLI | CLI | cli |
| WORKER | WORKER | worker_id |

---

## 11. 운영 배포 체크리스트

### 11.1 배포 전

```bash
git status
git pull
git log --oneline -5
```

확인 (`.env.deploy`):

- `THERMOOPS_VP_RUN_EXECUTOR=worker`
- `THERMOOPS_VP_RUN_WORKER_ENABLED=true`
- `THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED=true`
- `THERMOOPS_VP_SCHEDULE_WORKER_ENABLED=true`
- `THERMOOPS_VP_ADMIN_ACTIONS_ENABLED=false` (Admin Action PoC 테스트 시에만 true)
- `THERMOOPS_VP_RUN_WORKER_LOCK_TTL_SECONDS` (배포 예 300)

### 11.2 Migration

```bash
python3 scripts/apply_dev_migrations.py
```

### 11.3 기동

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build \
  backend frontend vp-run-worker vp-schedule-worker
```

### 11.4 상태 확인

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy ps
docker compose -f docker-compose.traefik.yml --env-file .env.deploy logs -f backend
docker compose -f docker-compose.traefik.yml --env-file .env.deploy logs -f vp-run-worker
docker compose -f docker-compose.traefik.yml --env-file .env.deploy logs -f vp-schedule-worker
```

### 11.5 Smoke

```bash
python scripts/test_visual_pipeline_ops.py
python scripts/test_visual_pipeline_audit_log.py
python scripts/test_visual_pipeline_admin_action.py

cd frontend
npm run build
node scripts/check-pages.mjs
node scripts/check-visual-pipeline-ops.mjs
```

주의:

- Docker FE Vite 캐시가 구버전을 서빙할 수 있음 → smoke 실패 시 frontend 재시작 후 재확인.
- 운영 외부 API 호출 smoke는 별도 통제 환경에서만 수행.

---

## 12. 운영 점검 체크리스트

### 12.1 Admin Ops UI (`/visual-pipeline-ops`)

- [ ] Run Status Counts
- [ ] Activation Status Counts
- [ ] Stuck Summary
- [ ] Worker Config (`admin_actions_enabled` 포함)
- [ ] Activity Hints
- [ ] Stuck Runs
- [ ] Recent Failures
- [ ] Audit Logs (event_type filter / 새로고침)

비ADMIN: admin-required 안내 · ops/audit/mark-failed API 미호출.

### 12.2 CLI

```bash
python scripts/manage_visual_pipeline_ops.py summary
python scripts/manage_visual_pipeline_ops.py stuck-runs --pending-age-seconds 600
python scripts/manage_visual_pipeline_ops.py mark-failed --dry-run --pending-age-seconds 600
```

### 12.3 Admin Action (선택)

- [ ] `THERMOOPS_VP_ADMIN_ACTIONS_ENABLED=true`
- [ ] Stuck row `실패 처리` → Run ID 재입력 + reason(≥5)
- [ ] 성공 메시지 / FAILED 반영
- [ ] Audit Logs에 `RUN_MARK_FAILED_BY_OPS` 확인

---

## 13. 장애 대응 체크리스트

### 13.1 Run이 PENDING에서 멈춤

| | |
|--|--|
| 원인 | vp-run-worker 미기동 · executor=worker인데 worker 없음 · claim 실패 |
| 확인 | compose `ps` · worker logs · ops stuck-runs · `claimed_at`/`locked_until` |
| 조치 | worker 재기동 · stuck 확인 · mark-failed dry-run → 필요 시 CLI apply 또는 Admin Action |

### 13.2 Run이 RUNNING에서 멈춤

| | |
|--|--|
| 원인 | worker crash · lock TTL 만료 · long-running |
| 확인 | `locked_until` expired 여부 · `heartbeat_at` · worker logs |
| 조치 | worker 재기동 · expired면 mark-failed · non-expired면 대기 (강제 interrupt 없음) |

### 13.3 Scheduled run이 생성되지 않음

| | |
|--|--|
| 원인 | activation PAUSED/INACTIVE · next_due 미래 · schedule-worker 미기동 · skip |
| 확인 | activation status · `next_due_at` · `missed_count`/`last_skip_reason` · schedule-worker logs |
| 조치 | resume/재활성화 · worker 재기동 · skip reason(`ACTIVE_RUN_EXISTS` 등) 확인 |

### 13.4 mark-failed 실패

| | |
|--|--|
| 원인 | feature flag off · confirm mismatch · not eligible · audit fail-close · terminal |
| 확인 | HTTP detail code · stuck-runs 재조회 · audit/DB |
| 조치 | 목록 새로고침 · reason/confirm 재입력 · CLI dry-run · flag/audit 상태 확인 |

코드 참고: `VP_ADMIN_ACTIONS_DISABLED` · `RUN_MARK_FAILED_CONFIRM_MISMATCH` · `RUN_MARK_FAILED_NOT_ELIGIBLE` · `RUN_MARK_FAILED_AUDIT_REQUIRED_FAILED`

### 13.5 Audit Log가 보이지 않음

| | |
|--|--|
| 원인 | migration 미적용 · filter · 이벤트 미발생 · 비ADMIN |
| 확인 | `apply_dev_migrations.py` · `tb_visual_pipeline_audit_log` · audit API · UI filter |
| 조치 | migration · filter 초기화 · ADMIN mock · 액션 재실행 후 refresh |

### 13.6 Admin Ops UI가 구버전처럼 보임

| | |
|--|--|
| 원인 | Docker FE Vite 캐시 · browser cache |
| 확인 | frontend container · 소스 bind mount · testid 존재 여부 |
| 조치 | |

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy restart frontend
```

---

## 14. 보안/권한 경계

현재:

- `VITE_USER_ROLE`은 **Frontend mock 표시 제어**이며 운영 권한 체계가 아니다.
- Backend Admin ACL / Auth/Login/SSO/JWT **없음**.
- `THERMOOPS_VP_ADMIN_ACTIONS_ENABLED`는 **기능 노출 안전장치**이며 Auth 대체가 아니다.
- Admin Action · Audit actor(`mock_admin`)는 PoC이다.
- Audit payload는 secret recursive redaction · request/result JSON 전체 복사 금지.

후속 필요:

- 실 Auth + backend authorization
- actor_id를 인증 subject로 연계
- destructive action fail-close 범위 확대
- 운영 네트워크/접근 통제와 권한 체계 정합

---

## 15. 사용자 UI 용어 정리 필요사항

### 결정 (S7-15에서 UI 변경하지 않음)

현재 Studio 버튼명 **「R10 설정 반영」**은 내부 개발 단계명이 사용자에게 노출된 표현이다.

후속 UI 정리(S8-1)에서 버튼명을 **「실행 설정 반영」**으로 변경한다.

툴팁/설명 후보:

```text
현재 Visual Pipeline 그래프의 Compile 결과를 실행 설정으로 반영합니다.
외부 API 호출, 데이터 적재, 스케줄 활성화는 수행하지 않습니다.
```

함께 정리할 문구 후보:

- Compile / 실행 설정 반영 / Run Now / Schedule Activation 도움말
- materialization panel 내 “R10” 표기

---

## 16. Known Limitations

- 실 Auth / Backend Admin ACL 없음
- `VITE_USER_ROLE` mock · Admin Action feature flag는 Auth 대체 아님
- RUNNING interrupt / cancel 미지원
- retry 없음
- detailed / step-level progress 없음
- notification 없음
- multi-slot catch-up 없음
- process liveness 직접 probe 없음 (DB 상태·힌트만)
- R10 `run-due-worker`와 Visual Pipeline schedule **분리**
- R10 `active_yn=false` 유지
- mark-failed는 복구/rollback이 아님 (FAILED 강제 정리)
- audit는 최소 상태값만 · high-volume worker 이벤트 일부 미기록
- Option B(`background_tasks`)는 프로세스 재시작 시 stuck 가능
- 운영 외부 API 호출 smoke는 별도 통제 환경 필요
- Studio 「R10 설정 반영」 용어는 아직 사용자 친화 명칭이 아님

---

## 17. R11-S8 이후 Backlog

### R11-S8-0 Run History / Progress / Retry 설계

- run 상세 이력 · step-level progress
- retry policy · RUNNING cancel/interrupt 가능성
- catch-up · notification · worker recovery
- run artifact/log link

### R11-S8-1 UI 용어/UX 정리

- 「R10 설정 반영」→「실행 설정 반영」
- Compile / materialize / Run Now / Activation 문구·툴팁

### R11-S8-2 열수요 예측 Full Scenario 이용가이드 설계

- 실적/기상/특일 API → Transform → Upsert → Feature → 학습 → 예측 → 비교 → 스케줄

### R11-S8-3 Full Scenario 기반 UX 보완

- 가이드 수행 중 발견한 불편/미완 기능 반영 (즉시 섞지 않고 분리)

### 권장 순서

1. S7-15 마감 정리 (본 문서)  
2. **S8-0** Run History / Progress / Retry 설계  
3. **S8-1** UI 용어/UX 정리  
4. **S8-2** Full Scenario 이용가이드 설계  
5. **S8-3** Full Scenario 기반 UX 보완  

대안: 사용성 확인을 우선하면 S8-1/S8-2를 S8-0보다 앞당길 수 있다.  
운영 run 기능 완결성 관점에서는 **S8-0 우선**을 권장한다.

---

## 18. 열수요 예측 Full Scenario 이용가이드 후속 계획

Pipeline Studio가 운영 PoC로 닫힌 뒤, 사용자가 MLOps/Studio를 **실제 업무 시나리오**로 이해하도록 별도 가이드 작업을 둔다.

### 후속 후보

- `R11-S8-2 열수요 예측 Full Scenario 이용가이드 설계`
- `R11-S8-3 이용가이드 기반 UX/기능 보완`

### 예상 따라하기 흐름

1. 열수요실적 API Source 등록  
2. 기상 API Source 등록  
3. 특일/휴일 API Source 등록  
4. Transform으로 날짜/지사/시간 정규화  
5. Upsert Load로 원천/표준 테이블 적재  
6. Feature Dataset 생성  
7. 학습 대상 기간 선택  
8. 모델 학습 실행  
9. 예측 실행  
10. 예측 결과와 실적 비교  
11. 오류/누락/품질 이슈 확인  
12. 스케줄 활성화  

원칙:

- Studio 완성 후 작성한다.
- 가이드 중 불편·미완은 즉시 본편에 섞지 않고 S8-3 backlog로 분리한다.

---

## 19. 최종 Decision Log

| ID | 결정 |
|----|------|
| D1 | R11-S7은 Visual Pipeline 운영 기능 **1차 완성 단위**로 마감한다. |
| D2 | Manual Run과 Scheduled Run은 모두 `tb_visual_pipeline_run`으로 통합 관리한다. |
| D3 | 운영 실행은 **worker mode**를 권장한다. |
| D4 | Schedule Activation은 R10 due-worker와 **분리**한다. |
| D5 | R10 `active_yn=false`를 유지한다. |
| D6 | `vp-schedule-worker`는 scheduled PENDING **enqueue만** 담당한다. |
| D7 | `vp-run-worker`는 PENDING claim 후 `run_load`를 실행한다. |
| D8 | Admin Ops UI는 운영 조회와 **stuck 한정** mark-failed를 담당한다. |
| D9 | mark-failed **apply**는 CLI/API/UI 모두 audit required **fail-close**다. |
| D10 | Auth 전 Admin 기능은 mock role + feature flag 기반 PoC다. |
| D11 | Audit은 최소 운영 이벤트 중심으로 기록한다. |
| D12 | retry / progress / RUNNING interrupt / notification은 **R11-S8**로 넘긴다. |
| D13 | 「R10 설정 반영」은 후속 UI 정리에서 **「실행 설정 반영」**으로 변경한다. |
| D14 | 열수요 예측 Full Scenario 이용가이드는 Studio 완성 후 별도 작업으로 진행한다. |
| D15 | S7-15는 **docs-only**이며 code/DB/API/FE/package 변경이 없다. |

---

## 20. 검증 / 마감 기준

S7-15 마감 기준:

- [x] 본 마감 문서 작성
- [x] README R11-S7-15 요약·링크·다음 단계 갱신
- [x] S7-0~S7-14 기능 맵
- [x] Manual / Scheduled / Ops-Admin / Audit 흐름
- [x] 배포·점검·장애 체크리스트
- [x] 보안/권한 경계 · Known Limitations · S8 backlog · UI 용어 · Full Scenario 후속 · Decision Log

docs-only이므로 build/test는 생략한다.

검증 명령 예:

```bash
git diff --stat
git diff README.md
dir docs\md | findstr R11-S7-15
```

---

## 참조

- README R11-S7-0 ~ S7-14 섹션
- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md`
- `docs/md/THERMOps_R11-S7-5_Option_C_Run_Worker_검토.md`
- `docs/md/THERMOps_R11-S7-7_Schedule_Activation_설계.md`
- `docs/md/THERMOps_R11-S7-11_Admin_UI_Audit_설계.md`
