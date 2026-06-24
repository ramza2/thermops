# THERMOps Figma UI Master Spec

문서명: THERMOps Figma UI Master Spec  
대상 시스템: THERMOps: 열수요 예측 모델 운영 자동화 플랫폼  
읽기명: 써모옵스  
작성 목적: Figma 정식 UI 설계 및 인터랙티브 프로토타입 제작 기준 제공  
작성 기준: 기능정의서, 아키텍처 설계서, DB 설계서, 데이터 매핑 정의서, 배치/파이프라인 설계서, API 설계서, 화면 설계서  
주의: 본 문서는 샘플 UI 제작용이 아니라, 개발자가 화면 구현에 참고할 수 있는 정식 UI 프로토타입 제작용 기준서이다.

---

## 1. Figma 제작 목표

THERMOps는 열수요 예측 모델의 데이터 적재, 데이터 매핑, Feature 설정, 모델 학습, 모델 등록, 배치 예측, 성능 모니터링, 재학습 후보 관리를 지원하는 오픈소스 기반 MLOps 운영 플랫폼이다.

Figma 작업자는 본 문서를 기준으로 다음 수준의 결과물을 생성해야 한다.

1. 전체 메뉴 구조를 반영한 엔터프라이즈 웹 UI
2. 메뉴별 모든 화면 Frame 생성
3. 화면별 주요 검색 조건, 목록, 상세, 버튼 배치
4. 버튼 클릭 시 화면 이동, 팝업, 다이얼로그, Toast, 상태 변화 연결
5. 등록/수정/삭제/실행/저장/취소/상세/다운로드/Champion 지정/재학습 요청 등 주요 액션에 대한 인터랙션 연결
6. 공통 컴포넌트 페이지 생성
7. 공통 팝업/다이얼로그 페이지 생성
8. 주요 업무 흐름에 대한 Prototype Flow 연결
9. Coverage Checklist 페이지 생성
10. Prototype Flow Map 페이지 생성

---

## 2. Figma 파일 구성

Figma 파일은 다음 Page 구조로 생성한다.

| Page | 설명 |
|---|---|
| 00_Cover | 프로젝트 표지 |
| 01_IA_Menu | 전체 메뉴 구조 |
| 02_Design_System | 컬러, 타이포그래피, 상태값, 버튼 스타일 |
| 03_Common_Components | Header, Sidebar, Table, Modal, Toast 등 공통 컴포넌트 |
| 04_Dashboard | 대시보드 화면 |
| 05_Data_Management | 데이터 관리 화면 |
| 06_Feature_Management | Feature 관리 화면 |
| 07_Model_Management | 모델 관리 화면 |
| 08_Prediction_Management | 예측 관리 화면 |
| 09_Operation_Management | 운영 관리 화면 |
| 10_Modals_Toasts | 공통 팝업, 다이얼로그, Toast |
| 11_Prototype_Flow_Map | 업무 흐름 및 화면 이동 맵 |
| 12_Coverage_Checklist | 누락 검수 체크리스트 |

---

## 3. Frame 및 Component 이름 규칙

### 3.1 화면 Frame 이름 규칙

화면 Frame은 반드시 화면ID와 화면명을 포함한다.

```text
SCR-001_대시보드_열수요예측현황
SCR-002_데이터관리_데이터소스관리
SCR-003_데이터관리_데이터매핑설정
SCR-004_데이터관리_데이터품질점검
SCR-005_Feature관리_Feature목록
SCR-006_Feature관리_FeatureSet관리
SCR-007_Feature관리_Feature설정상세
SCR-008_모델관리_모델학습설정
SCR-009_모델관리_모델학습실행
SCR-010_모델관리_모델성능비교
SCR-011_모델관리_모델Registry관리
SCR-012_예측관리_배치예측실행
SCR-013_예측관리_예측결과조회
SCR-014_예측관리_실제값매칭오차분석
SCR-015_운영관리_파이프라인실행이력
SCR-016_운영관리_성능모니터링
SCR-017_운영관리_드리프트리포트
SCR-018_운영관리_재학습후보관리
```

### 3.2 팝업/다이얼로그 Frame 이름 규칙

```text
MOD-001_모델학습실행확인
MOD-002_배치예측실행확인
MOD-003_Champion지정확인
MOD-004_재학습요청확인
MOD-005_삭제확인
MOD-006_데이터소스연결테스트결과
MOD-007_FeatureSet선택
MOD-008_모델상세
MOD-009_파이프라인실행상세
MOD-010_권한없음안내
```

### 3.3 Toast/Message 이름 규칙

```text
MSG-001_저장완료Toast
MSG-002_실행요청완료Toast
MSG-003_삭제완료Toast
MSG-004_오류발생Toast
MSG-005_필수값누락Toast
```

### 3.4 Component 이름 규칙

```text
CMP_Header
CMP_Sidebar
CMP_SearchPanel
CMP_DataTable
CMP_Pagination
CMP_PrimaryButton
CMP_SecondaryButton
CMP_DangerButton
CMP_StatusBadge
CMP_Modal
CMP_Toast
CMP_MetricCard
CMP_ChartCard
CMP_LineChart
CMP_BarChart
CMP_FormField
CMP_SelectBox
CMP_DateRangePicker
CMP_Tab
CMP_Breadcrumb
CMP_EmptyState
CMP_ErrorState
CMP_LoadingState
```

---

## 4. 디자인 방향

### 4.1 전체 톤

- 엔터프라이즈 운영 시스템 느낌
- MLOps/운영 관제 플랫폼 느낌
- 과도한 장식보다 정보 밀도와 가독성 우선
- 제안/시연/개발 참조가 가능한 완성형 UI

### 4.2 컬러 방향

| 용도 | 컬러 방향 |
|---|---|
| Primary | 안정적인 Blue 계열 |
| Secondary | Green 또는 Teal 계열 |
| Warning | Amber/Orange 계열 |
| Error | Red 계열 |
| Success | Green 계열 |
| Background | Light Gray 또는 Cool Gray |
| Table Header | Pale Blue/Gray |
| Sidebar | Deep Navy 또는 Dark Blue |

### 4.3 상태 배지 색상

| 상태값 | 표시명 | 색상 방향 |
|---|---|---|
| READY | 대기 | Gray |
| RUNNING | 실행중 | Blue |
| SUCCESS | 성공 | Green |
| FAILED | 실패 | Red |
| WARNING | 경고 | Orange |
| REGISTERED | 등록 | Blue |
| CHAMPION | 운영중 | Green |
| CANDIDATE | 후보 | Purple |
| DISABLED | 비활성 | Gray |
| DRIFT_DETECTED | 드리프트 감지 | Orange |
| RETRAIN_REQUIRED | 재학습 필요 | Red |

---

