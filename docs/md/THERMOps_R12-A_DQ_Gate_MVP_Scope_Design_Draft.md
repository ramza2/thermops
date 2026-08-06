# THERMOps R12-A Data Quality Gate & Handoff Hardening MVP Scope Design Draft

> **문서 성격:** 본 문서는 R12-A Data Quality Gate & Handoff Hardening의 **MVP 범위와 설계 방향**을 정의하기 위한 **초안**이다.  
> 본 문서는 **구현 착수 문서가 아니며**, API / DB / UI / worker / component registry를 변경하지 않는다.  
> **최종 구현 범위와 착수 여부는 별도 승인 후 확정**한다.

| 항목 | 값 |
|------|-----|
| 문서 ID | R12-A-0 |
| 후보 | R12-A Data Quality Gate & Handoff Hardening |
| 기준 | R12 Prioritization `021a0ee` · Closeout `286a93d` |
| 관련 | [B7 Handoff](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md), [B22 Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md), [R12 Prioritization](./THERMOps_R12_Candidate_Prioritization_Draft.md) |

---

## 1. 목적

- R12-A에서 **무엇을 MVP로 할지** 정의한다.
- 첫 구현을 **non-blocking / read-only** 중심으로 제한하는 원칙을 고정한다.
- DQ Gate가 Run을 **차단하는지 여부**를 정책 단계로 분리한다.
- B7 Handoff checklist와 DQ Gate의 **연결 지점**을 정의한다.
- DQ Rule Catalog · Target Profiling · Result Model · Studio/Ops 표시 위치 초안을 정리한다.
- 향후 구현을 **작은 backlog**로 나눈다.
- **실제 API / DB / UI / worker / node 구현은 하지 않는다.**

---

## 2. 기준 문서

| 문서 | 역할 |
|------|------|
| [R12 Candidate Prioritization Draft](./THERMOps_R12_Candidate_Prioritization_Draft.md) | R12-A를 1순위 **후보**로 추천 (미확정) |
| [R11-S8-9-28 Closeout](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md) | Studio/Ops UX 마감 · R12 후속 후보 |
| [B7 Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md) | Data Load → ML **인수 기준** |
| [B22 DISABLED Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md) | `VP_DATA_QUALITY` = roadmap · P1/R12-A |
| [B23 Branding](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md) | THERMOps 유지 · VP=Data Load/Workflow · 열수요=예시 |
| [S8-8 Full Scenario](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) | 대표 예시 시나리오 |

---

## 3. R12-A 위치와 범위

### 3.1 제품 흐름에서의 위치

```text
REST Source
  → Transform
  → Upsert Load
  → Target Table / Standard Dataset
  → Run SUCCESS
  → Target Preview / Schema-Key 확인
  → DQ Summary (R12-A 후보)
  → Handoff Ready 판단 (운영자)
  → Feature / Training / Prediction (R12-B/C/D 후보)
```

### 3.2 이번 문서(R12-A-0) 범위

| 포함 | 제외 |
|------|------|
| MVP 원칙 · Phase 단계화 | backend API / DB migration |
| Rule catalog · profiling · result model **초안** | DQ engine · profiling API · result 테이블 구현 |
| Studio/Run/Ops **표시 위치 초안** | FE 본기능 · registry/palette |
| Backlog 분할 후보 | `VP_DATA_QUALITY` node 상태 변경 |
| B7 checklist 연결 | Run blocking · Feature/Train/Predict · Notification 본구현 |

`VP_DATA_QUALITY`는 B22상 **DISABLED roadmap 후보**이다. **node 활성화는 별도 단계(Phase G)** 이며 본 문서에서 수행하지 않는다.

---

## 4. MVP 기본 원칙

