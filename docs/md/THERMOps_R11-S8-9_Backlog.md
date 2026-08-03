# THERMOps R11-S8-9 Backlog (Full Scenario UX / 기능 보완)

> **성격:** 구현 대기 목록 (단일 소스) — ChatGPT·Cursor·운영자 동기화용  
> **범위:** Visual Pipeline Studio / Data Source / 표준 데이터셋 / Ops UX (범용 MLOps, 열수요 전용 하드코딩 지양)  
> **기준:** R11-S8-8 Full Scenario 이용가이드 실사용 중 발견 이슈 + S8-0~S8-8 설계 backlog 통합  
> **갱신 규칙:** 신규 이슈는 본 문서에 ID를 부여해 추가한다. S8-8 이용가이드 본편에는 섞지 않는다.

---

## 1. 이 문서 사용법

| 용도 | 방법 |
|------|------|
| ChatGPT 동기화 | 본 파일 전체 또는 「전체 backlog 표」+「1순위」+「변경 이력」을 컨텍스트로 붙여넣기 |
| 구현 착수 | 항목 ID를 커밋/PR 제목에 포함 (예: `fix(R11-S8-9): B25 REST API 연결 목록 size 수정`) |
| 완료 처리 | 표의 **상태**를 `done`으로 바꾸고 **변경 이력**에 날짜·커밋 기록 |
| 우선순위 조정 | §3 1순위 / §4 그룹만 수정 — ID는 유지 |

**상태 값:** `open` · `in_progress` · `done` · `deferred` · `cancelled`

---

## 2. 전체 Backlog (B1 ~ B27)

