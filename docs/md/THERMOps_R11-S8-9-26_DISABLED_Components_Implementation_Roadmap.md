# THERMOps R11-S8-9-26 DISABLED Components Implementation Roadmap

> **문서 성격:** 본 문서는 Visual Pipeline Studio의 DISABLED 또는 후순위 컴포넌트에 대한 **본구현 판단 기준**과 **후속 roadmap**을 정의한다.  
> 본 문서는 **구현 문서가 아니라 기획·설계 roadmap**이며, 이번 작업에서 DISABLED 컴포넌트를 **활성화하거나 신규 node를 구현하지 않는다.**

| 항목 | 값 |
|------|-----|
| Backlog | B22 |
| 단계 ID | R11-S8-9-26 |
| Catalog SoT | `backend/app/services/visual_pipeline/component_catalog_service.py` (code-based, no DB) |
| 관련 | R11-S8-9 Backlog, B7 Handoff Guide |

---

## 1. 목적

- Studio Palette에 보이는 DISABLED(“Coming later”) 컴포넌트가 **왜 비활성인지**, **언제·어떤 조건으로 본구현할지** 기준을 제공한다.
- R11 MVP(ACTIVE)와 후속 범위(DISABLED / 미등록 후보)를 구분한다.
- 활성화·구현을 단정하지 않고, **후속 후보 roadmap**으로만 정리한다.

---

## 2. 현재 R11 Visual Pipeline MVP 범위

R11 Data Load MVP는 다음 ACTIVE 컴포넌트와 Studio/Ops UX로 구성된다.

```text
VP_REST_API_SOURCE → VP_TRANSFORM → VP_UPSERT_LOAD
                         ↑
              VP_CRON_SCHEDULE (optional trigger)
```

- Compile / 실행 설정 반영 / Manual·Scheduled Run / Run History · Ops 가시성
- Starter Template · Domain Preset · Schema/Key · Preview 등 FE 보조 UX
- **DISABLED 8종은 canvas에 추가되지 않으며 compile/run 대상이 아니다.**

---

## 3. 현재 Component 상태 요약

| 출처 | ACTIVE | DISABLED | EXPERIMENTAL |
|------|--------|----------|--------------|
| `ACTIVE_COMPONENT_TYPES` / `DISABLED_COMPONENT_TYPES` | 4 | 8 | (catalog 미사용) |
| Studio Palette | 클릭으로 Canvas 추가 | “Coming later”, 클릭 불가 | — |
| FE config form registry | 4종 form | 없음 | — |

확인 경로:

| 계층 | 파일/동작 |
|------|-----------|
| Backend catalog | `component_catalog_service.py` |
| API | `getComponentCatalog()` |
| Studio | ACTIVE만 `onAdd`; DISABLED는 표시만 |
| Palette UI | `VpComponentPalette.tsx` |

---

## 4. Component 분류 기준

| 분류 | 정의 |
|------|------|
| **MVP 유지** | 현재 `status=ACTIVE`, Data Load smoke/E2E 대상 |
| **후속 구현 후보** | catalog에 `DISABLED`로 존재하며 product value는 있으나 R11 범위 밖 |
| **검토 보류** | DISABLED이지만 복잡도·사용빈도·운영 리스크가 불명확해 우선순위를 낮춘 항목 |
| **숨김/폐기 후보** | 문서상 검토만 — 이번 작업에서 palette 숨김/삭제를 **하지 않음** |
| **Roadmap 후보 (미등록)** | 코드 catalog에 **없는** 개념 노드 — “현재 DISABLED”로 단정하지 않음 |

---

## 5. MVP 유지 Component

| Component ID | 표시명(대표) | category | 비고 |
|--------------|--------------|----------|------|
| `VP_REST_API_SOURCE` | REST API Source | DATA_INPUT | Data Source / credential |
| `VP_TRANSFORM` | Transform | TRANSFORM | 예: WIDE_HOUR_TO_LONG |
| `VP_UPSERT_LOAD` | Upsert Load | LOAD | SDS / target / conflict keys |
| `VP_CRON_SCHEDULE` | CRON Schedule | TRIGGER | Schedule activation |

FE Inspector config form은 위 4종만 제공한다.

---

## 6. DISABLED / 후순위 Component 분류

아래는 **코드에서 확인된** `DISABLED_COMPONENT_TYPES`이다.  
`disabled_reason` / description은 catalog 정의를 인용한다.

