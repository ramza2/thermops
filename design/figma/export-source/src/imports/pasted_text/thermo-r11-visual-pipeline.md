Figma Make 작업 요청: THERMOps R11 Visual Pipeline Studio v2 화면을 기존 Make 프로토타입에 추가해 주세요.

대상 Figma Make URL:
https://www.figma.com/make/0ou4ygTitcw7uW75yWX5rb/THERMOps?p=f&t=IzxdP9ukovUGr67a-0

중요:
- 이 작업은 Figma Design Frame 생성이 아니라, Figma Make의 React 프로토타입 화면 추가 작업입니다.
- 기존 SCR-001~SCR-018 화면은 삭제하거나 덮어쓰지 마세요.
- 기존 화면은 Legacy/Reference로 유지하고, Visual Pipeline Studio 화면을 신규 Screen으로 추가해 주세요.
- 기존 Sidebar/Header/Card/Table/Button 스타일과 전체 THERMOps 톤을 최대한 유지해 주세요.
- 로컬 프로젝트의 design/figma/export-source 폴더나 Cursor 코드베이스를 직접 안다고 가정하지 마세요.
- 아래에 명시한 R11-S1/S2/S3 기준을 기능 요구사항으로 사용해 주세요.
- 이 작업 결과는 실제 제품 코드가 아니라 UI/UX 비교용 Make 프로토타입입니다.

목표:
- 기존 THERMOps Make 프로토타입에 `Visual Pipeline Studio` 메뉴와 화면을 추가합니다.
- 화면 목적은 REST API 데이터 적재 파이프라인을 노드와 연결선으로 구성하는 UI를 시각적으로 검토하는 것입니다.
- Design 파일의 정적 와이어프레임과 비교하기 위해 Make에서는 좀 더 실제 화면처럼 보이는 인터랙티브 프로토타입을 만듭니다.
- 단, 실제 API 호출/DB 연동/React Flow 구현은 하지 않아도 됩니다.
- 화면 상태와 UI 구조를 표현하는 mock data 기반 프로토타입이면 충분합니다.

현재 R11 구현 기준:
1. R11-S1 Component Catalog API 완료
   - ACTIVE 컴포넌트:
     - VP_REST_API_SOURCE
     - VP_TRANSFORM
     - VP_UPSERT_LOAD
     - VP_CRON_SCHEDULE
   - DISABLED 컴포넌트:
     - VP_NOTIFICATION
     - VP_DATA_QUALITY
     - VP_FEATURE_BUILD
     - VP_MODEL_TRAINING
     - VP_BATCH_PREDICTION
     - VP_FORECAST_PROVIDER
     - VP_DB_SOURCE
     - VP_CSV_SOURCE

2. R11-S2 Graph 저장 API 완료
   - pipeline_kind: VISUAL_DATA_LOAD
   - template_id: PT-VISUAL-DATA-LOAD
   - current_sync_status: NOT_COMPILED
   - graph 저장: current_graph_json
   - version 저장: snapshot_json.graph

3. R11-S3 예정
   - React Flow Canvas PoC
   - 4개 MVP 노드 추가/이동/삭제/연결
   - 좌측 Component Palette
   - 중앙 Canvas
   - 우측 Node Inspector
   - 하단 Graph Status Panel
   - 아직 compile/run/semantic validation/node 상세 설정 form은 제외

Make에 추가할 화면 구조:
- 신규 Sidebar 메뉴:
  - 그룹 또는 메뉴명: `Visual Pipeline Studio`
  - 기존 `작업 흐름 구성` 또는 Pipeline Builder와 구분되도록 설명 추가
- 신규 Screen:
  - `SCR-R11-001 Visual Pipeline 목록`
  - `SCR-R11-002 Visual Pipeline Studio Canvas`
  - 가능하면 한 화면 안에서 목록/Canvas 전환을 탭 또는 상태로 표현해도 됩니다.

