# THERMOps R11-S8-9-28 Visual Pipeline Studio/Ops Closeout Release Note

> **문서 성격:** 본 문서는 R11-S8-9에서 수행한 Visual Pipeline Studio/Ops 개선 항목의 **closeout / release note**이다.  
> 본 문서는 **신규 기능 구현 문서가 아니며**, route / API / component ID / DB / worker / package를 변경하지 않는다.

| 항목 | 값 |
|------|-----|
| 단계 ID | R11-S8-9-28 |
| Backlog 범위 | B1 ~ B27 (전부 done) |
| 기준 커밋 (B23) | `f1fa489` — Product Branding Generalization |
| 관련 | [B7 Handoff](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md), [B22 Roadmap](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md), [B23 Branding](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md) |

---

## 1. 목적

R11-S8-9에서 **무엇이 완료되었는지**, 어떤 UX/운영 흐름이 정리되었는지, 어떤 검증을 통과했는지, 무엇이 **known limitation / 후속 후보**인지, 배포 전 확인사항은 무엇인지 한 문서로 정리한다.

- THERMOps 제품명은 유지한다.
- Visual Pipeline은 **범용 Data Load / Workflow Studio**로 설명한다.
- 열수요 예측은 **대표 적용 예시**로만 설명한다.
- ML 학습·예측 pipeline, DISABLED component 활성화는 **이번 closeout 범위에 포함하지 않는다**.

---

## 2. Release 범위

| 포함 | 제외 |
|------|------|
| B1~B27 완료 상태 요약 (backlog/README 근거) | backend API 신규/변경 |
| 사용자·Ops·Docs 흐름 기준 release note | DB migration |
| smoke / 배포 전 확인사항 | FE 본기능 로직 변경 |
| Known limitations · R12/R13 **후속 후보** | component registry / palette 변경 |
| README · Backlog · check-pages 문서 링크/정적 검사 | DISABLED 활성화 · 신규 node 구현 |
| | ML 학습/예측 · Feature Store · DQ engine · Notification 본구현 |
| | route/API/component ID/env/docker/package 이름·의존성 변경 |

**제품 표현 기준 (B7 / B22 / B23):**

- **B7:** Data Load → ML Workflow **handoff 기준만** 제공. ML 학습/예측 실행 경로는 구현하지 않음.
- **B22:** DISABLED components는 **roadmap 후보**. 활성화·신규 node 구현 아님.
- **B23:** THERMOps 유지 · Visual Pipeline = 범용 Data Load / Workflow · 열수요 = 대표 예시.

---

## 3. 완료 항목 요약

Backlog **B1~B27 전부 `done`**. Open 항목 없음. 본 closeout은 별도 기능 backlog를 열지 않고 S8-9 마감 요약만 수행한다.

### 3.1 Studio Onboarding / 생성 UX

| Backlog | 단계 | 요약 | 사용자 효과 | 비고 |
|---------|------|------|-------------|------|
| B1 | R11-S8-9-23 | Starter Template | REST→Transform→Upsert 골격 빠른 생성 | `c329ecc` |
| B2 | R11-S8-9-24 | Domain Preset Framework | 도메인 hint/preset 선택 (SoT 아님) | `6f4f911` |
| B13 | R11-S8-9-4 | Inspector select 기본값 | 표시 기본값이 config에 저장되어 검증 경고 감소 | `0593d69` |
| B17 | R11-S8-9-1 | Studio layout / Operations Dock | viewport 고정 작업대 + Bottom Dock | `e23461b` |
| B19 | R11-S8-9-9 | REST Data Source 인라인 생성 | Inspector에서 최소 DS 생성 후 선택 | `2310c21` |
| B20 | R11-S8-9-10 | SDS 인라인 생성 | DRAFT Standard Dataset 생성·반영 | `7bf4a8c` |

### 3.2 Data Load 설정·검증 UX

| Backlog | 단계 | 요약 | 사용자 효과 | 비고 |
|---------|------|------|-------------|------|
| B3 | R11-S8-9-22 | Schema / Key Mapping Helper | 원천→표준 매핑 진단·제안 | `4a2d644` · 자동 확정 아님 |
| B14 | R11-S8-9-5 | Transform Unmapped Policy enum | Studio↔backend enum 정렬 | `b8bc37c` |
| B15 | R11-S8-9-12 | Source↔Target Column Normalization | 대소문자·snake_case 정합성 미리보기 | `6b7455f` |
| B16 | R11-S8-9-3 | 검증 → Compile dirty 흐름 | 검증 후 dirty 미재발 · Compile 연속 | `77a6e05` |
| B18 | R11-S8-9-14 | Target Table sample preview | 적재 후 sample rows 확인 | `5294f72` · sample only |
| B21 | R11-S8-9-11 | Transform → SDS column proposal | 표준 컬럼 후보 제안 | `f53a662` |
| B27 | R11-S8-9-13 | Upsert conflict keys 검증 | conflict key 선택·사전 검증 | `0fb49c2` · 자동 확정 아님 |

