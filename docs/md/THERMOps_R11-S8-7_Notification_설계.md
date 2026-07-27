# THERMOps R11-S8-7 Notification 설계

> **단계:** R11-S8-7  
> **성격:** docs-only 설계 (code / DB / API / FE / worker / package 변경 없음)  
> **기준 커밋:** `a604f77` — `feat(R11-S8-6): Schedule Catch-up PoC 추가`  
> **선행:** R11-S8-0 설계 · S8-1~S8-6 PoC (History / Progress / Retry / soft-cancel / Catch-up)  
> **후속 구현:** S8-7-1 read-model badge PoC · S8-7-2 persistent table/API · S8-7-3 external channel · R12 preference/ACL

---

## 1. 문서 개요

본 문서는 Visual Pipeline **운영 Notification 정책**을 설계한다.

목적:

1. Audit / Run Event / Notification의 역할을 분리한다.
2. S8-3~S8-6에서 추가된 운영 이벤트를 포함해, 운영자에게 **알려야 할 상황**을 분류한다.
3. severity · 중복 억제 · read/ack/resolve · UI badge · DB/API 후보를 정의한다.
4. 외부 채널(Slack/Email/SMS/Webhook/Web Push)은 **후속**으로 분리한다.
5. S8-7-1 이후 PoC 구현의 기준 문서로 사용한다.

비범위 (본 단계):

- Notification DB migration / table / entity / API 구현
- FE badge / drawer / list 구현
- Slack / Email / SMS / Webhook / Web Push 발송
- scheduler / worker 신규 구현
- 기존 audit / run_event 저장 로직 변경
- retry / soft-cancel / catch-up / mark-failed / schedule worker / claim·lock·lease 정책 변경
- R10 `run-due-worker` 연결 · `active_yn=true` 전환
- Auth / Login / SSO / JWT / Admin ACL
- package / dependency 추가
- 「R10 설정 반영」사용자 문구 재노출 (S8-1 「실행 설정 반영」유지)

**지금 구현됨 vs 후속**

| 구분 | 내용 |
|------|------|
| **지금 (S8-7)** | 본 설계 문서 + README 요약 |
| **후속 (S8-7-1+)** | read-model badge · persistent table · external delivery |
| **구현되지 않음** | notification table, API, UI badge, 외부 발송 |

---

## 2. S8 운영 기능 현재 상태

S8-6까지 반영된 운영 가시성·복구 기능:

| 단계 | 상태 | Notification 관점 |
|------|------|-------------------|
| S8-1 UI 용어 | 완료 | 「실행 설정 반영」유지 |
| S8-2 Run History | 완료 | 실패/상태 조회 기반 |
| S8-3 Progress / run_event | 완료 | timeline source (전부 알림 아님) |
| S8-4 Retry | 완료 | retry fail / max exceeded 알림 후보 |
| S8-5 soft-cancel | 완료 | cancel request · 미반영 알림 후보 |
| S8-6 Catch-up | 완료 | eligible candidate · catch-up fail 알림 후보 |
| S7 Ops stuck / mark-failed | 완료 | stuck · mark-failed 알림 후보 |
| S7 Audit | 완료 | 증적 source (≠ notification) |

현재 운영자가 조치 필요 상태를 보는 위치:

- Studio: Run History / Run Detail / Schedule Activation Panel (catch-up 후보)
- Ops (`/visual-pipeline-ops`): summary · stuck · recent failures · audit logs
- 별도 Notification UI / badge / unread model: **없음** (본 설계 대상)

참고: 컴포넌트 카탈로그의 `VP_NOTIFICATION`(DISABLED)은 그래프 노드용이며, 본 문서의 **운영 Notification**과 별개다. R10-S9 알림/장애 통보 테이블과도 1차 범위에서 통합하지 않는다.

---

## 3. Notification의 목적

운영자가 **확인하거나 조치해야 할 상태 변화**를 표면화한다.