| Component ID | 표시명 | category | 현재 상태 | 문서 분류 | 본구현 필요성 | 선행 의존성(요약) | 우선순위 | 후속 단계 | 비고 |
|--------------|--------|----------|-----------|-----------|---------------|-------------------|----------|-----------|------|
| `VP_DATA_QUALITY` | Data Quality Check | QUALITY | DISABLED | 후속 구현 후보 | 높음 (handoff gate) | rule model, profiling, Ops | P1 | R12-A | reason: Connector load 경로와 직접 연동 범위가 S1에 없음 |
| `VP_FEATURE_BUILD` | Feature Build | FEATURE | DISABLED | 후속 구현 후보 | 높음 (ML 입력) | handoff contract, feature meta | P1 | R12-B | reason: 2차 MVP |
| `VP_MODEL_TRAINING` | Model Training | MODEL | DISABLED | 후속 구현 후보 | 높음 | Feature dataset, runner, registry | P2 | R12-C | reason: 2차 MVP |
| `VP_BATCH_PREDICTION` | Batch Prediction | PREDICTION | DISABLED | 후속 구현 후보 | 높음 | model artifact, result table | P2 | R12-D | reason: 2차 MVP |
| `VP_NOTIFICATION` | Notification | OPERATION | DISABLED | 후속 구현 후보 | 중 (운영 알림) | persistence, routing, channels | P3 | R12-E | S8-7 Ops badge/PoC와 **구분**; reason: Alert Rule 연결은 R11-S6 이후 검토 |
| `VP_FORECAST_PROVIDER` | Forecast Provider | DATA_INPUT | DISABLED | 검토 보류 | 중·불명 | R10 on-demand와 축 정리 | P4 | R12-D 연계 검토 | reason: R10-S5 on-demand forecast와 별도 축 |
| `VP_DB_SOURCE` | DB Source | DATA_INPUT | DISABLED | 검토 보류 | 중 | connection, schema, security | P4 | R13 | reason: 1차 MVP 제외 |
| `VP_CSV_SOURCE` | CSV Upload | DATA_INPUT | DISABLED | 검토 보류 | 중 | upload storage, schema infer | P4 | R13 | reason: 1차 MVP 제외 |

### 6.1 Roadmap 후보 Component (코드에 없음)

다음 항목은 catalog에 **존재하지 않는다.** “현재 DISABLED”가 아니라 **검토 후보**이다.

| 후보 개념 | 분류 | 후속 단계 | 비고 |
|-----------|------|-----------|------|
| Multi-source Join | Advanced Flow | R13 | multi REST/DB merge |
| Branch / Conditional | Advanced Flow | R13 | 분기·조건 실행 |
| Advanced Transform variants | Transform | R13 | 신규 transform_type / 노드 분리 여부 미정 |
| Serving / Model Registry node | MODEL | R13 | 기존 Model Registry 화면과 역할 중복 검토 |
| Lineage / Monitoring node | OPERATION | R13 | Run lineage · forecast monitor |
| Admin roadmap preview mode | UX | R13 | DISABLED 미리보기 전용 모드 (미구현) |

---

## 7. 본구현 우선순위 기준

본구현 착수·우선순위는 아래를 **종합**해 판단한다 (단정 일정 아님).

1. 사용자 업무 흐름 기여도 (Data Load → ML)
2. [B7 Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)와의 연결성
3. 선행 데이터 모델 / DB / API 필요 여부
4. 실행·운영 리스크 (blocking DQ, 잘못된 학습 등)
5. 검증 가능성 (smoke / E2E)
6. UI·Inspector 복잡도
7. 범용 MLOps 적합성 (도메인 하드코딩 지양)
8. 열수요 예측 **예시** 적용성

권장 순서(후보): **DQ → Feature → Training → Prediction → Notification → (DB/CSV/Forecast Provider 검토)**

---

## 8. 컴포넌트별 선행 의존성

모두 **roadmap 후보**이며 본 문서 작업에서 구현하지 않는다.

### `VP_DATA_QUALITY`

- rule definition model
- target / transform profiling
- blocking vs non-blocking policy
- issue/result schema
- Ops·Run Detail 연계 UI

### `VP_FEATURE_BUILD`

- B7 handoff contract (SDS / Target / keys)
- feature definition metadata
- training window / time split
- output feature dataset 관리

### `VP_MODEL_TRAINING`

- Feature dataset builder
- training job runner
- MLflow / model registry
- evaluation metric storage
- CPU/GPU execution policy

### `VP_BATCH_PREDICTION`

- trained model artifact
- prediction input contract
- forecast/prediction result table
- monitoring UI (후속)

### `VP_NOTIFICATION`

- notification persistence table
- read/unread (또는 동등) state — **현재 Ops badge PoC와 별개**
- user/role routing
- external channel policy  
- Visual Pipeline graph 노드 vs Ops 알림 제품 경계 정리

### `VP_FORECAST_PROVIDER` / `VP_DB_SOURCE` / `VP_CSV_SOURCE`

- 보안·커넥터·스키마 추론·기존 R10/데이터 소스 UX와의 중복 여부 검토 후 착수

---

## 9. 컴포넌트별 Roadmap 표 (단계)

> **확정 일정이 아니라 후속 후보**이다.