## 5. 권한 정의

Figma 화면에서는 권한별 버튼 노출 기준을 표현한다. 실제 인증 구현은 하지 않지만, 권한 없음 팝업과 Disabled 버튼 상태를 포함한다.

| 권한 | 설명 | 주요 가능 기능 |
|---|---|---|
| ADMIN | 관리자 | 전체 설정, 저장, 삭제, 실행, Champion 지정, 재학습 요청 |
| ANALYST | 분석가 | 데이터 조회, Feature 설정, 모델 학습, 성능 분석, 예측 실행 |
| VIEWER | 조회 사용자 | 대시보드, 예측 결과, 성능 조회 중심 |

권한별 버튼 노출 기준:

| 버튼 유형 | ADMIN | ANALYST | VIEWER |
|---|---:|---:|---:|
| 조회 | O | O | O |
| 상세보기 | O | O | O |
| 등록/수정/저장 | O | O | X |
| 삭제 | O | X | X |
| 학습 실행 | O | O | X |
| 예측 실행 | O | O | X |
| Champion 지정 | O | X | X |
| 재학습 요청 | O | O | X |
| 다운로드 | O | O | O |

---

## 6. 전체 메뉴 구조

좌측 Sidebar는 1Depth/2Depth 구조로 구성한다.

```text
대시보드
 ├─ 열수요 예측 현황
 ├─ 예측 오차 현황
 └─ 모델 운영 상태

데이터 관리
 ├─ 데이터 소스 관리
 ├─ 데이터 매핑 설정
 └─ 데이터 품질 점검

Feature 관리
 ├─ Feature 목록
 ├─ Feature Set 관리
 └─ Feature 설정 상세

모델 관리
 ├─ 모델 학습 설정
 ├─ 모델 학습 실행
 ├─ 모델 성능 비교
 └─ 모델 Registry 관리

예측 관리
 ├─ 배치 예측 실행
 ├─ 예측 결과 조회
 └─ 실제값 매칭 및 오차 분석

운영 관리
 ├─ 파이프라인 실행 이력
 ├─ 성능 모니터링
 ├─ 드리프트 리포트
 └─ 재학습 후보 관리
```

---

## 7. 화면 목록 및 Route

| 화면ID | 메뉴 | 화면명 | Route | 권한 |
|---|---|---|---|---|
| SCR-001 | 대시보드 | 열수요 예측 현황 | `/dashboard` | ADMIN, ANALYST, VIEWER |
| SCR-002 | 데이터 관리 | 데이터 소스 관리 | `/data/sources` | ADMIN, ANALYST |
| SCR-003 | 데이터 관리 | 데이터 매핑 설정 | `/data/mappings` | ADMIN, ANALYST |
| SCR-004 | 데이터 관리 | 데이터 품질 점검 | `/data/quality` | ADMIN, ANALYST, VIEWER |
| SCR-005 | Feature 관리 | Feature 목록 | `/features` | ADMIN, ANALYST |
| SCR-006 | Feature 관리 | Feature Set 관리 | `/feature-sets` | ADMIN, ANALYST |
| SCR-007 | Feature 관리 | Feature 설정 상세 | `/feature-sets/:id` | ADMIN, ANALYST |
| SCR-008 | 모델 관리 | 모델 학습 설정 | `/models/training-configs` | ADMIN, ANALYST |
| SCR-009 | 모델 관리 | 모델 학습 실행 | `/models/training-runs` | ADMIN, ANALYST |
| SCR-010 | 모델 관리 | 모델 성능 비교 | `/models/performance` | ADMIN, ANALYST, VIEWER |
| SCR-011 | 모델 관리 | 모델 Registry 관리 | `/models/registry` | ADMIN, ANALYST |
| SCR-012 | 예측 관리 | 배치 예측 실행 | `/predictions/batch-runs` | ADMIN, ANALYST |
| SCR-013 | 예측 관리 | 예측 결과 조회 | `/predictions/results` | ADMIN, ANALYST, VIEWER |
| SCR-014 | 예측 관리 | 실제값 매칭 및 오차 분석 | `/predictions/evaluation` | ADMIN, ANALYST, VIEWER |
| SCR-015 | 운영 관리 | 파이프라인 실행 이력 | `/operations/pipeline-runs` | ADMIN, ANALYST, VIEWER |
| SCR-016 | 운영 관리 | 성능 모니터링 | `/operations/performance-monitoring` | ADMIN, ANALYST, VIEWER |
| SCR-017 | 운영 관리 | 드리프트 리포트 | `/operations/drift-reports` | ADMIN, ANALYST |
| SCR-018 | 운영 관리 | 재학습 후보 관리 | `/operations/retraining-candidates` | ADMIN, ANALYST |

---

## 8. 공통 레이아웃

모든 주요 화면은 다음 영역을 기본으로 한다.

```text
┌───────────────────────────────────────────────┐
│ Header: 로고, 페이지명, 사용자 정보, 알림       │
├───────────────┬───────────────────────────────┤
│ Sidebar       │ Breadcrumb                     │
│ - 메뉴        │ Page Title                     │
│ - 하위메뉴    │ Search Panel                   │
│               │ Summary Cards / Chart          │
│               │ Data Table                     │
│               │ Button Area / Pagination       │
└───────────────┴───────────────────────────────┘
```

### 8.1 Header

| 요소 | 설명 |
|---|---|
| Logo | THERMOps |
| 시스템명 | 열수요 예측 모델 운영 자동화 플랫폼 |
| 현재 사용자 | 예: 관리자 홍길동 |
| 권한 배지 | ADMIN/ANALYST/VIEWER |
| 알림 아이콘 | 실패 배치, 재학습 후보, 드리프트 감지 건수 표시 |
| 환경 표시 | DEV/STG/PROD 중 하나를 배지로 표시 |

### 8.2 Sidebar

- 현재 선택 메뉴 Active 상태 표시
- 메뉴 hover 상태 표시
- 권한이 없는 메뉴는 숨기거나 Disabled 처리
- 1Depth 클릭 시 하위 메뉴 펼침/접힘 표현

### 8.3 공통 검색 패널

화면별 검색 조건이 다르더라도 다음 구조를 유지한다.

| 요소 | 설명 |
|---|---|
| 기간 | Date Range Picker |
| 지사/권역 | SelectBox |
| 상태 | Multi Select |
| 모델명/버전 | SelectBox |
| 검색 버튼 | 조건 조회 |
| 초기화 버튼 | 검색 조건 초기화 |
| 다운로드 버튼 | 목록 다운로드 |

---

## 9. 공통 컴포넌트 정의

### 9.1 버튼