- “이 Run이 실패했다”
- “이 Run이 stuck이다”
- “soft-cancel이 요청됐지만 아직 RUNNING이다”
- “누락 실행 보정 후보가 있다”
- “재시도 한도를 초과했다”

목표가 **아닌** 것:

- 모든 실행 성공을 축하하는 알림 스트림
- Audit 로그의 UI 재포장
- Run Detail timeline의 전체 복제
- 외부 메신저 즉시 발송 (후속)

---

## 4. Notification과 Audit / Run Event의 차이

### 4.1 Audit

- **목적:** 누가, 언제, 어떤 운영 행위를 했는지 **추적·감사 증적**
- **성격:** 변경 행위의 불변 기록 (삭제/수정하지 않음)
- **예:** `RUN_RETRY_ENQUEUED`, `RUN_CANCEL_REQUESTED`, `SCHEDULE_CATCHUP_ENQUEUED`, `RUN_MARK_FAILED_BY_OPS`, `OPS_MARK_FAILED_APPLY`, schedule activate/pause
- **UI:** Ops Audit Logs
- **Notification과 다름:** 모든 audit가 즉시 알림일 필요는 없음

현재 audit event (S8-6 기준):

| Event | 비고 |
|-------|------|
| `SCHEDULE_ACTIVATE` / `DEACTIVATE` / `PAUSE` / `RESUME` | 스케줄 상태 변경 |
| `RUN_CANCELLED` / `RUN_CANCEL_REQUESTED` | soft-cancel / PENDING cancel |
| `RUN_RETRY_ENQUEUED` | Retry enqueue |
| `SCHEDULE_CATCHUP_ENQUEUED` | Catch-up enqueue |
| `RUN_MARK_FAILED_BY_OPS` / `OPS_MARK_FAILED_*` | mark-failed |
| `SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN` | schedule skip |

### 4.2 Run Event

- **목적:** 특정 Run 내부의 **진행/상태 timeline**
- **성격:** append-only, fail-open
- **예:** `RUN_CREATED`, `WORKER_CLAIMED`, `STEP_STARTED/COMPLETED`, `RUN_COMPLETED`, `RUN_FAILED`, `RUN_CANCEL_REQUESTED`
- **UI:** Run Detail progress / event timeline
- **중요:** **모든 run_event가 Notification이 되는 것은 아니다**

현재 run_event types (S8-6 기준):

| Event | Notification 기본 |
|-------|-------------------|
| `RUN_CREATED` | suppress |
| `WORKER_CLAIMED` | suppress |
| `RUN_STARTED` | suppress |
| `STEP_STARTED` / `STEP_COMPLETED` | suppress |
| `LOAD_FINALIZE` | suppress |
| `RUN_COMPLETED` (SUCCESS) | suppress |
| `RUN_COMPLETED` (PARTIAL) | create WARNING |
| `RUN_FAILED` | create ERROR |
| `RUN_CANCELLED` | create WARNING |
| `RUN_CANCEL_REQUESTED` | create WARNING |
| `RUN_RETRY_REQUESTED` | INFO / badge 제외 가능 |
| `SCHEDULE_CATCHUP_ENQUEUED` | INFO / badge 제외 가능 |

### 4.3 Notification

- **목적:** 운영자가 확인·조치해야 할 **상태 변화 / 조치 필요 항목**
- **성격:** UI badge · unread · acknowledge · (후속) 외부 채널
- **예:** Run 실패, PARTIAL, stuck, catch-up 후보, cancel 장기 미반영, retry max exceeded
- **Audit 재사용 비권장:** 목적·수명·dedup·read model이 다름 (S8-0 D9)

```text
[운영 행위] → Audit (증적)
[Run 진행]  → Run Event (timeline)
[조치 필요] → Notification (badge / list / 후속 채널)
```

---

## 5. 알림 대상 이벤트 분류

### 5.1 Run 결과 알림

