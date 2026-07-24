# THERMOps R11-S8-0 Run History / Progress / Retry 설계

> **단계:** R11-S8-0  
> **성격:** docs-only 설계 / 검토 (code / DB / API / FE / worker / package 변경 없음)  
> **기준 커밋:** `a141944` — `docs(R11-S7-15): Visual Pipeline 운영 기능 마감 정리 추가`  
> **선행:** R11-S7 Visual Pipeline 운영 기능 1차 완성 (S7-0 ~ S7-15)

---

## 1. 문서 개요

본 문서는 R11-S7에서 1차 완성한 Visual Pipeline 운영 기능 위에, **R11-S8에서 다룰 Run History / Step-level Progress / Retry / RUNNING Interrupt / Schedule Catch-up / Notification** 방향을 설계한다.

목적:

1. S7 완료 상태와 S8 설계 목적을 한 문서에서 조망한다.
2. History / Progress / Retry / Interrupt / Catch-up / Notification을 **한 번에 구현하지 않고** 단계별 PoC로 나눈다.
3. R11-S8 구현 항목과 R12+ / 별도 보안 단계로 넘길 항목을 분리한다.
4. 「R10 설정 반영」→「실행 설정 반영」UI 용어 정리와 열수요 예측 Full Scenario 이용가이드와의 관계를 명시한다.

비범위 (본 단계):

- production code / schema / migration / API / FE / worker / compose / env / package 변경
- retry · progress · RUNNING interrupt · catch-up · notification 구현
- Auth/Login/SSO/JWT/User management · Admin ACL 구현
- R10 `run-due-worker` 연결 · R10 `active_yn=true` 전환

---

## 2. S7 완료 상태와 S8 설계 목적

### 2.1 S7에서 닫힌 것

| 영역 | 상태 |
|------|------|
| Compile → materialization(실행 설정 반영) | 완료(PoC) |
| Manual Run (HTTP 202 PENDING + polling) | 완료(PoC) |
| `vp-run-worker` claim / lock / heartbeat / `run_load` | 완료(PoC, 운영 권장) |
| Schedule Activation + `vp-schedule-worker` enqueue | 완료(PoC) |
| pause / resume / deactivate · PENDING cancel · skip/missed | 완료(PoC) |
| Ops summary / stuck · mark-failed CLI/API/UI | 완료(PoC) |
| Audit Log · mark-failed apply fail-close | 완료(PoC) |
| S7 마감 정리 (체크리스트 · Known Limitations) | docs-only 완료 |

### 2.2 S8 설계 목적

운영자가 **“무슨 일이 일어났는지 / 어디서 멈췄는지 / 어떻게 다시 돌릴지”**를 볼 수 있게 가시성·복구를 확장한다.

| S8 테마 | 한 줄 |
|---------|------|
| Run History | 단일·목록 이력 조회 고도화 |
| Progress | step-level timeline / percent |
| Retry | 실패 run 재시도 + lineage |
| Interrupt | RUNNING soft cancel 검토 |
| Catch-up | missed schedule 보상 정책 |
| Notification | 실패/stuck 알림 (audit과 분리) |

### 2.3 S7-15 backlog 번호와의 정렬

S7-15 문서의 초기 backlog는 Full Scenario를 S8-2로 적었으나, **본 문서(S8-0) 로드맵이 우선**한다.

- S8-2 = Run History UI/API 고도화  
- Full Scenario 이용가이드 = **S8-8**  
- Full Scenario UX 보완 = **S8-9**

---

## 3. 현재 Run 모델 요약

### 3.1 테이블: `tb_visual_pipeline_run`

| 컬럼 | 용도 (S7 기준) |
|------|----------------|
| `visual_run_id` | PK |
| `pipeline_id` | 파이프라인 |
| `compile_result_id` | compile 스냅샷 |
| `materialization_result_id` | 실행 설정(materialization) 스냅샷 |
| `graph_version_hash` | 그래프 버전 |
| `load_run_id` | R10 LoadRun 연결 (있을 때) |
| `mode` | `MANUAL` / `SCHEDULED` 등 |
| `execution_mode` | `BACKGROUND` / worker 경로 |
| `run_status` | 아래 상태 모델 |
| `request_json` | 요청 요약 |
| `result_json` | 결과 요약 (run-level) |
| `issues_json` | 이슈 목록 |
| `error_message` | 실패 메시지 |
| `started_at` / `finished_at` / `created_at` | 시간 |
| `claimed_at` / `claimed_by` / `locked_until` / `heartbeat_at` / `attempt_count` | worker lease |
| `activation_id` / `r10_schedule_id` / `scheduled_for` / `triggered_at` / `dedup_key` | schedule provenance |