1. Visual Pipeline 목록 화면

화면 제목:
`Visual Pipeline Studio`

설명:
`REST API 데이터 적재 파이프라인을 노드와 연결선으로 구성합니다.`

필수 UI:
- `새 Visual Pipeline` 버튼
- `새로고침` 버튼
- 검색 input
- status select
- 목록 table 또는 card list

목록 mock data:
- `ASOS 관측 기상 적재 파이프라인`
  - status: DRAFT
  - current_sync_status: NOT_COMPILED
  - nodes: 4
  - edges: 3
- `열수요 API 적재 파이프라인`
  - status: DRAFT
  - current_sync_status: NOT_COMPILED
  - nodes: 3
  - edges: 2

목록 컬럼:
- pipeline_name
- description
- status
- current_sync_status
- node_count
- edge_count
- updated_at
- 열기
- archive

빈 상태도 함께 표현 가능하면 좋습니다:
`아직 생성된 Visual Pipeline이 없습니다. 새 Visual Pipeline을 만들어 REST API 적재 흐름을 구성해 보세요.`

2. Studio Canvas 화면

기본 레이아웃:
- 상단 Header/Toolbar
- 좌측 Component Palette
- 중앙 Canvas
- 우측 Node Inspector
- 하단 Graph Status Panel

Toolbar 버튼:
- 목록
- 신규
- 저장
- 버전 저장
- Fit View

비활성/Coming Soon 버튼:
- Compile
- Run Now
- 스케줄 활성화

주의:
- Compile/Run Now는 실제 기능이 아니므로 비활성 또는 Coming Soon으로 표시합니다.
- 배포 버튼은 만들지 않습니다.

3. Component Palette

ACTIVE Nodes:
- REST API Source
  - VP_REST_API_SOURCE
  - 설명: REST API 호출 결과를 원천 rows로 가져옵니다.
- Transform
  - VP_TRANSFORM
  - 설명: 원천 rows를 적재 가능한 형태로 변환합니다.
- Upsert Load
  - VP_UPSERT_LOAD
  - 설명: 변환된 rows를 표준 데이터셋/대상 테이블에 적재합니다.
- CRON Schedule
  - VP_CRON_SCHEDULE
  - 설명: 주기적으로 Source를 트리거하는 일정을 정의합니다.

DISABLED Nodes:
- Notification
- Data Quality
- Feature Build
- Model Training
- Batch Prediction
- Forecast Provider
- DB Source
- CSV Source

DISABLED 표현:
- 회색 카드
- Coming later badge
- Canvas 추가 불가 느낌
- tooltip 또는 짧은 disabled_reason

4. Canvas 시각화

Canvas에 아래 흐름을 시각적으로 배치해 주세요.

`CRON Schedule` → `REST API Source` → `Transform` → `Upsert Load`

Edge label:
- trigger
- raw_rows
- transformed_rows

Canvas 표현:
- grid background
- 노드 카드
- 연결선
- 선택된 노드 강조
- MiniMap/Controls 비슷한 UI 표현
- 실제 React Flow 기능 구현이 어려우면 정적 연결선/카드 배치로 표현해도 됩니다.

노드 카드 공통 표시:
- 노드 타입명
- component_type
- 짧은 설명
- input/output port
- status badge
- 삭제 또는 더보기 icon

노드별 포트:
- VP_REST_API_SOURCE
  - input: trigger
  - output: raw_rows
- VP_TRANSFORM
  - input: input_rows
  - output: transformed_rows
- VP_UPSERT_LOAD
  - input: input_rows
  - output: load_result
- VP_CRON_SCHEDULE
  - output: schedule_config

5. Node Inspector

선택된 노드가 없을 때:
`노드를 선택하면 상세 정보가 표시됩니다.`

선택된 노드 예시는 REST API Source로 구성:
- node id
- label
- component_type
- category
- status
- input ports
- output ports
- config placeholder JSON
- label 수정 input
- 삭제 버튼