| 대상 | Severity 후보 | 비고 |
|------|---------------|------|
| `RUN_FAILED` | ERROR | retry/catch-up run 실패 포함 |
| `RUN_COMPLETED` + PARTIAL | WARNING | 부분 성공 |
| `RUN_CANCELLED` | WARNING | 사용자/시스템 중단 완료 |
| `RUN_CANCEL_REQUESTED` 후 threshold 초과 RUNNING | ERROR | soft-cancel 미반영 |
| retry run failed | ERROR | lineage 포함 |
| catch-up run failed | ERROR | provenance 포함 |

알림 제외 또는 낮은 우선순위:

- `RUN_COMPLETED` SUCCESS
- 단순 `RUN_CREATED`
- `WORKER_CLAIMED`
- `STEP_STARTED` / `STEP_COMPLETED`
- 정상 Retry enqueue
- 정상 Catch-up enqueue

### 5.2 운영 조치 필요 알림

| 대상 | Severity 후보 | Source 후보 |
|------|---------------|-------------|
| Stuck PENDING (`PENDING_TOO_OLD`) | WARNING | ops read-model |
| Stuck RUNNING (`RUNNING_LOCK_EXPIRED`) | ERROR | ops read-model |
| schedule skip `ACTIVE_RUN_EXISTS` 반복 | WARNING | audit / schedule |
| catch-up candidate eligible | WARNING | catch-up read-model |
| repeated failure (동일 pipeline window) | CRITICAL 후보 | derive |
| retry max exceeded | ERROR | retry service / derive |
| soft-cancel requested (초기) | WARNING | run_event/audit |
| soft-cancel not acknowledged after threshold | ERROR | derive |

### 5.3 Schedule / Catch-up 알림

| 대상 | Severity 후보 | 비고 |
|------|---------------|------|
| missed_count 증가 (가시화) | WARNING | S8-6 자동 catch-up 없음 |
| catch-up candidate eligible | WARNING | “후보 있음” |
| catch-up enqueue success | INFO | badge 제외 가능 |
| catch-up enqueue failure | ERROR | confirm/policy 실패는 audit/HTTP, 알림은 선택 |
| INACTIVE + missed_count > 0 | WARNING | 억제 정책 적용 가능 |
| PAUSED + missed 누적 | WARNING | 억제 정책 적용 가능 |

주의: S8-6은 **수동 1건**만 지원. Notification도 “전체 missed 재구성”을 암시하지 않는다.

### 5.4 Security / Policy 알림

| 대상 | Severity | 단계 |
|------|----------|------|
| audit fail-close action failure | ERROR | S8-7-1+ 후보 |
| notification delivery failure | ERROR | S8-7-3+ |
| retry/cancel/catch-up confirm mismatch 반복 | WARNING | 후속 |
| admin action feature flag disabled 접근 | INFO/WARNING | 후속 |

---

## 6. Severity 정책

권장 enum:

- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

| 상황 | Severity |
|------|----------|
| Run SUCCESS | 알림 없음 (또는 INFO 비표시) |
| Run PARTIAL | WARNING |
| Run FAILED | ERROR |
| Retry max exceeded | ERROR |
| Stuck RUNNING lock expired | ERROR |
| Stuck PENDING too old | WARNING |
| soft-cancel requested | WARNING |
| soft-cancel not acknowledged (threshold) | ERROR |
| Catch-up candidate eligible | WARNING |
| Catch-up enqueued | INFO |
| Audit fail-close failure | ERROR |
| Repeated failures (same pipeline) | CRITICAL 후보 |
| Worker unavailable inferred | CRITICAL 후보 |

**MVP:** CRITICAL은 정의만 하고 **실제 사용하지 않을 수 있음**. S8-7-1은 WARNING/ERROR 중심.

---

## 7. Notification 생성 기준

### 7.1 두 가지 방식

