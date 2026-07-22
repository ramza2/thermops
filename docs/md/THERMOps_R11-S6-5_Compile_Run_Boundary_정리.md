# THERMOps R11-S6-5 Compile / Run Boundary 정리

> **문서 유형**: 경계 고정 (안정화 / 테스트 / 문서)  
> **작성 기준**: `master` @ R11-S6-4 (`f163d45`) 완료 시점  
> **범위**: Preview / Compile / Materialize 와 Run / Schedule Activation 의 책임 분리  
> **비범위**: Run API, Schedule activation, due worker, FE Materialize UI, package 변경

관련 설계: `docs/md/THERMOps_R11-S6-0_Visual_Pipeline_Compile_설계.md`

---

## 1. 목적

R11-S6-1~S6-4까지 구현된 Preview / Compile / Materialize는 **실행 준비** 단계이다.  
실제 외부 REST 호출, load/transform/upsert 실행, CRON activation, due worker 연결은 **아직 열리지 않았다**.

본 문서는 그 경계를 문서·테스트로 고정하여, 다음 단계(Run 또는 Materialize UI)로 넘어가기 전 안전 기준을 확정한다.

---

## 2. 단계별 의미

| 단계 | API | DB write | R10 설정 row | 실행 | schedule activation |
|------|-----|----------|---------------|------|---------------------|
| **Compile Preview** | `POST .../compile-preview` | 없음 | 없음 | 없음 | 없음 |
| **Compile** | `POST .../compile` | `tb_visual_pipeline_compile_result` | 없음 | 없음 | 없음 |
| **Materialize** | `POST .../materialize` | `tb_visual_pipeline_materialization_result` | Operation / Transform / Write Policy / Schedule **create·update** | 없음 | 없음 |
| **Run** | **미구현** | 실행 이력 예정 | 기존 설정 사용 예정 | 예정 | 아님 |
| **Schedule Activation** | **미구현** | schedule `active_yn` 전환 예정 | 기존 schedule 사용 예정 | due worker 대상 예정 | 예정 |

부가 조회:

| API | 의미 |
|-----|------|
| `GET .../compile-result` | 최신 compile 이력 (없으면 404) |
| `GET .../materialization-result` | 최신 materialization 이력 (없으면 404) |

---

## 3. Side-effect 표

| 이벤트 | `current_sync_status` | compile_result | materialization_result | R10 config rows | load/call/schedule_run | target table |
|--------|----------------------|----------------|------------------------|-----------------|------------------------|--------------|
| compile-preview | **변경 없음** | 없음 | 없음 | 없음 | 없음 | 없음 |
| compile SUCCESS | → `IN_SYNC` | +1 | 없음 | 없음 | 없음 | 없음 |
| compile FAILED | → `COMPILE_FAILED` | +1 | 없음 | 없음 | 없음 | 없음 |
| PUT graph (의미 변경) | `STALE` / `NOT_COMPILED` 등 | 없음 | 없음 | 없음 | 없음 | 없음 |
| materialize SUCCESS | **변경 없음** | 없음 | +1 | upsert | 없음 | 없음 |
| materialize FAILED (도메인) | **변경 없음** | 없음 | +1 (FAILED) | rollback (부분 row 없음) | 없음 | 없음 |
| materialize precondition | **변경 없음** | 없음 | 없음 (409) | 없음 | 없음 | 없음 |

---

## 4. 상태 분리

### 4.1 `current_sync_status` (compile 계열)

| 값 | 의미 |
|----|------|
| `NOT_COMPILED` | 성공 compile 없음 |
| `IN_SYNC` | 최신 SUCCESS compile hash == current graph hash |
| `STALE` | graph 의미 변경으로 SUCCESS compile과 불일치 |
| `COMPILE_FAILED` | 동일 hash의 최신 compile이 FAILED |

**Materialize는 이 값을 바꾸지 않는다.**  
materialization 실패 ≠ compile 실패.

### 4.2 `materialization_status`

| 값 | 의미 |
|----|------|
| `SUCCESS` | R10 설정 row upsert 완료 (실행 아님) |
| `FAILED` | 도메인 매핑 실패 (data_source 없음 등). HTTP 200 + FAILED |

Precondition 실패는 HTTP **409** (`VISUAL_PIPELINE_COMPILE_REQUIRED` / `..._NOT_SUCCESS` / `..._STALE`).