REST API Source placeholder config:
```json
{
  "data_source_id": "미설정",
  "endpoint_path": "미설정",
  "http_method": "GET"
}
```

S3에서 제외할 상세 Form:
- data_source_id 선택
- API operation 선택
- target_table 선택
- cron expression 검증
- transform 상세 설정
- write policy 상세 Form
- compile/run 버튼

6. Bottom Graph Status Panel

표시:
- pipeline_id
- pipeline_kind: VISUAL_DATA_LOAD
- template_id: PT-VISUAL-DATA-LOAD
- current_sync_status: NOT_COMPILED
- node_count: 4
- edge_count: 3
- dirty/saved 상태
- 마지막 저장 시간
- 오류 메시지 영역
- Graph JSON preview

Graph JSON preview:
```json
{
  "nodes": 4,
  "edges": 3,
  "viewport": {
    "x": 0,
    "y": 0,
    "zoom": 1
  }
}
```

7. New Pipeline Modal

필드:
- pipeline_name
- description
- 기본 graph template

Template 후보:
- Blank
- REST → Transform → Upsert
- CRON → REST → Transform → Upsert

버튼:
- 취소
- 생성

생성 후 Canvas 화면으로 이동하는 흐름을 표현합니다.

8. Save / Version Flow

표현:
- 저장 버튼 클릭 시 저장 중/저장됨 상태
- 버전 저장 버튼 클릭 시 toast:
  - `현재 Graph가 version snapshot으로 저장되었습니다.`
- 간단한 Version 목록 drawer 또는 modal:
  - version_no
  - created_at
  - change_summary
  - node_count
  - edge_count

9. Error / Loading / Empty 상태

가능하면 아래 상태를 화면 안에 표현해 주세요.
- 목록 loading
- 목록 error
- catalog loading
- catalog error
- Canvas empty
- Canvas save failed
- selected node none
- unsaved changes
- disabled component hover

오류 메시지 예:
- `컴포넌트 카탈로그를 불러오지 못했습니다.`
- `Visual Pipeline 목록을 불러오지 못했습니다.`
- `Graph 저장에 실패했습니다.`
- `현재 단계에서는 Compile/Run을 지원하지 않습니다.`

10. Make 프로토타입 구현 시 주의사항

- 기존 SCR-001~SCR-018 화면은 유지합니다.
- 기존 전체 App 구조가 단일 App.tsx라면 신규 Screen state를 추가하는 방식으로 구현해 주세요.
- 기존 Sidebar 메뉴 스타일을 재사용합니다.
- 기존 PageHeader, Card, Table, Button 스타일을 재사용합니다.
- 외부 API 호출은 하지 말고 mock data로 구성해도 됩니다.
- 실제 React Flow 패키지를 설치하지 않아도 됩니다. Make 프로토타입에서는 정적/가짜 Canvas UI로 충분합니다.
- 실제 제품 코드와 혼동되지 않게 주석 또는 화면 내 annotation으로 `Prototype only` 또는 `R11-S3 UI Draft`를 표시해 주세요.
- 가능한 경우 결과 화면이 너무 저충실도 회색 박스만 되지 않도록 기존 THERMOps UI 톤을 살려 주세요.

11. 완료 보고 형식

완료 후 아래 형식으로 보고해 주세요.

1. 추가한 Screen/Menu 목록
2. 기존 Make 화면에서 재사용한 스타일/컴포넌트
3. 구현한 Visual Pipeline Studio UI 범위
4. 목록 화면 구성
5. Canvas 화면 구성
6. Component Palette / Node Inspector / Status Panel 구성
7. Save/Version/Modal/Error 상태 구성
8. 실제 구현하지 않은 항목
9. R11-S3 Cursor 구현 시 참고할 수 있는 부분
10. Make URL에서 확인해야 할 화면