1. 첫 MVP는 **non-blocking**으로 시작한다.
2. 첫 MVP는 **read-only DQ summary** 중심으로 시작한다.
3. **Run 실행 자체를 차단하지 않는다.**
4. DQ 결과는 **운영자 판단 보조 정보**로 제공한다.
5. DQ 경고/실패는 Handoff 판단에 반영하되, **자동으로 ML Workflow를 실행하거나 차단하지 않는다.**
6. **`VP_DATA_QUALITY` node 활성화는 별도 단계**로 분리한다.
7. DQ rule은 **최소 catalog**부터 시작한다.
8. Target profiling은 sample preview보다 넓은 품질 요약으로 정의하되, 첫 단계에서 **full scan을 강제하지 않는다.**
9. Feature / Training / Prediction 구현과 **분리**한다.
10. API / DB migration 여부는 **후속 구현 단계에서 별도 판단**한다.

---

## 5. Non-blocking / Read-only 우선 정책

| 원칙 | 의미 |
|------|------|
| non-blocking | Compile / Materialization / Manual·Scheduled Run을 DQ 결과로 **막지 않음** |
| read-only | 첫 단계 summary는 조회·표시 중심 · write policy / unique index / DROP 등과 무관 |
| 판단 보조 | `handoff_recommendation`은 **자동 승인 상태가 아님** |
| 분리 | blocking policy · node 활성화 · Feature/Train은 각각 후속 승인 |

운영자 메시지 권장 요지(구현 시):

- PASS → “Handoff 후보. 체크리스트와 함께 인수 판단.”
- WARN / REVIEW_REQUIRED → “검토 필요. Run은 막지 않음.”
- FAIL / NOT_READY → “인수 보류 권고. Run 재실행·데이터 수정 검토.” (자동 차단 아님)

---

## 6. B7 Handoff Checklist와 DQ Gate 연결

B7 요지: **Data Load 완료 ≠ ML 입력 준비 완료**. Domain Preset은 FE hint이며 backend SoT가 아니다. ML 학습·예측 실행 경로는 미구현이다.

### 6.1 Handoff Checklist → DQ 입력 조건

| B7 체크 항목 (요지) | DQ Gate와의 관계 |
|---------------------|------------------|
| Graph saved / validation | DQ 평가 **전제** (그래프·설정 안정) |
| Compile IN_SYNC / materialization | DQ 평가 **전제** (실행 가능 설정) |
| Run SUCCESS (또는 조건부) | DQ Summary **트리거 후보** |
| Target Preview (sample) | DQ의 **선행 육안 확인** · sample만으로 전수 품질 보증 아님 |
| Schema / Key Helper | DQ-001/007 등과 **보완** |
| Conflict keys | DQ-003 Duplicate Key와 **연계** |
| PARTIAL / skip / action required | Handoff 보류 · DQ는 보조 정보 |
| Domain Preset | SoT 아님 · DQ threshold/도메인 규칙의 **참고만** |

### 6.2 DQ가 추가하는 단계

```text
[B7 Checklist] + [DQ Summary] → 운영자 Handoff 판단 → (후속) R12-B/C/D
```

- Preview/sample만으로는 부족할 수 있어 **profiling / rule summary** 후보를 둔다.
- DQ 결과는 Feature/Training/Predict **전 사전 판단 자료**로만 쓴다 (자동 넘김 없음).

---

## 7. DQ Rule Catalog 후보

Severity: `INFO` / `WARN` / `ERROR`  
Blocking 가능성: `NONE` / `LATER` / `POSSIBLE`  
**첫 MVP에서는 Blocking = NONE만 적용한다** (실제 blocking 미구현).

