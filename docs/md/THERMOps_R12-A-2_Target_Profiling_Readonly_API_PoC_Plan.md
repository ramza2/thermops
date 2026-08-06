# THERMOps R12-A-2 Target Profiling Read-only API PoC Scope / Implementation Plan

> **문서 성격:** 본 문서는 R12-A-2 Target Profiling Read-only API PoC의 **범위와 구현 계획**을 정의하기 위한 문서이다.  
> 본 문서는 **API 구현 문서가 아니며**, backend route/service/schema, DB, UI, worker, component registry를 변경하지 않는다.  
> **실제 API 구현과 테스트는 별도 승인 후 진행**한다.

| 항목 | 값 |
|------|-----|
| 문서 ID | R12-A-2-0 |
| 상위 | [R12-A-0 Scope](./THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md), [R12-A-1 Catalog](./THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md) |
| 기준 커밋 | `1c044be` (sample CSV) · `c5a6a51` (R12-A-1) |
| Fixture 후보 | `data/samples/classification_sample.csv` (합성 샘플 · **본 문서 작업에서 수정하지 않음**) |

---

## 1. 목적

- Target Profiling **Read-only API PoC**의 범위를 정의한다.
- endpoint · request/response · service 책임 · SQL safety · performance · test 전략을 정리한다.
- R12-A-1 Rule Catalog와 연결되는 **최소 metric**을 정의한다.
- API는 read-only이며 write/persist/blocking이 아님을 명시한다.
- 구현을 R12-A-2-0~2-7로 나눈다.
- **이번 작업에서는 route/service/schema/test를 구현하지 않는다.**

---

## 2. 기준 문서

| 문서 | 역할 |
|------|------|
| [R12-A-0](./THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md) | non-blocking / read-only · Profiling 후보 · Phase |
| [R12-A-1](./THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md) | DQ-001~010 · MVP set · threshold/handoff 정책 |
| [B7 Handoff](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md) | Preview≠전수 · Handoff 보조 |
| [B22 Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md) | `VP_DATA_QUALITY` = DISABLED roadmap |
| [B23 Branding](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md) | 범용 Data Load · 열수요=예시 |

---

## 3. R12-A-2 위치와 범위

```text
R12-A-0 Scope → R12-A-1 Catalog/Policy → [R12-A-2 Profiling API PoC] → R12-A-3 Summary Contract → …
```

| 포함 (계획) | 제외 (이번·PoC 공통) |
|-------------|---------------------|
| endpoint/contract 후보 | Rule engine 전체 |
| MVP metric 산출 계획 | threshold 적용·저장 |
| read-only SQL safety | Run/Compile blocking |
| guardrail · test 전략 | DQ result persist |
| backlog 2-0~2-7 | `VP_DATA_QUALITY` 활성화 |
| | Handoff status 반영 (A-3/A-5) |
| | FE UI · package · CSV 수정 |

**Target Profile Summary ≠ DQ Rule Result.**  
`handoff_recommendation`은 **R12-A-3 / A-5 이후**로 분리한다.

---

## 4. 기존 구현 확인 결과

| 영역 | 경로/엔드포인트 | PoC 시사점 |
|------|-----------------|------------|
| Target Preview (B18) | `GET /api/v1/standard-dataset-types/target-table-preview?target_table=` · `target_table_preview_service.py` | SELECT-only · `quote_ident` · SDS 등록 검증 · `row_count` + LIMIT sample. **Profile과 분리**(sample rows 최소화) |
| SQL identifier | `app/utils/sql_identifier.py` | `ALLOWED_SCHEMA`, `TABLE_NAME_RE`, `quote_ident` 재사용 후보 |
| VP Run | `GET /visual-pipelines/{pipeline_id}/runs/{run_id}` | nested run 패턴 → **target-profile 부착 후보** |
| Materialization | `…/materialize`, `…/materialization-result` | target 해석 메타 후보 |
| Ops | summary / stuck / skips | Profile과 무관 |

Preview는 `target_table` query를 받지만, **R12-A-2는 외부에서 임의 테이블명을 받지 않고** run/materialization metadata로 제한한다.

---

## 5. API PoC 기본 원칙

