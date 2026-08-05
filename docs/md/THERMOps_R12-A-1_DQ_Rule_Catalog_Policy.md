# THERMOps R12-A-1 DQ Rule Catalog & Policy

> **문서 성격:** 본 문서는 R12-A Data Quality Gate의 **DQ Rule Catalog와 Policy**를 정의하는 문서이다.  
> 본 문서는 **구현 착수 문서가 아니며**, Rule engine 실행 · Run 차단 · `VP_DATA_QUALITY` node 활성화 · API/DB/UI/worker를 변경하지 않는다.  
> **최종 구현 범위와 착수 여부는 별도 승인 후 확정**한다.

| 항목 | 값 |
|------|-----|
| 문서 ID | R12-A-1 |
| 상위 | [R12-A-0 Scope Design Draft](./THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md) |
| 기준 | R12 Candidate Prioritization · B7 Handoff · B22 Roadmap · B23 Branding |
| 기준 커밋(상위 문서) | `36fe102` (R12-A-0) |

---

## 1. 목적

- DQ-001~DQ-010 **전체 rule catalog**를 정의한다.
- **MVP rule set**과 **후속 rule set**을 구분한다.
- Severity · Rule Status · Threshold · Handoff Recommendation **정책**을 정의한다.
- Threshold 수치는 **확정값이 아니라 후보**로만 표현한다.
- DQ 결과는 Handoff **판단 보조**이며, 자동 승인·자동 차단이 아님을 명시한다.
- Rule engine / profiling API / UI / Run blocking은 **범위 밖**이다.

---

## 2. 기준 문서

| 문서 | 역할 |
|------|------|
| [R12-A-0 Scope Design](./THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md) | MVP 원칙 · Phase · Result Model 초안 · Catalog 후보 표 |
| [R12 Prioritization](./THERMOps_R12_Candidate_Prioritization_Draft.md) | R12-A 1순위 후보 · non-blocking 권고 |
| [B7 Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md) | Handoff checklist · Preview≠전수 보증 |
| [B22 DISABLED Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md) | `VP_DATA_QUALITY` = roadmap · 미활성 |
| [B23 Branding](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md) | 범용 Data Load · 열수요=예시 |

---

## 3. Policy 기본 원칙

1. **Catalog ≠ Engine:** 본 문서는 rule 정의·정책만 담는다. 평가 실행기는 후속(R12-A-2+)·별도 승인.
2. **Non-blocking:** 첫 MVP(Phase A~C)에서 Run/Compile을 DQ로 막지 않는다.
3. **Read-only summary:** 결과는 운영자 판단 보조다.
4. **Handoff 보조:** `handoff_recommendation`은 자동 승인·자동 ML 진입이 아니다.
5. **Threshold는 후보:** 수치·단위는 도메인·테넌트별로 조정 가능한 **후보**이며 제품 고정값이 아니다.
6. **Domain Preset ≠ SoT:** Heat Demand preset / 열수요 예시는 hint·예시일 뿐 backend source of truth가 아니다.
7. **`VP_DATA_QUALITY` 활성화는 별도 단계** (R12-A-8 · Phase G).
8. Feature / Training / Prediction / Notification 본구현과 분리한다.

---

## 4. Severity Policy

| Severity | 의미 | 운영자 기대 | MVP에서 Run 영향 |
|----------|------|-------------|------------------|
| `INFO` | 참고·후보 신호 | 기록·추후 검토 | 없음 |
| `WARN` | 품질 리스크 | REVIEW 권고 | 없음 (non-blocking) |
| `ERROR` | 품질 기준 위반 후보 | 수정·재적재 검토 | 없음 (non-blocking) |

- Rule의 **기본 Severity**는 catalog에 정의한다.
- 평가 시 metric이 threshold를 넘으면 rule **status**가 WARN/FAIL로 올라갈 수 있다 (엔진은 후속).
- Severity를 이유로 **지금 단계에서 Run을 차단하지 않는다.**

---

## 5. Rule Status Policy