| ID | 제목 | 설명 | 그룹 | 상태 | 비고 |
|----|------|------|------|------|------|
| B1 | Visual Pipeline Starter Template | 범용 multi-source ingestion 스타터. REST Source 여러 개 → Transform 병렬/정규화 → Upsert Load 기본 그래프를 빠르게 생성. 열수요 실적+기상+특일은 **샘플 시나리오 중 하나**로만 제공 | D | **done** | **R11-S8-9-23** |
| B2 | Domain Preset Framework | 업무 도메인별 preset 등록·선택 구조. 노드 라벨, 기본 CRON, target table/conflict key, Transform 기본 mapping 포함. 열수요 preset은 **예시 preset 하나**로만 | D | **done** | **R11-S8-9-24** |
| B3 | Schema / Key Mapping Helper | 원천 필드 → 표준 컬럼 mapping 범용 helper. 날짜/시간, 엔티티 ID, 지사/노드 코드, 측정값 category 자동 제안 | B | **done** | **R11-S8-9-22** |
| B4 | Catch-up 안내 개선 | missed 의미·window·경고 카피 강화 (Studio Catch-up 섹션) | C | **done** | **R11-S8-9-19** |
| B5 | Notification badge PoC | S8-7-1 read-model badge (Ops/Studio). S8-7 설계 범위 | D | **done** | **R11-S8-9-21** |
| B6 | 실패 원인 요약 개선 | Run Detail에 step+reason 한줄 요약 | C | **done** | **R11-S8-9-16** |
| B7 | Data Load → ML Workflow Handoff Guide | Visual Pipeline 적재 이후 Feature Dataset / Training / Batch Prediction으로 넘기는 **범용 handoff 가이드** (docs) | D | **done** | **R11-S8-9-25** |
| B8 | PARTIAL 중복 적재 가시화 | Retry 전 영향 범위 힌트 | C | **done** | **R11-S8-9-20** |
| B9 | Schedule skip 이력 UI | `ACTIVE_RUN_EXISTS` 등 skip 반복 가시화 | C | **done** | **R11-S8-9-18** |
| B10 | Ops 「조치 필요」카드 | stuck / failures / catch-up 후보 그룹 (notification 전단계) | C | **done** | **R11-S8-9-17** |
| B11 | Connector / Data Source 선택 UX | Wizard/Mappings에서 `size≤100` 유지 + 클라이언트 검색·더 보기·새로고침. 서버 keyword 없음 한계 안내 | A | **done** | **R11-S8-9-8** |
| B12 | Visual Pipeline E2E Smoke Scenario | REST → Transform → Upsert → Compile → 실행 설정 반영 → 즉시 실행 → History 범용 smoke. fixture는 generic sample dataset | D | **done** | **R11-S8-9-15** |
| B13 | Inspector select 기본값 미반영 | `http_method`·`transform_type` 등 select **표시** 기본값이 config에 저장되지 않아 Graph 검증 required 경고. **A+B:** schema default 주입 + Type B placeholder | A | **done** | **R11-S8-9-4** |
| B14 | Transform Unmapped Policy enum 정렬 | Studio `KEEP`/`DROP`/`ERROR` → backend `FAIL_LOAD`/`SKIP_UNMAPPED`/`LOG_ONLY`. Wizard 공통 상수. legacy C안(ERROR/DROP remap, KEEP 재선택) | A | **done** | **R11-S8-9-5** |
| B15 | Source ↔ Target Column Normalization UX | API `ND_ID` vs 테이블 `nd_id` 등 대소문자·snake_case 불일치. Upsert conflict key 오류(`MATERIALIZE_WRITE_POLICY_FAILED`) 방지. Transform 스키마·Upsert target 비교·매핑·conflict key 힌트 (범용) | B | **done** | **R11-S8-9-12** |
| B16 | 검증 → Compile dirty 흐름 개선 | Graph 검증 후 `applyConfigValidationCache`가 노드에 결과를 써 dirty 재발. **A안:** UI 전용 `configValidationByNodeId` + dirty/save에서 `config.validation` canonicalize | A | **done** | **R11-S8-9-3** |
| B17 | Studio 이중 스크롤 정리 | Node Inspector·하단 패널 누적 스크롤. viewport 고정 작업대 + Bottom Operations Dock | A | **done** | **R11-S8-9-1** 완료 |
| B18 | Target Table sample rows 미리보기 | 즉시 실행 SUCCESS 후 Studio에서 적재 row·건수 확인 UI 없음 (현재 SQL만). Run Detail 또는 Upsert 연계 LIMIT N preview | C | **done** | **R11-S8-9-14** |
| B19 | Studio REST — Data Source 인라인 생성 | Inspector에서 REST_API Data Source 최소 생성(이름·base URL·domain, auth=NONE) 후 ID 자동 선택. 선택 UI는 B11 검색/더 보기/새로고침 재사용. secret/credential 저장 UI 없음 | B | **done** | **R11-S8-9-9** |
| B20 | Studio Upsert — 표준 데이터셋 인라인 생성 | Inspector에서 Standard Dataset 선택·DRAFT 인라인 생성 후 `standard_dataset_id`+`target_table` 자동 반영. 물리 테이블/ACTIVE/DROP 제외 | B | **done** | **R11-S8-9-10** |
| B21 | Transform 출력 → 표준 테이블 컬럼 자동 제안 | Transform 스키마/미리보기에서 Upsert·표준 데이터셋 컬럼·conflict key 제안. B15·B20 연계 | B | **done** | **R11-S8-9-11** |
| B22 | DISABLED(Coming later) 컴포넌트 본구현 | Palette DISABLED 노드 활성화 로드맵. **DATA_INPUT:** `VP_DB_SOURCE`, `VP_CSV_SOURCE`, `VP_FORECAST_PROVIDER`. **QUALITY:** `VP_DATA_QUALITY`. **FEATURE:** `VP_FEATURE_BUILD`. **MODEL:** `VP_MODEL_TRAINING`. **PREDICTION:** `VP_BATCH_PREDICTION`. **OPERATION:** `VP_NOTIFICATION` (S8-7 운영 알림과 구분) | D | **done** | **R11-S8-9-26** |
| B23 | Product Branding Generalization | 특정 고객/도메인 문구를 범용 MLOps 운영 플랫폼 기준으로 정리. 고객명·도메인명은 demo scenario / tenant / project label로 분리 | D | **done** | **R11-S8-9-27** |
| B24 | 표준 데이터셋 보관(archive) UI | `POST /standard-dataset-types/{id}/archive` FE 보관 버튼·confirm·refresh. 물리 테이블 DROP/unarchive 제외 | A | **done** | **R11-S8-9-6** |
| B25 | REST API 연결 목록 로드 버그 | `ApiConnectorPanel`이 `GET /data-sources?size=200` 호출 → API max 100으로 **422** → Wizard 데이터 소스 셀렉트 항상 빈 목록. `DATA_SOURCE_LIST_PAGE_SIZE=100` + 등록/수정/삭제 후 패널 refresh + empty/error 구분 | A | **done** | **R11-S8-9-2**. 100건 초과 1페이지 제한 → B11 |
| B26 | Ops smoke soft-cancel assertion 안정화 | `check-visual-pipeline-ops.mjs`가 첫 번째 `run-detail-button`을 상태 확인 없이 클릭해, stuck 목록에 `RUNNING`이 있으면 soft-cancel 버튼 표시 여부 assertion이 깨지는 flaky 이슈. run 상태별 대상 선택과 assertion 분기로 안정화 | C | **done** | **R11-S8-9-7** |
| B27 | Upsert conflict_keys 선택/검증 UX | Upsert Load 노드에서 INSERT/UPDATE 기준이 되는 conflict_keys를 Target 컬럼 기준으로 선택하고, Source/Transform 출력 컬럼과의 존재 여부·nullable·type mismatch를 미리 검증하는 UX. 자동 확정이나 backend upsert 정책 변경은 제외 | B | **done** | **R11-S8-9-13** |