| 버튼명 | 스타일 | 사용 예 |
|---|---|---|
| Primary Button | 진한 Blue | 조회, 저장, 실행, 등록 |
| Secondary Button | Outline | 취소, 초기화, 닫기 |
| Danger Button | Red | 삭제, 강제 중단 |
| Ghost Button | Text only | 상세보기, 로그보기 |
| Disabled Button | Gray | 권한 없음, 실행 불가 |

### 9.2 테이블

모든 목록 테이블은 다음 요소를 포함한다.

- 체크박스 선택 영역
- 정렬 가능한 컬럼 헤더
- 상태 배지
- 행 단위 액션 버튼
- 페이지네이션
- Empty State
- Loading State
- Error State

### 9.3 Modal

Modal 공통 구성:

| 영역 | 설명 |
|---|---|
| Header | 제목, 닫기 X |
| Body | 확인 메시지 또는 입력 항목 |
| Footer | 확인, 취소, 닫기 버튼 |
| State | 기본, 로딩, 성공, 실패 |

### 9.4 Toast

Toast 공통 위치: 우측 상단  
표시 시간: 3초 표현  
종류: Success, Error, Warning, Info

---

## 10. API 연계 매트릭스

실제 API 호출은 Figma에서 구현하지 않지만, 버튼 클릭 후 상태 변화와 Toast 메시지로 API 결과를 표현한다.

| 기능 | Method | API 경로 예시 | 사용 화면 |
|---|---|---|---|
| 대시보드 요약 조회 | GET | `/api/v1/dashboard/summary` | SCR-001 |
| 데이터 소스 목록 조회 | GET | `/api/v1/data-sources` | SCR-002 |
| 데이터 소스 등록 | POST | `/api/v1/data-sources` | SCR-002 |
| 데이터 소스 수정 | PUT | `/api/v1/data-sources/{id}` | SCR-002 |
| 데이터 소스 삭제 | DELETE | `/api/v1/data-sources/{id}` | SCR-002 |
| 연결 테스트 | POST | `/api/v1/data-sources/{id}/test` | SCR-002 |
| 데이터 매핑 목록 조회 | GET | `/api/v1/data-mappings` | SCR-003 |
| 데이터 매핑 저장 | POST | `/api/v1/data-mappings` | SCR-003 |
| 데이터 품질 점검 실행 | POST | `/api/v1/data-quality/checks/run` | SCR-004 |
| Feature 목록 조회 | GET | `/api/v1/features` | SCR-005 |
| Feature Set 저장 | POST | `/api/v1/feature-sets` | SCR-006 |
| 모델 학습 설정 저장 | POST | `/api/v1/training-configs` | SCR-008 |
| 모델 학습 실행 | POST | `/api/v1/training-runs` | SCR-009 |
| 모델 성능 조회 | GET | `/api/v1/models/performance` | SCR-010 |
| 모델 Registry 조회 | GET | `/api/v1/models/registry` | SCR-011 |
| Champion 지정 | POST | `/api/v1/models/{id}/promote` | SCR-011 |
| 배치 예측 실행 | POST | `/api/v1/prediction-runs` | SCR-012 |
| 예측 결과 조회 | GET | `/api/v1/predictions` | SCR-013 |
| 실제값 매칭 | POST | `/api/v1/predictions/evaluate` | SCR-014 |
| 파이프라인 이력 조회 | GET | `/api/v1/pipeline-runs` | SCR-015 |
| 드리프트 리포트 조회 | GET | `/api/v1/drift-reports` | SCR-017 |
| 재학습 요청 | POST | `/api/v1/retraining-requests` | SCR-018 |

---

# 11. 화면별 상세 설계

---

## 11.1 SCR-001 대시보드 - 열수요 예측 현황

### 목적

전체 열수요 예측 운영 상태, 최근 예측 정확도, 모델 상태, 배치 실행 상태를 한 화면에서 확인한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| Summary Cards | 오늘 예측 대상 수, 평균 MAPE, 운영 모델 수, 실패 파이프라인 수 |
| Chart 1 | 시간대별 예측 열수요 vs 실제 열수요 라인 차트 |
| Chart 2 | 지사별 예측 오차 막대 차트 |
| Table 1 | 최근 예측 실행 목록 |
| Table 2 | 재학습 후보 목록 |
| Alert Panel | 드리프트 감지, 실패 배치, 성능 저하 경고 |

### 주요 더미 데이터

| 항목 | 예시 |
|---|---|
| 평균 MAPE | 4.8% |
| 운영 모델 | HDM-LGBM-v12 |
| 최근 예측 상태 | 성공 |
| 드리프트 감지 | 2건 |
| 재학습 후보 | 3건 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 예측 결과 상세 | SCR-013 예측 결과 조회 화면 이동 |
| 성능 상세 | SCR-016 성능 모니터링 화면 이동 |
| 실패 이력 보기 | SCR-015 파이프라인 실행 이력 화면 이동 |
| 재학습 후보 보기 | SCR-018 재학습 후보 관리 화면 이동 |
| 새로고침 | 현재 대시보드 Loading State 후 갱신 상태 표현 |

---

## 11.2 SCR-002 데이터 소스 관리

### 목적

열수요 실적, 기상, 달력, 운영 데이터의 원천 데이터 소스를 등록하고 연결 상태를 관리한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| 데이터 유형 | Select: 열수요, 기상, 달력, 운영 |
| 연결 방식 | Select: CSV, DB, API |
| 상태 | Select: 정상, 오류, 비활성 |
| 키워드 | Text Input |

### 목록 컬럼

| 컬럼 | 예시 |
|---|---|
| 데이터 소스 ID | DS-001 |
| 데이터 유형 | 열수요 실적 |
| 연결 방식 | DB |
| 원천명 | HEAT_DEMAND_HOURLY |
| 상태 | 정상 |
| 최근 적재 시각 | 2026-06-24 02:00 |
| 작업 | 상세, 수정, 연결 테스트, 삭제 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 조회 | 목록 Loading 후 갱신 |
| 신규 등록 | 데이터 소스 등록 패널 또는 등록 Modal 표시 |
| 수정 | 선택 행의 상세/수정 상태 표시 |
| 연결 테스트 | MOD-006 연결 테스트 결과 Modal 표시 |
| 삭제 | MOD-005 삭제 확인 Modal 표시 |
| 저장 | MSG-001 저장 완료 Toast 표시 |
| 취소 | 입력값 초기화 또는 Modal 닫기 |

---

## 11.3 SCR-003 데이터 매핑 설정

### 목적

원천 데이터 컬럼을 THERMOps 표준 스키마 컬럼에 매핑한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 데이터 소스 선택 | 데이터 소스 SelectBox |
| 원천 컬럼 목록 | 원천 컬럼명, 타입, 샘플값 |
| 표준 컬럼 매핑 | 표준 컬럼명 선택, 필수 여부, 변환 규칙 |
| 미리보기 | 변환 후 표준 데이터 샘플 |
| 검증 결과 | 필수 컬럼 누락, 타입 오류, 단위 오류 |