| 단계 | 목적 | 대상 Component | 선행 조건 | 산출물(후보) | 구현 판단 기준 |
|------|------|----------------|-----------|--------------|----------------|
| R12-A | Data Quality Gate & Handoff hardening | `VP_DATA_QUALITY` | Target Preview·키 검증 안정 | DQ node + rule/result | handoff 전 자동/반자동 gate 필요성 |
| R12-B | Feature Dataset Builder | `VP_FEATURE_BUILD` | R12-A 또는 수동 DQ 수용 | Feature dataset | ML 입력 스키마 제품화 |
| R12-C | ML Training Workflow | `VP_MODEL_TRAINING` | R12-B | Training job · metrics | 학습 오케스트레이션 요구 |
| R12-D | Forecast / Prediction | `VP_BATCH_PREDICTION` (+ `VP_FORECAST_PROVIDER` 검토) | R12-C | Prediction run · result | 예측 실행 제품화 |
| R12-E | Notification 본구현 | `VP_NOTIFICATION` | S8-7 설계·Ops 경계 합의 | Graph/Ops 알림 | 채널·영속화 필요성 |
| R13 | Multi-source / Advanced / Lineage | DB/CSV + 미등록 후보 | R12 경험 | Join/Branch/Lineage | 사용빈도·복잡도 |

---

## 10. Studio UX 처리 원칙

- MVP에서 쓰지 않는 컴포넌트를 **무리하게 ACTIVE처럼** 노출하지 않는다.
- DISABLED를 노출할 경우 “Coming later”와 catalog `disabled_reason`을 유지한다.
- 실사용 가능(ACTIVE)과 roadmap(DISABLED)을 UI에서 혼동시키지 않는다.
- **활성화 전에는 compile/run/materialize 대상에 포함하지 않는다.**
- 향후 Admin/Dev 전용 roadmap preview를 둘 수 있으나 **미구현**.
- 이번 B22 작업에서 palette 숨김·status 변경을 **하지 않는다.**

---

## 11. Data Load → ML Workflow 관계

- [B7 Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md): Data Load 산출물이 ML로 넘어가기 전 **gate·체크리스트**를 정의한다.
- **본 문서(B22):** 그 **이후** Feature / DQ / Training / Forecast / Notification **노드 본구현 순서**를 정의한다.
- B7만으로 ML Workflow가 구현된 것이 아니며, B22 roadmap도 **활성화 완료를 의미하지 않는다.**

```text
[R11 ACTIVE Data Load] → [B7 Handoff Gate] -.-> [R12-A DQ] → [R12-B Feature] → [R12-C Train] → [R12-D Predict]
                                                      (DISABLED 본구현 후보 · 미구현)
```

---

## 12. THERMOps 열수요 예측 예시

> **예시**이다. 구현 완료·특정 기관 전용이 아니다.

1. **R11:** REST → WIDE_HOUR_TO_LONG → Upsert로 표준 Target 적재  
2. **R12-A (후보):** Data Quality로 결측·중복·시간축 확인  
3. **R12-B (후보):** Feature Build로 시간/기상/운영 feature 구성  
4. **R12-C (후보):** Model Training으로 학습·평가  
5. **R12-D (후보):** Batch Prediction으로 예측 실행·결과 저장  

---

## 13. R12/R13 후속 후보 요약

| ID | 요약 |
|----|------|
| R12-A | `VP_DATA_QUALITY` |
| R12-B | `VP_FEATURE_BUILD` |
| R12-C | `VP_MODEL_TRAINING` |
| R12-D | `VP_BATCH_PREDICTION` (+ Forecast Provider 검토) |
| R12-E | `VP_NOTIFICATION` |
| R13 | `VP_DB_SOURCE` / `VP_CSV_SOURCE` + Join/Branch/Lineage 등 미등록 후보 |

B7 문서의 R12-1~7 후보와 정합하되, **본 문서는 Visual Pipeline component ID 기준**으로 재정렬한다.

---

## 14. Known Limitations

- roadmap 문서이며 **DISABLED 활성화·신규 node 구현이 아니다.**
- catalog/palette/backend status를 변경하지 않았다.
- 미등록 후보를 “현재 DISABLED”로 단정하지 않는다.
- R12/R13은 **확정 일정이 아니다.**
- Ops Action Badge(B5) ≠ `VP_NOTIFICATION` 본구현.
- 자동 학습·즉시 예측을 실행한다고 약속하지 않는다.

---

## 15. 용어

| 용어 | 설명 |
|------|------|
| ACTIVE | catalog `status=ACTIVE`, Palette에서 Canvas 추가 가능 |
| DISABLED | catalog `status=DISABLED`, “Coming later”, 추가 불가 |
| Component catalog | R11-S1 code-based 계약 (`component_catalog_service`) |
| Coming later | Palette DISABLED 배지 문구 |
| Handoff | B7: Data Load → ML 인수 기준 |
| R12/R13 | 후속 구현 **후보** 단계 라벨 |

---

## 관련 문서

- [THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-7_Notification_설계.md](./THERMOps_R11-S8-7_Notification_설계.md)
- [THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md](./THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md)