**아직 없음:** `retry_of_run_id`, `cancel_requested_at`, step event, notification 링크.

### 3.2 상태 모델

| `run_status` | 의미 | S7 지원 |
|--------------|------|---------|
| `PENDING` | 대기 (enqueue됨) | 생성 · cancel 가능 |
| `RUNNING` | worker claim 후 실행 중 | interrupt **불가** (cancel → 409) |
| `SUCCESS` | 정상 종료 | terminal |
| `PARTIAL` | 부분 성공 | terminal |
| `FAILED` | 실패 (실행 실패 또는 mark-failed) | terminal |
| `CANCELLED` | PENDING에서만 취소 | terminal |

활성 집합: `PENDING` ∪ `RUNNING` (`ACTIVE_RUN_STATUSES`).

### 3.3 실행 흐름 (요약)

```text
[Manual]
  POST .../runs → PENDING (202)
    → vp-run-worker claim → RUNNING
    → R10 run_load → SUCCESS | PARTIAL | FAILED

[Scheduled]
  Activation ACTIVE
    → vp-schedule-worker due scan
    → mode=SCHEDULED PENDING (+ scheduled_for, dedup_key)
    → (동일) vp-run-worker → run_load → terminal

[Cancel]
  PENDING only → CANCELLED + audit (fail-open)
  RUNNING → RUN_CANCEL_RUNNING_NOT_SUPPORTED

[Ops]
  stuck list → mark-failed dry-run/apply
  apply = audit required fail-close → FAILED (정리 액션, interrupt 아님)
```

### 3.4 UI가 보는 범위 (S7)

| 화면 | 범위 |
|------|------|
| Studio `VpRunPanel` | latest/current run · polling · PENDING 취소 · issues/error 요약 |
| Studio Schedule panel | activation 상태 · pause/resume/deactivate |
| Admin Ops | summary · stuck · recent failures 성격 조회 · mark-failed · audit list |
| 미지원 | history drawer · step timeline · retry · progress % · interrupt · catch-up · notification |

### 3.5 R10 LoadRun과의 연결

- Visual Run은 `load_run_id`로 R10 LoadRun을 **링크**할 수 있다.
- S7에서는 step-level Visual 이력을 복사하지 않는다.
- S8 History는 **링크 우선**, 상세 로그 복제는 후순위(필요 시 R12+).

---

## 4. Run History 설계

### 4.1 목표

운영자가 단일 `visual_run_id`의 상세 실행 이력과, 파이프라인 단위 목록 필터를 확인할 수 있게 한다.

### 4.2 후보 기능

**List filtering**

- `pipeline_id` (path)
- `mode`, `run_status`
- `activation_id`
- `scheduled_for` range / `created_at` range
- (후속) `retry_of_run_id`

**Detail**

- request / compile / materialization snapshot 요약
- worker claim 정보 (`claimed_by`, lease, heartbeat, attempt_count)
- schedule provenance
- retry lineage (S8-4 이후)
- error / issues 요약
- audit 링크
- `load_run_id` → R10 Load History 링크

**네비게이션**

- Admin Ops: recent failures / stuck → run detail
- Studio Run Panel: latest + history list / detail drawer

### 4.3 설계 결정

| 후보 | 평가 |
|------|------|
| `tb_visual_pipeline_run`만으로 list/detail 확장 | **S8-2 권장 시작점** (migration 없이) |
| 별도 `tb_visual_pipeline_run_event` | Progress용 — **S8-3** |
| R10 Load History 일부 복사 | 비권장 (링크만) |

### 4.4 권장

