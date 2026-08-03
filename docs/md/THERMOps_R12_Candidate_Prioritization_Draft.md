# THERMOps R12 Candidate Prioritization Draft

> **문서 성격:** 본 문서는 R11-S8-9 closeout 이후 R12/R13 후보의 **우선순위 판단을 돕기 위한 초안**이다.  
> 본 문서는 **구현 착수 문서가 아니며**, R12 범위·일정·순서를 **확정하지 않는다**.  
> **최종 우선순위는 사업·고객·일정 판단을 반영해 별도 승인**한다.

| 항목 | 값 |
|------|-----|
| 문서 ID | R12 Candidate Prioritization Draft |
| 기준 closeout | R11-S8-9-28 (`286a93d`) |
| 관련 | [B7 Handoff](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md), [B22 Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md), [B23 Branding](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md), [Closeout](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md) |

---

## 1. 목적

- R11-S8-9 closeout 이후 R12/R13 후보를 **한눈에 비교**한다.
- 후보별 필요성·의존성·난이도·위험·검증·사용자 가치·THERMOps 적용성을 정리한다.
- **추천 우선순위 초안**을 제시한다.
- 점수는 의사결정 **참고용**이며, **최종 판단은 사람이 한다**.
- 본 문서 작업에서 R12 기능을 **구현하지 않는다**.

---

## 2. 기준 문서

| 문서 | 역할 |
|------|------|
| [R11-S8-9-28 Closeout](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md) | S8-9 마감 · R12/R13 후속 후보 목록 |
| [R11-S8-9 Backlog](./THERMOps_R11-S8-9_Backlog.md) | B1~B27 done · open 없음 |
| [B7 Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md) | Data Load → ML **인수 기준** (실행 경로 아님) |
| [B22 DISABLED Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md) | DISABLED=roadmap · R12-A~E / R13 매핑 |
| [B23 Branding](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md) | THERMOps 유지 · VP=Data Load/Workflow · 열수요=예시 |
| [S8-7 Notification 설계](./THERMOps_R11-S8-7_Notification_설계.md) | R12-E 경계 (Ops badge PoC와 구분) |

참고: B7 가이드의 R12-1~7 번호는 구 라벨이다. **본 문서는 B22/Closeout의 R12-A~E·R13을 단일 기준**으로 쓴다.

---

## 3. R11-S8-9 closeout 요약

- Backlog **B1~B27 전부 done**, open 항목 없음.
- Studio Onboarding · Data Load 설정·검증 · Run/Ops · E2E · Docs/Productization이 정리됨.
- 사용자 흐름: Template → Preset → 설정 → 검증 → Compile → Run → Ops → **Handoff 판단**.
- ML 학습·예측 **실행 경로는 미구현** (B7: handoff 기준만).
- DISABLED components는 **활성화되지 않음** (B22: roadmap 후보).
- R12/R13은 closeout에서 **확정 일정이 아니라 후속 후보**로만 제시됨.
- 종료 기준 커밋: `286a93d`.

---

## 4. R12/R13 후보 목록

| ID | 후보 | 주요 DISABLED / 범위 |
|----|------|----------------------|
| R12-A | Data Quality Gate & Handoff Hardening | `VP_DATA_QUALITY` |
| R12-B | Feature Dataset Builder | `VP_FEATURE_BUILD` |
| R12-C | ML Training Workflow | `VP_MODEL_TRAINING` |
| R12-D | Forecast / Batch Prediction Workflow | `VP_BATCH_PREDICTION` (+ `VP_FORECAST_PROVIDER` 검토) |
| R12-E | Notification 본구현 | `VP_NOTIFICATION` (S8-7 Ops badge와 구분) |
| R13 | Multi-source / DB·CSV / Advanced Transform / Join / Branch / Lineage / Monitoring | `VP_DB_SOURCE`, `VP_CSV_SOURCE` + 미등록 후보 |

모두 **후속 후보**이며, 본 문서만으로 착수·일정을 단정하지 않는다.

---

## 5. 우선순위 평가 기준

