# THERMOps R11-S7-0 Visual Pipeline Run 설계

> **문서 유형**: 설계 (구현 없음)  
> **작성 기준**: `master` @ R11-S6-5 (`20692a2`) 완료 시점  
> **범위**: Visual Pipeline Manual Run — precondition, API 후보, 실행 방식, status/이력, security, 로드맵  
> **비범위**: Run API 구현, 외부 REST 호출, Transform/Upsert 실행, Schedule Activation, due worker, FE, DB migration, package 변경  
> **후속**: R11-S7-1 Manual Run API PoC (별도 승인)

관련 문서:

- `docs/md/THERMOps_R11-S6-0_Visual_Pipeline_Compile_설계.md`
- `docs/md/THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md`

---

## 1. 배경과 목적

### 1.1 S6까지 완료된 내용

| 단계 | 내용 | 실행? |
|------|------|-------|
| S6-0 | Compile 설계 | 없음 |
| S6-1 | Compile Preview API | 없음 |
| S6-2 | Compile persist + `current_sync_status` | 없음 |
| S6-3 | Studio Compile Preview / Compile UI | 없음 |
| S6-4 | R10 materialization PoC (설정 row만) | 없음 |
| S6-5 | Compile/Run boundary + materialization 안정화 | 없음 |

S6까지는 **실행 준비**만 열렸다. Materialize 후에도 schedule은 `active_yn=false`, `activation=NOT_REQUESTED`, `run_created=false`이며 due worker 대상이 아니다.

### 1.2 S7의 목적

- Materialized R10 설정(`operation_id` / optional `transform_config_id` / `write_policy_id`)을 사용해 **안전한 1회 Manual Run** 경로를 설계한다.
- **Manual Run**과 **Schedule Activation**을 명확히 분리한다.
- Run의 side effect, status, 이력, 실패, 재시도, security, audit를 구현 전에 고정한다.
- 기존 R10 `run_load` / call_log / load_run / write_policy / due worker를 **재사용·래핑**하되, Visual Pipeline 경계를 흐리지 않는다.

### 1.3 S7-0 성격

**docs-only.** 본 문서는 구현 전 설계이다. Run API·실행 코드·migration·UI는 포함하지 않는다.

---

## 2. 용어 정의

| 용어 | 정의 |
|------|------|
| **Manual Run** | 사용자가 명시적으로 요청한 1회 실행. schedule `active_yn`·due worker와 무관. |
| **Scheduled Run** | active schedule + due worker에 의해 트리거된 실행. Activation 이후. |
| **Run Request** | Manual Run API에 제출된 요청 payload. |
| **Run Job** | 추적 가능한 실행 단위(동기 PoC에서도 run_id로 식별). |
| **Run Attempt** | 한 Run Job에 대한 실제 시도(MVP는 1 attempt = 1 job). |
| **Run Status** | 실행 단위 상태(`PENDING`/`RUNNING`/`SUCCESS`/…). sync/materialization과 별개. |
| **Run Result** | 완료 시점의 metrics·errors·step 요약. |
| **Materialized Object** | materialize가 만든 R10 설정 row(operation, transform_config, write_policy, schedule). |
| **Execution Plan** | materialization objects + compile artifact로 구성된 실행 단계 계획. |
| **Runtime Adapter** | R10 실행 경로(`run_load` 등)를 Visual Pipeline Run이 호출하는 어댑터. |
| **API Call** | 외부 REST 호출 1회(또는 pagination 페이지). |
| **Transform Execution** | transform_config 적용 변환. |
| **Write Execution** | write_policy 기반 upsert/insert/dedup 쓰기. |
| **Dedup Summary** | 중복 처리 요약 기록. |
| **Partial Failure** | 일부 step/row만 성공한 종료 상태(`PARTIAL`). |
| **Retry** | 실패 후 재시도(정책·한도 적용). |
| **Cancel** | 진행 중 Run 중단(S7-1 MVP 제외 가능). |
| **Dry Run** | 외부 호출/쓰기 없이 또는 쓰기 없이 검증하는 모드(S7-1 구현 보류 가능). |
| **Activation** | schedule을 due worker 대상으로 올리는 별도 단계(`active_yn=true`). Materialize/Manual Run과 무관. |

