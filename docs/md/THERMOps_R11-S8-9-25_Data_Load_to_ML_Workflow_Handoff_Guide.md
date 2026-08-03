# THERMOps R11-S8-9-25 Data Load → ML Workflow Handoff Guide

> **문서 성격:** 본 문서는 Visual Pipeline의 Data Load 결과를 이후 ML Workflow에서 활용하기 위한 **handoff 기준**을 정의한다.  
> 본 문서는 **구현 문서가 아니라 운영·설계 가이드**이며, **신규 ML 학습/예측 기능을 구현하지 않는다.**  
> Data Load가 끝났다고 해서 ML 입력이 자동으로 준비되거나, 학습·예측이 자동으로 실행된다는 의미가 아니다.

| 항목 | 값 |
|------|-----|
| Backlog | B7 |
| 단계 ID | R11-S8-9-25 |
| 관련 | R11-S8-9 Backlog, Visual Pipeline Studio/Ops |

---

## 1. 목적

- Data Load Visual Pipeline이 생성·적재한 결과 중 **무엇을 ML Workflow로 넘길지** 명확히 한다.
- **Data Load 완료 조건**과 **ML 입력 가능 조건**을 구분한다.
- R11에서 제공하는 검증·운영 가시성 기능과, 아직 없는 후속 ML 기능을 구분한다.
- 열수요 예측은 **범용 handoff 구조를 설명하는 예시**로만 사용한다.

---

## 2. 현재 R11 Visual Pipeline 범위

R11 Visual Pipeline(Data Load)이 담당하는 범위는 대략 다음과 같다.

```text
REST API Source
  → Transform
  → Upsert Load
  → Standard Dataset / Target Table 적재
  → Compile / 실행 설정 반영 / Manual·Scheduled Run
  → Run History · Ops에서 실행·실패·PARTIAL·skip 확인
```

### 2.1 Studio · 구성 UX (완료된 항목)

| 영역 | Backlog | 요약 |
|------|---------|------|
| Starter Template | B1 | cron-full / rest-upsert skeleton (Type B 비움, 자동 저장·실행 없음) |
| Domain Preset | B2 | FE-only 설정 가이드·Type A hint (backend SoT 아님) |
| Schema / Key Helper | B3 | Source↔Target·기준키 보조 안내 |
| Column match preview | B15 | 컬럼 정합성 진단 (mapping 자동 저장 없음) |
| Conflict keys | B27 | conflict_key_columns_json 선택·검증 (자동 확정 없음) |
| Target Preview | B18 | Target Table sample rows 읽기 전용 |
| Transform → SDS 컬럼 제안 | B21 | DRAFT 컬럼 후보 제안 |
| Data Source / SDS 인라인 | B19 / B20 | Inspector 선택·최소 생성 |
| Graph 검증 / dirty / schema default | B16 / B13 / B14 | 검증 cache, Type A default, unmapped_policy |
| Studio 레이아웃 | B17 | viewport + Operations Dock |

### 2.2 실행 · 운영 가시성 (완료된 항목)

| 영역 | Backlog | 요약 |
|------|---------|------|
| E2E smoke | B12 | REST→…→Run→Preview 여정 고정 |
| Failure summary | B6 | Run Detail 실패 한 줄 요약 |
| PARTIAL impact | B8 | Retry 전 영향 범위 안내 (중복 단정 없음) |
| Schedule Skip | B9 | skip 이력 read-only |
| Catch-up 안내 | B4 | 용어·checklist (자동 복구 암시 없음) |
| Ops 조치 필요 | B10 | stuck/failed/partial/catch-up 카드 |
| Ops/Studio badge | B5 | 운영 확인 필요 badge PoC |

### 2.3 R11이 하지 않는 것

- Feature Engineering / Feature Store 구현
- 모델 학습·평가·예측 실행 파이프라인 구현
- MLflow 실험·모델 등록 자동화
- Data Quality rule 엔진
- Data Load → ML 자동 연계 / lineage 제품화

위 항목은 **후속 후보(§12)** 이며 본 가이드 범위 밖이다.

---

## 3. Data Load와 ML Workflow의 경계

### 3.1 한 줄 정의

**Data Load Visual Pipeline**은 외부/원천 데이터를 표준 Target Table에 적재하고, 그 적재 결과가 ML Workflow에서 사용할 수 있는 상태인지 **확인하는 단계까지** 담당한다.