각 항목 **1~5점**. **단순 합산**, **가중치 없음(초안)**.  
가중치는 추후 의사결정 시 별도 조정 가능하다. 점수는 Cursor 초안이며 **사람이 최종 조정**한다.

| # | 항목 | 설명 |
|---|------|------|
| 1 | 사용자 가치 | 운영자·사업 가치가 큰가 |
| 2 | B7 Handoff 연결성 | Data Load 인수 다음 단계와 직접 연결되는가 |
| 3 | 후속 ML Workflow 선행성 | Feature/Train/Predict 전에 필요한가 |
| 4 | 구현 난이도 역점수 | **쉬울수록 높음** |
| 5 | 운영 리스크 역점수 | **위험이 낮을수록 높음** |
| 6 | 검증 가능성 | smoke/E2E·docs로 검증하기 쉬운가 |
| 7 | 범용성 | 특정 도메인에 묶이지 않는가 (B23) |
| 8 | THERMOps 열수요 예시 적용성 | 대표 예시(열수요)로 설명·검증하기 쉬운가 |

**총점 = 8항목 합산 (최대 40).**

---

## 6. 후보별 상세 분석

### 6.1 R12-A Data Quality Gate & Handoff Hardening

| 항목 | 내용 |
|------|------|
| 목적 | 적재 Target이 ML 입력으로 넘길 수 있는 품질인지 **게이트·가시성**을 제공한다. |
| 사용자 가치 | “학습에 써도 되는 데이터인가”를 운영자가 판단·설명할 수 있다. |
| B7/B22/B23/Closeout | B7 handoff 다음 단계 · B22 P1/`VP_DATA_QUALITY` · Preview/Key/PARTIAL의 자연 확장 · 범용 DQ |
| 선행 의존성 | R11 Target Preview · Schema/Key · Conflict Key · Run SUCCESS 가시성 (이미 closeout) |
| 구현 범위 후보 | DQ rule catalog 설계 · profiling read-only · result model 초안 · blocking vs non-blocking 정책 · Studio/Run Detail 요약 |
| 제외 | 한 번에 전체 DQ engine · 즉시 blocking 실행 강제 · Feature/Train/Predict 본구현 · DISABLED 일괄 활성화 |
| 검증 후보 | docs/check-pages · read-only API smoke · Studio/Ops 요약 UI |
| 위험 | rule 과도 설계 · false positive로 Run 차단 · 물리 스키마 변경 범위 확대 |
| 최소 착수 단위 | §10.1 |
| 추천 순위(초안) | **1** |

### 6.2 R12-B Feature Dataset Builder

| 항목 | 내용 |
|------|------|
| 목적 | Target table → Feature dataset contract·메타·시간 분할 정책을 제품화한다. |
| 사용자 가치 | 학습 입력 스키마를 재현 가능하게 만든다. |
| 관계 | B7 ML 입력 조건 · B22 `VP_FEATURE_BUILD` · R12-A(또는 수동 DQ 수용) 권장 선행 |
| 선행 | Handoff 산출물 확정 · (권장) DQ 기준 |
| 범위 후보 | feature contract 문서 · mapping design · definition metadata · train window/split 정책 |
| 제외 | Feature Store 전체 · 자동 feature 폭발 · Training runner 본구현 |
| 검증 | contract/docs · mapping fixture · 열수요 예시 컬럼 |
| 위험 | 도메인 lock-in · SoT 없는 preset과 혼동 |
| 최소 착수 | §10.2 |
| 추천(초안) | **2** |

### 6.3 R12-C ML Training Workflow