| Rule ID | 구분 | Rule | 목적 | 기본 Severity | 적용 대상 | Blocking 가능성 | MVP |
|---------|------|------|------|---------------|-----------|-----------------|-----|
| DQ-001 | Schema | Required Column Presence | 필수 컬럼 존재 | ERROR | Target / SDS columns | LATER | **Y** |
| DQ-002 | Completeness | Null Ratio Check | 컬럼별 null 비율 | WARN | 측정값·키 컬럼 | LATER | **Y** |
| DQ-003 | Uniqueness | Duplicate Key Check | conflict key 중복 | ERROR | conflict_key 집합 | POSSIBLE | **Y** |
| DQ-004 | Freshness | Timestamp Range / Freshness | 시간 범위·지연 | WARN | timestamp 컬럼 | LATER | **Y** |
| DQ-005 | Validity | Numeric Range Check | 수치 허용 범위 | WARN | numeric 측정값 | LATER | N |
| DQ-006 | Volume | Row Count Min / Delta | 최소 건수·급변 | WARN | table / partition | LATER | **Y** |
| DQ-007 | Schema | Schema Drift Check | 기대 스키마 대비 변화 | WARN | columns vs expected | LATER | **Y** |
| DQ-008 | Type | Type Compatibility Check | 타입 정합 | WARN | source↔target | LATER | N |
| DQ-009 | Outlier | Outlier Candidate Check | 이상치 후보 | INFO | numeric | NONE | N |
| DQ-010 | Series | Time Series Gap Check | 시계열 공백 | WARN | entity×time | LATER | N |

- **MVP 우선:** DQ-001, DQ-002, DQ-003, DQ-004, DQ-006, DQ-007  
- **후속:** DQ-005, DQ-008, DQ-009, DQ-010  
- threshold·도메인 기본값 후보는 **[R12-A-1 DQ Rule Catalog & Policy](./THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md)** 에서 정의한다 (엔진·저장 미구현).

---

## 8. Target Profiling 후보

| Profile Item | 설명 | 계산 범위 | MVP | 비고 |
|--------------|------|-----------|-----|------|
| row_count | 적재 행 수 | table / 최근 파티션 후보 | Y | Preview LIMIT과 구분 |
| column_count | 컬럼 수 | table schema | Y | |
| null_count / null_ratio | 컬럼별 null | column | Y | DQ-002 |
| distinct_count (keys) | 키 distinct | conflict key | Y | |
| duplicate_key_count | 키 중복 건수 | conflict key | Y | DQ-003 |
| min/max timestamp | 시간 범위 | timestamp col | Y | DQ-004 |
| freshness_lag | 최신 시각 대비 지연 | timestamp | Y | |
| numeric min/max/avg | 수치 요약 | numeric | 후속 | DQ-005/009 |
| schema vs expected | 기대 컬럼 비교 | SDS / Transform | Y | DQ-007 |
| last_run_id / generated_at | 평가 메타 | run 연계 | Y | |

주의:
- full profiling은 대용량에서 비용이 클 수 있다 → **sampling / limit / async**는 후속 검토.
- 첫 MVP는 **read-only / summary** 중심이며 API 구현은 [R12-A-2 Plan](./THERMOps_R12-A-2_Target_Profiling_Readonly_API_PoC_Plan.md) 이후 **별도 승인**.

---

## 9. DQ Result Model 초안

문서 초안만. **DB/API 구현 금지.**

### 9.1 DqRunSummary

| 필드 | 설명 |
|------|------|
| pipeline_id | Visual Pipeline ID |
| pipeline_version_id / compiled_version_id | 버전 후보 (후속 확정) |
| run_id | Visual / load run 연계 |
| target_table / standard_dataset_id | 평가 대상 |
| overall_status | `NOT_EVALUATED` / `PASS` / `WARN` / `FAIL` |
| evaluated_at | 평가 시각 |
| rule_count / pass_count / warn_count / fail_count | 집계 |
| blocking_applied | 첫 MVP는 항상 `false` |
| handoff_recommendation | `READY` / `REVIEW_REQUIRED` / `NOT_READY` (**자동 승인 아님**) |

### 9.2 DqRuleResult

| 필드 | 설명 |
|------|------|
| rule_id / rule_name | catalog 참조 |
| severity | INFO / WARN / ERROR |
| status | PASS / WARN / FAIL / SKIPPED |
| metric_name / metric_value / threshold | 측정값·임계 |
| message | 운영자용 요약 |
| affected_columns | 영향 컬럼 |
| sample_rows_ref | 샘플 참조 후보 (후속) |

첫 MVP에서 DB 영속화 없이 **read-only 계산 또는 임시 응답**으로 시작할 수 있는지는 R12-A-3/A-6에서 판단한다.

---

## 10. Studio / Run Detail / Ops 표시 위치 초안