**ML Workflow**는 적재된 표준 데이터를 기반으로 feature 생성, 학습 데이터셋 구성, 모델 학습·평가, 예측 실행, 모델 운영을 담당한다.  
→ 현재 THERMOps R11은 이 ML Workflow를 **제품으로 연결 구현하지 않는다.**

### 3.2 경계 표

| | R11 Data Load | 후속 ML Workflow (미구현 / roadmap) |
|--|---------------|-------------------------------------|
| 입력 | REST API / Data Source / credential | 적재된 Standard Dataset · Target Table |
| 처리 | Transform, Upsert, CRON, Compile, Run | Feature, Training dataset, Train/Eval, Predict |
| 산출 | Target rows, SDS 메타, Run/Ops 이력 | Feature set, Model, Prediction result |
| 검증 | Graph 검증, Schema/Key, Preview, Run 상태 | DQ gate, train/serve skew, forecast monitor (후보) |

```text
[R11 Data Load]                    [Handoff Gate]                 [후속 ML Workflow]
Source → Transform → Upsert  →  SDS/Target/Key/RunOK 확인  -.->  Feature → Train → Predict
         ↑ Studio/Ops 가시성          (본 문서)                    (구현 아님 · 후보)
```

### 3.3 Data Load 완료 vs ML 입력 가능

| 구분 | 의미 |
|------|------|
| **Data Load 완료** | Graph가 저장·Compile되고, 의도한 Run이 SUCCESS(또는 허용된 조건부 상태)이며 Target에 적재가 확인된 상태 |
| **ML 입력 가능** | 위 조건에 더해, ML이 요구하는 **엔티티·시간·값 컬럼**과 **키/스키마**가 확정되어 있고, 운영상 FAILED/미해결 PARTIAL/미확인 skip이 handoff를 막지 않는 상태 |

Data Load 완료만으로 ML 입력이 자동 보장되지 않는다.

---

## 4. Handoff 대상 산출물

| 산출물 | 설명 | 생성/확인 위치 | ML Workflow에서의 용도 | Handoff 조건 |
|--------|------|----------------|------------------------|--------------|
| Standard Dataset | 표준 데이터셋 메타·컬럼 정의 | Studio Upsert / 표준 데이터셋 화면 | 학습·예측 입력 스키마의 기준 메타 | ACTIVE(또는 합의된 상태) SDS와 target_table 연결 확인 |
| Target Table | 실제 적재 물리 테이블 | Upsert `target_table` · Preview | Feature/학습의 원천 테이블 | Preview 또는 동등 수단으로 row 존재·스키마 확인 |
| Target Table sample preview | LIMIT N sample | Upsert Inspector (B18) | 적재 형태·null·타입 육안 확인 | SUCCESS(또는 조건부) Run 이후 sample 확인 |
| Schema / Column definition | Transform 출력·SDS 컬럼 | B21 제안 · SDS 컬럼 · B15 match | feature 컬럼 후보 | Source↔Target 정합성 위험 항목 해소 또는 문서화 |
| Conflict Key | Upsert 기준키 (`conflict_key_columns_json`) | B27 / B3 Helper | 시계열·엔티티 중복 정의의 운영 기준 | 키가 Target/Source에 존재하고 검증 경고 해소 |
| Domain Preset hint | transform/key/schema **안내** | Starter modal · B3 hint (B2) | 도메인 관례 참고 | **SoT 아님** — Target/Run으로 최종 판단 |
| Run History | 적재 실행 이력 | Studio Dock / Ops | 데이터 최신성·성공 여부 | 최근 의도 Run이 SUCCESS |
| Run Detail failure summary | 실패 한 줄 요약 | Run Detail (B6) | 실패 원인 triage | FAILED면 handoff 불가 |
| PARTIAL impact card | 부분 성공 영향 안내 | Run Detail (B8) | 중복·누락 리스크 검토 | PARTIAL이면 보류/조건부 |
| Schedule Skip History | CRON skip 사유 | Ops (B9) | 적재 공백 가능성 | skip 반복 시 Catch-up/재실행 판단 |
| Ops Action Required | stuck/failed/partial/catch-up | Ops 카드·badge (B10/B5) | 운영 차단 여부 | 미조치 항목 있으면 handoff 보류 권장 |

---

## 5. Handoff 전 검증 기준 (체크리스트)

