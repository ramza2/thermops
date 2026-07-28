# THERMOps R11-S8-8 열수요 예측 Full Scenario 이용가이드

> **단계:** R11-S8-8  
> **성격:** docs-only 이용가이드 (code / DB / API / FE / worker / package 변경 없음)  
> **기준 커밋:** `d519529` — `docs(R11-S8-7): Notification 설계 추가`  
> **선행:** R11-S7 운영 PoC · R11-S8-1~S8-6 운영 가시성/복구 · R11-S8-7 Notification 설계  
> **후속:** R11-S8-9 Full Scenario 기반 UX/기능 보완 · (병행) S8-7-1 Notification badge PoC

---

## 1. 문서 개요

본 문서는 THERMOps **Visual Pipeline Studio**를 사용해, 열수요 예측에 필요한 **입력 데이터(열수요실적 · 기상 · 특일)를 적재**하는 운영자 여정을 처음부터 끝까지 설명한다.

| 이 문서가 하는 일 | 이 문서가 하지 않는 일 |
|------------------|------------------------|
| 운영자 **사용자 여정** 중심 따라하기 | 기능별 API 레퍼런스 복제 |
| REST → Transform → Upsert → 실행·스케줄·복구 | Feature Dataset / 모델 학습 / 예측 **본편** |
| 장애 시 Retry · soft-cancel · Catch-up · Ops 확인 | Notification UI/DB 구현 (S8-7 설계만) |
| S8-9에 넘길 UX backlog 정리 | FE/기능 즉시 구현 |

**범위 경계**

- **본편:** Visual Pipeline으로 입력 데이터 **적재** 운영
- **참고만:** Feature Dataset 생성 · 학습 · 예측 · 실적 비교는 **적재 이후 도메인 단계**이며 Studio Visual Pipeline 본편과 섞지 않는다
- **용어:** 「**실행 설정 반영**」사용. 「R10 설정 반영」사용자 문구 **재노출 금지**

---

## 2. 대상 독자 · 전제 조건

### 2.1 대상

- 열수요 예측 입력 데이터를 주기적으로 적재하는 **운영자 / 데이터 담당**
- Studio에서 파이프라인을 구성·검증·실행·스케줄하는 역할

### 2.2 전제

| 항목 | 권장 |
|------|------|
| 역할 | Studio 편집: mock `VITE_USER_ROLE=ADMIN` (Auth 아님) |
| Ops mark-failed | Admin Ops + Admin Action flag (환경에 따름) |
| 실행기 | **`vp-run-worker`** 권장 (BackgroundTasks-only는 PoC 한계) |
| 스케줄 | **`vp-schedule-worker`** (R10 due-worker와 **분리**, `active_yn=false` 유지) |
| Connector | API Connector / Data Source가 실적·기상·특일 REST에 연결 가능 |
| 배포 URL | `https://thermops.openlink.kr` (또는 로컬 README 기준) |

### 2.3 화면 위치

| 화면 | 경로(개념) | 용도 |
|------|------------|------|
| Visual Pipeline Studio | `/visual-pipelines/:id` | 그래프 · Compile · 실행 설정 반영 · 즉시 실행 · 스케줄 · History |
| Visual Pipeline Ops | `/visual-pipeline-ops` | stuck · recent failures · mark-failed · audit |

---

## 3. 시나리오 목표와 산출물

### 3.1 목표

1. 열수요실적 · 기상 · 특일 REST를 Visual Pipeline으로 가져와  
2. Transform으로 날짜/지사/시간 등 키를 정규화하고  
3. Upsert Load로 원천/표준 테이블에 적재하며  
4. 즉시 실행으로 1회 검증한 뒤  
5. CRON 스케줄을 활성화해 주기 적재를 운영하고  
6. 실패·중단·누락 시 기존 PoC 기능으로 복구한다.

### 3.2 산출물 (적재 본편)

- 저장된 Visual Pipeline 그래프 (REST × N + Transform + Upsert + Schedule)
- Compile 결과 · **실행 설정 반영**(materialization) 스냅샷
- Manual / Scheduled `visual_run_id` 이력과 step progress
- (선택) ACTIVE Schedule Activation

### 3.3 적재 이후 도메인 단계 (참고 · 본편 제외)

적재가 안정화된 뒤 별도 화면/프로세스로 진행한다. **본 가이드에서 따라하지 않는다.**

6. Feature Dataset 생성  
7. 학습 대상 기간 선택  
8. 모델 학습  
9. 예측 실행  
10. 예측↔실적 비교 · 품질 이슈 확인  

→ 연계 상세는 별도 가이드(S8-9 backlog 후보)로 분리한다.

---

## 4. 사용자 여정 한눈에 보기