- **S8-2**에서 기존 run table 기반 list/detail API·UI 고도화
- step-level은 S8-3 event table로 분리
- artifact/log deep link는 History detail의 “연결” 영역으로 두고, 본문 복사는 하지 않음

---

## 5. Step-level Progress 설계

### 5.1 문제

`run_status`는 run-level만 제공한다. 장시간 `RUNNING` 시 어느 단계에서 멈췄는지 알기 어렵다.

### 5.2 후보 비교

#### A안: `result_json` / `issues_json` / heartbeat 확장

| | |
|--|--|
| 장점 | DB 변경 적음, 구현 빠름 |
| 단점 | timeline 조회 어려움, update race, structured history 부적합 |

#### B안: 별도 event table (권장)

테이블 후보: `tb_visual_pipeline_run_event`

| 컬럼 후보 | 설명 |
|-----------|------|
| `event_id` | PK |
| `visual_run_id` | FK 성격 (물리 FK는 단계별 결정) |
| `event_type` | `RUN_CREATED` / `WORKER_CLAIMED` / `STEP_*` / `RUN_*` / `RETRY_*` / `RUN_CANCEL_REQUESTED` / `RUN_INTERRUPTED` 등 |
| `step_key` | `SOURCE_FETCH` / `TRANSFORM` / `UPSERT_LOAD` / … |
| `step_name` | 표시명 |
| `progress_percent` | 0–100 또는 NULL |
| `message` | 짧은 메시지 |
| `metadata_json` | 부가 |
| `created_at` | 시각 |

| | |
|--|--|
| 장점 | timeline·UI·retry/interrupt/notification 연결에 적합 |
| 단점 | migration · event volume 관리 필요 |

### 5.3 권장

- **S8-3**에서 event table PoC
- 첫 대상 step: **REST fetch / transform / upsert load** 3단계 정도
- LLM / 학습 / 예측 progress는 Full Scenario 이후 확장
- S8-0은 설계만 (구현·migration 금지)

### 5.4 Progress API / UI 후보

```text
GET /api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/events
GET /api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/progress
```

UI: Run Detail Drawer · timeline · progress bar · step badges · last heartbeat

---

## 6. Retry Policy 설계

### 6.1 대상 상태

| 상태 | retry | 비고 |
|------|-------|------|
| `FAILED` | 가능 | 포함 mark-failed로 FAILED된 경우 — reason 경고 |
| `PARTIAL` | 가능 | 별도 confirm 권장 |
| `CANCELLED` | **기본 보류** | 정책 확정 후 선택적 허용 |
| `PENDING` | 불가 | |
| `RUNNING` | 불가 | |
| `SUCCESS` | 불가 | |

### 6.2 방식 후보

#### A안: 기존 `visual_run_id` 재사용

- 단순해 보이지만 history 훼손 · audit/lineage 충돌 → **비권장**

#### B안: 새 `visual_run_id` + lineage (권장)

- 원본 run 불변
- 새 PENDING run enqueue
- `retry_of_run_id` / `retry_attempt` / `retry_reason` (컬럼 또는 metadata)
- request + compile/materialization **SAME_SNAPSHOT** 복제 기본
- “최신 설정으로 재시도”는 후속 옵션 (`LATEST_MATERIALIZATION`)

### 6.3 Retry와 schedule / dedup

- catch-up과 retry는 **분리**
- retry된 run의 `dedup_key`는 original과 **달라야** 함
- scheduled run retry 시 `scheduled_for` 유지 여부는 S8-4에서 명시 (권장: 원본 시각 메타 보존, dedup은 retry suffix)

### 6.4 API / audit 후보

```http
POST /api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/retry
```

```json
{
  "reason": "retry after transient API failure",
  "mode": "SAME_SNAPSHOT"
}
```

```json
{
  "original_visual_run_id": "VPR-...",
  "retry_visual_run_id": "VPR-...",
  "retry_attempt": 1,
  "run_status": "PENDING"
}
```

Audit 후보: `RUN_RETRY_REQUESTED`, `RUN_RETRY_ENQUEUED`  
정책 세부: max retry · cooldown · fail-open vs fail-close는 S8-4에서 확정 (새 run 생성이므로 fail-open 후보 가능)