현재 제품에서 **확인 가능한** 항목만 체크한다. 자동 Data Quality 게이트는 없다(§12 후보).

### 5.1 Graph · 실행 준비

- [ ] Graph 저장 완료 (dirty 없음)
- [ ] Graph 검증 통과, 또는 WARNING을 문서화하고 수용
- [ ] Compile 성공 · 동기화 상태 **IN_SYNC**(또는 동등 UI 표시)
- [ ] 「실행 설정 반영」(Materialization) 완료

### 5.2 적재 · 스키마

- [ ] Manual 또는 Scheduled Run이 **SUCCESS** (또는 §9의 조건부 규칙 충족)
- [ ] Target Table Preview에서 sample rows 확인
- [ ] Schema/Key Helper에서 source–target·기준키 상태 확인
- [ ] `conflict_key_columns_json`이 Upsert 정책(INSERT_ONLY 제외 시)에 맞게 설정됨
- [ ] Standard Dataset · `target_table`이 의도한 값인지 확인

### 5.3 운영 차단 여부

- [ ] FAILED Run이 handoff 대상 구간을 가리지 않음
- [ ] PARTIAL이면 B8 영향 카드 + Target Preview 확인 후 보류/조건부 결정
- [ ] Schedule skip / Catch-up 후보가 있으면 Ops에서 확인
- [ ] Ops 「조치 필요」·badge에 미확인 차단 항목이 없음(또는 수용 기록)

**금지 해석:** 위 체크를 통과했다고 해서 학습·예측이 자동으로 준비되거나 실행된다는 뜻이 아니다.

---

## 6. Handoff 후 ML Workflow 입력 조건

ML Workflow(후속)가 시작되려면 Data Load 완료에 더해 보통 다음이 필요하다.

| 조건 | 설명 |
|------|------|
| 엔티티 축 | 예: `entity_id` (또는 합의된 엔티티 컬럼) |
| 시간 축 | 예: `measured_at` (또는 합의된 시각 컬럼) |
| 값 / 타깃 컬럼 | 예: `heat_demand` 등 예측·학습 대상 |
| 스키마 안정성 | SDS 컬럼·타입이 feature 정의와 일치 |
| 데이터 구간 | 학습/예측에 필요한 기간이 Target에 적재됨 |
| 키 정책 | conflict key와 ML join key가 모순되지 않음 |

R11은 위 조건을 **자동 판정하지 않는다.** 운영자/ML 담당자가 Target Preview·SDS·Run 이력을 보고 판단한다.

---

## 7. 표준 데이터셋 / Target Table 기준

- **Standard Dataset**은 논리 스키마·메타의 기준이다. DRAFT 인라인 생성(B20)만으로 ACTIVE·물리 테이블이 완성됐다고 보지 않는다.
- **Target Table**은 Upsert가 쓰는 물리 적재 대상이다. Handoff의 실질 데이터 원천이다.
- Preview(B18)는 읽기 전용 sample이며 전체 건수·품질 보증이 아니다.
- 물리 DDL/unique index 변경은 본 가이드·R11 Data Load UX 범위 밖이다.

---

## 8. Schema / Key 기준

- ML Workflow는 보통 **시간축 · 엔티티축 · 값 컬럼**을 명확히 알아야 한다.
- 시계열 적재의 대표 conflict key 후보는 `entity_id` + `measured_at`이다.
- 열수요 예시에서는 `measured_at`, `entity_id`, `heat_demand`가 핵심 후보이나, **실제 키는 SDS/Target 기준으로 사용자가 확정**해야 한다.
- B3 Helper · B15 · B27은 보조 진단·선택 UX이며, 자동으로 ML join key를 확정하지 않는다.

---

## 9. Run 상태별 handoff 판단

| Run 상태 | Handoff 판단 | 확인 항목 | 조치 |
|----------|--------------|-----------|------|
| SUCCESS | 가능 후보 | Preview, Schema/Key, SDS/target | §5 체크리스트 완료 후 handoff |
| PARTIAL | 보류 또는 조건부 | B8 impact, Preview, conflict key | 영향 수용 시에만 조건부; 기본은 재실행·보류 |
| FAILED | 불가 | B6 failure summary, Ops | 원인 수정 후 재실행 |
| RUNNING / PENDING | 보류 | Run History | 완료 대기 |
| CANCELLED | 불가(또는 재실행) | soft-cancel 이력 | 재실행 여부 판단 |
| (Schedule) SKIPPED | Run 부재 가능 | B9 Skip · B4 Catch-up | 공백 구간 확인 후 Catch-up/재실행 |