| 항목 | 내용 |
|------|------|
| 목적 | Feature dataset 기반 학습·평가 오케스트레이션 경로를 정의·구현한다. |
| 사용자 가치 | THERMOps 학습 루프를 Visual Pipeline과 연결. |
| 관계 | B22 `VP_MODEL_TRAINING` · R12-B 선행 · MLflow/기존 모델 화면과 역할 정리 필요 |
| 선행 | R12-B · runner/CPU·GPU policy · registry 경계 |
| 범위 후보 | training job contract · MLflow 연계 검토 · runner 설계 · execution policy |
| 제외 | “학습이 이미 자동으로 돌아간다”는 UX · GPU 최적화 전면 · DISABLED 무분별 ACTIVE |
| 검증 | job contract · dry-run · metrics 저장 스모크 (Docker/MLflow 환경) |
| 위험 | 인프라 의존 · 기존 배치/학습 경로와 이중화 |
| 최소 착수 | §10.3 |
| 추천(초안) | **3** |

### 6.4 R12-D Forecast / Batch Prediction Workflow

| 항목 | 내용 |
|------|------|
| 목적 | 학습된 모델로 배치 예측·결과 저장·(선택) Forecast Provider 축 정리. |
| 사용자 가치 | 예측 실행·결과 테이블 제품화. |
| 관계 | B22 `VP_BATCH_PREDICTION` · `VP_FORECAST_PROVIDER`는 R10 on-demand와 축 정리 후 검토 |
| 선행 | R12-C · model artifact · result table |
| 범위 후보 | I/O contract · result table · batch run policy · monitoring 후보 |
| 제외 | “예측이 즉시/자동으로 된다”는 단정 UX · serving 전체 |
| 검증 | batch dry-run · result schema · 열수요 horizon 예시 |
| 위험 | Forecast Provider와 R10 중복 · 결과 모니터링 범위 비대 |
| 최소 착수 | §10.4 |
| 추천(초안) | **4** |

### 6.5 R12-E Notification 본구현

| 항목 | 내용 |
|------|------|
| 목적 | S8-7 설계 기반 영속화·read/ack·routing·채널. Ops badge PoC와 **구분**. |
| 사용자 가치 | 운영 알림·조치 필요 신호의 제품화. |
| 관계 | B5 badge는 read-model PoC · B22 `VP_NOTIFICATION` · Closeout known limitation |
| 선행 | S8-7 재검토 · Ops badge와의 경계 합의 |
| 범위 후보 | persistence · read-unread · routing policy · Graph/Ops 경계 |
| 제외 | 외부 채널 전면(email/Slack 등) 일괄 · badge를 “새 알림”으로 오해하는 UX |
| 검증 | API/UI read-model · dedup · severity |
| 위험 | ML 경로와 무관한데 일정 전체를 밀 수 있음 · 채널 범위 비대 |
| 예외 | **운영 알림 요구가 강하면 R12-B/C 앞 또는 병렬 검토 가능** |
| 최소 착수 | §10.5 |
| 추천(초안) | **5** (병렬 예외 가능) |

### 6.6 R13 Multi-source / Advanced / Lineage / Monitoring

| 항목 | 내용 |
|------|------|
| 목적 | DB/CSV source · Join/Branch · Advanced Transform · Lineage · Monitoring 등 장기 확장. |
| 사용자 가치 | 적재 소스·그래프 복잡도·추적성 확대. |
| 관계 | B22 P4 · Closeout R13 · Data Load MVP(ACTIVE REST)와 구분 |
| 선행 | R12 경험 · security review · 사용빈도 |
| 범위 후보 | DB/CSV security · join design · lineage model · transform 분류 |
| 제외 | R12 ML 경로보다 먼저 전면 착수하는 것을 기본으로 두지 않음 |
| 검증 | 설계 문서 · security checklist · PoC 단위 |
| 위험 | 보안·스키마 추론·그래프 복잡도 · MVP 흐림 |
| 최소 착수 | §10.6 |
| 추천(초안) | **6** |

---

## 7. 후보별 비교 매트릭스

점수: 1(낮음)~5(높음). 난이도·리스크는 **역점수**(쉬움/안전할수록 높음).