---

## 3. Run 범위와 Non-goals

### 3.1 설계 범위 (후속 구현 후보)

- SUCCESS compile / SUCCESS materialization / hash 일치 확인
- materialized R10 object id 검증
- REST connector call → extract → (optional) transform → write_policy/upsert
- run history / step status / metrics / error 저장
- Manual Run API·조회 API 설계
- concurrent·stale·secret·timeout 정책

### 3.2 Non-goals (S7-0 및 S7-1 기본)

| 제외 | 이유 |
|------|------|
| Schedule Activation | 별도 단계(S7-5+) |
| due worker 자동 실행 | activation 경계 |
| Airflow DAG / 분산 workflow 전체 | PoC 과도 |
| 실시간 스트리밍 | 범위 외 |
| 대규모 Studio UI | S7-4 이후 |
| Auth/SSO/JWT | 플랫폼 범위 외 |
| ML 학습/예측 Run | Visual Data Load와 무관 |
| R10 runtime 대규모 리팩토링 | 래핑·한도만 |
| auto-materialize | 명시적 materialize 필수 |
| S6 API 동작 변경 | 경계 유지 |

---

## 4. Run 전제 조건

| # | 조건 | 미충족 시 |
|---|------|-----------|
| 1 | `pipeline_kind = VISUAL_DATA_LOAD` | 404 |
| 2 | latest compile result = `SUCCESS` | 409 `RUN_COMPILE_REQUIRED` / `RUN_COMPILE_NOT_SUCCESS` |
| 3 | `current_sync_status = IN_SYNC` **권장(S7-1 강제)** | 409 `RUN_COMPILE_STALE` |
| 4 | latest materialization result = `SUCCESS` | 409 `RUN_MATERIALIZATION_REQUIRED` |
| 5 | `materialization.graph_version_hash == compile.graph_version_hash == current graph hash` | 409 `RUN_*_STALE` |
| 6 | `objects.operation_id`, `objects.write_policy_id` 존재 | 409 `RUN_OBJECT_NOT_FOUND` |
| 7 | `transform_config_id`는 pattern에 transform이 있을 때만 필수 | 없으면 skip 또는 409 |
| 8 | `schedule_id` optional — Manual Run에 **불필요** | — |
| 9 | R10 row 존재 + `visual_pipeline_origin` 일치 | 409 `RUN_OBJECT_NOT_FOUND` / `RUN_OBJECT_STALE` |
| 10 | 동일 pipeline에 `RUNNING` run 없음 | 409 `RUN_CONCURRENT_RUN_EXISTS` |

### 4.1 Materialize 필수 / auto-materialize 금지

- S7-1: materialization 없이 Run **거부**.
- Run 경로에서 암묵적 materialize **금지**.
- 운영자는 Compile → Materialize → Run 순서를 따른다.

### 4.2 Schedule inactive와 Manual Run

- Materialized schedule은 **항상** `active_yn=false` 유지(S6-4/S6-5).
- **Manual Run은 schedule active 상태와 독립** — inactive여도 실행 가능.
- Manual Run이 schedule을 activate하거나 due worker에 등록하지 않는다.
- Manual Run이 `schedule_run`을 필수로 만들지 않는다(선택적 연계는 후속 검토).

---

## 5. Manual Run과 Schedule Activation 분리

| | Materialize | Manual Run | Schedule Activation |
|--|-------------|------------|---------------------|
| 목적 | R10 설정 row | 지금 1회 실행 | 주기 실행 가능 상태 |
| 외부 REST | 없음 | **있음** | (이후 Scheduled Run) |
| target write | 없음 | **있음** | (이후) |
| schedule `active_yn` | **false 강제** | 변경 없음 | **true** |
| due worker | 미대상 | 미사용 | 대상 |
| `activation` | `NOT_REQUESTED` | 해당 없음 | 요청/완료 |
| `run_created` | `false` | Run 이력 생성 | schedule_run 이력 |
| S7-1 | 기존 유지 | **구현 후보** | **제외** |

**결정(D1):** S7-1은 Manual Run만. Activation은 S7-5 설계 후 S7-6 PoC(또는 S8).