### 매핑 대상 표준 컬럼 예시

| 표준 컬럼 | 설명 |
|---|---|
| site_id | 지사/권역/공급구역 ID |
| measured_at | 측정 시각 |
| heat_demand | 열수요 실적값 |
| temperature | 외기온도 |
| humidity | 습도 |
| supply_temp | 공급온도 |
| return_temp | 회수온도 |
| flow_rate | 유량 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 데이터 소스 선택 | 원천 컬럼 목록 갱신 |
| 자동 매핑 | 컬럼명 유사도 기반 매핑 결과 표시 |
| 매핑 검증 | 필수 컬럼/타입 검증 결과 패널 표시 |
| 미리보기 | 변환 데이터 미리보기 테이블 표시 |
| 저장 | MSG-001 저장 완료 Toast 표시 |
| 초기화 | 매핑 설정 초기화 확인 후 초기화 |
| 취소 | 이전 저장 상태로 복원 |

---

## 11.4 SCR-004 데이터 품질 점검

### 목적

적재 데이터의 결측, 중복, 이상치, 시간 누락 여부를 점검한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| 데이터셋 | Select |
| 점검 기간 | Date Range Picker |
| 점검 유형 | 결측, 중복, 이상치, 시간 누락 |
| 지사/권역 | Select |

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 품질 점수 카드 | 총점, 결측률, 중복률, 이상치 건수 |
| 품질 추이 차트 | 기간별 품질 점수 |
| 점검 결과 목록 | 점검항목, 결과, 영향도, 조치상태 |
| 상세 결과 | 오류 데이터 샘플 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 품질 점검 실행 | 실행 확인 후 Loading State, 성공 Toast |
| 결과 다운로드 | 다운로드 Toast |
| 상세보기 | 점검 상세 Modal 표시 |
| 조치완료 처리 | 상태 배지 변경 |
| 파이프라인 이력 보기 | SCR-015 이동 |

---

## 11.5 SCR-005 Feature 목록

### 목적

모델 학습에 사용할 수 있는 원천 Feature와 파생 Feature를 관리한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| Feature 그룹 | 열수요 이력, 기상, 달력, 운영, 지역, 파생 |
| 사용 여부 | 사용, 미사용 |
| 파생 여부 | 원천, 파생 |
| 키워드 | Text |

### 목록 컬럼

| 컬럼 | 예시 |
|---|---|
| Feature ID | FEAT-001 |
| Feature 명 | lag_24h_demand |
| Feature 그룹 | 열수요 이력 |
| 파생 여부 | 파생 |
| 계산 방식 | 24시간 전 수요 |
| 사용 여부 | 사용 |
| 중요도 | 0.234 |
| 작업 | 상세, 수정, 비활성 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 신규 등록 | Feature 등록 Modal 표시 |
| 상세 | Feature 상세 Modal 표시 |
| 수정 | 수정 가능 상태 전환 |
| 비활성 | 비활성 확인 Modal |
| 저장 | 저장 완료 Toast |

---

## 11.6 SCR-006 Feature Set 관리

### 목적

모델 학습에 사용할 Feature 조합을 Feature Set으로 관리한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| Feature Set 목록 | 이름, 설명, Feature 수, 사용 모델, 생성일 |
| Feature 선택 영역 | 그룹별 Feature 체크박스 |
| Feature 중요도 미리보기 | 기존 학습 결과 기반 중요도 |
| 적용 대상 | 전체, 특정 지사/권역 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 신규 Feature Set | Feature Set 등록 영역 표시 |
| Feature 선택 | MOD-007 Feature Set 선택 또는 Feature 선택 Modal 표시 |
| 저장 | 저장 완료 Toast |
| 복사 | 기존 Feature Set 복사 후 신규 이름 입력 |
| 삭제 | 삭제 확인 Modal |
| 상세 | SCR-007 Feature 설정 상세 이동 |

---

## 11.7 SCR-007 Feature 설정 상세

### 목적

선택한 Feature Set의 상세 구성, 적용 대상, 결측 처리, 변환 규칙을 설정한다.

### 주요 입력 항목

| 항목 | 설명 |
|---|---|
| Feature Set 명 | 예: 기본_시간별_열수요_v1 |
| 설명 | Feature Set 설명 |
| 적용 대상 | 전체/지사/권역 |
| 결측 처리 | 직전값, 평균값, 0, 제외 |
| 정규화 여부 | 사용/미사용 |
| Feature 목록 | 사용 여부 체크 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 저장 | 저장 완료 Toast |
| 모델 학습 설정으로 이동 | SCR-008 이동 |
| Feature 추가 | Feature 선택 Modal |
| 삭제 | 삭제 확인 Modal |
| 목록 | SCR-006 이동 |

---

## 11.8 SCR-008 모델 학습 설정

### 목적

모델 학습 조건을 정의하고 저장한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| 학습 설정명 | Text |
| 모델 알고리즘 | Select |
| 예측 단위 | 시간별, 일별 |
| 상태 | 사용, 미사용 |

### 입력 항목

| 항목 | 예시 |
|---|---|
| 학습 설정명 | 시간별_LGBM_기본설정 |
| 학습 대상 | 전체 지사 |
| 학습 기간 | 최근 2년 |
| 검증 기간 | 최근 3개월 |
| 예측 단위 | 시간별 |
| 예측 기간 | D+1, D+7 |
| 알고리즘 | LightGBM, XGBoost, RandomForest, Baseline |
| 평가 지표 | MAE, RMSE, MAPE |
| Feature Set | 기본_시간별_열수요_v1 |
| 모델 등록 여부 | 학습 후 Registry 등록 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 조회 | 목록 갱신 |
| 신규 | 신규 입력 상태 표시 |
| Feature 선택 | MOD-007 Feature Set 선택 Modal 표시 |
| 저장 | 저장 완료 Toast |
| 학습 실행 | MOD-001 모델학습실행확인 Modal 표시 |
| 성능 보기 | SCR-010 모델 성능 비교 화면 이동 |
| 삭제 | MOD-005 삭제 확인 Modal |

---

## 11.9 SCR-009 모델 학습 실행

### 목적

저장된 학습 설정을 기반으로 모델 학습 파이프라인을 실행하고 이력을 확인한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 학습 실행 조건 | 학습 설정, 대상 지사, 실행 방식 |
| 실행 이력 목록 | 실행ID, 설정명, 상태, 시작/종료시각, 성능 |
| 실행 로그 패널 | 단계별 로그 |
| 단계 진행 표시 | 데이터 준비, Feature 생성, 학습, 평가, Registry 등록 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 학습 실행 | MOD-001 표시 |
| 실행 확인 | 실행 요청 완료 Toast 후 SCR-015 이동 또는 이력 추가 |
| 로그보기 | 학습 실행 로그 상세 표시 |
| 중단 | 중단 확인 Modal 표시 |
| 성능 비교 | SCR-010 이동 |
| Registry 보기 | SCR-011 이동 |