### 3.3 Run / Ops 운영 가시성

| Backlog | 단계 | 요약 | 사용자 효과 | 비고 |
|---------|------|------|-------------|------|
| B4 | R11-S8-9-19 | Catch-up 안내 UX | missed/window 의미 안내 | `a1ffb66` |
| B5 | R11-S8-9-21 | 운영 확인 필요 badge PoC | Ops/Studio read-model badge | `1df1975` · Notification 본구현 아님 |
| B6 | R11-S8-9-16 | Run Detail 실패 원인 요약 | step+reason 한 줄 | `7aec0c7` |
| B8 | R11-S8-9-20 | PARTIAL 영향 범위 안내 | Retry 전 확인 힌트 | `6c79d8c` |
| B9 | R11-S8-9-18 | Schedule skip 이력 UI | skip 반복 가시화 | `3397613` |
| B10 | R11-S8-9-17 | Ops 조치 필요 카드 | stuck/failed/partial/catch-up | `e4a0093` |
| B24 | R11-S8-9-6 | SDS archive UI | 표준 데이터셋 보관 | `8688a3f` |
| B25 | R11-S8-9-2 | Data Source 목록 로드 수정 | size≤100 · 빈 목록 버그 해소 | `fbfe8f2` |
| B26 | R11-S8-9-7 | Ops smoke soft-cancel 안정화 | flaky assertion 제거 | `6abaeb9` |

### 3.4 End-to-End / Regression

| Backlog | 단계 | 요약 | 사용자 효과 | 비고 |
|---------|------|------|-------------|------|
| B11 | R11-S8-9-8 | Data Source 100건 초과 UX | 검색·더 보기·새로고침 | `3ac54b0` |
| B12 | R11-S8-9-15 | Visual Pipeline E2E Smoke | REST→…→History 범용 smoke | `49e4590` |
| — | — | check-pages / studio / ops / e2e | 정적·브라우저 회귀 | 배포 전 필수 |

### 3.5 Productization / Docs

| Backlog | 단계 | 요약 | 사용자 효과 | 비고 |
|---------|------|------|-------------|------|
| B7 | R11-S8-9-25 | Data Load → ML Handoff Guide | 후속 ML 인수 **기준** 문서 | `5c18cbc` · 구현 아님 |
| B22 | R11-S8-9-26 | DISABLED Components Roadmap | Coming later 판단 기준 | `8486bcd` · 활성화 아님 |
| B23 | R11-S8-9-27 | Product Branding Generalization | 범용 Data Load/Workflow 표현 | `f1fa489` |
| — | R11-S8-9-28 | Closeout Release Note (본 문서) | S8-9 마감 요약 | docs only |

---

## 4. 사용자 흐름 기준 완료 요약

권장 운영 여정(자동화 단정이 아님):

1. Studio 진입  
2. Starter Template 선택 (B1)  
3. Domain Preset 선택 — optional (B2; FE hint, backend SoT 아님)  
4. REST Source / Transform / Upsert 설정  
5. Data Source / Standard Dataset **인라인 최소 생성** (B19, B20)  
6. Schema / Key / Column 정합성 확인 (B3, B14, B15, B21, B27)  
7. Graph 검증 (B13, B16)  
8. Compile  
9. 실행 설정 반영  
10. Manual / Scheduled Run  
11. Run History / Ops 확인 (B4–B6, B8–B10)  
12. Target Preview 확인 (B18; sample)  
13. [Handoff Guide](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)로 ML 후속 **인수 판단** (학습·예측 실행 경로는 미구현)

열수요 예측 Full Scenario([S8-8](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md))는 위 흐름의 **대표 예시**이다.

---

## 5. 운영/Ops 기준 완료 요약

- Catch-up · PARTIAL · Schedule skip · 실패 원인 요약으로 **운영자가 다음 조치를 판단**할 수 있는 UI 정리
- Ops 「조치 필요」카드 + 「확인 필요」badge PoC (read-model; Notification 본구현·읽음/미읽음 아님)
- soft-cancel / stuck run 관련 Ops smoke assertion 안정화
- Target sample preview · SDS archive로 적재 결과·데이터셋 수명 관리 보조