---

## 6. Run API 설계안 (후속 구현 후보)

### 6.1 Manual Run

**Endpoint 후보 (권장):** `POST /api/v1/visual-pipelines/{pipeline_id}/runs`

대안: `POST .../run` (단수). S7-1에서 하나 선택.

```json
{
  "materialization_result_id": null,
  "compile_result_id": null,
  "mode": "MANUAL",
  "dry_run": false,
  "idempotency_key": null,
  "params": {
    "request_params_override": {},
    "max_pages": 1,
    "limit": 100
  }
}
```

| 정책 | 내용 |
|------|------|
| 기본 materialization | 최신 SUCCESS; id 지정 시 해당 건 + hash 재검증 |
| stale | 409 |
| materialization 없음 | 409 `RUN_MATERIALIZATION_REQUIRED` |
| `dry_run` | S7-1: 필드 예약, **구현은 `false`만** 또는 미지원. R10 `run_load(dry_run=True)`는 후속 |
| override | `request_params` 일부만; **secret/credential/Authorization 금지** |
| response (Option A) | 완료 결과 동기 반환 + `run_id` |
| response (Option B 전환 시) | `202` + `run_id` + `status=PENDING/RUNNING` |

### 6.2 조회 / Cancel

| API | S7-1 |
|-----|------|
| `GET .../runs` | 권장(목록) |
| `GET .../runs/{run_id}` | 권장(상세) |
| `POST .../runs/{run_id}/cancel` | MVP **제외** (Option B 이후) |

---

## 7. Run 실행 방식

| Option | 내용 | 장점 | 단점 |
|--------|------|------|------|
| **A 동기 API** | 요청 중 REST→transform→write 완료 | PoC 단순, 기존 `run_load` 직결 | timeout, 취소/진행률 약함 |
| **B Background job** | run row 생성 후 worker | 상태 추적, timeout 대응 | queue/worker 설계 |
| **C due worker 재사용** | schedule을 잠깐 돌리거나 run-due 경로 | 기존 체계 | Manual↔Activation 경계 혼동 |
| **D Airflow trigger** | DAG | 장기 운영 | Visual Run PoC에 과도 |

### 권장안

| 단계 | 권장 |
|------|------|
| **S7-1 PoC** | **Option A** — materialized `operation_id`로 R10 `run_load` 래핑. Manual 한도(`max_pages`/`limit`)를 R10 기본보다 **보수적**으로. |
| **한계 명시** | HTTP gateway timeout, 장시간 pagination, cancel 불가, 진행률 부재 |
| **S7-2+** | 실측 timeout·UX 필요 시 **Option B로 전환** 권장 |
| Manual Run | **C/D 비권장** |
| Activation 이후 Scheduled Run | C(due worker) 자연 연결 — **S7-1 제외** |

기존 R10 앵커: `api_connector_service.run_load` (call → transform → write_policy/upsert, `ApiConnectorLoadRun` 기록). Visual Pipeline Run은 이를 **직접 대체하지 않고** adapter로 호출한다.

---

## 8. Runtime 단계 설계

| Step | 이름 | 입력 | 출력 | 실패 코드 예 |
|------|------|------|------|--------------|
| 0 | Precondition | pipeline, hashes, objects | Execution Plan | `RUN_*_REQUIRED` / `STALE` / `OBJECT_*` |
| 1 | Run row 생성 | plan | `run_id`, `RUNNING` | persistence error |
| 2 | REST source call | `operation_id`, params, pagination | raw items, call_log | `RUN_REST_CALL_FAILED` |
| 3 | Response extraction | item path / array mode | row list | `RUN_RESPONSE_EXTRACTION_FAILED` |
| 4 | Transform (optional) | `transform_config_id`, rows | transformed rows | `RUN_TRANSFORM_FAILED` |
| 5 | Write / upsert | `write_policy_id`, target_table | insert/update/skip counts | `RUN_WRITE_POLICY_FAILED` / `RUN_UPSERT_FAILED` |
| 6 | Dedup / metrics | write result | dedup summary | `RUN_DEDUP_FAILED` |
| 7 | Finalize | all | `SUCCESS`/`FAILED`/`PARTIAL` | `RUN_UNKNOWN_ERROR` |