### 6.5 mark-failed와의 관계

- mark-failed는 **운영 정리** (stuck → FAILED)
- interrupt / rollback / 자동 재실행이 **아님**
- mark-failed 후 retry는 가능하되, UI에 “강제 FAILED 정리 후 재시도” 경고

---

## 7. RUNNING Cancel / Interrupt 설계 검토

### 7.1 현재

- PENDING cancel만 지원
- RUNNING cancel → `RUN_CANCEL_RUNNING_NOT_SUPPORTED` (409)
- mark-failed ≠ 실제 interrupt

### 7.2 후보

| 안 | 내용 | 평가 |
|----|------|------|
| A soft cancel | `cancel_requested_at` + worker가 step boundary에서 확인 | **검토 권장** |
| B process kill | worker 프로세스 강제 종료 | **금지** |
| C timeout only | REST/DB timeout | interrupt가 아님 |

### 7.3 권장

- **S8-5**에서 soft cancel 설계 또는 PoC
- progress/event table · `cancel_requested_*` 준비 후 구현
- process kill 금지
- `run_load` 내부 cancel-aware 범위가 핵심 리스크 → PoC는 interruptible step만

### 7.4 API / UI 후보

```http
POST /api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/cancel-request
```

- PENDING: 기존 cancel API 유지 가능
- RUNNING: cancel_requested 표시 → step boundary에서 `CANCELLED` 또는 `INTERRUPTED` 전이 (명칭 S8-5 확정)

UI 안내 예:

> 현재 실행 중인 단계가 중단 가능한 지점에 도달하면 취소됩니다.

Audit: `RUN_CANCEL_REQUESTED`, `RUN_INTERRUPTED` — **audit required 권장**

---

## 8. Schedule Catch-up Policy 설계

### 8.1 현재

- catch-up 없음
- due slot이 active run 때문에 skip → `missed_count` 증가 + `next_due` 전진
- missed run 자동 보상 없음

### 8.2 후보

| 안 | 내용 |
|----|------|
| A no catch-up | 단순·안전 — **기본 유지** |
| B limited catch-up | 최근 N개 / window window |
| C manual catch-up | 운영자 선택 enqueue |

### 8.3 권장

- 기본 **A 유지**
- **S8-6**에서 manual/limited 설계 또는 manual PoC
- 열수요 예측에서 “누락 시간대 예측”의 의미는 **Full Scenario(S8-8)** 검토 후 정책 확정
- `scheduled_for` / `dedup_key` / retry와 충돌하지 않도록 분리

### 8.4 API 후보 (설계만)

```text
GET  /api/v1/visual-pipeline-ops/missed-schedule-slots
POST /api/v1/visual-pipeline-ops/missed-schedule-slots/{slot_id}/enqueue
```

Audit 후보: `SCHEDULE_CATCH_UP_ENQUEUED`

---

## 9. Notification Policy 설계

### 9.1 알림 대상 후보

- run `FAILED`
- retry exhausted
- RUNNING expired / stuck
- schedule skip `ACTIVE_RUN_EXISTS` 반복
- audit fail-close failure
- worker heartbeat stale
- admin mark-failed apply

### 9.2 채널 후보

| 채널 | 우선순위 |
|------|----------|
| UI badge | PoC 1순위 |
| email / webhook | optional, 별도 승인 |
| Slack / Doto 그룹웨어 | 별도 승인 |
| SMS | 후순위 |

### 9.3 권장

- **S8-7** Notification 설계
- audit(`누가 무엇을`)과 notification(`누구에게 알림`) **분리**
- 기본 테스트에서 외부 send 금지 (mock)
- 테이블 후보: `tb_visual_pipeline_notification_event` (audit 재사용 비권장)

---

## 10. Worker Recovery / Stuck 처리 관계

### 10.1 현재 (S7)

- stuck 조회
- mark-failed cleanup
- retry 없음 · auto recovery 없음
- worker process liveness 직접 probe 없음

### 10.2 S8 후보

| 후보 | 권장 |
|------|------|
| expired RUNNING 자동 FAILED | 신중 — 기본 OFF, 장기 config |
| auto retry | 신중 — 기본 OFF |
| heartbeat stale detection (Ops) | History/Ops 가시성 강화와 병행 |
| lease reclaim | worker hardening 후속 |