| 안 | 설명 | 장점 | 단점 |
|----|------|------|------|
| **A. Event-driven** | run_event/audit 저장 시 notification 생성 | 즉시성 | 기존 service 복잡도·중복·트랜잭션 |
| **B. Read-model derived** | Ops/Studio가 현재 상태를 조회해 알림처럼 표시 | 구현 단순, migration 최소화 | unread/ack 어려움 |

### 7.2 권장 로드맵

1. **S8-7 (본 문서):** 설계 only  
2. **S8-7-1 PoC:** **B안** — read-model based UI badge  
3. **S8-7-2:** persistent `tb_visual_pipeline_notification` (+ 선택적 event-driven create)  
4. **S8-7-3:** external channel delivery  

S8-7-1에서 “생성”은 물리 insert가 아니라 **조회 시점 derivation**을 의미한다.

### 7.3 생성하지 않는 기본 규칙

- SUCCESS terminal
- STEP progress events
- worker claim / run started
- 정상 운영 enqueue (retry/catch-up) — INFO 로그성만, badge count 제외 가능

---

## 8. 중복 억제 / Grouping / Suppression 정책

### 8.1 Dedup / Grouping

| 규칙 | 설명 |
|------|------|
| 기본 key | `pipeline_id` + `notification_type` + `source_id` |
| Run FAILED | 동일 `visual_run_id`당 1건 |
| soft-cancel requested | ack/terminal 시 resolved |
| catch-up candidate | `activation_id` + `candidate_scheduled_at`당 1건 |
| repeated failure | window 내 count로 group (후속 CRITICAL) |
| stuck | `visual_run_id` + stuck_reason당 1건 |

### 8.2 Read / Ack / Resolve 구분

| 상태 | 의미 |
|------|------|
| **read** | 사용자가 목록/상세에서 확인 |
| **acknowledged** | 운영자가 조치 필요성을 **인지** |
| **resolved** | 원인 상태 해소 또는 후속 조치 완료 |

예:

- FAILED 알림 → 사용자가 read → retry enqueue 후 원본 알림은 ack 가능 → 새 retry run이 SUCCESS면 관련 open 알림 resolve 후보
- catch-up candidate → enqueue 성공 시 해당 candidate 알림 resolve
- stuck → mark-failed 또는 worker 정상 terminal 시 resolve

### 8.3 Suppression

기본 suppress:

- SUCCESS 알림
- `STEP_STARTED` / `STEP_COMPLETED`
- `WORKER_CLAIMED` / `RUN_STARTED` / `LOAD_FINALIZE`
- Retry success enqueue (INFO only, badge 제외 가능)
- Catch-up success enqueue (INFO only, badge 제외 가능)

조건부 억제:

- known INACTIVE / PAUSED activation의 missed 반복 경고 (동일 activation window)
- `ACTIVE_RUN_EXISTS` skip의 과도한 반복 (occurrence_count 증가 방식 후보)

---

## 9. Read Model / Unread / Acknowledge 설계

### 9.1 S8-7-1 (read-model, no DB)

- Ops summary / stuck / recent failures / catch-up candidates를 **notification-like DTO**로 projection
- unread/ack 없음 (또는 session-local UI state만 — 권장하지 않음, 명시적 후속)
- badge count = derived action-required items

### 9.2 S8-7-2 Persistent 후보 컬럼

| 컬럼 | 용도 |
|------|------|
| `notification_id` | PK |
| `notification_type` | 유형 |
| `severity` | INFO/WARNING/ERROR/CRITICAL |
| `title` / `message` | 표시 문구 |
| `pipeline_id` / `visual_run_id` / `activation_id` | 링크 |
| `source_type` / `source_id` | run_event / audit / ops / catchup |
| `dedup_key` | 중복 억제 |
| `status` | `UNREAD` / `READ` / `ACKNOWLEDGED` / `RESOLVED` |
| `metadata_json` | redacted 요약만 |
| `created_at` / `read_at` / `acknowledged_at` / `resolved_at` | lifecycle |

정책:

- Badge count: **UNREAD + unresolved WARNING/ERROR** 중심
- MVP는 **read만** 먼저 가능, ack/resolve는 단계적
- Notification에서 Retry/Cancel/Catch-up을 **직접 실행하지 않음** — 기존 Detail/Activation Panel로 이동

---

## 10. UI 표시 설계

용어: S8-1 유지. 「R10 설정 반영」재노출 금지. 「실행 설정 반영」사용.

### 10.1 Studio

표시 위치 후보:

- Studio 상단 status strip — `운영 알림 N` badge
- Run Panel 「운영 알림」카드
- Schedule Activation Panel — catch-up warning badge (기존 누락 보정 섹션과 연계)
- Run Detail — 해당 Run 관련 알림 badge

MVP (S8-7-1):

- 상단 badge + severity별 count
- 클릭 시 drawer/list
- item click → Run Detail 또는 Activation Panel

대규모 레이아웃 변경 금지. 기존 패널 additive.

### 10.2 Admin Ops

표시 위치 후보:

- `/visual-pipeline-ops` 최상단 — Notification / 「조치 필요」카드
- Stuck / Failures / Catch-up candidates를 notification-like list로 그룹
- **Audit Logs와 별도 section**

MVP:

- 「조치 필요」카드 (stuck / failed / catch-up candidate)
- read/ack는 후속 (S8-7-2)

### 10.3 Run Detail

- 해당 Run 관련 알림 (failed / partial / cancel / retry / catch-up lineage)
- badge 표시
- 액션 버튼은 기존 retry / soft-cancel과 **분리** (알림에서 실행하지 않음)

### 10.4 External Channel UI

후속. S8에서는 채널 preference UI 구현하지 않음.

---

## 11. External Channel 연동 설계

이번 단계 **구현하지 않음**. S8-7-3 또는 R12 / 별도 승인 후.

채널 후보:

| 채널 | 우선순위 |
|------|----------|
| UI badge | PoC 1순위 (S8-7-1) |
| Webhook | 별도 승인 |
| Slack | 별도 승인 |
| Email | 별도 승인 |
| SMS / Web Push | 후순위 |

채널 정책 (설계만):

- 어떤 severity를 외부로 보낼지 (권장: ERROR+만, CRITICAL 포함 시)
- 중복 방지 (`dedup_key` + window window)
- 발송 실패 처리 (delivery fail → ERROR notification / audit)
- webhook URL / token은 **secret ref-only**
- user/channel preference (R12)
- 기본 테스트에서 외부 send 금지 (mock)

R10-S9 (`tb_notification_*`, `/notifications`)와의 통합은 **R12 검토 후보**. S8 Visual Pipeline Notification은 VP 운영 범위로 먼저 닫는다.

---

## 12. DB 설계 후보

> **주의:** 아래 SQL은 **설계 후보**이며 S8-7에서 **적용하지 않는다**. 실제 migration은 S8-7-2에서 별도 승인.

신규 table 후보: `tb_visual_pipeline_notification`

```sql
CREATE TABLE IF NOT EXISTS tb_visual_pipeline_notification (
    notification_id VARCHAR(40) PRIMARY KEY,
    notification_type VARCHAR(80) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message VARCHAR(1000),
    pipeline_id VARCHAR(40),
    visual_run_id VARCHAR(40),
    activation_id VARCHAR(40),
    source_type VARCHAR(40),
    source_id VARCHAR(80),
    dedup_key VARCHAR(200) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'UNREAD',
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    read_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vp_notification_dedup_active
    ON tb_visual_pipeline_notification (dedup_key)
    WHERE status IN ('UNREAD', 'READ', 'ACKNOWLEDGED');

CREATE INDEX IF NOT EXISTS ix_vp_notification_pipeline_created
    ON tb_visual_pipeline_notification (pipeline_id, created_at);

CREATE INDEX IF NOT EXISTS ix_vp_notification_status_severity
    ON tb_visual_pipeline_notification (status, severity);

CREATE INDEX IF NOT EXISTS ix_vp_notification_run
    ON tb_visual_pipeline_notification (visual_run_id);
```