`DqRuleResult.status` 후보 (R12-A-0 Result Model과 정합):

| Status | 의미 |
|--------|------|
| `PASS` | 측정값이 후보 threshold 이내 (또는 조건 충족) |
| `WARN` | 경고 구간 · 운영자 검토 권고 |
| `FAIL` | 실패 구간 · Handoff 보류 권고 (자동 차단 아님) |
| `SKIPPED` | 입력 부족·해당 없음·미구현 rule 등 |

집계 → `DqRunSummary.overall_status`:

| overall_status | 조건(정책 후보) |
|----------------|-----------------|
| `NOT_EVALUATED` | 평가 미실행 |
| `PASS` | FAIL 없음 · WARN 없음 (또는 WARN을 허용하는 정책 선택 시) |
| `WARN` | FAIL 없음 · WARN ≥ 1 |
| `FAIL` | FAIL ≥ 1 |

MVP 기본 제안: **FAIL이 하나라도 있으면 overall=FAIL**, 아니면 WARN이 있으면 WARN, 아니면 PASS.  
`SKIPPED`만 있는 경우는 `NOT_EVALUATED` 또는 `WARN`으로 둘지 **후속 계약(R12-A-3)** 에서 확정.

---

## 6. Handoff Recommendation Policy

| handoff_recommendation | 의미 | 자동 동작 |
|------------------------|------|-----------|
| `READY` | B7 checklist + DQ overall이 양호해 **넘길 수 있음** | 없음 · 자동 Feature/Train 진입 없음 |
| `REVIEW_REQUIRED` | WARN 또는 조건부 항목 · **사람 검토 필요** | Run 미차단 |
| `NOT_READY` | FAIL 또는 B7 필수 미충족 후보 | Run 미차단 · ML 자동 시작 없음 |

권장 매핑(초안 · 확정 아님):

| overall_status | handoff_recommendation 후보 |
|----------------|------------------------------|
| `NOT_EVALUATED` | `REVIEW_REQUIRED` (미평가이므로 검토) |
| `PASS` | `READY` (단, B7 checklist도 충족해야 실질 handoff) |
| `WARN` | `REVIEW_REQUIRED` |
| `FAIL` | `NOT_READY` |

- DQ만으로 handoff를 **자동 승인하지 않는다.**
- B7 checklist(graph saved, validation, compile IN_SYNC, materialization, run SUCCESS, preview, schema/key, conflict key, PARTIAL 등)와 **AND**로 판단한다.
- Domain Preset 선택만으로 READY가 되지 않는다.

---

## 7. Threshold Policy

| 원칙 | 설명 |
|------|------|
| 후보다 | 아래 수치는 **예시·후보**이며 제품 기본값으로 확정하지 않는다 |
| 분리 | Threshold 저장 UI/API는 본 문서 범위 밖 (후속 승인) |
| 단위 | 비율(0~1 또는 %), 건수, 시간(분/시간), 절대값 등 rule별 명시 |
| 도메인 | 열수요 예시는 컬럼명·키 조합만 예시로 제시 |
| 미설정 | threshold 미정이면 rule은 `SKIPPED` 또는 INFO로 둘 수 있음 (후속 계약) |

Blocking 가능성 필드 (`NONE` / `LATER` / `POSSIBLE`)는 **미래 Phase F 검토용**이다.  
**현재 MVP에서는 모두 실질 Blocking = 적용하지 않음.**

---

## 8. MVP Rule Set vs 후속 Rule Set

| Set | Rule IDs | 목적 |
|-----|----------|------|
| **MVP** | DQ-001, DQ-002, DQ-003, DQ-004, DQ-006, DQ-007 | Handoff 직전 최소 품질 요약 |
| **후속** | DQ-005, DQ-008, DQ-009, DQ-010 | 범위·타입·이상치·시계열 gap 심화 |

MVP set만으로도 B7의 “Preview만으로는 부족”한 부분을 **문서상** 보강한다.  
실행·UI는 R12-A-2~A-5 **별도 승인** 후.

---

## 9. Full Rule Catalog (DQ-001 ~ DQ-010)