### 10.3 권장 운영 루프

```text
stuck detect → (운영자) mark-failed → (운영자) retry
```

장기 policy config 후보:

- `auto_mark_failed_after_seconds`
- `auto_retry_enabled` / `max_retry_count`
- `notification_on_stuck`

자동 FAILED/자동 retry는 **R12 또는 명시 승인** 전까지 기본 비활성.

---

## 11. Audit / Admin Action과의 관계

| 기능 | Audit event 후보 | 정책 메모 |
|------|-------------------|-----------|
| retry request/enqueue | `RUN_RETRY_*` | 새 run 생성 → fail-open 후보 |
| cancel request / interrupt | `RUN_CANCEL_REQUESTED` / `RUN_INTERRUPTED` | **fail-close(audit required) 권장** |
| catch-up enqueue | `SCHEDULE_CATCH_UP_ENQUEUED` | Admin ops 성격 |
| notification send | `NOTIFICATION_SENT` 또는 notification log | audit와 혼동 금지 |
| auto recovery | `RUN_AUTO_*` | 도입 시 필수 |
| mark-failed apply | 기존 S7-14 | **fail-close** 유지 |

원칙:

- destructive / interrupt는 audit required fail-close 검토
- mark-failed는 retry·interrupt·rollback이 **아님** (운영 정리)

---

## 12. UI/UX 설계 방향

### 12.1 S8-1 UI 용어/UX 정리 (우선)

확정 backlog:

- 버튼: 「R10 설정 반영」→「**실행 설정 반영**」
- 툴팁 예:

```text
현재 Visual Pipeline 그래프의 Compile 결과를 실행 설정으로 반영합니다.
외부 API 호출, 데이터 적재, 스케줄 활성화는 수행하지 않습니다.
```

- Compile / 실행 설정 반영 / Run Now / Schedule Activation 도움말 정리
- 사용자 문구에서 내부 단계명(R10, S7 등) 노출 최소화

**S8-0에서는 UI 변경하지 않는다.**

### 12.2 Run History / Progress UX

| 위치 | 방향 |
|------|------|
| Studio Run Panel | Latest + History list + Detail drawer + (S8-3) Timeline |
| Admin Ops | failures/stuck/audit → run detail |

원칙:

- 위험 액션(mark-failed, interrupt, catch-up)은 strong confirm
- Full Scenario 이용 중 막히는 UX는 S8-9 backlog로 분리

---

## 13. API 설계 후보

> S8-0에서 구현 금지. path 충돌 유의.

### Run History (기존 확장)

```text
GET /api/v1/visual-pipelines/{pipeline_id}/runs
    ?status=&mode=&activation_id=&from=&to=&retry_of_run_id=
GET /api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}
```

### Progress

```text
GET .../runs/{visual_run_id}/events
GET .../runs/{visual_run_id}/progress
```

### Retry / Cancel-request

```text
POST .../runs/{visual_run_id}/retry
POST .../runs/{visual_run_id}/cancel-request
```

기존 PENDING cancel:

```text
POST .../runs/{run_id}/cancel
```

### Ops (Admin)

```text
/api/v1/visual-pipeline-ops/...   # summary, stuck, mark-failed, audit 유지
/api/v1/visual-pipeline-ops/missed-schedule-slots   # catch-up 후보
/api/v1/visual-pipeline-ops/notifications           # notification 후보
```

경계:

- pipeline 단위 run action → `/visual-pipelines/{pipeline_id}/runs/...`
- Admin 운영 action → `/visual-pipeline-ops`

---

## 14. DB 설계 후보

> S8-0에서 migration/schema 변경 금지. 후속 단계 후보만.

### 14.1 `tb_visual_pipeline_run` 확장 컬럼 후보

| 컬럼 | 용도 |
|------|------|
| `retry_of_run_id` | lineage |
| `retry_attempt` | 시도 횟수 |
| `retry_reason` | 사유 |
| `cancel_requested_at` | soft cancel |
| `cancel_requested_by` | actor |
| `cancel_reason` | 사유 |