### 4.3 compile_result vs materialization_result

| | compile_result | materialization_result |
|--|----------------|------------------------|
| 입력 | STRICT graph | SUCCESS compile artifact (+ current hash 일치) |
| 산출 | artifact JSON | R10 object ids + 시도 이력 |
| sync | 갱신함 | 갱신 안 함 |
| 실행 | 없음 | 없음 |

---

## 5. Schedule inactive 정책 (고정)

- Materialize 시 schedule row는 **항상** `active_yn=false`.
- Artifact에 `active_yn=true`가 있어도 DB는 inactive.
- Response: `activation=NOT_REQUESTED`, `run_created=false`.
- due worker는 active schedule만 대상 → materialize만으로는 **미실행 보장**.
- Activation은 **별도 미구현 단계**.

---

## 6. Idempotency

- R10 row 식별: `metadata_json.visual_pipeline_origin` (`pipeline_id` + `node_id` + …).
- 동일 pipeline/compile 기준 재 materialize → **동일** `operation_id` / `transform_config_id` / `write_policy_id` / `schedule_id`.
- R10 object row count는 증가하지 않음.
- `tb_visual_pipeline_materialization_result`는 **시도 이력**이므로 호출마다 +1 할 수 있음 (R10 중복과 구분).

---

## 7. No-run / No-activation 보장 (테스트)

검증 스크립트: `python scripts/test_visual_pipeline_materialization.py` (quick group **미포함**)

| # | 보장 |
|---|------|
| 1 | materialize 성공/실패 후 `current_sync_status` 불변 (실패 시 `COMPILE_FAILED`로 전이 금지) |
| 2 | schedule 강제 inactive + `NOT_REQUESTED` / `run_created=false` |
| 3 | idempotency: R10 ids 동일, object count 불변; result 이력 +1 허용 |
| 4 | STALE / 이전 `compile_result_id` → 409, R10 추가 변경 없음 |
| 5 | compile 없음 / FAILED compile → 409, R10 미생성 |
| 6 | REST→Upsert direct → transform_config skip |
| 7 | secret 원문 response/objects에 없음 |
| 8 | load_run / call_log / schedule_run / dedup / target table write 증가 없음 |
| 9 | `apply_dev_migrations.py` 재실행 가능 |

Preview / Compile 경계:

- preview: compile_result / materialization_result / R10 / sync 불변
- compile: compile_result +1, materialization_result·R10·version 불변

---

## 8. S6 완료 상태 요약

| 단계 | 상태 |
|------|------|
| S6-0 설계 | 완료 |
| S6-1 Compile Preview | 완료 |
| S6-2 Compile Persist + sync | 완료 |
| S6-3 Studio Compile UI | 완료 |
| S6-4 R10 Materialization PoC | 완료 |
| **S6-5 Boundary + 안정화 테스트** | **본 문서** |

아직 열리지 않음: Run, Schedule Activation, due worker 연결, Materialize Studio UI.

---

## 9. 다음 단계 후보

### Option A — R11-S7-0 Visual Pipeline Run 설계 (권장 선행)

- 실제 실행 전 **설계 문서**만.
- Materialized R10 설정으로 **1회 수동 Run**을 어떻게 만들지 정의.
- 외부 REST / load / transform / upsert / 이력 / 실패 정책 / sync와의 관계를 선행 설계.
- **실행 위험이 크므로 설계 선행을 권장.**

### Option B — R11-S6-6 Materialization UI

- Studio에 materialize 버튼 / 결과 패널.
- 여전히 실행·activation 없음.
- FE 완결성·운영자 확인 UX에 유리.

**권장:** 실행 경계를 먼저 고정하려면 **A 선행**. Studio 연속성만 필요하면 B도 가능.  
본 단계(S6-5)에서는 **구현하지 않는다.**

---

## 10. 참조

- `docs/md/THERMOps_R11-S6-0_Visual_Pipeline_Compile_설계.md`
- `POST /api/v1/visual-pipelines/{id}/compile-preview`
- `POST /api/v1/visual-pipelines/{id}/compile`
- `POST /api/v1/visual-pipelines/{id}/materialize`
- `scripts/test_visual_pipeline_compile_preview.py`
- `scripts/test_visual_pipeline_compile_persist.py`
- `scripts/test_visual_pipeline_materialization.py`