```text
[Connector/Data Source 준비]
        ↓
[Studio 그래프: REST×3 → Transform → Upsert (+ CRON)]
        ↓
[Graph 검증 → Compile → 실행 설정 반영]
        ↓
[즉시 실행] → [History / Progress 확인]
        ↓
[스케줄 활성화] → [schedule-worker enqueue] → [run-worker 실행]
        ↓
[일상 점검: History · Ops stuck/failures]
        ↓
[장애 시: Retry / soft-cancel / mark-failed / Catch-up]
```

---

## 5. Phase A — API Connector / Data Source 준비

운영자가 Studio에 들어가기 전, REST 호출이 가능한 **연결 정의**를 준비한다.

### 5.1 할 일

1. API Connector에서 실적 · 기상 · 특일(휴일) 엔드포인트 연결을 확인한다.
2. Data Source를 각 REST에 매핑한다 (인증·base URL·operation은 Connector 정책 따름).
3. Studio REST 노드에서 선택할 수 있는 **ACTIVE/사용 가능** 상태인지 확인한다.

### 5.2 확인 포인트

- secret/token이 UI에 raw로 노출되지 않는지
- 테스트 호출(Connector 쪽)이 가능한 환경인지
- 지사/기간 파라미터가 Transform·Upsert 키와 맞는지 (계약은 사이트별로 다름)

### 5.3 막히면

- Connector/Data Source 화면에서 연결부터 수정한다. Studio Compile만으로는 외부 API를 호출하지 않는다.

---

## 6. Phase B — 파이프라인 그래프 구성

Studio에서 새 파이프라인을 만들거나 기존 파이프라인을 연다.

### 6.1 REST Source × 3 (권장 구성)

| 노드 | 역할 | 설정 요지 |
|------|------|-----------|
| REST — 열수요실적 | 실적 시계열 수집 | Data Source · operation · 기간/지사 파라미터 |
| REST — 기상 | 기온 등 기상 수집 | 동일 키(날짜·지사·시간) 정렬 가능하도록 |
| REST — 특일/휴일 | 특일 플래그 | 캘린더/특일 API |

Inspector에서 operation_name · Data Source를 맞추고, dirty 상태를 저장한다.

### 6.2 Transform

- 날짜/시각 timezone · 지사 코드 · 시간 버킷 정규화
- 세 REST 결과를 Upsert가 기대하는 컬럼/키로 매핑
- null/결측 처리 규칙을 사이트 정책에 맞게 명시 (가이드는 계약 불변)

### 6.3 Upsert Load

- 적재 대상 테이블(원천/표준)과 키(예: 지사+시각) 설정
- upsert/중복 정책은 환경 설정을 따름
- **실행 설정 반영·즉시 실행 전에는 DB write가 발생하지 않음** (Compile만으로는 적재 없음)

### 6.4 CRON Schedule

- Schedule 노드에 CRON 표현식 입력 · 다음 실행 예정 미리보기
- 활성화는 그래프 저장과 **별개** (Phase E)
- 자동 Catch-up 없음 (S8-6)

### 6.5 Graph 검증

- Studio 「Graph 검증」으로 CONFIG/연결 이슈를 확인한다.
- ERROR가 있으면 Compile/실행 전 수정한다. WARNING은 운영 판단.

---

## 7. Phase C — Compile · 실행 설정 반영

### 7.1 Compile

1. Compile Preview로 변환 결과·step을 확인한다.
2. 필요 시 persisted Compile으로 저장한다.
3. **Compile은** 외부 API 호출 · 데이터 적재 · 스케줄 활성화를 **수행하지 않는다.**

### 7.2 실행 설정 반영

1. 「**실행 설정 반영**」으로 materialization 스냅샷을 만든다.
2. 성공 시 즉시 실행 / 스케줄 활성화 전제 조건이 충족된다.
3. **실행 설정 반영만으로는** 적재·스케줄 due를 시작하지 않는다.

용어 주의: UI/운영 문서에서 「R10 설정 반영」을 쓰지 않는다.

---

## 8. Phase D — 즉시 실행 · History · Progress

### 8.1 즉시 실행

1. Run Panel에서 「**즉시 실행**」을 요청한다.
2. API는 보통 **202 + PENDING** `visual_run_id`를 반환한다.
3. **`vp-run-worker`**가 claim → RUNNING → `run_load` → terminal(SUCCESS/PARTIAL/FAILED/CANCELLED).

### 8.2 Run History 확인

- 「최근 실행 이력」에서 상태 · mode(`즉시 실행`/`스케줄`) · 시간 필터로 목록을 본다.
- 항목 클릭으로 Detail을 연다 (read-only 중심).

### 8.3 Step-level Progress 확인

Detail에서:

- 진행률 바 · 단계 badge (`SOURCE_FETCH` / `TRANSFORM` / `UPSERT_LOAD` 등)
- 이벤트 timeline (`RUN_CREATED` → … → `RUN_COMPLETED` / `RUN_FAILED`)

운영 해석:

| 관찰 | 의미 |
|------|------|
| SUCCESS | 적재 본편 성공 (알림 없음이 정상) |
| PARTIAL | 부분 성공 — 중복 적재 위험 검토 후 Retry 가능 |
| FAILED | 실패 — Progress로 어느 step에서 멈췄는지 확인 |
| RUNNING 장기 | stuck 후보 — Ops 기준 확인 |

---

## 9. Phase E — 스케줄 활성화 · worker 흐름

### 9.1 스케줄 활성화

1. Schedule Activation Panel에서 「**스케줄 활성화**」.
2. Activation이 ACTIVE가 된다.
3. **활성화만으로 즉시 적재하지 않는다.** due 시점에 schedule-worker가 PENDING Run을 만든다.

### 9.2 scheduled PENDING → worker 실행

```text
vp-schedule-worker: due 평가
  → skip (예: ACTIVE_RUN_EXISTS) 또는 enqueue PENDING SCHEDULED Run
vp-run-worker: claim → RUNNING → run_load → terminal
```

운영자 확인:

- Studio History에서 `mode=SCHEDULED` Run
- pause / resume / deactivate는 운영 정책에 따라 사용
- R10 `run-due-worker`와 **연결하지 않음** · R10 `active_yn=true` **전환하지 않음**

### 9.3 일상 점검

- Studio: 최근 SCHEDULED Run 성공 여부
- Ops: stuck count · recent failures · audit (누가 pause/retry/catch-up 했는지)

---

## 10. Phase F — 장애 대응 여정

### 10.1 FAILED / PARTIAL → Retry

1. Run Detail에서 실패 step·사유를 확인한다.
2. FAILED 또는 PARTIAL만 「**재시도**」 가능 (원본 Run 불변, **새** `visual_run_id` PENDING).
3. confirm + reason 필수 · 동일 pipeline에 active PENDING/RUNNING 있으면 불가.
4. max attempts 초과 시 Retry 불가 — 그래프/소스 수정 후 새 즉시 실행을 검토.
5. PARTIAL Retry 시 **중복 적재** 가능성을 UI 경고로 인지한다.

### 10.2 RUNNING 오실행 → soft-cancel

1. 잘못 돌린 RUNNING Run Detail에서 「**중단 요청**」.
2. confirm + reason 필수.
3. **즉시 process kill 없음** — step boundary에서 cooperative 중단.
4. blocking REST/upsert 중에는 바로 안 멈출 수 있음 → Progress로 `중단 요청` 이벤트 확인.
5. PENDING은 기존 cancel로 즉시 CANCELLED 가능.

### 10.3 PENDING / RUNNING stuck → Ops mark-failed

1. `/visual-pipeline-ops`에서 stuck 목록 (`PENDING_TOO_OLD` / `RUNNING_LOCK_EXPIRED`) 확인.
2. dry-run 후 apply로 mark-failed (권한·flag 필요).
3. mark-failed는 **운영 정리**이지 Retry/interrupt/rollback이 아님.
4. 필요 시 이후 Retry 또는 즉시 실행으로 재개.

### 10.4 missed / ACTIVE_RUN_EXISTS → Catch-up

1. Schedule Activation Panel 「**누락 실행 보정**」에서 후보를 조회한다.
2. eligible이면 **최근 1건만** 수동 enqueue (자동 Catch-up 없음 · bulk 없음).
3. Ops에는 enqueue 버튼 없음 — Studio에서만 생성.
4. 생성 Run은 PENDING → 기존 `vp-run-worker`가 실행 (`next_due_at` 불변).
5. INACTIVE · active run 존재 · duplicate scheduled_at · window 초과 시 불가.

### 10.5 Notification — 현재 확인 방법

| 구분 | 상태 |
|------|------|
| Notification 설계 | S8-7 **완료 (docs)** |
| Notification badge / DB / 외부 발송 | **미구현** |
| **지금 운영자가 볼 곳** | Studio **Run History / Detail** · Ops **stuck / recent failures / audit** |

- SUCCESS는 알림하지 않는 것이 정상이다.
- Slack/Email 등 외부 채널은 없다 (S8-7-3 / R12 후속).
- 향후 Studio/Ops 「운영 알림」badge는 **S8-7-1** 후보.

---

## 11. 정상 E2E 체크리스트

운영 오픈 전/후 점검용.