| 위치 | 초안 역할 | MVP 단계 |
|------|-----------|----------|
| Studio Inspector | Handoff readiness / DQ 요구 힌트 | C 이후 |
| Compile Preview | “DQ 미평가” 안내 후보 | C (선택) |
| Run Detail | **DQ Summary card** (주 표시) | C |
| Target Preview | profiling summary 연결 | B~C |
| Ops Action Required | WARN/FAIL → REVIEW_REQUIRED 힌트 | E (선택) |

주의:
- **이번 문서에서 UI를 구현하지 않는다.**
- Ops badge / Action Required와 **Notification 본구현을 혼동하지 않는다** (B5 PoC · S8-7 구분).

---

## 11. Run Blocking Policy 단계화

| Phase | 내용 | Blocking | 승인 |
|-------|------|----------|------|
| **A** | Documentation / Scope (본 문서 R12-A-0) | none | 문서 |
| **B** | Read-only Profiling API | none | 별도 |
| **C** | Studio / Run Detail DQ Summary UI | none | 별도 |
| **D** | Persisted DQ Result | none | 별도 |
| **E** | Handoff Status Integration | none (review hint) | 별도 |
| **F** | Optional Blocking Policy Design | 검토 가능 | 별도 |
| **G** | Optional `VP_DATA_QUALITY` node 활성화 검토 | — | **별도** |

정책:
- **Phase A~C: non-blocking only**
- Phase D~E: REVIEW_REQUIRED 표시 가능 (Run 미차단)
- Phase F 이후: blocking **검토** 가능 (구현 단정 아님)
- Phase G: component/node 상태 변경 → **registry 승인 필수**

---

## 12. 사용자 흐름 예시

1. Visual Pipeline 생성·수정  
2. REST Source → Transform → Upsert 설정  
3. Compile 및 Run  
4. Run SUCCESS 후 Target Preview 확인  
5. **DQ Summary**가 Target 품질을 요약 (read-only)  
6. WARN/FAIL이면 Handoff는 **REVIEW_REQUIRED** (자동 차단 아님)  
7. rule 결과를 보고 schema/key/data 문제 수정  
8. Summary가 PASS이고 B7 checklist를 충족하면 **후속 Feature/Training 후보 단계로 넘길 수 있음** (자동 실행 없음)

---

## 13. 열수요 예시 적용

열수요는 **대표 적용 예시**이다. THERMOps / Visual Pipeline을 한 도메인 전용으로 설명하지 않는다. Heat Demand preset은 FE hint이며 SoT가 아니다.

| 예시 확인 | 연계 Rule / Profile |
|-----------|-------------------|
| timestamp 컬럼 존재 | DQ-001 / DQ-004 |
| entity / branch key 존재 | DQ-001 |
| freshness / 시간 범위 | DQ-004 · freshness_lag |
| 시계열 gap | DQ-010 (후속) |
| 수요량 numeric range | DQ-005 (후속) |
| row count minimum | DQ-006 |
| duplicate key (`entity_id` + `measured_at`) | DQ-003 |

---

## 14. 구현 Backlog 분할 후보

| ID | 내용 | 비고 |
|----|------|------|
| **R12-A-0** | DQ Gate MVP Scope Design Draft | 상위 문서 |
| **R12-A-1** | DQ Rule Catalog & Policy 문서 | [본 단계 문서](./THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md) · threshold·severity (엔진 미구현) |
| **R12-A-2** | Target Profiling Read-only API PoC | [Plan R12-A-2-0](./THERMOps_R12-A-2_Target_Profiling_Readonly_API_PoC_Plan.md) · API 구현은 별도 승인 |
| R12-A-3 | DQ Summary Response Contract | |
| R12-A-4 | Run Detail DQ Summary UI PoC | |
| R12-A-5 | Handoff Readiness Status PoC | |
| R12-A-6 | Persisted DQ Result 검토 | migration 여부 포함 |
| R12-A-7 | Optional Blocking Policy Design | |
| R12-A-8 | Optional `VP_DATA_QUALITY` Node Activation Review | **가장 후순위 · 별도 승인** |