공통 컬럼: Rule ID · 구분 · Rule · 목적 · 기본 Severity · 적용 대상 · Blocking 가능성 · MVP · Threshold 후보 · Heat Demand 예시(선택)

### 9.1 DQ-001 Required Column Presence

| 항목 | 내용 |
|------|------|
| 구분 | Schema |
| 목적 | 필수 컬럼이 Target/SDS에 존재하는가 |
| 기본 Severity | ERROR |
| 적용 대상 | Target columns / SDS column defs / expected list |
| Blocking 가능성 | LATER |
| MVP | **Y** |
| Threshold 후보 | 필수 컬럼 목록 길이 ≥ 1; 누락 건수 = 0 → PASS |
| Metric 후보 | `missing_required_columns` (list/count) |
| Heat Demand 예시 | `entity_id`, `measured_at`, `heat_demand` 존재 여부 (예시) |

### 9.2 DQ-002 Null Ratio Check

| 항목 | 내용 |
|------|------|
| 구분 | Completeness |
| 목적 | 핵심 컬럼 null 비율이 과도하지 않은가 |
| 기본 Severity | WARN |
| 적용 대상 | 키·측정값 컬럼 |
| Blocking 가능성 | LATER |
| MVP | **Y** |
| Threshold 후보 | null_ratio ≤ **0.05**(키) / ≤ **0.10**(측정값) — **후보** |
| Metric 후보 | `null_ratio` by column |
| Heat Demand 예시 | `heat_demand` null_ratio |

### 9.3 DQ-003 Duplicate Key Check

| 항목 | 내용 |
|------|------|
| 구분 | Uniqueness |
| 목적 | conflict key 기준 중복 적재 후보 탐지 |
| 기본 Severity | ERROR |
| 적용 대상 | `conflict_key_columns_json` 집합 |
| Blocking 가능성 | POSSIBLE (Phase F 이후 검토) |
| MVP | **Y** |
| Threshold 후보 | `duplicate_key_count` = **0** → PASS; \>0 → FAIL 후보 |
| Metric 후보 | `duplicate_key_count` |
| Heat Demand 예시 | (`entity_id`, `measured_at`) 중복 |

### 9.4 DQ-004 Timestamp Range / Freshness Check

| 항목 | 내용 |
|------|------|
| 구분 | Freshness |
| 목적 | 시간 컬럼 존재·범위·최신성 |
| 기본 Severity | WARN |
| 적용 대상 | timestamp / measured_at 후보 컬럼 |
| Blocking 가능성 | LATER |
| MVP | **Y** |
| Threshold 후보 | `freshness_lag` ≤ **24h** 또는 ≤ **7d** (운영 주기별 **후보**) |
| Metric 후보 | `min_ts`, `max_ts`, `freshness_lag` |
| Heat Demand 예시 | `measured_at` 최댓값 vs 현재 |

### 9.5 DQ-005 Numeric Range Check

| 항목 | 내용 |
|------|------|
| 구분 | Validity |
| 목적 | 수치 측정값이 허용 범위인가 |
| 기본 Severity | WARN |
| 적용 대상 | numeric 측정 컬럼 |
| Blocking 가능성 | LATER |
| MVP | **N (후속)** |
| Threshold 후보 | min/max per column — 도메인별 **미확정 후보** (예: heat_demand ≥ 0) |
| Metric 후보 | `out_of_range_count`, `min`, `max` |

### 9.6 DQ-006 Row Count Minimum / Delta Check

| 항목 | 내용 |
|------|------|
| 구분 | Volume |
| 목적 | 최소 적재 건수·이전 대비 급변 |
| 기본 Severity | WARN |
| 적용 대상 | table / 최근 파티션 후보 |
| Blocking 가능성 | LATER |
| MVP | **Y** |
| Threshold 후보 | `row_count` ≥ **1** (smoke) 또는 운영 최소 N; delta \|Δ\| ≤ **50%** — **후보** |
| Metric 후보 | `row_count`, `row_count_delta_ratio` |