### REST

- `operation_id` + params / pagination / `response_item_path`
- `credential_ref` → 안전 저장소 resolve
- timeout / retry / max pages·items
- call_log: **masked URL/params**, sample only

### Transform

- 없으면 skip (`REST_UPSERT_DIRECT`)
- 있으면 `transform_config` adapter (`WIDE_HOUR_TO_LONG` 등)

### Write

- `write_policy_id` / `target_table` / conflict keys / duplicate·null policy
- `save_dedup_summary_yn` 반영
- dry_run=false 시 실제 target write (S7-1+ 구현 시)

---

## 9. Run status 설계

### 9.1 Run status

`PENDING` → `RUNNING` → `SUCCESS` | `FAILED` | `PARTIAL` | `CANCELLED`

| 상태 | 의미 |
|------|------|
| `PENDING` | Option B에서 대기 |
| `RUNNING` | 실행 중 |
| `SUCCESS` | 전 step 성공 |
| `FAILED` | 치명 실패 |
| `PARTIAL` | 일부 성공(정책 허용 시) |
| `CANCELLED` | 취소(후속) |
| `SKIPPED` | step 단위 |

### 9.2 Step status

`PENDING` | `RUNNING` | `SUCCESS` | `FAILED` | `SKIPPED`

### 9.3 상태 축 분리 (필수)

| 축 | 의미 | Run 영향 |
|----|------|----------|
| `current_sync_status` | graph vs SUCCESS compile | **Run이 변경하지 않음** |
| `materialization_status` | R10 설정 반영 | **Run이 변경하지 않음** |
| `run_status` | 실제 실행 | Run만 갱신 |

**Run 실패 ≠ `COMPILE_FAILED`.** Compile/Materialize 성공 상태를 덮어쓰지 않는다.

---

## 10. Run persistence 설계

### 10.1 기존 R10 테이블 (확인됨)

| 테이블 | 역할 |
|--------|------|
| `tb_api_connector_load_run` | load 실행 이력 |
| `tb_api_connector_call_log` | HTTP 호출 로그(masked) |
| `tb_api_connector_load_dedup_summary` | dedup 요약 |
| `tb_api_connector_response_snapshot` | 응답 스냅샷(정책 검토) |
| `tb_data_load_schedule_run` | **Scheduled** run — Manual Run 기본 경로에 강제 사용하지 않음 |

### 10.2 옵션

| Option | 내용 | 평가 |
|--------|------|------|
| A | R10 load_run만 | 단순, VP provenance 약함 |
| B | VP 전용 run 테이블만 | 중복 실행 로직 위험 |
| **C** | R10 load_run + **VP run mapping** | **권장** — provenance + 재사용 |
| D | compile/materialization에 summary만 | 이력·동시성 부족 |

**권장(D3):** Option **C**. S7-1 PoC는 (1) `run_load` → load_run 생성, (2) VP `run_id` ↔ `load_run_id` / `pipeline_id` / compile·materialization id / hash를 mapping 또는 metadata로 연결.  
전용 스키마 상세·migration은 **후속 구현 전 검토 항목** (본 S7-0은 migration 없음).

---

## 11. Materialized object 사용 방식

1. `materialization_result.objects_json`에서 id 로드  
2. R10 row 존재 확인  
3. `metadata_json.visual_pipeline_origin`의 `pipeline_id` / `node_id` / (가능하면) `compile_result_id`·hash 일치  
4. 불일치·삭제 → `RUN_OBJECT_NOT_FOUND` / `RUN_OBJECT_STALE`  
5. 최신 SUCCESS materialization이 아니거나 hash ≠ current → Run 거부  

Manual Run은 `schedule_id`를 **실행 트리거에 사용하지 않는다**.

---

## 12. Stale / Race / Idempotency

| 검사 | 정책 |
|------|------|
| hash 삼중 일치 | 필수 |
| `IN_SYNC` | S7-1 강제 권장 |
| latest SUCCESS materialization | 기본; 지정 id도 hash 재검증 |
| concurrent `RUNNING` | **409 거부** |
| 완료 후 재실행 | **허용** (새 run_id) |
| `idempotency_key` | optional 설계; S7-1 미구현 가능 |
| repeated Manual Run | upsert idempotency는 write_policy conflict key에 의존 |