R12-A-2 이후는 **별도 승인** 없이 착수하지 않는다.

---

## 15. 수용 기준 (문서·후속 구현 공통)

문서(R12-A-0) 수용:
- MVP 원칙 · non-blocking/read-only · B7 연결 · Rule/Profiling/Result · UI 위치 · Phase · Backlog 분할이 문서화됨
- 구현·착수 확정이 아님을 명시

후속 구현(승인 후) 수용 후보:
- Phase B/C가 non-blocking · read-only 유지
- Run을 DQ로 막지 않음
- Feature/Train/Predict / Notification / node 활성화를 끌어오지 않음

---

## 16. 검증 전략

| 단계 | 검증 |
|------|------|
| R12-A-0 (지금) | docs · README 링크 · check-pages 정적 assert · package empty · studio/ops/e2e 회귀 |
| R12-A-2+ | read-only API smoke · contract fixture |
| R12-A-4+ | Run Detail summary UI smoke |
| R12-A-5+ | handoff recommendation 표시 (자동 승인 아님) 검사 |

본 문서 작업에서는 API/UI smoke 대상 기능이 없다.

---

## 17. Known Limitations

- 본 문서는 **설계 초안**이며 DQ Gate / profiling / result / UI를 **구현하지 않는다.**
- **최종 구현 범위와 착수 여부는 별도 승인**이 필요하다.
- `VP_DATA_QUALITY`는 여전히 DISABLED roadmap 후보이다.
- Handoff recommendation은 **자동 승인이 아니다.**
- full scan · async · blocking · 영속화는 미정.
- ML 학습·예측 실행 경로 · Feature Store는 범위 밖이다.
- 열수요 규칙은 **예시**일 뿐 제품 전용이 아니다.

---

## 18. 변경하지 않는 것

- THERMOps 제품명 · route / API / component ID
- DB migration · backend API · worker
- FE 본기능 · registry / palette · `VP_DATA_QUALITY` 상태
- Run blocking · DQ engine · profiling API · result 테이블
- Feature / Training / Prediction · Notification 본구현
- package / requirements

---

## 19. 다음 의사결정 질문

1. R12-A-1(Rule Catalog & Policy)을 다음 문서로 승인할 것인가?  
2. Phase B profiling을 **동기 LIMIT**로 시작할지, async를 검토할지?  
3. DQ Summary를 **Run Detail 우선**으로 둘 것인가?  
4. 영속화(A-6) 없이 read-only 응답만으로 PoC할지?  
5. blocking(A-7)을 당분간 검토 대상에서 제외할지?  
6. `VP_DATA_QUALITY` node(A-8)를 언제 재검토할지?

---

## 20. 용어

| 용어 | 의미 |
|------|------|
| DQ Gate | Data Load 산출물 품질 확인·Handoff 보조 (자동 ML 아님) |
| non-blocking | DQ 결과가 Run/Compile을 막지 않음 |
| read-only summary | 조회·표시 중심 품질 요약 |
| handoff_recommendation | READY / REVIEW_REQUIRED / NOT_READY — **판단 보조** |
| `VP_DATA_QUALITY` | DISABLED roadmap component · 활성화는 Phase G |
| R12-A-0 | 본 Scope / Design Draft |

---

## 21. 관련 문서

- [THERMOps_R12-A-2_Target_Profiling_Readonly_API_PoC_Plan.md](./THERMOps_R12-A-2_Target_Profiling_Readonly_API_PoC_Plan.md) — R12-A-2-0 Profiling API PoC Plan (API 구현 문서 아님)
- [THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md](./THERMOps_R12-A-1_DQ_Rule_Catalog_Policy.md) — R12-A-1 Rule Catalog & Policy (구현 착수 문서 아님)
- [THERMOps_R12_Candidate_Prioritization_Draft.md](./THERMOps_R12_Candidate_Prioritization_Draft.md)
- [THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)
- [THERMOps_R11-S8-9-27_Product_Branding_Generalization.md](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md)
- [THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)
- [THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) — 대표 예시