S8-0의 `tb_visual_pipeline_notification_event` 명칭 후보는 본 문서의 `tb_visual_pipeline_notification`로 정리한다 (event 테이블과 혼동 방지).

금지 (S8-7):

- migration 스크립트 추가
- `entities.py` / `01_schema.sql` 반영
- audit / run_event table 구조 변경

---

## 13. API 설계 후보

> S8-7에서는 API **구현하지 않음**.

후속 API 후보:

```http
GET  /api/v1/visual-pipeline-notifications
GET  /api/v1/visual-pipeline-notifications/summary
POST /api/v1/visual-pipeline-notifications/{notification_id}/read
POST /api/v1/visual-pipeline-notifications/{notification_id}/acknowledge
POST /api/v1/visual-pipeline-notifications/{notification_id}/resolve
```

Query 후보: `status`, `severity`, `pipeline_id`, `visual_run_id`, `activation_id`, `unread_only`, `created_from`/`to`, `limit`/`offset`

Summary response 후보:

```json
{
  "unread_total": 5,
  "warning_count": 3,
  "error_count": 2,
  "critical_count": 0,
  "action_required_count": 4
}
```

**S8-7-1 대안:** 기존 Ops summary API를 additive 확장해 derived notifications를 반환. 신규 notification router는 S8-7-2.

---

## 14. Event Source Mapping

| Source | Source Event / Condition | Notification Type | Severity | Default |
|--------|--------------------------|-------------------|----------|---------|
| run_event | `RUN_FAILED` | `RUN_FAILED` | ERROR | create |
| run_event | `RUN_COMPLETED`(PARTIAL) | `RUN_PARTIAL` | WARNING | create |
| run_event | `RUN_CANCELLED` | `RUN_CANCELLED` | WARNING | create |
| run_event | `RUN_CANCEL_REQUESTED` | `RUN_CANCEL_REQUESTED` | WARNING | create |
| derive | cancel requested + RUNNING > threshold | `RUN_CANCEL_STALE` | ERROR | create/derive |
| audit | `RUN_RETRY_ENQUEUED` | `RUN_RETRY_ENQUEUED` | INFO | suppress badge |
| audit | `SCHEDULE_CATCHUP_ENQUEUED` | `SCHEDULE_CATCHUP_ENQUEUED` | INFO | suppress badge |
| audit | `RUN_CANCEL_REQUESTED` | (audit 증적 + 위 notification) | — | audit ≠ notif 전용 |
| catch-up service | eligible candidate | `SCHEDULE_CATCHUP_AVAILABLE` | WARNING | read-model |
| ops service | `PENDING_TOO_OLD` | `RUN_STUCK_PENDING` | WARNING | read-model |
| ops service | `RUNNING_LOCK_EXPIRED` | `RUN_STUCK_RUNNING` | ERROR | read-model |
| retry service | max exceeded | `RUN_RETRY_MAX_EXCEEDED` | ERROR | create/derive |
| audit | mark-failed apply | `RUN_MARK_FAILED_BY_OPS` | INFO/WARNING | optional |
| audit | fail-close failure | `AUDIT_FAIL_CLOSE_FAILED` | ERROR | create |
| schedule | `ACTIVE_RUN_EXISTS` 반복 | `SCHEDULE_SKIP_ACTIVE_RUN` | WARNING | derive/suppress window |
| run_event | SUCCESS / STEP_* / CLAIMED | — | — | suppress |

---

## 15. Security / Redaction 정책