### 14.2 `tb_visual_pipeline_run_event`

§5.2 참고. S8-3 PoC.

### 14.3 Notification

`tb_visual_pipeline_notification_event` 후보 — audit와 분리.

---

## 15. 테스트 전략

| 단계 | 검증 포인트 |
|------|-------------|
| S8-2 History | list filter · detail relation · Studio/Ops 네비 · **mutation 없음** |
| S8-3 Progress | migration · event append · progress API · timeline UI · worker emit · volume limit |
| S8-4 Retry | FAILED→새 run · lineage · max count · audit · 원본 불변 · dedup 분리 · worker 실행 |
| S8-5 Cancel-request | RUNNING request · step boundary · audit · non-interruptible 경고 · **no kill** |
| S8-6 Catch-up | missed query · manual enqueue · dedup conflict · activation 경계 |
| S8-7 Notification | trigger · channel mock · 기본 테스트 외부 send 없음 · notification log |

회귀: 기존 schedule/run/ops/audit/admin-action · quick group · FE build/check 스크립트 유지.

---

## 16. 단계별 구현 로드맵

| 단계 | 내용 | 성격 |
|------|------|------|
| **R11-S8-0** | 본 설계 | docs-only |
| **R11-S8-1** | UI 용어/UX 정리 (실행 설정 반영) | FE 문구 |
| **R11-S8-2** | Run History UI/API 고도화 (기존 run table) | API/FE |
| **R11-S8-3** | Step-level Progress PoC (run_event) | DB+worker+API+FE |
| **R11-S8-4** | Retry Policy PoC (새 run + lineage) | API+DB+audit+FE |
| **R11-S8-5** | RUNNING soft-cancel 설계/PoC | 설계±PoC |
| **R11-S8-6** | Schedule Catch-up 설계/manual PoC | 설계±PoC |
| **R11-S8-7** | Notification 설계 | docs (±badge PoC는 별도 승인) |
| **R11-S8-8** | 열수요 예측 Full Scenario 이용가이드 설계 | docs |
| **R11-S8-9** | Full Scenario 기반 UX/기능 보완 | FE/기능 backlog |

권장 순서: **S8-1 → S8-2 → S8-3 → S8-4** 이후 interrupt/catch-up/notification → Full Scenario.

대안: 사용성 확인이 급하면 S8-8을 S8-2 전으로 앞당길 수 있으나, History/Progress 부족 시 운영 해석이 어려우므로 **S8-1/S8-2 후 가이드 권장**.

### R11-S8 vs R12+

| R11-S8 | R12+ / 별도 |
|--------|-------------|
| History · Progress event · Retry lineage · soft-cancel 검토 · catch-up 설계/manual · Notification 설계 · UI 용어 · Full Scenario 가이드 | 실 Auth/ACL · process kill · R10 due-worker 연결 · `active_yn=true` · SMS/외부 채널 본구현 · auto-retry/auto-mark-failed 기본 ON · R10 로그 대량 복제 |

---

## 17. Full Scenario 이용가이드와의 관계

- 사용자가 MLOps/Studio를 이해하려면 **실제 업무 시나리오 가이드**가 필요하다.
- 열수요실적 / 기상 / 특일 API 연결 가이드는 **S8-8**에서 설계한다.
- 예상 따라하기 흐름:

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

- 가이드 진행 중 불편·미완은 즉시 섞지 않고 **S8-9 backlog**로 분리한다.
- 실제 API contract에 따라 pipeline 설계가 달라질 수 있음 → Known Limitations.

---

## 18. UI 용어/UX 정리와의 관계

| 항목 | 결정 |
|------|------|
| 현재 | Studio에 「R10 설정 반영」노출 (내부 단계명) |
| S8-1 | 「**실행 설정 반영**」+ 툴팁/도움말 정리 |
| S8-0 | **문서·Decision Log만** — UI 변경 없음 |

관련 파일(후속 수정 대상, 본 단계 미수정):

- `VisualPipelineStudioPage.tsx` (버튼·토스트·가드 메시지)
- materialization 관련 패널/도움말

---

## 19. Known Limitations