---

## 11.10 SCR-010 모델 성능 비교

### 목적

모델별/버전별 성능지표를 비교하고 운영 후보 모델을 검토한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| 모델명 | Select |
| 모델 버전 | Select |
| 평가 기간 | Date Range |
| 지사/권역 | Select |
| 평가 지표 | MAE, RMSE, MAPE |

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 성능 비교 차트 | 모델 버전별 MAPE/RMSE |
| 모델별 지표 카드 | 최고 성능 모델, 현재 Champion, 후보 모델 |
| 성능 목록 | 모델명, 버전, 알고리즘, MAE, RMSE, MAPE |
| Feature Importance | 주요 Feature 기여도 막대 차트 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 상세 | MOD-008 모델 상세 Modal 표시 |
| Registry 이동 | SCR-011 이동 |
| Champion 지정 | MOD-003 Champion 지정 확인 Modal 표시 |
| 결과 다운로드 | 다운로드 Toast |
| 예측 결과 보기 | SCR-013 이동 |

---

## 11.11 SCR-011 모델 Registry 관리

### 목적

MLflow Registry와 연계되는 모델 버전, 상태, Champion 모델을 관리한다.

### 목록 컬럼

| 컬럼 | 예시 |
|---|---|
| 모델명 | heat-demand-lgbm |
| 버전 | v12 |
| 알고리즘 | LightGBM |
| 상태 | CHAMPION |
| 등록일 | 2026-06-24 |
| MAPE | 4.8% |
| 생성 실행ID | TRN-20260624-001 |
| 작업 | 상세, Champion 지정, 비활성 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 상세 | MOD-008 모델 상세 Modal |
| Champion 지정 | MOD-003 표시 |
| 비활성 | 비활성 확인 Modal |
| 성능 비교 | SCR-010 이동 |
| 예측 실행 | SCR-012 이동 |

---

## 11.12 SCR-012 배치 예측 실행

### 목적

Champion 모델 또는 선택 모델을 기준으로 D+1/D+7 열수요 예측 배치를 실행한다.

### 입력 항목

| 항목 | 예시 |
|---|---|
| 예측 대상 | 전체 지사 또는 특정 지사 |
| 예측 기간 | D+1, D+7 |
| 예측 단위 | 시간별 |
| 모델 선택 | Champion 또는 특정 모델 버전 |
| 실행 방식 | 즉시 실행, 예약 실행 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 예측 실행 | MOD-002 배치예측실행확인 표시 |
| 실행 확인 | 실행 요청 완료 Toast 후 SCR-015 또는 SCR-013 이동 |
| 결과 보기 | SCR-013 이동 |
| 실행 이력 보기 | SCR-015 이동 |
| 초기화 | 입력값 초기화 |

---

## 11.13 SCR-013 예측 결과 조회

### 목적

생성된 열수요 예측 결과를 조회하고 실제값과 비교한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| 예측 대상 기간 | Date Range |
| 지사/권역 | Select |
| 모델명/버전 | Select |
| 예측 기간 | D+1, D+7 |
| 상태 | 성공, 실패, 대기 |

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 라인 차트 | 예측값 vs 실제값 |
| 오차 차트 | 시간대별 오차 |
| 예측 결과 테이블 | target_at, predicted_demand, actual_demand, error_rate |
| 모델 정보 카드 | 모델명, 버전, 알고리즘, 생성시각 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 조회 | 목록/차트 갱신 |
| 상세 | 예측 상세 Modal |
| 다운로드 | 다운로드 Toast |
| 실제값 매칭 | SCR-014 이동 |
| 성능 모니터링 | SCR-016 이동 |

---

## 11.14 SCR-014 실제값 매칭 및 오차 분석

### 목적

예측값과 실제 열수요 실적값을 매칭하고 오차를 분석한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 매칭 조건 | 예측 실행ID, 대상 기간, 지사 |
| 매칭 결과 요약 | 총 건수, 매칭 성공, 미매칭, 평균 오차 |
| 오차 분석 차트 | 시간대별/지사별 오차 |
| 미매칭 목록 | target_at, site_id, 사유 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 실제값 매칭 실행 | 확인 후 매칭 진행 상태 표시 |
| 오차 재계산 | Loading 후 결과 갱신 |
| 미매칭 상세 | 미매칭 상세 Modal |
| 결과 다운로드 | 다운로드 Toast |
| 예측 결과 보기 | SCR-013 이동 |

---

## 11.15 SCR-015 파이프라인 실행 이력

### 목적

Airflow/Dagster 기반 데이터 적재, 학습, 예측, 모니터링 파이프라인 실행 상태를 확인한다.

### 검색 조건

| 항목 | 타입 |
|---|---|
| 파이프라인 유형 | 데이터 적재, Feature 생성, 학습, 예측, 모니터링 |
| 실행 상태 | 대기, 실행중, 성공, 실패 |
| 기간 | Date Range |
| 실행ID | Text |

### 목록 컬럼

| 컬럼 | 예시 |
|---|---|
| 실행ID | RUN-20260624-001 |
| 파이프라인명 | daily_prediction_dag |
| 유형 | 예측 |
| 상태 | 성공 |
| 시작시각 | 2026-06-24 02:00 |
| 종료시각 | 2026-06-24 02:15 |
| 소요시간 | 15분 |
| 작업 | 상세, 로그보기, 재실행 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 상세 | MOD-009 파이프라인 실행 상세 Modal |
| 로그보기 | 로그 패널 표시 |
| 재실행 | 실행 확인 Modal 후 Toast |
| 실패만 보기 | 필터 적용 |
| 다운로드 | 실행 이력 다운로드 Toast |

---

## 11.16 SCR-016 성능 모니터링

### 목적

운영 모델의 예측 성능 추이를 모니터링한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 성능 지표 카드 | MAE, RMSE, MAPE, 성능 저하 여부 |
| 성능 추이 차트 | 일별/주별 MAPE |
| 모델별 비교 차트 | Champion vs Candidate |
| 알림 목록 | 임계치 초과, 성능 저하, 드리프트 감지 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 기간 조회 | 차트/목록 갱신 |
| 상세 분석 | SCR-014 이동 |
| 드리프트 리포트 | SCR-017 이동 |
| 재학습 후보 등록 | MOD-004 재학습 요청 확인 표시 |
| 리포트 다운로드 | 다운로드 Toast |

---