자동 복구·자동 재시도 확정·중복 적재 단정은 하지 않는다.

---

## 6. 문서/제품화 기준 완료 요약

- **Handoff Guide (B7):** Data Load 산출물을 Feature/Training/Prediction으로 넘기기 위한 **기준**만. ML Workflow는 후속 후보.
- **DISABLED Roadmap (B22):** 8종 Coming later 컴포넌트 본구현 판단 기준. **활성화하지 않음.**
- **Branding (B23):** THERMOps 유지 · Visual Pipeline = Data Load / Workflow · 열수요 = 대표 예시.
- **본 Closeout (R11-S8-9-28):** S8-9 전체 마감 요약. 신규 기능 구현 아님.

---

## 7. 주요 검증 / smoke

```bash
cd frontend
npm run build
node scripts/check-pages.mjs
node scripts/check-visual-pipeline-studio.mjs
node scripts/check-visual-pipeline-ops.mjs
node scripts/check-visual-pipeline-e2e.mjs
```

| 명령 | 역할 |
|------|------|
| `npm run build` | frontend typecheck + production build |
| `check-pages.mjs` | 문서/금지 문구/정적 assert (closeout·B7/B22/B23 포함) |
| `check-visual-pipeline-studio.mjs` | Studio 생성·검증·설정 UX |
| `check-visual-pipeline-ops.mjs` | Ops/Run 운영 가시성 |
| `check-visual-pipeline-e2e.mjs` | Data Load end-to-end 흐름 |

배포 전 `frontend/package.json` · `package-lock.json` · `backend/requirements.txt` diff가 **비어 있는지** 확인한다.

---

## 8. 배포 전 확인사항

| # | 확인 | 비고 |
|---|------|------|
| 1 | `master` 최신 commit (B23 `f1fa489` 이후 closeout 반영) | |
| 2 | package / requirements diff 없음 | S8-9 docs·FE 중심 |
| 3 | migration 필요 없음 | 본 closeout·최근 S8-9 docs 단계 |
| 4 | `npm run build` 통과 | |
| 5 | pages / studio / ops / e2e smoke 통과 | |
| 6 | Docker/Traefik 재기동 필요 여부 | FE 문구·정적 자산 반영 시 |
| 7 | run / schedule worker 상태 | 운영 Run이 필요하면 worker 포함 배포 |
| 8 | frontend cache refresh | 브라우저/CDN |
| 9 | README / Backlog / closeout 문서 링크 | |

배포 참고 (기존 절차):

```bash
docker compose -f docker-compose.traefik.yml --env-file .env.deploy up -d --build backend frontend vp-run-worker vp-schedule-worker
```

---

## 9. Known Limitations

- **ML Workflow / 학습·예측 실행 경로는 구현하지 않음** (B7: handoff 기준만)
- **DISABLED components는 활성화되지 않음** (B22: roadmap 후보)
- R12 / R13은 **확정 일정이 아니라 후속 후보**
- Domain Preset은 **FE hint/preset**이며 backend source of truth가 아님
- Target Preview는 **sample preview**이며 전수 품질 보증이 아님
- Data Quality Gate는 후속 후보
- Schema/Key/conflict helper는 **사용자 판단을 보조**할 뿐 자동 확정하지 않음
- Ops badge / 조치 필요 카드는 Notification 본구현·발송이 아님
- 과거 제안서·시나리오 문서의 고객사·도메인 표현은 historical/예시 문맥으로 남을 수 있음
- **본 문서는 closeout이며 신규 기능 구현이 아님**

---

## 10. R12/R13 후속 후보

확정 일정이 아니다. 착수 전 별도 승인·범위 정의가 필요하다.

| 후보 | 요지 |
|------|------|
| R12-A | Data Quality Gate & Handoff Hardening |
| R12-B | Feature Dataset Builder |
| R12-C | ML Training Workflow |
| R12-D | Forecast / Batch Prediction Workflow |
| R12-E | Notification 본구현 |
| R13 | Multi-source / DB·CSV / Advanced Transform / Join / Branch / Lineage / Monitoring |

상세 후보·의존성은 [B7](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md), [B22](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)를 따른다.

---

## 11. 변경하지 않은 것

- THERMOps 제품명
- route / API / component ID
- DB migration · backend API
- component registry / palette status
- DISABLED component 활성화 · 신규 node 구현
- ML 학습/예측 pipeline
- package / requirements

(본 closeout 단계 기준. 과거 S8-9 FE 단계의 개별 UX 변경은 §3·§12 참고.)

---