- S8-0은 **docs-only** — 구현 없음
- S7 기준: step progress · retry · RUNNING interrupt · catch-up · notification 없음
- Admin Action mark-failed는 **정리 액션**이지 interrupt/rollback이 아님
- `VITE_USER_ROLE`은 mock — Auth 아님
- worker liveness 직접 probe 없음
- R10 `load_run` 상세와 Visual Run 연결이 제한적일 수 있음
- Full Scenario 가이드 미작성
- 열수요실적/기상/특일 API contract에 따라 설계가 달라질 수 있음
- soft cancel은 `run_load` cancel-aware 범위에 의존 — 전 단계 interrupt 보장 불가
- event table 도입 시 volume/retention 정책 필요

---

## 20. Decision Log

| ID | 결정 |
|----|------|
| D1 | S8은 S7 운영 기능 위에 **run visibility / recovery**를 확장하는 단계다. |
| D2 | S8-0은 **docs-only**이며 History/Progress/Retry/Interrupt/Catch-up/Notification을 구현하지 않는다. |
| D3 | Run History는 기존 `tb_visual_pipeline_run` 기반 **list/detail 고도화부터** 시작한다 (S8-2). |
| D4 | Step-level Progress는 별도 **`tb_visual_pipeline_run_event`**를 권장한다 (S8-3). |
| D5 | Retry는 기존 run 재사용이 아니라 **새 `visual_run_id` + retry lineage**를 권장한다 (S8-4). |
| D6 | **FAILED / PARTIAL**은 retry 후보, **PENDING / RUNNING / SUCCESS**는 제외, **CANCELLED**는 기본 보류. |
| D7 | RUNNING interrupt는 **process kill 금지**, soft cancel requested 방식만 검토한다 (S8-5). |
| D8 | catch-up은 기본 **no catch-up** 유지, manual/limited는 후속 검토한다 (S8-6). |
| D9 | notification은 **audit와 분리**한다 (S8-7). |
| D10 | **mark-failed**는 retry/interrupt/rollback이 아니라 **운영 정리 액션**이다. |
| D11 | 「R10 설정 반영」은 **S8-1**에서 「실행 설정 반영」으로 변경한다. |
| D12 | Full Scenario 이용가이드는 **S8-8**, 발견 불편은 **S8-9** backlog로 분리한다. |
| D13 | R10 due-worker와 Visual Pipeline schedule **분리** · `active_yn=false` 원칙은 유지한다. |
| D14 | Auth / Admin ACL은 **별도 보안 단계**에서 다룬다. |
| D15 | R11-S8 구현 순서는 **UI 용어 → Run History → Progress → Retry**를 권장한다. |

---

## 21. S8-1 이후 제안 작업

1. **R11-S8-1** UI 용어/UX 정리 — 「실행 설정 반영」및 관련 메시지  
2. **R11-S8-2** Run History list/detail API·Studio/Ops 네비  
3. **R11-S8-3** `tb_visual_pipeline_run_event` + worker step emit + timeline UI  

선택 병행: S8-8 Full Scenario 가이드 초안을 S8-2와 병행 작성할 수 있으나, 운영 해석 품질을 위해 History 이후를 권장한다.

---

## 참조

- `docs/md/THERMOps_R11-S7-15_Visual_Pipeline_운영기능_마감정리.md`
- `docs/md/THERMOps_R11-S7-11_Admin_UI_Audit_설계.md`
- `docs/md/THERMOps_R11-S7-7_Schedule_Activation_설계.md`
- `docs/md/THERMOps_R11-S7-5_Option_C_Run_Worker_검토.md`
- `docs/md/THERMOps_R11-S7-0_Visual_Pipeline_Run_설계.md`
- `backend/app/models/entities.py` (`VisualPipelineRun`)
- `backend/app/api/v1/visual_pipelines.py` / `visual_pipeline_ops.py`
- `backend/app/services/visual_pipeline/manual_run_service.py` / `run_worker_service.py` / `ops_service.py` / `audit_service.py`
- `frontend/src/components/visualPipeline/VpRunPanel.tsx`
- `frontend/src/pages/VisualPipelineOpsPage.tsx` / `VisualPipelineStudioPage.tsx`