---

## 10. Domain Preset과 Handoff의 관계

- Domain Preset(B2)은 **ML Handoff metadata가 아니라 FE hint/preset**이다.
- Studio UI state에 보관되며 reload 시 소실될 수 있다. **backend source of truth가 아니다.**
- Heat Demand preset은 transform/key/schema **안내**만 제공한다.
- 실제 ML 입력 가능 여부는 **적재된 Target Table · SDS · Run/Preview 검증**으로 판단한다.
- Preset을 적용했다고 해서 Data Load 완료 또는 ML 준비가 된 것이 아니다.

---

## 11. THERMOps 열수요 예측 예시

> **예시**이다. 특정 기관 전용이 아니며, 학습·예측 파이프라인이 구현되었음을 의미하지 않는다.

```text
REST API Source
  → Transform (예: WIDE_HOUR_TO_LONG)
  → Upsert Load → heat demand 표준 Target Table
  → conflict key 후보: entity_id + measured_at
  → (후속) ML Workflow에서 entity_id / measured_at / heat_demand 기반 feature 생성·학습·예측
```

| 단계 | 예시에서의 의미 |
|------|-----------------|
| Data Load | wide hour → long, 표준 테이블 적재 |
| Handoff | Preview로 row 확인, 키·스키마 확정, SUCCESS Run 확인 |
| ML (후속) | feature / train / forecast — **미구현** |

---

## 12. 후속 구현 Roadmap (후보)

아래는 **확정 일정·범위가 아닌 후속 후보**이다.

| ID | 후보 | 설명 |
|----|------|------|
| R12-1 | Feature Dataset Builder | 적재 Target → feature dataset 구성 |
| R12-2 | Data Quality Gate | handoff 전 자동 DQ 규칙 |
| R12-3 | ML Training Workflow | 학습·평가 오케스트레이션 |
| R12-4 | Forecast Run Workflow | 배치/스케줄 예측 실행 |
| R12-5 | Model Registry / MLflow 연계 | 실험·모델 등록 |
| R12-6 | Prediction Result Monitoring | 예측 결과·드리프트 모니터링 |
| R12-7 | Data Load ↔ ML lineage | 적재 Run ↔ feature/model lineage |

B22(DISABLED 컴포넌트: Feature/Model/Prediction 등)도 동일하게 **별도 승인 후** 본구현 후보이다.

---

## 13. Known Limitations

- 본 문서는 **가이드**이며 ML Workflow·Feature Store·학습/예측 실행을 구현하지 않는다.
- 자동 Data Quality / 자동 handoff / 자동 학습·예측 연계는 없다.
- Domain Preset·일부 Helper는 FE-only이며 backend SoT가 아니다.
- Target Preview는 sample LIMIT이며 전수·품질 보증이 아니다.
- PARTIAL/Skip에 대한 handoff는 운영 판단이 필요하며 시스템이 자동 승인하지 않는다.

---

## 14. 용어

| 용어 | 설명 |
|------|------|
| Data Load Visual Pipeline | REST→Transform→Upsert 중심의 적재 graph |
| Handoff | Data Load 산출물을 ML 단계 입력으로 넘기기 전 확인·인수 기준 |
| Standard Dataset (SDS) | 표준 데이터셋 메타·컬럼 정의 |
| Target Table | Upsert 적재 물리 테이블 |
| Conflict Key | Upsert INSERT/UPDATE 기준 컬럼 집합 |
| Domain Preset | FE 설정 가이드/추천 (SoT 아님) |
| ML Workflow | feature·학습·예측·모델 운영 단계 (R11 미구현) |
| Compile / Materialization | graph 컴파일 · 「실행 설정 반영」 |
| PARTIAL | 일부 성공·일부 실패/경고 성격의 Run 상태 |

---

## 관련 문서

- [THERMOps_R11-S8-9_Backlog.md](./THERMOps_R11-S8-9_Backlog.md)
- [THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md](./THERMOps_R11-S8-8_열수요예측_Full_Scenario_이용가이드.md)
- [THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md](./THERMOps_R11-S6-5_Compile_Run_Boundary_정리.md)
- [THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md](./THERMOps_R11-S8-0_Run_History_Progress_Retry_설계.md)