### 9.7 DQ-007 Schema Drift Check

| 항목 | 내용 |
|------|------|
| 구분 | Schema |
| 목적 | 기대 스키마(Transform/SDS) 대비 컬럼 추가·삭제·이름 변화 |
| 기본 Severity | WARN |
| 적용 대상 | expected columns vs actual |
| Blocking 가능성 | LATER |
| MVP | **Y** |
| Threshold 후보 | added/removed column count = **0** → PASS; \>0 → WARN/FAIL 후보 |
| Metric 후보 | `added_columns`, `removed_columns` |
| 비고 | B15 column match / B21 proposal과 **보완 관계** (자동 확정 아님) |

### 9.8 DQ-008 Type Compatibility Check

| 항목 | 내용 |
|------|------|
| 구분 | Type |
| 목적 | 기대 타입과 실제 타입 정합 |
| 기본 Severity | WARN |
| 적용 대상 | column type metadata |
| Blocking 가능성 | LATER |
| MVP | **N (후속)** |
| Threshold 후보 | incompatible type count = 0 |
| Metric 후보 | `type_mismatch_columns` |

### 9.9 DQ-009 Outlier Candidate Check

| 항목 | 내용 |
|------|------|
| 구분 | Outlier |
| 목적 | 통계적 이상치 **후보** 표기 (단정 아님) |
| 기본 Severity | INFO |
| 적용 대상 | numeric |
| Blocking 가능성 | NONE |
| MVP | **N (후속)** |
| Threshold 후보 | IQR·z-score 등 — **미확정 후보** |
| Metric 후보 | `outlier_candidate_count` |

### 9.10 DQ-010 Time Series Gap Check

| 항목 | 내용 |
|------|------|
| 구분 | Series |
| 목적 | entity×time 격자 공백 |
| 기본 Severity | WARN |
| 적용 대상 | 시계열 키 + timestamp |
| Blocking 가능성 | LATER |
| MVP | **N (후속)** |
| Threshold 후보 | gap 허용 길이(예: 1h) — **후보** |
| Metric 후보 | `gap_count`, `max_gap` |
| Heat Demand 예시 | 시간대별 수요 공백 (예시) |

---

## 10. Catalog Summary Table

| Rule ID | Rule | Severity | MVP | Blocking* | Threshold 성격 |
|---------|------|----------|-----|-----------|----------------|
| DQ-001 | Required Column Presence | ERROR | Y | LATER | 필수 컬럼 목록 |
| DQ-002 | Null Ratio Check | WARN | Y | LATER | 비율 후보 |
| DQ-003 | Duplicate Key Check | ERROR | Y | POSSIBLE | 중복 건수=0 후보 |
| DQ-004 | Timestamp / Freshness | WARN | Y | LATER | lag 시간 후보 |
| DQ-005 | Numeric Range | WARN | N | LATER | min/max 후보 |
| DQ-006 | Row Count Min / Delta | WARN | Y | LATER | 건수·delta 후보 |
| DQ-007 | Schema Drift | WARN | Y | LATER | add/remove=0 후보 |
| DQ-008 | Type Compatibility | WARN | N | LATER | mismatch=0 |
| DQ-009 | Outlier Candidate | INFO | N | NONE | 통계 후보 |
| DQ-010 | Time Series Gap | WARN | N | LATER | gap 허용 후보 |

\*Blocking 가능성 라벨일 뿐, **MVP에서 Run 차단을 적용하지 않는다.**

---

## 11. B7 Handoff Checklist 매핑

| B7 / R11 확인 | 보완 Rule | 비고 |
|---------------|-----------|------|
| Target Preview sample | DQ-006, profiling row_count | Preview≠전수 |
| Schema / Key Helper | DQ-001, DQ-007 | 자동 확정 아님 |
| Conflict keys | DQ-003 | |
| Run SUCCESS | (전제) | DQ는 이후 단계 |
| PARTIAL | DQ-003, DQ-006 주의 | B8과 병행 검토 |
| Domain Preset | — | hint만 · SoT 아님 |