- `metadata_json`에 raw `request_json` / `result_json` **저장 금지**
- secret / token / password / credential / api_key / authorization 키 **redaction**
- external channel target / webhook URL은 **secret ref-only** (평문 저장 금지)
- notification `message`는 민감 정보 축약 (run_id, pipeline_id, status, reason code 수준)
- Audit와 Notification 모두 운영 정보이므로 권한이 필요하지만 **S8에서는 Auth 미구현** (mock role `VITE_USER_ROLE` 수준)
- 외부 발송 구현 시 channel preference · secret management는 **별도 설계**
- UI에 secret raw / 전체 request·result dump 노출 금지 (기존 History 정책과 동일)

---

## 16. 테스트 전략

### 16.1 S8-7 (docs-only)

- `docs/md/THERMOps_R11-S8-7_Notification_설계.md` 존재
- README에 R11-S8-7 요약·링크
- code / DB / package 변경 없음
- 「R10 설정 반영」FE 재노출 없음

### 16.2 S8-7-1 read-model PoC

- summary count / severity mapping
- duplicate suppression
- badge UI (Studio/Ops)
- persistent table **없음**
- 기존 audit/run_event **무변경**
- 외부 send **없음**

### 16.3 S8-7-2 persistent notification

- migration / dedup unique
- create / read / ack / resolve
- redaction
- action link → Run Detail / Activation
- 기존 audit/run_event unaffected
- retry/cancel/catch-up 정책 회귀

### 16.4 S8-7-3 external channel

- delivery policy / retry delivery
- failure audit
- secret handling
- channel opt-in/out
- 기본 테스트 mock (실발송 OFF)

---

## 17. 단계별 구현 로드맵

| 단계 | 내용 | 성격 |
|------|------|------|
| **R11-S8-7** | 본 Notification 설계 | **docs-only** |
| **R11-S8-7-1** | read-model based notification badge PoC (Ops summary derived, no DB) | API additive + FE badge |
| **R11-S8-7-2** | persistent notification table/API (read/ack/resolve, dedup) | DB+API+FE |
| **R11-S8-7-3** | external channel delivery design/PoC | 별도 승인 후 |
| **R11-S8-8** | 열수요 예측 Full Scenario 이용가이드 설계 | docs |
| **R11-S8-9** | Full Scenario 기반 UX/기능 보완 | FE/기능 backlog |
| **R12** | user preference, permission, escalation, SLA, channel policy, R10-S9 통합 검토 | 후속 |

권장 순서: **S8-7 → S8-8 → (병행 가능) S8-7-1** → S8-9.  
Notification badge PoC는 Full Scenario 가이드와 병행 가능하나, S8-8 문서의 사용자 여정에 notification trigger를 반영하는 것이 좋다.

---

## 18. Known Limitations

1. S8-7은 **설계만** — badge/UI/API/DB 없음.
2. 자동 catch-up 없음 → “후보 있음” 알림만 의미 있음.
3. soft-cancel은 cooperative → cancel stale threshold 알림은 derive 필요.
4. worker process liveness 직접 probe 없음 → “worker unavailable” CRITICAL은 추론 한계.
5. Auth/ACL 없음 → notification 권한은 mock role 수준.
6. R10-S9 알림 체계와 미통합.
7. CRITICAL / repeated failure grouping은 MVP 이후.
8. read-model은 unread persistence 불가.
9. Notification에서 운영 액션을 직접 실행하지 않음 (의도적).
10. 그래프 컴포넌트 `VP_NOTIFICATION`과 혼동 가능 — 문서/UI에서 “운영 알림”으로 구분.

---

## 19. Decision Log