- [ ] Connector/Data Source로 실적·기상·특일 호출 가능
- [ ] Studio 그래프: REST×3 → Transform → Upsert (+ CRON) 저장됨
- [ ] Graph 검증 ERROR 0 (또는 수용한 WARNING만)
- [ ] Compile 성공
- [ ] **실행 설정 반영** 성공
- [ ] **즉시 실행** → History에서 SUCCESS (또는 의도한 terminal)
- [ ] Detail Progress에서 SOURCE_FETCH → TRANSFORM → UPSERT_LOAD 확인
- [ ] **스케줄 활성화** ACTIVE
- [ ] due 후 SCHEDULED PENDING → worker가 SUCCESS까지 처리
- [ ] Ops stuck=0 (또는 알려진 예외만)
- [ ] (선택) pause/resume/deactivate 동작 이해
- [ ] 장애 시나리오를 스테이징에서 1회씩 연습 (Retry / soft-cancel / Catch-up)

---

## 12. Known Limitations

1. 실제 API contract(파라미터·스키마)는 사이트별로 다르며 본 문서는 **여정 템플릿**이다.
2. Feature / 학습 / 예측은 본편 제외 — 별도 운영.
3. soft-cancel은 cooperative only — 전 구간 즉시 중단 보장 없음.
4. Catch-up은 수동 1건 · 과거 전체 missed 재구성 없음.
5. Notification UI/외부 발송 없음 — Ops/History로 확인.
6. Auth는 mock role — 실 ACL 없음.
7. R10 due-worker 미연결 · `active_yn=false` 유지.
8. PARTIAL/Upsert 중복 · 품질 이슈는 도메인 검증이 추가로 필요할 수 있다.
9. multi-source 템플릿/preset UI 없음 (S8-9 후보).
10. worker process liveness 직접 probe 없음.

---

## 13. S8-9 backlog

Full Scenario 이용 중 발견된 UX/기능 보완 항목은 **별도 문서**에서 관리한다.

→ **[THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)** (B1~B25, 1순위·그룹·변경 이력·완료 상태)

원칙: 가이드 사용 중 새 불편이 나오면 본편에 섞지 말고 **S8-9 backlog 문서**에 추가한다.

---

## 14. Decision Log

| ID | 결정 |
|----|------|
| D1 | S8-8은 **docs-only** 이용가이드이다. |
| D2 | 본편은 Visual Pipeline **입력 데이터 적재** 여정이다. |
| D3 | Feature/학습/예측은 **적재 이후 도메인 단계**로만 언급한다. |
| D4 | 사용자 용어는 「실행 설정 반영」·「즉시 실행」·「스케줄 활성화」를 쓴다. |
| D5 | 「R10 설정 반영」사용자 문구를 **재노출하지 않는다**. |
| D6 | Notification은 설계 단계이며, 현 확인은 **Ops stuck/failures + Run History**이다. |
| D7 | Catch-up은 자동 없음 · Studio에서 수동 1건. |
| D8 | Retry/soft-cancel/mark-failed는 기존 PoC 정책을 그대로 안내한다. |
| D9 | R10 due-worker 연결 · `active_yn=true` 전환은 하지 않는다. |
| D10 | 가이드 중 UX 이슈는 **S8-9 backlog 문서**로 분리한다. |
| D11 | S7-15 초기 번호(S8-2 Full Scenario)는 S8-0 로드맵의 **S8-8**이 우선한다. |
| D12 | S8-9 backlog 단일 소스는 `THERMOps_R11-S8-9_Backlog.md`이다. |

---

## 15. 관련 문서

- [`THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md`](./THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md)
- [`THERMOps_R11-S8-7_Notification_설계.md`](./THERMOps_R11-S8-7_Notification_설계.md)
- [`THERMOps_R11-S7-15_Visual_Pipeline_운영기능_마감정리.md`](./THERMOps_R11-S7-15_Visual_Pipeline_운영기능_마감정리.md)
- [`THERMOps_R11-S7-7_Schedule_Activation_설계.md`](./THERMOps_R11-S7-7_Schedule_Activation_설계.md)
- [`THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md`](./THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md)
- README: R11-S8-1~S8-7 요약

---

## 부록. 용어 빠른 참조

| UI/문서 용어 | 의미 |
|--------------|------|
| 실행 설정 반영 | materialization — 실행 스냅샷 반영 (적재·스케줄 due 아님) |
| 즉시 실행 | Manual Run |
| 스케줄 활성화 | Schedule Activation ACTIVE |
| 재시도 | Retry — 새 PENDING Run |
| 중단 요청 | soft-cancel request (RUNNING) |
| 누락 실행 보정 | Catch-up 수동 enqueue |
| Graph 검증 | 그래프/config validation |
| Compile | 실행 가능 스냅샷 변환 (side-effect 최소) |