---

## 12. 열수요(Heat Demand) 예시 — 대표 예시만

THERMOps / Visual Pipeline을 열수요 **전용**으로 설명하지 않는다.

| 예시 확인 | Rule |
|-----------|------|
| `entity_id`, `measured_at`, `heat_demand` 존재 | DQ-001 |
| `heat_demand` null 비율 | DQ-002 |
| (`entity_id`,`measured_at`) 중복 | DQ-003 |
| `measured_at` freshness | DQ-004 |
| 수요량 ≥ 0 (후보) | DQ-005 (후속) |
| 최소 row | DQ-006 |
| SDS 대비 컬럼 drift | DQ-007 |
| 시간대 gap | DQ-010 (후속) |

Heat Demand Domain Preset은 **FE hint**이며 catalog threshold의 SoT가 아니다.

---

## 13. 구현·저장과의 경계

| 항목 | 본 문서 | 후속 |
|------|---------|------|
| Rule ID/정책 정의 | ✅ | — |
| Threshold 후보 문서화 | ✅ | 테넌트별 확정은 별도 |
| Rule engine 실행 | ❌ | R12-A-2+ |
| Profiling API | ❌ | R12-A-2 |
| Summary UI | ❌ | R12-A-4 |
| Threshold DB 저장 | ❌ | 별도 승인 |
| Run blocking | ❌ | R12-A-7 / Phase F |
| `VP_DATA_QUALITY` ACTIVE | ❌ | R12-A-8 / Phase G |

---

## 14. 수용 기준 (문서)

- DQ-001~DQ-010 정의됨
- MVP vs 후속 구분됨
- Severity / Status / Threshold / Handoff Recommendation 정책이 문서화됨
- Threshold는 후보임을 명시
- 구현 착수 문서가 아님 · 별도 승인 명시
- non-blocking · node 활성화 별도 단계 명시
- 열수요는 예시 · Preset≠SoT

---

## 15. Known Limitations

- Rule engine·평가 실행·threshold 저장·UI·blocking·node 활성화는 **없다**.
- Threshold 수치는 **미확정 후보**다.
- overall/handoff 매핑은 초안이며 R12-A-3/A-5에서 조정 가능.
- 대용량 full scan 비용·sampling은 R12-A-2에서 검토.
- 본 문서만으로 DQ Gate가 제품화된 것이 아니다.

---

## 16. 변경하지 않는 것

- backend API / DB / worker / FE 본기능
- component registry / palette / `VP_DATA_QUALITY` status
- package / route / component ID
- Feature / Training / Prediction / Notification 본구현

---

## 17. 다음 의사결정 질문

1. MVP rule set(001/002/003/004/006/007) threshold 후보를 어떤 운영 주기(일/시간) 기준으로 조정할 것인가?
2. overall=PASS일 때 WARN 0건을 필수할 것인가, WARN 허용 READY를 둘 것인가?
3. R12-A-2 Profiling Read-only API PoC를 다음으로 승인할 것인가?
4. DQ-003의 Blocking 가능성(POSSIBLE)을 Phase F에서 실제로 검토할 것인가?

---

## 18. 용어

| 용어 | 의미 |
|------|------|
| Rule Catalog | Rule ID·목적·severity 정의 집합 |
| Threshold 후보 | 문서상 예시 임계 · 제품 확정값 아님 |
| handoff_recommendation | Handoff 판단 **보조** 라벨 |
| MVP rule set | 첫 요약에 포함할 rule 부분집합 |
| Blocking 가능성 | 미래 정책 라벨 · 현재 미적용 |

---

## 19. 관련 문서

- [THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md](./THERMOps_R12-A_DQ_Gate_MVP_Scope_Design_Draft.md) — R12-A-0
- [THERMOps_R12_Candidate_Prioritization_Draft.md](./THERMOps_R12_Candidate_Prioritization_Draft.md)
- [THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)
- [THERMOps_R11-S8-9-27_Product_Branding_Generalization.md](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md)
- [THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) — 대표 예시