## 11.17 SCR-017 드리프트 리포트

### 목적

최근 입력 데이터와 학습 기준 데이터의 분포 차이를 점검하고 드리프트 여부를 확인한다.

### 주요 구성

| 영역 | 구성요소 |
|---|---|
| 드리프트 요약 카드 | 감지 Feature 수, 전체 Feature 수, 위험도 |
| Feature별 Drift Table | Feature명, Drift Score, 상태 |
| Drift Chart | 기준분포 vs 최근분포 |
| 리포트 목록 | 생성일, 대상 기간, 모델 버전 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 리포트 생성 | 생성 확인 후 Loading, 완료 Toast |
| 상세 | Drift 상세 Modal |
| 재학습 요청 | MOD-004 표시 |
| 다운로드 | 다운로드 Toast |
| 성능 모니터링 | SCR-016 이동 |

---

## 11.18 SCR-018 재학습 후보 관리

### 목적

성능 저하, 드리프트 감지, 운영자 판단으로 발생한 재학습 후보를 관리한다.

### 목록 컬럼

| 컬럼 | 예시 |
|---|---|
| 후보ID | RTC-001 |
| 발생 사유 | MAPE 임계치 초과 |
| 모델명/버전 | heat-demand-lgbm v12 |
| 지사/권역 | 전체 |
| 위험도 | 높음 |
| 상태 | 검토중 |
| 생성일 | 2026-06-24 |
| 작업 | 상세, 재학습 요청, 보류, 제외 |

### 버튼 이벤트

| 버튼 | 동작 |
|---|---|
| 상세 | 후보 상세 Modal |
| 재학습 요청 | MOD-004 표시 |
| 보류 | 상태를 보류로 변경 후 Toast |
| 제외 | 제외 확인 Modal |
| 모델 학습 실행 | SCR-009 이동 |

---

# 12. 팝업/다이얼로그 상세 정의

## 12.1 MOD-001 모델학습실행확인

| 항목 | 내용 |
|---|---|
| 표시 조건 | 모델 학습 설정 또는 모델 학습 실행 화면에서 학습 실행 클릭 |
| 제목 | 모델 학습을 실행하시겠습니까? |
| 본문 | 학습 설정명, 학습 대상, 학습 기간, 알고리즘, Feature Set, 모델 등록 여부 표시 |
| 버튼 | 실행, 취소 |
| 실행 클릭 | 실행 요청 완료 Toast 표시 후 SCR-015 파이프라인 실행 이력 이동 |
| 취소 클릭 | Modal 닫기 |

## 12.2 MOD-002 배치예측실행확인

| 항목 | 내용 |
|---|---|
| 표시 조건 | 배치 예측 실행 화면에서 예측 실행 클릭 |
| 제목 | 배치 예측을 실행하시겠습니까? |
| 본문 | 예측 대상, 예측 기간, 모델 버전, 실행 방식 표시 |
| 버튼 | 실행, 취소 |
| 실행 클릭 | 실행 요청 완료 Toast 후 SCR-015 또는 SCR-013 이동 |
| 취소 클릭 | Modal 닫기 |

## 12.3 MOD-003 Champion지정확인

| 항목 | 내용 |
|---|---|
| 표시 조건 | 모델 성능 비교 또는 Registry에서 Champion 지정 클릭 |
| 제목 | Champion 모델로 지정하시겠습니까? |
| 본문 | 현재 Champion과 신규 Champion 후보 비교 표시 |
| 버튼 | 지정, 취소 |
| 지정 클릭 | MSG-001 저장 완료 Toast, 모델 상태 배지 CHAMPION으로 변경 |
| 취소 클릭 | Modal 닫기 |

## 12.4 MOD-004 재학습요청확인

| 항목 | 내용 |
|---|---|
| 표시 조건 | 성능 모니터링, 드리프트 리포트, 재학습 후보 관리에서 재학습 요청 클릭 |
| 제목 | 재학습을 요청하시겠습니까? |
| 본문 | 발생 사유, 대상 모델, 대상 기간, 권장 조치 표시 |
| 버튼 | 요청, 취소 |
| 요청 클릭 | 재학습 후보 상태를 요청완료로 변경, Toast 표시 |
| 취소 클릭 | Modal 닫기 |

## 12.5 MOD-005 삭제확인

| 항목 | 내용 |
|---|---|
| 표시 조건 | 삭제 버튼 클릭 |
| 제목 | 삭제하시겠습니까? |
| 본문 | 삭제 대상명, 삭제 후 복구 불가 안내 |
| 버튼 | 삭제, 취소 |
| 삭제 클릭 | 삭제 완료 Toast, 목록 갱신 |
| 취소 클릭 | Modal 닫기 |

## 12.6 MOD-006 데이터소스연결테스트결과

| 항목 | 내용 |
|---|---|
| 표시 조건 | 데이터 소스 관리 화면에서 연결 테스트 클릭 |
| 제목 | 데이터 소스 연결 테스트 결과 |
| 본문 | 연결 성공/실패, 응답시간, 오류 메시지, 샘플 데이터 수 |
| 버튼 | 닫기 |
| 닫기 클릭 | Modal 닫기 |

## 12.7 MOD-007 FeatureSet선택

| 항목 | 내용 |
|---|---|
| 표시 조건 | 모델 학습 설정에서 Feature 선택 클릭 |
| 제목 | Feature Set 선택 |
| 본문 | Feature Set 목록, 설명, Feature 수, 최근 사용 여부 |
| 버튼 | 선택, 취소 |
| 선택 클릭 | 선택한 Feature Set이 부모 화면에 반영됨 |
| 취소 클릭 | Modal 닫기 |

## 12.8 MOD-008 모델상세

| 항목 | 내용 |
|---|---|
| 표시 조건 | 모델 상세 버튼 클릭 |
| 제목 | 모델 상세 정보 |
| 본문 | 모델명, 버전, 알고리즘, 성능 지표, Feature Set, 학습 실행ID, 등록일 |
| 버튼 | 닫기, Registry 보기 |
| Registry 보기 클릭 | SCR-011 이동 |
| 닫기 클릭 | Modal 닫기 |

## 12.9 MOD-009 파이프라인실행상세

| 항목 | 내용 |
|---|---|
| 표시 조건 | 실행 이력 상세 클릭 |
| 제목 | 파이프라인 실행 상세 |
| 본문 | 실행ID, DAG/Job명, Task별 상태, 시작/종료시각, 로그 |
| 버튼 | 로그 다운로드, 닫기 |
| 로그 다운로드 클릭 | 다운로드 Toast |
| 닫기 클릭 | Modal 닫기 |

## 12.10 MOD-010 권한없음안내