| ID | 결정 |
|----|------|
| D1 | S8-7은 **design-only**이다. |
| D2 | Notification은 **Audit과 별도** 개념이다. |
| D3 | **모든 run_event가 notification은 아니다.** |
| D4 | MVP 구현 방향은 **read-model based badge**부터 시작한다 (S8-7-1). |
| D5 | Persistent table은 **S8-7-2** 후속이다. |
| D6 | External channel은 S8 본구현 밖이며 **R12 또는 별도 승인** 후 진행한다. |
| D7 | SUCCESS / STEP / CLAIMED 이벤트는 **기본 suppress**한다. |
| D8 | Run FAILED / PARTIAL / Stuck / Catch-up candidate는 **action-required** 후보이다. |
| D9 | Notification metadata는 raw request/result를 **저장하지 않는다**. |
| D10 | Auth / Admin ACL은 별도 단계이다. |
| D11 | 사용자 문구 「R10 설정 반영」은 **재노출하지 않는다**. |
| D12 | Retry / Cancel / Catch-up 액션은 기존 기능과 분리하며 notification에서 **직접 실행하지 않는다**. |
| D13 | Badge count는 unresolved **WARNING/ERROR** 중심으로 시작한다. |
| D14 | Read / Ack / Resolve는 **단계적으로** 분리한다 (MVP는 read 우선). |
| D15 | S8-8 Full Scenario에서 notification trigger를 **사용자 여정**에 반영한다. |
| D16 | `VP_NOTIFICATION` 그래프 노드와 운영 Notification은 **별개**이다. |
| D17 | R10-S9 알림 테이블과의 통합은 **R12 검토**로 미룬다. |
| D18 | S8-7에서 migration / API / FE / worker / package 변경은 **금지**한다. |
| D19 | CRITICAL severity는 정의하되 MVP에서 **미사용 가능**하다. |
| D20 | 정상 Retry/Catch-up enqueue는 INFO이며 **badge count 제외 가능**하다. |

---

## 20. S8-8 이후 연계

### 20.1 S8-8 Full Scenario 이용가이드

열수요 예측 시나리오(실적/기상/특일 → transform → upsert → schedule) 문서에 아래를 반영한다.

- 실패 시 어디서 알림을 확인하는지 (Studio badge / Ops 「조치 필요」)
- stuck / mark-failed / retry / soft-cancel / catch-up 후보의 **알림 의미**
- SUCCESS는 알림하지 않음
- 외부 Slack/Email은 아직 없다는 한계

### 20.2 S8-9 UX 보완

Full Scenario 사용 중 발견된 알림 UX 불편은 S8-9 backlog로 수집한다.

### 20.3 S8-7-1 병행

S8-8 작성 중에도 S8-7-1 badge PoC를 별도 승인으로 진행할 수 있다. 가이드 문서에는 “현재는 Ops stuck/failures로 확인, badge는 후속”으로 명시 가능.

---

## 부록 A. 관련 문서

- [`THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md`](./THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md) §9 Notification Policy
- [`THERMOps_R11-S7-15_Visual_Pipeline_운영기능_마감정리.md`](./THERMOps_R11-S7-15_Visual_Pipeline_운영기능_마감정리.md)
- [`THERMOps_R11-S7-11_Admin_UI_Audit_설계.md`](./THERMOps_R11-S7-11_Admin_UI_Audit_설계.md)
- README R11-S8-6 / R11-S8-7 요약

## 부록 B. 현재 구현 소스 (읽기 전용 참고)

| 영역 | 파일 |
|------|------|
| Audit | `backend/app/services/visual_pipeline/audit_service.py` |
| Run Event | `backend/app/services/visual_pipeline/run_event_service.py` |
| Ops stuck | `backend/app/services/visual_pipeline/ops_service.py` |
| Retry | `backend/app/services/visual_pipeline/run_retry_service.py` |
| soft-cancel | `backend/app/services/visual_pipeline/run_cancel_service.py` |
| Catch-up | `backend/app/services/visual_pipeline/schedule_catchup_service.py` |
| Ops UI | `frontend/src/pages/VisualPipelineOpsPage.tsx` |
| Run Detail | `frontend/src/components/visualPipeline/VpRunDetailPanel.tsx` |
| History | `frontend/src/components/visualPipeline/VpRunHistorySection.tsx` |
| Activation / Catch-up UI | `frontend/src/components/visualPipeline/VpScheduleActivationPanel.tsx` |