1. API는 **read-only**다.  
2. DB write/update/delete/insert를 하지 않는다.  
3. DQ result를 **저장하지 않는다**.  
4. Run/Compile/Worker를 차단·변경하지 않는다 (**non-blocking**).  
5. `VP_DATA_QUALITY` node를 **활성화하지 않는다**.  
6. Target table은 임의 문자열이 아니라 **run/materialization metadata**에서 확인된 값만.  
7. SQL identifier는 **whitelist + quoting** 필수.  
8. **full scan을 기본 강제하지 않는다.**  
9. limit / sampling / timeout / max-column **guardrail**을 둔다.  
10. 결과는 **Target Profile Summary** (DQ Rule Result 아님).  
11. `handoff_recommendation`은 A-3/A-5로 분리.  
12. **실제 API 구현은 별도 승인 후** 진행한다.

---

## 6. Endpoint 후보

### 6.1 권장 초안 (확정 아님)

```text
GET /api/v1/visual-pipelines/{pipeline_id}/runs/{run_id}/target-profile
```

- 기존 nested run 라우트와 정합  
- POST/PUT/PATCH/DELETE **사용하지 않음**  
- `target_table`을 query parameter로 **직접 받지 않음**

### 6.2 Query 후보 (확정 아님)

| Query | 설명 | 비고 |
|-------|------|------|
| `profile_mode` | `BASIC` \| `EXTENDED` | PoC는 **BASIC 우선** |
| `sample_limit` | metric/scan 상한 후보 | Preview LIMIT과 역할 분리 |
| `include_columns` | 프로파일 컬럼 제한 | whitelist 내 |

`key_columns` / `timestamp_column`은 compile·write policy·SDS·Upsert conflict key **메타 우선**. request override는 후속 검토.

### 6.3 비권장

- `GET …/target-profile?target_table=…` (임의 테이블 입력)  
- `GET /visual-pipeline-runs/{run_id}/target-profile` — 가능하나 pipeline 컨텍스트가 약함 (보조 후보만)

---

## 7. Request / Response Contract 후보

문서 초안만. Pydantic/구현은 **R12-A-2-1 이후·별도 승인**.

### 7.1 TargetProfileSummary

| 필드 | 설명 |
|------|------|
| pipeline_id | Visual Pipeline ID |
| run_id | Visual run ID |
| target_ref | 해석된 물리 테이블 참조 (노출 최소화 검토) |
| standard_dataset_id | 후보 |
| profile_mode | BASIC / EXTENDED |
| generated_at | 산출 시각 |
| profile_status | §13 상태 코드 |
| row_count | MVP |
| column_count | MVP |
| columns | ColumnProfile[] |
| key_profile | KeyProfile 후보 |
| timestamp_profile | TimestampProfile 후보 |
| schema_profile | SchemaProfile 후보 |
| warnings | string[] |
| profiling_scope | table / sampled 등 |
| is_sampled | bool |
| sample_limit | 적용 상한 |
| data_freshness | freshness 요약 후보 |

**제외:** `handoff_recommendation`, rule_id별 PASS/WARN/FAIL, threshold 판정.

### 7.2 ColumnProfile

`column_name` · `data_type`(후보) · `null_count` · `null_ratio` · `distinct_count`(후보) · `min_value`/`max_value`(후속·민감도 검토)

### 7.3 KeyProfile

`key_columns` · `duplicate_key_count` · `distinct_key_count`(후보)

### 7.4 TimestampProfile

`timestamp_column` · `min_timestamp` · `max_timestamp` · `freshness_lag_seconds`(후보)

### 7.5 SchemaProfile

`expected_columns`(후보) · `actual_columns` · `missing_columns` · `extra_columns`

---

## 8. Profiling Metric MVP Set

| Metric | 설명 | BASIC |
|--------|------|-------|
| row_count | 행 수 | Y |
| column_count | 컬럼 수 | Y |
| null_count / null_ratio | 선택 컬럼 | Y |
| duplicate_key_count | conflict key | Y |
| timestamp min/max | 시간 컬럼 | Y |
| freshness_lag | 후보 | Y |
| schema vs expected | missing/extra | Y |
| generated_at | 메타 | Y |