| 항목 | 내용 |
|---|---|
| 표시 조건 | 권한 없는 버튼 또는 메뉴 접근 |
| 제목 | 권한이 없습니다 |
| 본문 | 해당 기능을 실행할 권한이 없습니다. 관리자에게 문의하세요. |
| 버튼 | 확인 |
| 확인 클릭 | Modal 닫기 |

---

# 13. 버튼 이벤트 공통 규칙

| 버튼 유형 | 기본 동작 |
|---|---|
| 조회 | 현재 화면 Loading State 표시 후 목록/차트 갱신 |
| 신규 | 등록 Form 또는 Modal 표시 |
| 저장 | 필수값 검증 후 저장 완료 Toast 표시 |
| 삭제 | 삭제 확인 Modal 표시 |
| 실행 | 실행 확인 Modal 표시 |
| 확인 | API 성공 가정 후 Toast 또는 화면 이동 |
| 취소 | Modal 닫기 또는 이전 화면 이동 |
| 상세 | 상세 Modal 표시 |
| 다운로드 | 다운로드 완료 Toast 표시 |
| 재실행 | 실행 확인 Modal 표시 |
| Champion 지정 | Champion 지정 확인 Modal 표시 |
| 재학습 요청 | 재학습 요청 확인 Modal 표시 |
| 권한 없음 | 권한 없음 Modal 표시 또는 Disabled 상태 표시 |

---

# 14. 주요 Prototype Flow

## 14.1 메뉴 이동 흐름

```text
Sidebar 대시보드 클릭
 → SCR-001

Sidebar 데이터 관리 > 데이터 소스 관리 클릭
 → SCR-002

Sidebar 데이터 관리 > 데이터 매핑 설정 클릭
 → SCR-003

Sidebar 데이터 관리 > 데이터 품질 점검 클릭
 → SCR-004

Sidebar Feature 관리 > Feature 목록 클릭
 → SCR-005

Sidebar Feature 관리 > Feature Set 관리 클릭
 → SCR-006

Sidebar 모델 관리 > 모델 학습 설정 클릭
 → SCR-008

Sidebar 모델 관리 > 모델 학습 실행 클릭
 → SCR-009

Sidebar 모델 관리 > 모델 성능 비교 클릭
 → SCR-010

Sidebar 모델 관리 > 모델 Registry 관리 클릭
 → SCR-011

Sidebar 예측 관리 > 배치 예측 실행 클릭
 → SCR-012

Sidebar 예측 관리 > 예측 결과 조회 클릭
 → SCR-013

Sidebar 운영 관리 > 파이프라인 실행 이력 클릭
 → SCR-015
```

## 14.2 모델 학습 실행 흐름

```text
SCR-008 모델 학습 설정
 → Feature 선택 버튼
 → MOD-007 FeatureSet선택
 → 선택 버튼
 → SCR-008에 Feature Set 반영
 → 저장 버튼
 → MSG-001 저장완료Toast
 → 학습 실행 버튼
 → MOD-001 모델학습실행확인
 → 실행 버튼
 → MSG-002 실행요청완료Toast
 → SCR-015 파이프라인 실행 이력
 → 학습 실행 상세 클릭
 → MOD-009 파이프라인실행상세
```

## 14.3 모델 성능 비교 및 Champion 지정 흐름

```text
SCR-010 모델 성능 비교
 → 모델 상세 버튼
 → MOD-008 모델상세
 → Registry 보기 버튼
 → SCR-011 모델 Registry 관리
 → Champion 지정 버튼
 → MOD-003 Champion지정확인
 → 지정 버튼
 → MSG-001 저장완료Toast
 → SCR-011에서 상태 배지 CHAMPION 표시
```

## 14.4 배치 예측 실행 흐름

```text
SCR-012 배치 예측 실행
 → 예측 대상/기간/모델 선택
 → 예측 실행 버튼
 → MOD-002 배치예측실행확인
 → 실행 버튼
 → MSG-002 실행요청완료Toast
 → SCR-015 파이프라인 실행 이력
 → 예측 결과 보기 버튼
 → SCR-013 예측 결과 조회
```

## 14.5 실제값 매칭 및 오차 분석 흐름

```text
SCR-013 예측 결과 조회
 → 실제값 매칭 버튼
 → SCR-014 실제값 매칭 및 오차 분석
 → 실제값 매칭 실행 버튼
 → Loading State
 → MSG-002 실행요청완료Toast
 → 매칭 결과/오차 차트 갱신
```

## 14.6 드리프트 감지 및 재학습 요청 흐름

```text
SCR-016 성능 모니터링
 → 드리프트 리포트 버튼
 → SCR-017 드리프트 리포트
 → 재학습 요청 버튼
 → MOD-004 재학습요청확인
 → 요청 버튼
 → MSG-002 실행요청완료Toast
 → SCR-018 재학습 후보 관리
```

---

# 15. Empty/Error/Loading State

각 목록/차트 화면은 다음 상태를 포함해야 한다.

| 상태 | 표시 내용 |
|---|---|
| Loading | Skeleton 또는 Spinner, "데이터를 불러오는 중입니다." |
| Empty | "조회된 데이터가 없습니다." |
| Error | "데이터 조회 중 오류가 발생했습니다." |
| Permission Denied | "해당 기능에 접근할 권한이 없습니다." |
| Disabled | 버튼 비활성 및 Tooltip 표시 |

---

# 16. 더미 데이터 기준

Figma 화면에는 실제 운영 데이터를 연상할 수 있는 더미 데이터를 넣는다.

## 16.1 지사/권역 예시

| site_id | site_name |
|---|---|
| SITE-001 | 중앙지사 |
| SITE-002 | 강남지사 |
| SITE-003 | 분당지사 |
| SITE-004 | 고양지사 |
| SITE-005 | 대전지사 |

## 16.2 모델 예시

| 모델명 | 버전 | 알고리즘 | 상태 |
|---|---|---|---|
| heat-demand-lgbm | v12 | LightGBM | CHAMPION |
| heat-demand-xgb | v07 | XGBoost | CANDIDATE |
| heat-demand-baseline | v03 | Baseline | REGISTERED |

## 16.3 성능 예시

| 지표 | 값 |
|---|---|
| MAE | 12.4 |
| RMSE | 18.7 |
| MAPE | 4.8% |

## 16.4 파이프라인 예시

| 실행ID | 파이프라인명 | 상태 |
|---|---|---|
| RUN-20260624-001 | daily_prediction_dag | SUCCESS |
| RUN-20260624-002 | model_training_dag | RUNNING |
| RUN-20260624-003 | drift_monitoring_dag | FAILED |

---

# 17. Figma 제작 체크리스트

Figma 작업 완료 후 반드시 `12_Coverage_Checklist` Page에 아래 표를 생성하고 체크 상태를 표시한다.