## 12. Commit / 단계 추적표

### 12.1 최근 주요 (상세)

| Backlog | 단계 | Commit | 메시지 |
|---------|------|--------|--------|
| B1 | R11-S8-9-23 | `c329ecc` | feat(R11-S8-9-23): Visual Pipeline Starter Template 추가 |
| B2 | R11-S8-9-24 | `6f4f911` | feat(R11-S8-9-24): Domain Preset Framework 추가 |
| B7 | R11-S8-9-25 | `5c18cbc` | docs(R11-S8-9-25): Data Load ML Workflow handoff guide 추가 |
| B22 | R11-S8-9-26 | `8486bcd` | docs(R11-S8-9-26): DISABLED components roadmap 추가 |
| B23 | R11-S8-9-27 | `f1fa489` | docs(R11-S8-9-27): Product branding generalization 추가 |

### 12.2 전체 단계 (요약)

| 단계 | Backlog | Commit | 요약 |
|------|---------|--------|------|
| R11-S8-9-1 | B17 | `e23461b` | Studio scroll / Operations Dock |
| R11-S8-9-2 | B25 | `fbfe8f2` | Data Source size≤100 |
| R11-S8-9-3 | B16 | `77a6e05` | 검증→Compile dirty |
| R11-S8-9-4 | B13 | `0593d69` | Inspector select defaults |
| R11-S8-9-5 | B14 | `b8bc37c` | Unmapped policy enum |
| R11-S8-9-6 | B24 | `8688a3f` | SDS archive UI |
| R11-S8-9-7 | B26 | `6abaeb9` | Ops smoke soft-cancel |
| R11-S8-9-8 | B11 | `3ac54b0` | DS 100+ UX |
| R11-S8-9-9 | B19 | `2310c21` | REST DS inline create |
| R11-S8-9-10 | B20 | `7bf4a8c` | SDS inline create |
| R11-S8-9-11 | B21 | `f53a662` | Transform→SDS columns |
| R11-S8-9-12 | B15 | `6b7455f` | Column match preview |
| R11-S8-9-13 | B27 | `0fb49c2` | Conflict keys UX |
| R11-S8-9-14 | B18 | `5294f72` | Target sample preview |
| R11-S8-9-15 | B12 | `49e4590` | E2E smoke |
| R11-S8-9-16 | B6 | `7aec0c7` | Failure summary |
| R11-S8-9-17 | B10 | `e4a0093` | Ops action card |
| R11-S8-9-18 | B9 | `3397613` | Schedule skip UI |
| R11-S8-9-19 | B4 | `a1ffb66` | Catch-up UX |
| R11-S8-9-20 | B8 | `6c79d8c` | PARTIAL impact |
| R11-S8-9-21 | B5 | `1df1975` | Ops badge PoC |
| R11-S8-9-22 | B3 | `4a2d644` | Schema/Key helper |
| R11-S8-9-23 | B1 | `c329ecc` | Starter Template |
| R11-S8-9-24 | B2 | `6f4f911` | Domain Preset |
| R11-S8-9-25 | B7 | `5c18cbc` | Handoff Guide |
| R11-S8-9-26 | B22 | `8486bcd` | DISABLED Roadmap |
| R11-S8-9-27 | B23 | `f1fa489` | Branding |
| R11-S8-9-28 | — | (본 closeout) | Closeout Release Note |

---

## 13. 용어

| 용어 | 의미 |
|------|------|
| THERMOps | 제품명 (유지) |
| Visual Pipeline Studio | 범용 Data Load / Workflow 편집·검증·Compile UI |
| Visual Pipeline Ops | Run/Schedule 운영 가시성 UI |
| Data Load | REST → Transform → Upsert 적재 흐름 |
| Domain Preset | FE hint (backend SoT 아님) |
| Handoff | Data Load 산출물을 후속 ML 단계로 넘기기 위한 **기준** (실행 경로 아님) |
| DISABLED / Coming later | Palette 비활성 후보 · roadmap만 |
| Closeout | 구간 마감 요약 · 신규 기능 구현 문서 아님 |

---

## 14. 관련 문서

- [THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)
- [THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md](./THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md)
- [THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md](./THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md)
- [THERMOps_R11-S8-9-27_Product_Branding_Generalization.md](./THERMOps_R11-S8-9-27_Product_Branding_Generalization.md)
- [THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md) — 대표 예시
- [THERMOps_R11-S8-7_Notification_설계.md](./THERMOps_R11-S8-7_Notification_설계.md)
- [THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md](./THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md)
- [THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md](./THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md)