**MVP에서 하지 않음:** rule status 산출 · threshold 적용 · outlier · gap · numeric range · type full validation · persist · blocking · sample row 반환(Preview와 분리).

---

## 9. Profiling Metric 후속 후보

- numeric min/max/avg  
- type compatibility summary  
- outlier candidate count  
- time-series gap  
- row_count_delta vs previous run  
- approximate distinct  
- partition-level profile  
- persisted profile  
- EXTENDED mode · async/background profiling  

---

## 10. R12-A-1 Rule Catalog와의 매핑

| Rule | Metric 입력 | 본 PoC |
|------|-------------|--------|
| DQ-001 Required Column Presence | schema missing/extra | metric만 |
| DQ-002 Null Ratio | null_count / null_ratio | metric만 |
| DQ-003 Duplicate Key | duplicate_key_count | metric만 |
| DQ-004 Timestamp / Freshness | min/max / freshness_lag | metric만 |
| DQ-006 Row Count | row_count | metric만 |
| DQ-007 Schema Drift | expected vs actual | metric만 |
| DQ-005 / 008 / 009 / 010 | — | **후속** |

threshold·severity severity·handoff 매핑 적용은 **Rule engine / A-3·A-5** 영역이며 본 PoC 밖이다.

---

## 11. Read-only SQL Safety 정책

- **SELECT only**  
- **no INSERT / no UPDATE / no DELETE / no TRUNCATE / no DDL**  
- transaction read-only 후보  
- raw SQL 시 identifier **whitelist + `quote_ident`** 필수 (`sql_identifier` 재사용 후보)  
- table/schema는 **run/materialization metadata**에서 확인된 값만  
- **arbitrary table name query parameter 금지**  
- column names는 actual/expected schema에서 확인된 값만  
- LIMIT / sampling 필수  
- statement_timeout 후보  
- 오류 시 partial unsafe result보다 **안전 실패** 응답 후보  

DB 롤 자체가 read-only인지, app-level guard만으로 충분한지는 §21 질문으로 남긴다.

---

## 12. Performance Guardrail

| Guardrail | 후보 |
|-----------|------|
| default_sample_limit | Preview와 별도 상수 (예: 정책 문서 확정) |
| max_sample_limit | 상한 clamp |
| max_profile_columns | BASIC 컬럼 수 제한 |
| max_key_columns | conflict key 개수 제한 |
| profile_mode | **BASIC 우선** · EXTENDED 후속 |
| row_count | exact COUNT vs approximate 검토 |
| full table scan | 비용 경고 · 기본 비강제 |
| timeout | statement_timeout 후보 |
| async | 후속 |
| 대용량 | sampled summary로 시작 |

---

## 13. Error / Status Policy 후보

| profile_status | 의미 |
|----------------|------|
| `PROFILE_READY` | BASIC metric 산출 성공 |
| `PROFILE_PARTIAL` | 일부 metric만 (후속 정책) |
| `PROFILE_NOT_READY` | 전제 미충족 |
| `TARGET_NOT_FOUND` | 물리 테이블 없음 |
| `TARGET_NOT_MATERIALIZED` | materialization/메타 부족 |
| `INVALID_TARGET` | 식별자/등록 정책 위반 |
| `UNSUPPORTED_TARGET` | PoC 미지원 형태 |
| `PROFILE_FAILED` | 조회 실패 |

이 값은 **DQ overall_status(PASS/WARN/FAIL)가 아니다.** 혼동하지 않는다.

---

## 14. Security / Access Boundary

현재 THERMOps 1차는 Auth/SSO/JWT **미구현**(Mock `VITE_USER_ROLE`). 문서상 검토 질문:

1. Auth 부재 범위에서 profile API 접근을 어떻게 제한할 것인가?  
2. `target_ref` / 테이블명 노출 범위는?  
3. sample values vs **metric only**? → PoC는 **metric 중심** 권장  
4. column min/max가 민감 데이터가 될 수 있는가? → BASIC에서 최소화  
5. 운영 테이블용 **read-only DB connection** 분리가 필요한가?  

권장: sample rows는 **기존 Target Preview**에 맡기고, Profile은 metric만.