---

## 3. 1순위 (Studio 실사용 차단)

| 순서 | ID | 상태 | 비고 |
|------|-----|------|------|
| 1 | B17 | done | S8-9-1 Operations Dock |
| 2 | B25 | done | S8-9-2 data-sources size≤100 + refresh |
| 3 | B16 | done | S8-9-3 검증 후 Compile dirty 미재발 |
| 4 | B13 | done | S8-9-4 Inspector select schema default 주입 |
| 5 | B24 | done | S8-9-6 표준 데이터셋 보관 UI |
| 6 | B26 | done | S8-9-7 Ops smoke soft-cancel assertion 안정화 |

---

## 4. 그룹별 분류

### A — Studio / 데이터 관리 실사용 개선

B11(done), B13(done), B14(done), B16(done), B17(done), B24(done), B25(done)

### B — 범용 Visual Pipeline 구성 편의

B1(done), B2(done), B3(done), B15(done), B19(done), B20(done), B21(done), B27(done)

### C — 운영 가시성 / 복구 UX

B4(done), B6(done), B8(done), B9(done), B10(done), B18(done), B26(done)

### D — 범용 MLOps 확장 / 문서 / 장기

B5(done), B7(done), B12(done), B22(done), B23(done)

---

## 5. 완료 요약

| 단계 | ID | 완료 내용 | 커밋/참고 |
|------|-----|-----------|-----------|
| R11-S8-9-1 | B17 | Studio viewport 고정 + Bottom Operations Dock. Palette/Canvas/Inspector 내부 스크롤 | `e23461b` — `feat(R11-S8-9-1): Studio 스크롤과 Operations Dock 정리` (master push 완료) |
| R11-S8-9-2 | B25 | REST API 연결 Wizard Data Source 목록 `size≤100` 수정, 등록 후 refresh, empty/error 구분 | `fbfe8f2` |
| R11-S8-9-3 | B16 | Graph 검증 UI cache 분리 — 검증 후 dirty 미재발, Compile 연속 가능 | `77a6e05` |
| R11-S8-9-4 | B13 | Inspector select schema default 주입 (PLACEHOLDER 분리, Type B placeholder) | `0593d69` |
| R11-S8-9-5 | B14 | Transform unmapped_policy → FAIL_LOAD/SKIP_UNMAPPED/LOG_ONLY + Wizard 공통 상수 | `b8bc37c` |
| R11-S8-9-6 | B24 | 표준 데이터셋 보관 UI — archive API + confirm + 목록 refresh | `8688a3f` |
| R11-S8-9-7 | B26 | Ops smoke soft-cancel: run_status별 선택·assertion 분기 + fail() throw | `6abaeb9` |
| R11-S8-9-8 | B11 | Data Source 100건 초과: 클라이언트 검색·더 보기·새로고침 (size≤100) | `3ac54b0` |
| R11-S8-9-9 | B19 | Studio REST Data Source 선택 + REST_API 인라인 생성 (auth=NONE, secret UI 없음) | `2310c21` |
| R11-S8-9-10 | B20 | Studio Upsert Standard Dataset 선택 + DRAFT 인라인 생성 | |
| R11-S8-9-11 | B21 | Transform 출력 기반 표준 컬럼 후보 제안 + 컬럼 editor + DRAFT 생성 payload 반영 | |
| R11-S8-9-12 | B15 | Source↔Target 컬럼 정합성 미리보기 (FE diagnosis, mapping 저장 없음) | |
| R11-S8-9-13 | B27 | Upsert conflict_key_columns_json 선택·검증·추천 UX (자동 확정 없음) | |
| R11-S8-9-14 | B18 | Upsert Target Table sample rows 읽기 전용 미리보기 (GET target-table-preview) | |
| R11-S8-9-15 | B12 | Visual Pipeline E2E smoke (`check-visual-pipeline-e2e.mjs`) | |
| R11-S8-9-16 | B6 | Run Detail 실패 원인 한 줄 요약 (FE-only) | |
| R11-S8-9-17 | B10 | Ops 「조치 필요」카드 (stuck/failed/partial/catch-up hint) | |
| R11-S8-9-18 | B9 | Ops Schedule Skip 이력 UI (read-only schedule-skips + reason 매핑) | |
| R11-S8-9-19 | B4 | Studio Catch-up 안내 UX (용어·checklist·reason 다음 확인, FE-only) | |
| R11-S8-9-20 | B8 | PARTIAL 영향/Retry 전 확인 카드 (FE-only, 중복 단정 없음) | |
| R11-S8-9-21 | B5 | Ops/Studio 운영 확인 필요 badge PoC (read-model, no table) | |
| R11-S8-9-22 | B3 | Schema / Key Mapping Helper (FE-only, 자동 저장·물리 스키마 변경 없음) | |
| R11-S8-9-23 | B1 | Visual Pipeline Starter Template (FE-only skeleton, Type B 비움) | |
| R11-S8-9-24 | B2 | Domain Preset Framework (FE-only hint, Type B 자동 설정 없음) | |
| R11-S8-9-25 | B7 | Data Load → ML Workflow Handoff Guide (docs, ML 구현 아님) | |
| R11-S8-9-26 | B22 | DISABLED Components Implementation Roadmap (docs, 활성화 아님) | |
| R11-S8-9-27 | B23 | Product Branding Generalization (문구 정리, ID/route 변경 아님) | |