---

## 13. Error / Issue code 설계

공통 shape:

```json
{
  "severity": "ERROR",
  "code": "RUN_REST_CALL_FAILED",
  "message": "...",
  "phase": "RUN",
  "step_id": "rest_call",
  "node_id": "n-rest",
  "details": {}
}
```

### Precondition (HTTP 409)

`RUN_COMPILE_REQUIRED`, `RUN_COMPILE_NOT_SUCCESS`, `RUN_MATERIALIZATION_REQUIRED`, `RUN_COMPILE_STALE`, `RUN_MATERIALIZATION_STALE`, `RUN_OBJECT_NOT_FOUND`, `RUN_OBJECT_STALE`, `RUN_CONCURRENT_RUN_EXISTS`, `RUN_UNSUPPORTED_PIPELINE_SHAPE`

### Runtime

`RUN_REST_CALL_FAILED`, `RUN_RESPONSE_EXTRACTION_FAILED`, `RUN_TRANSFORM_FAILED`, `RUN_WRITE_POLICY_FAILED`, `RUN_UPSERT_FAILED`, `RUN_DEDUP_FAILED`, `RUN_TIMEOUT`, `RUN_CANCELLED`, `RUN_UNKNOWN_ERROR`

### Security

`RUN_SECRET_RESOLUTION_FAILED`, `RUN_SECRET_INLINE_FORBIDDEN`

S7-1: precondition은 409; runtime 실패는 run row `FAILED` + HTTP 200/4xx/5xx 중 선택(구현 시 확정, compile 패턴과 혼동 금지).

---

## 14. Security / Credential 설계

- graph / compile artifact / materialization objects에 **secret 원문 없음** (S5/S6 유지)
- Run 시 `credential_ref`만 resolve
- request override로 secret 입력 **금지**
- call_log / error_message / audit에 Authorization·token·password 원문 **금지**
- response body: **masked / sample / truncated**; 전체 raw 기본 저장 금지
- PII·운영 데이터 보존 기간은 후속 운영 정책

---

## 15. Retry / Timeout / Pagination

| 영역 | S7-1 권장 |
|------|-----------|
| REST timeout | data_source/connection 기본값 사용 |
| REST retry | 제한적(5xx/timeout); 4xx 비재시도 |
| max pages / items | R10 `MAX_LOAD_PAGES`/`MAX_LOAD_ITEMS` **이하**로 Manual 기본 축소 |
| Transform/Write retry | 기본 비재시도(부분 write 위험); upsert는 conflict key에 의존 |
| Option A timeout | gateway/proxy 한도 문서화; 초과 시 B 전환 근거 |

---

## 16. Observability / Audit

### Run 기록 필드

`run_id`, `pipeline_id`, `compile_result_id`, `materialization_result_id`, `graph_version_hash`, `started_at`/`finished_at`, `status`, `duration_ms`, row counts(inserted/updated/skipped/failed), external call count, error code, step logs, sanitized samples

### Audit 이벤트

`RUN_REQUESTED`, `RUN_STARTED`, `RUN_COMPLETED`, `RUN_FAILED`, (`RUN_CANCELLED`)

조회: `GET .../runs`, `GET .../runs/{run_id}` (+ 기존 load_run/call_log 링크).

---

## 17. UI/UX 설계안 (후속, 구현 없음)

| 요소 | 내용 |
|------|------|
| Toolbar | Materialize / **Run Now** / Schedule Activation(후속) |
| Run Now enable | materialization SUCCESS + `IN_SYNC` + no RUNNING + ADMIN |
| Confirm | “실제 외부 API 호출 및 target table write가 발생합니다.” |
| Result Panel | status, steps, counts, errors, logs |
| Dry-run toggle | 후속 |

S6-6 Materialize UI와 S7-4 Run UI는 분리 가능.

---

## 18. 테스트 전략 (S7-1+)

