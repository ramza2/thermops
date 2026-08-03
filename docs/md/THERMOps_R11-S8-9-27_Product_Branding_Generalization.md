# THERMOps R11-S8-9-27 Product Branding Generalization

> **문서 성격:** 본 문서는 **THERMOps 제품명은 유지**하면서, Visual Pipeline Studio와 관련 문서를 **범용 Data Load / Workflow 플랫폼** 관점으로 설명하기 위한 branding / terminology 기준을 정의한다.  
> 본 문서는 **기능 구현 문서가 아니며**, route / API / component ID / DB / worker / package를 변경하지 않는다.

| 항목 | 값 |
|------|-----|
| Backlog | B23 |
| 단계 ID | R11-S8-9-27 |
| 관련 | B7 Handoff Guide, B22 DISABLED Roadmap |

---

## 1. 목적

- 제품명 THERMOps는 유지한다.
- R11 Visual Pipeline을 **범용 Data Load / Workflow Studio**로 설명한다.
- **열수요 예측은 대표 적용 예시**(및 Domain Preset 예시)로 유지한다.
- ML Workflow / Feature / Training / Prediction은 **후속 후보**로만 표현한다 ([B7](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)).
- DISABLED components는 **roadmap 후보**로만 표현한다 ([B22](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)).

---

## 2. Product / Module / Example 구분

| 구분 | 유지/수정 기준 | 예시 |
|------|----------------|------|
| Product name | **유지** | THERMOps |
| Module name | **유지** | Visual Pipeline Studio, Visual Pipeline Ops |
| Component ID | **유지** (코드·API) | `VP_REST_API_SOURCE`, `VP_TRANSFORM`, … |
| User-facing description | **범용화** | “Data Load / Workflow · MLOps 운영 플랫폼” |
| Example scenario | **예시로 유지** | 열수요 예측 Full Scenario (S8-8), Heat Demand preset |
| Domain preset | FE hint / 예시 | Heat Demand Forecast Data Load (SoT 아님) |
| Roadmap item | 후보로만 | R12 DQ/Feature/Train/Predict, DISABLED 8종 |
| Internal implementation term | **유지** | env, docker service, package, table, route |

권장 한 줄:

> THERMOps는 열수요 예측 적용 사례에서 출발했지만, R11 Visual Pipeline Studio는 REST Source · Transform · Upsert · Schedule · Ops를 조합하는 **범용 Data Load / Workflow** 기반으로 정리한다. 열수요 예측은 **대표 적용 예시**이며, Heat Demand preset은 도메인 설정을 돕는 FE hint이다. R11은 Data Load와 Handoff 기준을 제공하며, Feature / Training / Prediction은 R12/R13 **후속 후보**로 분리한다.

---

## 3. 유지할 표현

- THERMOps 제품명
- Visual Pipeline Studio / Ops
- component ID, API path, route, DB, env, docker, package
- Heat Demand Forecast Data Load preset 이름
- [`THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md`](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) (대표 예시 시나리오)
- R11 / S8 / S9 단계 ID, backlog ID (B1–B27)

---

## 4. 수정·피할 표현

| 피할 표현(요지) | 권장 |
|-----------------|------|
| 특정 도메인만의 플랫폼처럼 보이는 설명 | Data Load·Workflow 기반 MLOps 운영 플랫폼 (열수요는 대표 예시) |
| 한 도메인 데이터만 처리한다는 단정 | 열수요를 포함한 시계열·운영 데이터 처리 **예시** |
| 학습·예측이 자동/즉시 된다는 단정 | Handoff 기준 제공 · ML은 **후속 후보** |
| 예측 pipeline이 이미 제품화된 듯한 표현 | 예측 pipeline은 **후속 후보** |
| DISABLED 노드가 이미 제공·활성화된 듯한 표현 | DISABLED는 **roadmap 후보** (Coming later) |
| 특정 고객사명을 제품 tagline에 고정 | tenant / demo scenario / project label로 분리 |

---

## 5. 금지 문구 (사용자 노출·신규 가이드)

신규 README 서두·UI tagline·본 가이드의 **제품 소개 문장**에 다음을 쓰지 않는다 (회귀 검사는 check-pages B23 assert).

- 도메인 「전용」 플랫폼/시스템처럼 읽히는 단정
- 자동·즉시 학습/예측이 된다는 단정
- ML Workflow 또는 DISABLED 노드가 **이미 구현·활성화 완료**라는 단정
- 「R10」설정 반영 사용자 문구 재노출

허용: “열수요 예측 **예시**”, “대표 적용 예시”, “Heat Demand preset”, S8-8 파일명.

---

## 6. UI / docs 적용 원칙

### UI

- 고객사명을 전역 Header 등에 하드코딩하지 않는다.
- DISABLED는 “Coming later” / roadmap으로 유지한다.
- Domain Preset은 예시·hint임을 유지한다.
- component ID·testid·route는 바꾸지 않는다.

### docs

- README 서두는 범용 플랫폼 + 열수요 대표 예시로 쓴다.
- S8-8은 열수요 시나리오 문서로 **유지**하고, index에서는 “대표 예시 시나리오”로 링크한다.
- 과거 제안·아키텍처 문서(고객사 제안 문맥)는 historical로 두고, 이번 branding 작업에서 일괄 개편하지 않는다.
- B7 / B22 기준과 모순되는 완료 표현을 쓰지 않는다.

---

## 7. B7 / B22와의 관계

| 문서 | branding에 쓰는 기준 |
|------|----------------------|
| [B7 Handoff](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md) | ML 미구현 · 열수요 예시 · Preset은 SoT 아님 |
| [B22 DISABLED Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md) | DISABLED=roadmap · R12/R13=후보 · 활성화 없음 |

본 문서는 위 두 문서의 **표현 규칙을 제품 전반에 적용**하는 branding guideline이다.

---

## 8. Known Limitations

- branding generalization이며 **제품명·ID·route/API/DB/package 변경이 아니다.**
- 과거 제안서·기능정의서·아키텍처의 고객사 문맥은 이번 범위에서 전부 정리하지 않았다.
- S8-8 열수요 시나리오 본문의 도메인 용어는 의도적으로 유지한다.
- ML / DISABLED 본구현을 하지 않는다.

---

## 관련 문서

- [THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)
- [THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) — 대표 예시 시나리오