---

## 6. 변경 이력

| 날짜 | 변경 |
|------|------|
| 2026-07-27 | 문서 신규 생성. S8-8 §13 + stash(B13~B23) + 실사용 이슈(B24, B25) 통합. B1~B3·B7·B12 범용 MLOps 표현으로 정리 |
| 2026-07-27 | B17 → `done` (S8-9-1) |
| 2026-07-27 | B24 표준 데이터셋 archive UI, B25 REST API 연결 size=200 버그 추가 |
| 2026-07-28 | B17 완료 확정 (`e23461b` push). B26 Ops smoke soft-cancel assertion 안정화 이슈 추가. clean HEAD에서도 재현되어 S8-9-1과 무관한 기존 smoke flaky 이슈로 분리 |
| 2026-07-28 | B25 → `done` (S8-9-2). `DATA_SOURCE_LIST_PAGE_SIZE=100`, DataSourcesPage→ApiConnectorPanel refreshToken, empty/error 구분. 100건 초과 UX는 B11로 이관 |
| 2026-07-28 | B16 → `done` (S8-9-3). Graph 검증 UI cache 분리, dirty/save에서 `config.validation` canonicalize |
| 2026-07-28 | B16 push (`77a6e05`). B13 → `done` (S8-9-4). schema default 주입 + form fallback 정리 |
| 2026-07-28 | B13 push (`0593d69`). B14 → `done` (S8-9-5). unmapped_policy backend enum 정렬 + legacy C안 |
| 2026-07-28 | B14 push (`b8bc37c`). B24 → `done` (S8-9-6). 표준 데이터셋 보관 UI + check-pages smoke |
| 2026-07-30 | B24 push (`8688a3f`). B26 → `done` (S8-9-7). Ops smoke run_status별 soft-cancel assertion + fail() throw |
| 2026-07-30 | B26 push (`6abaeb9`). B11 → `done` (S8-9-8). Data Source 검색·더 보기·새로고침 (서버 keyword 없음) |
| 2026-07-30 | B19 → `done` (S8-9-9). Studio REST Data Source 선택·인라인 생성 (secret/credential 저장 UI 제외) |
| 2026-07-30 | B19 push (`2310c21`). B20 → `done` (S8-9-10). Studio Upsert Standard Dataset 선택·DRAFT 인라인 생성 |
| 2026-07-30 | B21 → `done` (S8-9-11). Transform 출력 기반 컬럼 후보 제안 + 컬럼 editor + DRAFT 생성 payload 반영 |
| 2026-07-31 | B15 → `done` (S8-9-12). Source↔Target 컬럼 정합성 미리보기 (FE diagnosis only) |
| 2026-07-31 | B27 추가 후 → `done` (S8-9-13). Upsert conflict_key_columns_json 선택·검증·추천 UX |
| 2026-07-31 | B18 → `done` (S8-9-14). Target Table sample rows 읽기 전용 미리보기 (Inspector, Run Detail 제외) |
| 2026-07-31 | B12 → `done` (S8-9-15). Visual Pipeline E2E smoke scenario (`check-visual-pipeline-e2e.mjs`) |
| 2026-07-31 | B6 → `done` (S8-9-16). Run Detail 실패 원인 한 줄 요약 (FE-only) |
| 2026-07-31 | B10 → `done` (S8-9-17). Ops 「조치 필요」카드 (FE-only, auto-action 없음) |
| 2026-07-31 | B9 → `done` (S8-9-18). Ops Schedule Skip 이력 UI (read-only `GET .../schedule-skips`, worker emit 미변경) |
| 2026-07-31 | B4 → `done` (S8-9-19). Studio Catch-up 안내 UX (FE-only, auto 복구 암시 없음) |
| 2026-07-31 | B8 → `done` (S8-9-20). PARTIAL 영향 범위 안내 (FE-only, 실제 중복 단정 없음) |
| 2026-07-31 | B5 → `done` (S8-9-21). Ops/Studio 운영 확인 필요 badge PoC (read-model, no notification table) |
| 2026-07-31 | B3 → `done` (S8-9-22). Schema / Key Mapping Helper (FE-only 진단·추천·form 적용, 자동 저장/물리 스키마 변경 없음) |
| 2026-07-31 | B1 → `done` (S8-9-23). Visual Pipeline Starter Template (FE-only skeleton, 자동 저장/실행 없음, Type B 비움) |
| 2026-08-03 | B2 → `done` (S8-9-24). Domain Preset Framework (FE-only preset hint, Type B 자동 설정 없음, 실행 가능한 완성 preset 아님) |
| 2026-08-03 | B7 → `done` (S8-9-25). Data Load → ML Workflow Handoff Guide (docs only; ML Workflow 구현 아님) |
| 2026-08-03 | B22 → `done` (S8-9-26). DISABLED Components Implementation Roadmap (docs only; 본구현/활성화 아님) |
| 2026-08-03 | B23 → `done` (S8-9-27). Product Branding Generalization (문구 정리; 제품명·ID·route/API 변경 아님) |