| 후보 | 가치 | Handoff | ML선행 | 난이도↑ | 리스크↑ | 검증 | 범용 | 열수요 | **총점** |
|------|------|---------|--------|---------|---------|------|------|--------|----------|
| R12-A DQ Gate | 5 | 5 | 5 | 4 | 4 | 5 | 5 | 5 | **38** |
| R12-B Feature | 5 | 4 | 5 | 3 | 3 | 4 | 4 | 5 | **33** |
| R12-C Training | 5 | 3 | 4 | 2 | 2 | 3 | 4 | 5 | **28** |
| R12-D Prediction | 5 | 2 | 3 | 2 | 2 | 3 | 4 | 5 | **26** |
| R12-E Notification | 4 | 2 | 1 | 3 | 3 | 4 | 5 | 3 | **25** |
| R13 Advanced | 3 | 1 | 2 | 1 | 1 | 2 | 4 | 2 | **16** |

해석 주의:
- 총점은 **상대 비교용**이다.
- R12-E는 ML 선행성은 낮지만 **운영 가치·검증·범용성**이 있어, 요구가 강하면 순서를 앞당기거나 병렬할 수 있다.
- R13은 장기 후보로 점수가 낮게 나온 것이며, 특정 고객 요구가 있으면 별도 재평가한다.

---

## 8. 추천 우선순위 초안

> 아래는 **추천 초안**이다. R12 범위·일정·순서를 **확정한 것이 아니다**.  
> **최종 우선순위는 사업·고객·일정 판단 후 별도 승인**한다.

| 순위(초안) | ID | 후보 |
|------------|-----|------|
| 1 | R12-A | Data Quality Gate & Handoff Hardening |
| 2 | R12-B | Feature Dataset Builder |
| 3 | R12-C | ML Training Workflow |
| 4 | R12-D | Forecast / Batch Prediction Workflow |
| 5 | R12-E | Notification 본구현 |
| 6 | R13 | Multi-source / DB·CSV / Advanced / Join / Branch / Lineage / Monitoring |

**예외:** 운영 알림 요구가 강하면 **R12-E를 R12-B/C 앞 또는 병렬**로 검토할 수 있다. 이 경우에도 S8-7 설계·Ops badge PoC와의 경계를 먼저 합의한다.

B22 권장 흐름과의 정합:

```text
[R11 Data Load] → [B7 Handoff] -.-> [R12-A DQ] → [R12-B Feature] → [R12-C Train] → [R12-D Predict]
                                                                      ↘ (병렬 가능) R12-E Notification
[R13] 장기: DB/CSV · Join/Branch · Lineage · Monitoring
```

---

## 9. R12-A를 먼저 검토해야 하는 이유

1. **B7 Handoff의 다음 단계**와 직접 연결된다 (자동 DQ는 아직 없음).
2. Target Preview · Schema/Key · Conflict Key · PARTIAL 안내 이후의 **자연스러운 확장**이다.
3. Feature / Training / Prediction **전에** “써도 되는 데이터인가” 기준이 필요하다.
4. rule catalog · read-only profiling · non-blocking summary처럼 **작은 MVP로 나누기 쉽다**.
5. docs/smoke/E2E **검증 가능성**이 상대적으로 높다.
6. 고객 설명이 쉽다: 적재 데이터를 학습에 넘겨도 되는지 **검증**.
7. B22에서 `VP_DATA_QUALITY`를 P1 / R12-A로 매핑해 두었다.

단, 이는 **우선 검토 추천**이지 구현 착수 승인이나 일정 단정이 아니다.

---

## 10. 후보별 최소 착수 단위

착수 시에도 **별도 승인**이 필요하다. 아래는 분할 예시일 뿐이다.

### 10.1 R12-A DQ Gate MVP 후보

- DQ rule catalog 설계 문서
- Target table profiling **read-only** API 검토
- DQ result model 초안
- Run **blocking vs non-blocking** policy (첫 단계에서는 blocking 강제 지양)
- Studio / Run Detail **read-only** DQ summary
- check-pages / docs smoke

### 10.2 R12-B Feature Dataset Builder MVP 후보

- Feature dataset contract 문서
- target → feature schema mapping design
- feature definition metadata 초안
- training window / time split 정책 문서

### 10.3 R12-C Training MVP 후보