| 분류 | 항목 |
|------|------|
| Precondition | no compile/materialize, stale, object missing, concurrent |
| Happy path | mock/local REST + test target table |
| Pattern | transform 있음 / REST→Upsert direct |
| Failure | REST / transform / write |
| Safety | secret masking, sync 불변, schedule 여전히 inactive, due worker 미연결 |
| History | run + load_run + call_log 연결 |
| Isolation | mock server / stub; 운영 테이블 destructive write 금지 |

---

## 19. 단계별 로드맵

### 권장 순서

| 단계 | 내용 |
|------|------|
| **R11-S7-0** | 본 문서 (Run 설계) |
| **R11-S7-1** | Manual Run API PoC skeleton + Option A + precondition |
| **R11-S7-2** | mock/local source 실제 실행 + (필요 시) Option B 전환 검토 |
| **R11-S7-3** | Run history / step log / mapping persistence |
| **R11-S7-4** | Studio Run Result UI + confirm |
| **R11-S7-5** | Schedule Activation 설계 |
| **R11-S7-6** | Schedule Activation PoC |
| **R11-S7-7** | safety / audit / regression |

### 병행 가능

- **R11-S6-6 Materialization UI** — 실행 없음, Run과 독립. Run보다 위험 낮음.
- 권장: **S7-0 완료 후** Manual Run(S7-1)과 Materialize UI(S6-6) 중 우선순위는 제품 판단. 실행 위험이 큰 Run은 설계(S7-0) 없이 구현하지 않는다.

---

## 20. Decision Log

| ID | 결정 | 선택 |
|----|------|------|
| **D1** | S7-1 범위 | Manual Run만. Schedule Activation 제외 |
| **D2** | 실행 방식 | S7-1 **Option A(동기)**; timeout/취소/진행률 한계 명시; S7-2+ **Option B** 전환 권장. C/D는 Manual에 비권장 |
| **D3** | Persistence | R10 load_run/call_log/dedup 재사용 + VP run mapping(후속). S7-0 migration 없음 |
| **D4** | Status 분리 | `current_sync_status` / `materialization_status` / `run_status` 분리. Run 실패 ≠ `COMPILE_FAILED` |
| **D5** | Materialization | **필수**. auto-materialize **금지** |
| **D6** | dry_run | S7-1 필드 예약·구현 보류/`false`만. 본구현 후속 |
| **D7** | params override | request_params 일부만. secret/credential **금지** |
| **D8** | concurrent | 동일 pipeline `RUNNING` → **409** |
| **D9** | credential | Run 시점 resolve; 실패 `RUN_SECRET_RESOLUTION_FAILED`; 원문 로그 금지 |
| **D10** | response/log | masked / sample / truncated |
| **D11** | retry/timeout | R10 정렬 + Manual 보수적 max pages/limit |
| **D12** | UI confirm | 외부 호출+write 경고 + confirm (S7-4) |
| **D13** | 로드맵 | S7-0→S7-1(A)→S7-2→S7-3→S7-4; Activation S7-5+; S6-6 UI 병행 가능 |
| **D14** | schedule vs Manual | Manual Run은 `active_yn=false`와 **독립**; activate하지 않음 |
| **D15** | R10 adapter | `run_load` 래핑; R10 본기능 대규모 변경 금지 |

---

## 21. S6 Boundary 대비 Side-effect (Run이 열면)

| 이벤트 | sync | materialization | R10 config | load/call | target write | schedule active |
|--------|------|-----------------|------------|-----------|--------------|-----------------|
| Preview/Compile/Materialize | (S6-5 표) | (S6-5) | materialize만 | 없음 | 없음 | false |
| **Manual Run (후속)** | **불변** | **불변** | 불변(설정) | **증가** | **발생** | **불변(false)** |
| Activation (후속) | 불변 | 불변 | schedule update | — | — | **true** |

---

## 22. 참조

- `docs/md/THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md`
- `docs/md/THERMOps_R11-S6-0_Visual_Pipeline_Compile_설계.md`
- `backend/app/services/api_connector_service.py` — `run_load`
- `backend/app/services/data_load_scheduler_service.py` — `run_due_schedules` (active only)
- `backend/app/services/visual_pipeline/materialization_service.py`