---

## 7. 관련 문서

- [R11-S8-9-27 Product Branding Generalization](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md) — branding/terminology (ID·route 변경 아님)
- [R11-S8-9-26 DISABLED Components Implementation Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md) — DISABLED/후순위 component roadmap (활성화 아님)
- [R11-S8-9-25 Data Load → ML Workflow Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md) — handoff 기준 (가이드, ML 구현 아님)
- [R11-S8-8 열수요 예측 Full Scenario 이용가이드](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) — 대표 예시 시나리오 (backlog 본편 제외)
- [R11-S8-0 Run History / Progress / Retry 설계](./THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md)
- [R11-S8-7 Notification 설계](./THERMOps_R11-S8-7_Notification_설계.md)

---

## 8. Decision Log

| ID | 결정 |
|----|------|
| D1 | S8-9 backlog **단일 소스**는 본 문서(`THERMOps_R11-S8-9_Backlog.md`)이다. |
| D2 | S8-8 이용가이드에는 여정만 두고, backlog 표는 본 문서로 이전한다. |
| D3 | backlog ID(B1~)는 유지한다. 재번호하지 않는다. |
| D4 | 열수요 예측은 **검증 시나리오**일 뿐; B1/B2 등은 범용 MLOps 제품 기능으로 기술한다. |
| D5 | 신규 이슈 발견 시 본 문서 §2 표 + §6 변경 이력에 반영한다. |