---

## 15. Test Strategy 후보

| 종류 | 내용 |
|------|------|
| unit | response schema 조립 |
| service | identifier quoting / whitelist |
| API | run not found · no target · BASIC success |
| DB | SELECT-only · DML 미호출 |
| regression | 기존 Target Preview 영향 없음 |
| docs | check-pages 정적 assert |

**Fixture:** `data/samples/classification_sample.csv`는 합성 샘플로 **향후 API PoC 검증 fixture 후보**.  
본 문서 작업에서 **파일을 수정하지 않는다.** 실제 테스트 사용 여부는 **R12-A-2-7 별도 승인**.

---

## 16. Implementation Backlog 분할

| ID | 내용 | 승인 |
|----|------|------|
| **R12-A-2-0** | API PoC Scope / Implementation Plan | **본 문서** |
| R12-A-2-1 | Response Contract / Pydantic Schema 초안 | 별도 |
| R12-A-2-2 | Target resolution service 검토 | 별도 |
| R12-A-2-3 | Basic Profiling service PoC | 별도 |
| R12-A-2-4 | Read-only API route PoC | 별도 |
| R12-A-2-5 | Backend tests | 별도 |
| R12-A-2-6 | README / API docs / check-pages | 별도 |
| R12-A-2-7 | Optional sample fixture use review | 별도 |

R12-A-2-1 이후는 **별도 승인 없이 착수하지 않는다.**

---

## 17. 수용 기준 (문서)

- Plan 문서 존재 · API 구현 문서 아님 · 별도 승인 명시  
- endpoint · contract · MVP/후속 metric · A-1 매핑  
- SQL safety · guardrail · error/status · security 질문 · test · backlog 2-0~2-7  
- README · A-0/A-1 링크  
- backend/FE/package/CSV 미변경  

---

## 18. 검증 전략

| 단계 | 검증 |
|------|------|
| R12-A-2-0 (지금) | docs · README · check-pages · package/CSV empty · studio/ops/e2e 회귀 |
| R12-A-2-1+ | contract 단위 테스트 (승인 후) |
| R12-A-2-4+ | API smoke · Preview 회귀 (승인 후) |

---

## 19. Known Limitations

- Profiling API·Rule engine·threshold·UI·blocking·node ACTIVE·handoff 반영은 **없다**.  
- endpoint/contract는 **후보**이며 확정 아님.  
- Auth 경계는 미해결 질문.  
- full scan/exact COUNT 비용은 운영 데이터에 따라 큼.  
- CSV fixture 사용은 미결정.  
- 본 문서만으로 Target Profiling API가 제공된 것이 아니다.

---

## 20. 변경하지 않는 것

- backend route/service/schema · migration · worker  
- FE 본기능 · registry/palette · `VP_DATA_QUALITY` status  
- package / requirements  
- `data/samples/classification_sample.csv`  
- Feature / Training / Prediction / Notification 본구현  

---

## 21. 다음 의사결정 질문

1. endpoint를 nested run path로 확정할 것인가?  
2. BASIC에서 `row_count`를 exact COUNT로 둘 것인가, approximate/sampled로 둘 것인가?  
3. DB read-only role을 분리할 것인가?  
4. R12-A-2-1 (Pydantic contract)을 다음으로 승인할 것인가?  
5. `classification_sample.csv`를 API 테스트 fixture로 쓸 것인가? (2-7)

---

## 22. 용어

| 용어 | 의미 |
|------|------|
| Target Profile Summary | read-only metric 요약 · Rule Result 아님 |
| BASIC | 최소 metric 모드 |
| profile_status | API 산출 상태 · DQ PASS/WARN/FAIL 아님 |
| Target resolution | run/materialization 메타에서 테이블 확정 |
| R12-A-2-0 | 본 Plan 문서 |

---

## 23. 관련 문서

- [THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md](./THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md)
- [THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md](./THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md)
- [THERMOps_R12_Candidate_Prioritization_Draft.md](./THERMOps_R12_Candidate_Prioritization_Draft.md)
- [THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)
- [THERMOps_R11-S8-9-27_Product_Branding_Generalization.md](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md)