| 검수 항목 | 완료 여부 |
|---|---|
| 전체 Page 구조 생성 |
| 전체 메뉴 구조 생성 |
| Sidebar 1Depth/2Depth 구성 |
| SCR-001 ~ SCR-018 전체 화면 생성 |
| MOD-001 ~ MOD-010 전체 Modal 생성 |
| MSG-001 ~ MSG-005 전체 Toast 생성 |
| 공통 컴포넌트 페이지 생성 |
| 데이터 테이블 컴포넌트 생성 |
| 상태 배지 컴포넌트 생성 |
| 검색 패널 컴포넌트 생성 |
| 대시보드 차트 구성 |
| 데이터 관리 화면 구성 |
| Feature 관리 화면 구성 |
| 모델 관리 화면 구성 |
| 예측 관리 화면 구성 |
| 운영 관리 화면 구성 |
| 주요 버튼 이벤트 연결 |
| 메뉴 클릭 화면 이동 연결 |
| 학습 실행 Flow 연결 |
| 배치 예측 실행 Flow 연결 |
| Champion 지정 Flow 연결 |
| 재학습 요청 Flow 연결 |
| 삭제 확인 Modal 연결 |
| 저장 완료 Toast 연결 |
| 권한 없음 Modal 연결 |
| Empty State 생성 |
| Error State 생성 |
| Loading State 생성 |
| Prototype Flow Map 생성 |

---

# 18. 누락 방지 지시사항

Figma 작업자는 다음 지시를 반드시 지켜야 한다.

1. 화면을 일부만 만들지 말고 SCR-001부터 SCR-018까지 모두 생성한다.
2. Modal은 화면 내부 요소가 아니라 별도 Frame 또는 Overlay로 생성한다.
3. 실행, 삭제, Champion 지정, 재학습 요청은 반드시 확인 Modal을 거친다.
4. 주요 버튼은 단순 장식으로 두지 말고 Prototype interaction을 연결한다.
5. 모든 화면에는 검색 영역, 목록 또는 차트 영역, 버튼 영역을 명확히 배치한다.
6. 권한이 없는 기능은 Disabled 또는 권한 없음 Modal로 표현한다.
7. 주요 결과 화면에는 Empty/Error/Loading 상태를 함께 표현한다.
8. 모델 학습과 배치 예측은 실행 이력 화면으로 연결한다.
9. 모델 성능 비교는 모델 Registry와 연결한다.
10. 드리프트 리포트와 성능 모니터링은 재학습 후보 관리로 연결한다.
11. Figma 마지막 Page에 Coverage Checklist를 반드시 생성한다.
12. Figma 마지막 Page에 Prototype Flow Map을 반드시 생성한다.

---

# 19. Figma 생성용 실행 프롬프트

아래 프롬프트는 Figma AI 또는 Figma Make/생성 기능에 본 MD 문서와 함께 전달한다.

```text
첨부한 THERMOps_Figma_UI_Master_Spec.md 문서를 기준으로 THERMOps: 열수요 예측 모델 운영 자동화 플랫폼의 정식 UI 설계 및 인터랙티브 프로토타입을 생성해 주세요.

이번 작업은 샘플 UI나 예시 화면이 아니라, 설계문서에 정의된 메뉴, 화면, 버튼, 팝업, 다이얼로그, 화면 이동, 상태 변화까지 반영한 정식 UI 프로토타입 제작입니다.

다음 기준을 반드시 지켜 주세요.

1. 전체 메뉴 구조를 기준으로 모든 화면을 빠짐없이 생성해 주세요.
2. 각 화면은 설계문서의 화면ID와 화면명을 Frame 이름에 포함해 주세요.
3. 대시보드, 데이터 관리, Feature 관리, 모델 관리, 예측 관리, 운영 관리 메뉴를 좌측 사이드바에 구성해 주세요.
4. 각 메뉴 클릭 시 해당 화면으로 이동하도록 Prototype 연결을 설정해 주세요.
5. 모든 주요 버튼은 다음 중 하나 이상의 동작을 가져야 합니다.
   - 다른 화면으로 이동
   - 다이얼로그 또는 팝업 표시
   - 확인/취소 상태 처리
   - 성공/실패 Toast 메시지 표시
   - Disabled 상태 표현
6. 버튼을 단순 장식으로 두지 말고, 설계문서의 버튼 이벤트 정의에 따라 Prototype interaction을 연결해 주세요.
7. 등록, 수정, 삭제, 실행, 저장, 취소, 조회, 다운로드, 상세보기, Champion 지정, 재학습 요청 버튼은 반드시 동작을 정의해 주세요.
8. 팝업과 다이얼로그는 별도 Frame 또는 Overlay로 생성하고, 확인/취소/닫기 버튼의 동작까지 연결해 주세요.
9. 모델 학습 실행, 배치 예측 실행, Champion 지정, 재학습 요청, 삭제 작업은 반드시 확인 다이얼로그를 거치도록 해 주세요.
10. API 호출 자체는 실제 구현하지 않지만, 버튼 클릭 후 화면 상태 변화나 Toast 메시지로 API 호출 결과를 표현해 주세요.
11. 공통 컴포넌트 페이지를 만들어 주세요.
12. 화면은 운영 시스템 느낌의 엔터프라이즈 웹 UI로 구성해 주세요.
13. 색상은 열에너지/운영 플랫폼 느낌이 나도록 안정적인 블루/그린 계열을 기본으로 하고, 경고/실패 상태는 명확히 구분해 주세요.
14. 모든 화면에는 실제 운영 데이터를 연상할 수 있는 더미 데이터를 넣어 주세요.
15. 차트가 필요한 화면에는 라인 차트, 막대 차트, 카드형 지표를 배치해 주세요.
16. 마지막에 Coverage Checklist 페이지를 생성해 주세요.
17. 마지막에 Prototype Flow Map 페이지를 생성해 주세요.
18. 작업 완료 후 누락된 화면, 연결되지 않은 버튼, 생성되지 않은 팝업이 없도록 자체 검수 결과를 Coverage Checklist 페이지에 표시해 주세요.
```

---

# 20. 최종 산출물 기준

Figma 작업 완료 후 산출물은 다음 기준을 만족해야 한다.

| 산출물 | 기준 |
|---|---|
| UI Frames | 모든 화면ID에 해당하는 Frame 존재 |
| Components | 공통 컴포넌트 Page에 재사용 컴포넌트 존재 |
| Modals | 주요 확인/상세/권한 Modal 존재 |
| Toasts | 성공/실패/경고/정보 Toast 존재 |
| Prototype | 주요 업무 흐름 연결 |
| Coverage Checklist | 누락 여부 검수 표 존재 |
| Flow Map | 화면 이동 및 업무 흐름 시각화 존재 |

---

문서 종료.