- Training job contract
- MLflow 연계 방식 검토 문서
- runner 설계
- CPU/GPU execution policy

### 10.4 R12-D Prediction MVP 후보

- prediction input/output contract
- forecast result table design
- batch prediction run policy
- monitoring 후보 (본구현과 분리)

### 10.5 R12-E Notification MVP 후보

- S8-7 Notification 설계 재검토
- persistence / read-unread / routing policy
- Ops badge PoC와 Notification 본구현 **경계** 정리

### 10.6 R13 후보

- DB/CSV source security review
- multi-source join design
- lineage model design
- advanced transform 분류

---

## 11. 리스크와 선행 의존성

| 후보 | 주요 선행 | 주요 리스크 |
|------|-----------|-------------|
| R12-A | Preview/Key/Run 가시성 | rule 비대 · blocking 오남용 |
| R12-B | Handoff 산출물 · (권장) DQ | 도메인 lock-in · metadata SoT 부재 |
| R12-C | R12-B · runner/MLflow | 인프라 · 기존 학습 경로 이중화 |
| R12-D | R12-C · artifact | R10 Forecast Provider 축 혼선 |
| R12-E | S8-7 · badge 경계 | 채널 범위 · ML 일정과의 경합 |
| R13 | R12 경험 · security | 복잡도 · MVP 범위 흐림 |

공통: DISABLED 활성화·신규 node·package/ID 변경은 **각 단계 승인 범위에만** 포함한다. 본 초안 문서에서는 수행하지 않는다.

---

## 12. 다음 의사결정 질문

사람이 최종 승인할 때 확인할 질문:

1. 다음 분기에 **데이터 품질 게이트**와 **Feature 제품화** 중 무엇을 더 시급히 보는가?
2. 운영 알림(Notification) 요구가 ML 경로보다 **강한가**? (그렇다면 R12-E 병렬/앞당김)
3. MLflow/학습 인프라를 R12-C에서 **어느 깊이**까지 가져갈 것인가?
4. Forecast Provider를 R12-D에 넣을지, R10 on-demand와 **분리**할지?
5. R13(DB/CSV 등)을 특정 고객 때문에 **조기 재평가**할 사유가 있는가?
6. R12-A 첫 MVP를 **non-blocking read-only**로 시작할 것인가?

---

## 13. Known Limitations

- 본 문서는 **우선순위 초안**이며 **구현 착수 문서가 아니다**.
- R12 범위·일정·순서를 **확정하지 않는다**.
- **최종 우선순위는 별도 승인**이 필요하다.
- 점수표는 가중치 없는 초안이며 사업·고객 요인을 모두 반영하지 않는다.
- ML 학습·예측 실행 경로 · DQ engine · Feature Store · Notification 본구현은 **아직 없다**.
- DISABLED components는 **활성화되지 않았다**.
- B7의 R12-1~7과 B22의 R12-A~E는 라벨이 다를 수 있으며, 본 문서는 **A~E 기준**을 쓴다.
- 열수요 예측은 **대표 예시**일 뿐 제품 범위를 한 도메인으로 고정하지 않는다 (B23).

---

## 14. 용어

| 용어 | 의미 |
|------|------|
| R12 / R13 | 후속 구현 **후보** 단계 라벨 (일정 단정 아님) |
| Handoff | Data Load 산출물을 ML 단계로 넘기기 전 **인수 기준** |
| DISABLED / Coming later | Palette 비활성 · roadmap 후보 |
| 우선순위 초안 | 의사결정 참고 문서 · 별도 승인 전 미확정 |
| 역점수 | 난이도·리스크가 낮을수록 높은 점수 |
| Notification 본구현 | S8-7 영속화·routing 등 · Ops badge PoC와 구분 |

---

## 15. 관련 문서

- [THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md](./THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md)
- [THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)
- [THERMOps_R11-S8-9-27_Product_Branding_Generalization.md](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md)
- [THERMOps_R11-S8-7_Notification_설계.md](./THERMOps_R11-S8-7_Notification_설계.md)
- [THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) — 대표 예시
