# THERMOps R11-S5-0 Visual Pipeline Inspector Config Form 설계

> **문서 유형**: 설계 (구현 없음)  
> **작성 기준**: `master` @ R11-S4-3 (`2905aa0`) 완료 시점  
> **범위**: Visual Pipeline Studio Node Inspector Config Form — 저장 구조, Form schema, validation 확장, compile 연계, 구현 로드맵

---

## 1. 배경과 목적

### 1.1 배경

R11-S1~S4까지 Visual Pipeline Studio는 다음을 완료했다.

| 단계 | 내용 |
|------|------|
| S1 | Component Catalog (ACTIVE 4종, ports, config_schema, connection rules) |
| S2 | Graph CRUD / version snapshot (`current_graph_json`, `snapshot_json.graph`) |
| S3 | React Flow Canvas, Inspector **placeholder**, 저장/로드 round-trip |
| S4-0 | 저장 vs 버전 저장 UX 분리 |
| S4-1/2 | Graph Validation (topology/port/handle), handle metadata round-trip |
| S4-3 | Studio 상세 route E2E |

현재 Inspector는 노드 label·ports·**placeholder JSON**만 표시하며, `node.data.config`를 편집·저장하지 않는다.  
`flowToGraph`는 이미 `node.data.config`를 graph JSON에 포함하지만, Form/UI/validation/compile 연계는 미구현이다.

### 1.2 목적

R11-S5부터 각 노드의 **설정값(config)** 을 Inspector에서 입력·저장할 수 있어야 compile/run으로 이어진다.  
Inspector Config Form은 Visual Pipeline graph가 **실제 Data Load Pipeline**으로 변환되기 전의 핵심 입력 계층이다.

**S5-0 산출물**: 구현 없이 설계 문서로 다음을 확정한다.

- config 저장 위치 및 JSON shape
- MVP 4노드별 config 필드 범위 (S1 catalog 정렬)
- Form schema 구조 및 UI/UX
- Graph Validation에 config validation 확장 방향
- R11-S6 compile target 매핑
- S5-1~ 후속 구현 단위 분할

---

## 2. 설계 원칙

| # | 원칙 |
|---|------|
| P1 | Graph 안에 node config를 저장한다 (`node.data.config`). |
| P2 | `values` 키는 **S1 catalog `config_schema[].name`** 과 1:1 정렬한다. |
| P3 | **secret 원문** (API key, token, password)은 graph에 저장하지 않는다. `credential_ref` / `credential_id` 참조만 허용. |
| P4 | config 없는 legacy graph도 정상 load·편집 가능 (`values: {}`, schema_version 생략 허용). |
| P5 | Node type별 config schema는 catalog / Form registry로 분리·재사용한다. |
| P6 | 저장/버전 저장 UX는 **S4-0 정책 유지** (PUT `create_version=false`, POST `/versions`). |
| P7 | Graph Validation(S4)에 config validation을 **확장**한다. S5 UI 저장은 ERROR로 차단하지 않는다. |
| P8 | `config.validation.status`는 **UI cache**; authoritative source는 validation API response. |
| P9 | Compile/Run/Schedule activation은 **S6+**; S5는 compile target 구조만 설계한다. |
| P10 | R10 Data Load Pipeline / API Connector / CRON 본기능은 **수정하지 않고** compile 시 매핑만 정의한다. |

### 2.1 기존 코드와의 정렬

- **Frontend** `flowToGraph` / `graphToFlow`: `node.data.config` round-trip **이미 구현** (`visualPipelineGraph.ts`).
- **Backend catalog** `component_catalog_service.py`: MVP 4종 `config_schema`, `validation_rules`, `compile_role`, `execution_adapter` 정의됨.
- **Placeholder 불일치**: `placeholderConfigJson()` 필드명이 catalog와 다름 → S5-1에서 catalog 기준으로 교체.

---

## 3. Config 저장 위치 설계

### 3.1 후보 비교

| 후보 | 장점 | 단점 | 결론 |
|------|------|------|------|
| **A. `node.data.config`** | `flowToGraph` 이미 사용; legacy `{}` 호환 | 구조 확장 시 migration 필요 | **채택** |
| B. `node.data.config_values` | values 분리 명시 | 신규 키; FE/BE/tests 전면 수정 | 기각 |
| C. `node.data.form` | schema+values 통합 | config와 중복; graph shape 변경 | 기각 |

### 3.2 최종 JSON shape

```json
{
  "id": "node-rest-1",
  "type": "VP_REST_API_SOURCE",
  "position": { "x": 320, "y": 100 },
  "data": {
    "label": "REST API Source",
    "component_type": "VP_REST_API_SOURCE",
    "description": "...",
    "input_ports": ["trigger"],
    "output_ports": ["raw_rows"],
    "config": {
      "schema_version": "R11-S5-0",
      "values": {
        "data_source_id": "DS-001",
        "endpoint_path": "/api/v1/sample",
        "http_method": "GET",
        "credential_ref": "CRED-abc123"
      },
      "validation": {
        "status": "NOT_VALIDATED",
        "last_validated_at": null,
        "issue_count": 0
      }
    }
  }
}
```

### 3.3 필드 정의

| 필드 | 설명 |
|------|------|
| `config.schema_version` | Form/validation 규칙 버전. MVP: `"R11-S5-0"`. 없으면 catalog `COMPONENT_CONTRACT_VERSION` fallback. |
| `config.values` | catalog `config_schema` field key → value map. **flat object**. |
| `config.validation` | Inspector badge / 마지막 검증 요약 (cache). Graph 검증 API 호출 후 FE가 갱신. |

### 3.4 Legacy / 호환성

| 상황 | load 동작 |
|------|-----------|
| `data.config` 없음 | `{}` 또는 `{ values: {} }` 로 normalize |
| `data.config` 가 flat object (구형) | `{ values: config, schema_version: null }` 로 upgrade (FE normalize, S5-1) |
| `values` 비어 있음 | 정상; BASIC 검증 시 `NODE_CONFIG_MISSING` WARNING 가능 |
| version snapshot | graph 전체가 snapshot에 포함 → config 동일 보존 |

### 3.5 edge / handle과의 분리

- **Node**: `node.data.config` — 컴포넌트 설정
- **Edge**: `sourceHandle`, `targetHandle`, `edge.data.source_port`, `target_port`, `data_type` (S4-2)
- 충돌 없음. `flowToGraph`는 node `data`와 edge metadata를 독립 처리.

### 3.6 Secret 정책

- catalog field `secret: true` → `store_in_graph: false` (이미 S1 `_field()` 반영).
- graph `values`에 허용: `credential_ref`, `credential_id`, `data_source_id` (참조 ID).
- graph `values`에 **금지**: `api_key`, `token`, `password`, `Authorization` header 원문.
- 위반 시 STRICT: `NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED` ERROR.

---

## 4. MVP Node별 Config 설계

S1 catalog `config_schema`를 **1차 source of truth**로 하고, S5 Form MVP 범위와 확장 후보를 구분한다.

### 4.1 VP_REST_API_SOURCE

**목적**: REST API Connector operation을 통해 raw rows 생성 (R10 Generic REST API Connector Builder 연계).

| field key (catalog) | S5 MVP Form | 타입 / UI | 비고 |
|---------------------|-------------|-----------|------|
| `data_source_id` | ✅ | select → `/api/v1/data-sources` | required |
| `operation_name` | ✅ | text | required; compile 시 operation 식별 |
| `endpoint_path` | ✅ | text | required; R10 `endpoint_path` |
| `http_method` | ✅ | select GET/POST | default GET |
| `request_params` | ✅ (advanced) | key_value_editor | compile → `tb_api_connector_param` |
| `pagination` | ○ (advanced) | object_editor | compile → pagination config |
| `response_item_path` | ✅ | text | JSON path |
| `credential_ref` | ✅ | credential_ref | secret; ref only |

**설계 확장 후보 (S5-2+, catalog 추가 검토)**:

- `connector_mode`: EXISTING_CONNECTOR | INLINE_CONFIG
- `connector_id`, `base_url`, `path`, `headers`, `auth_mode`, `timeout_seconds`, `retry_count`, `sample_limit`, `output_alias`

**주의**: INLINE_CONFIG deep binding, 실제 connector CRUD, 외부 API 호출은 S6 compile/실행 범위.

### 4.2 VP_TRANSFORM

**목적**: RAW_ROWS → TRANSFORMED_ROWS (R10 transform types 연계).

| field key (catalog) | S5 MVP Form | 타입 / UI | 비고 |
|---------------------|-------------|-----------|------|
| `transform_type` | ✅ | select | NONE, WIDE_HOUR_TO_LONG, ASOS_*, CALENDAR_* |
| `mapping_config` | ✅ (conditional) | object_editor / mapping_table | transform_type별 |
| `unmapped_policy` | ○ | select | |
| `hour_policy` | ○ | object_editor | WIDE_HOUR 등 |
| `target_schema_preview` | ○ | readonly_json | preview only |

**설계 확장 후보**:

- `transform_mode`, `field_mappings[]`, `filters[]`, `derived_fields[]`, `timezone`, `date_parse_policy`, `error_policy` (FAIL_FAST | SKIP_ROW | KEEP_RAW)

**주의**: transformation engine / custom script 원문 저장 금지 또는 후순위.

### 4.3 VP_UPSERT_LOAD

**목적**: TRANSFORMED_ROWS → target table 적재 (R10 Upsert/Dedup, Standard Dataset 연계).

| field key (catalog) | S5 MVP Form | 타입 / UI | 비고 |
|---------------------|-------------|-----------|------|
| `standard_dataset_id` | ✅ | dataset_selector | optional; target hint |
| `target_table` | ✅ | text / table_selector | required |
| `write_mode` | ✅ | select | INSERT_ONLY, DEDUPLICATE, UPSERT |
| `conflict_key_columns_json` | ✅ | column_list | required_if DEDUPLICATE/UPSERT |
| `duplicate_within_batch_policy` | ○ | select | KEEP_FIRST/LAST/ERROR |
| `null_update_policy` | ○ | select | |
| `save_dedup_summary_yn` | ○ | checkbox | |

**설계 확장 후보**:

- `target_mode`, `dedup_policy`, `timestamp_column`, `conflict_policy`, `batch_size`, `validate_before_load`, `dry_run_default`, `load_result_alias`

### 4.4 VP_CRON_SCHEDULE

**목적**: compiled operation CRON 실행 스케줄 (R10-S11 CRON parser/due 연계).

| field key (catalog) | S5 MVP Form | 타입 / UI | 비고 |
|---------------------|-------------|-----------|------|
| `schedule_type` | ✅ | select (CRON only) | MVP CRON 고정 |
| `cron_expression` | ✅ | cron | R10 cron validate/preview endpoint 재사용 |
| `timezone` | ✅ | timezone | default Asia/Seoul |
| `start_at` | ○ | datetime | |
| `end_at` | ○ | datetime | |
| `active_yn` | ✅ | checkbox | compile 전 false 가능 |
| `retry_enabled_yn` | ○ | checkbox | |
| `max_retry_count` | ○ | number | |
| `retry_interval_minutes` | ○ | number | |

**설계 확장 후보**:

- `schedule_mode` (MANUAL | CRON | INTERVAL), `catchup`, `max_active_runs`, `misfire_policy`, `due_worker_enabled`

**주의**: schedule **activation** (Worker due 반영)은 S6/S7. S5는 config 저장·검증만.

### 4.5 placeholder → catalog 정렬 (S5-1 작업)

| component | placeholder (현재) | catalog (목표) |
|-----------|-------------------|----------------|
| REST | `data_source_id`, `endpoint_path`, `http_method` | + `operation_name`, `credential_ref` |
| Transform | `transform_profile` | `transform_type` |
| Upsert | `dataset_type_id`, `upsert_mode` | `standard_dataset_id`, `write_mode` |
| CRON | `cron_expression` | + `schedule_type`, `timezone`, `active_yn` |

---

## 5. Form Schema 설계

### 5.1 Schema source

**1차 (S5-1 권장)**: Frontend local registry — catalog `config_schema`를 TS/JSON으로 mirror (API 변경 없음).

**2차 (S5-1A 옵션)**: Backend `GET /visual-pipelines/components/{type}` 응답의 `config_schema`를 직접 Form renderer에 사용 (이미 catalog API 존재).

**장기**: catalog `config_schema`에 `sections`, `visible_when` 확장 후 단일 source.

### 5.2 Form schema envelope (UI layer)

catalog flat `config_schema[]` 위에 UI grouping을 overlay:

```json
{
  "component_type": "VP_REST_API_SOURCE",
  "schema_version": "R11-S5-0",
  "sections": [
    {
      "id": "connection",
      "title": "연결",
      "fields": ["data_source_id", "operation_name", "credential_ref"]
    },
    {
      "id": "request",
      "title": "Request",
      "fields": ["endpoint_path", "http_method", "request_params", "pagination"]
    },
    {
      "id": "response",
      "title": "Response",
      "fields": ["response_item_path"]
    }
  ]
}
```

### 5.3 Field type 매핑

| catalog `type` / `ui_component` | Form widget | 비고 |
|---------------------------------|-------------|------|
| string + text | text | |
| string + select | select | `values` 또는 `option_source` |
| enum + select | select | |
| object + key_value_editor | key_value_list | |
| object + object_editor | json_editor / nested form | |
| array[string] + string_list | column_list / multi input | |
| reference + select (secret) | credential_ref | 마스킹, ref only |
| boolean + checkbox | boolean | |
| integer + number | number | |
| datetime + datetime | datetime | |
| string + text (cron) | cron | CRON 전용; validate endpoint 연동 |

### 5.4 공통 field 속성 (Form registry 확장)

catalog `_field()` + UI extension:

| 속성 | 설명 |
|------|------|
| `key` / `name` | `values` object key |
| `label` | 표시명 (catalog `description` 또는 i18n) |
| `type`, `ui_component` | widget 선택 |
| `required`, `required_if` | validation |
| `default` | 신규 노드 initial values |
| `placeholder`, `help_text` | UX |
| `options` / `option_source` | select 데이터 |
| `validation` | regex, min/max, custom rule id |
| `visible_when`, `disabled_when` | 조건부 표시 |
| `secret`, `store_in_graph` | secret 정책 |
| `advanced` | 고급 섹션 collapse |
| `depends_on` | option_source param (e.g. data_source_id → operations) |

---

## 6. Validation 설계

### 6.1 확장 위치

`graph_validation_service.validate_visual_pipeline_graph()`에 **Phase: Node Config** 추가 (S5-5 구현).

- S4 topology/port/handle 검증 **이후** 실행
- node별 `component_type` → catalog `config_schema` + `validation_rules` lookup
- issue에 `node_id`, `component_type`, `field_key` 포함

### 6.2 Issue code

| code | severity (BASIC) | severity (STRICT) | 조건 |
|------|------------------|-------------------|------|
| `NODE_CONFIG_MISSING` | WARNING | WARNING | `config`/`values` 없음 |
| `NODE_CONFIG_SCHEMA_VERSION_MISSING` | INFO | WARNING | schema_version 없음 (legacy) |
| `NODE_CONFIG_REQUIRED_FIELD_MISSING` | WARNING | **ERROR** | required / required_if 위반 |
| `NODE_CONFIG_FIELD_INVALID` | WARNING | **ERROR** | enum/type/range 위반 |
| `NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED` | WARNING | **ERROR** | secret pattern in values |
| `NODE_CONFIG_CREDENTIAL_REF_MISSING` | WARNING | **ERROR** | auth 필요 시 ref 없음 |
| `NODE_CONFIG_TARGET_MISSING` | WARNING | **ERROR** | Upsert target_table 등 |
| `NODE_CONFIG_KEY_COLUMNS_MISSING` | WARNING | **ERROR** | DEDUPLICATE/UPSERT keys |
| `NODE_CONFIG_CRON_INVALID` | WARNING | **ERROR** | cron parse fail |
| `NODE_CONFIG_MAPPING_INVALID` | WARNING | **ERROR** | mapping_config 구조 |
| `NODE_CONFIG_UNSUPPORTED_MODE` | WARNING | **ERROR** | 지원하지 않는 mode/type |

### 6.3 BASIC vs STRICT

| level | 저장 차단 | 용도 |
|-------|-----------|------|
| **BASIC** | **없음** (S4-0/S4-1 정책 유지) | Studio 「Graph 검증」 기본 |
| **STRICT** | **없음** (UI); **S6 compile gate** | compile/run 전 필수 |

- BASIC: config missing, required missing → 주로 **WARNING** (운영자가 graph 저장·iterating 가능).
- STRICT: required/secret/cron/target → **ERROR**; compile API는 STRICT FAIL 시 compile 거부 (S6).

### 6.4 validation.status (UI cache)

```json
"validation": {
  "status": "NOT_VALIDATED | OK | WARNING | ERROR",
  "last_validated_at": "2026-07-21T06:00:00Z",
  "issue_count": 0
}
```

- Graph 검증 API 응답 후 FE가 node별 issue aggregate하여 갱신.
- **Authoritative**: `POST .../validate` response `issues[]`.
- 저장 시 validation cache는 별도 DB 테이블에 persist하지 않고, graph JSON 내부의 optional cache로만 보존한다.

---

## 7. UI/UX 설계

### 7.1 Inspector 레이아웃

**미선택**:

> 노드를 선택하면 설정을 편집할 수 있습니다.

**선택 후**:

```
┌─ Node Inspector ─────────────────────┐
│ [Label]  VP_REST_API_SOURCE  [badge] │  ← validation.status cache
├──────────────────────────────────────┤
│ Tabs: [기본] [설정] [포트] [JSON]     │
│                                      │
│  (설정 tab) sections…                │
│  - 연결: data_source_id, credential  │
│  - Request: method, path, params     │
│                                      │
│  ℹ 설정 변경사항은 Graph 저장 시      │
│    함께 저장됩니다.                   │
│  ℹ 비밀값은 Credential 참조만 저장.   │
├──────────────────────────────────────┤
│ [노드 삭제]                           │
└──────────────────────────────────────┘
```

### 7.2 저장 UX (S4-0 유지)

| 동작 | 정책 |
|------|------|
| Form field 변경 | local React state → `node.data.config.values` 반영 → **graph dirty** |
| 「저장」 | 기존 PUT graph (create_version=false) |
| 「버전 저장」 | dirty면 PUT(false) → POST /versions |
| Inspector 내부 「설정 저장」 버튼 | **도입하지 않음** (중복 UX 방지) |
| auto-save | **없음** (명시적 Graph 저장) |

### 7.3 Form state 흐름

1. Node select → `graphToFlow`의 `node.data.config` load
2. normalize legacy → `{ schema_version, values, validation }`
3. Form edit → `onConfigChange(nodeId, values)` → nodes state update
4. dirty compare: `serializeGraphBody` (viewport 제외, S4-0 동일)
5. Graph 검증 → API → Validation Panel + per-node validation cache 갱신

### 7.4 data-testid (S5-1+)

- `visual-pipeline-inspector-config-form`
- `visual-pipeline-inspector-config-field-{key}`
- `visual-pipeline-inspector-validation-badge`

---

## 8. API / Backend 설계 (향후, S5-0 구현 금지)

### 8.1 현재 사용 가능

| API | 용도 |
|-----|------|
| `GET /visual-pipelines/components` | config_schema 목록 |
| `GET /visual-pipelines/components/{type}` | node별 schema |
| `POST /visual-pipelines/validate-graph` | graph+config 통합 검증 (S5-5 확장) |
| `POST /visual-pipelines/{id}/validate` | persisted graph 검증 |
| `GET /api/v1/data-sources` 등 | option_source |
| `POST /data-load-schedules/cron/validate` | CRON field 검증 (ui_hints) |

### 8.2 후보 (S5-1A / S5-5)

| API | 목적 |
|-----|------|
| `GET /visual-pipelines/config-schemas` | 전체 Form schema bundle |
| `GET /visual-pipelines/components/{type}/config-schema` | section 포함 enriched schema |
| `POST /visual-pipelines/validate-config` | single node config only (optional) |

**권장**: S5-1B는 catalog API 재사용; enriched schema는 catalog code 확장으로 제공 (DB migration 없음).

---

## 9. Compile 연계 설계 (R11-S6)

Visual Pipeline graph → 기존 **Data Load Pipeline Definition** / API Connector compile target.

### 9.1 Node → compile target 매핑

| Node | catalog compile_role | execution_adapter | R10 compile target (설계) |
|------|---------------------|-------------------|---------------------------|
| VP_REST_API_SOURCE | OPERATION_BASE | api_connector_operation | `tb_api_connector_operation`, params, pagination; `credential_ref` → credential lookup |
| VP_TRANSFORM | TRANSFORM_CONFIG | connector_transform_config | operation `transform_config` JSON |
| VP_UPSERT_LOAD | WRITE_POLICY | api_connector_load_write_policy | `tb_api_connector_write_policy` fields |
| VP_CRON_SCHEDULE | DATA_LOAD_SCHEDULE | data_load_scheduler | `schedule_config_json` / `tb_data_load_schedule` |

### 9.2 Compile 입력

- Input: `current_graph_json` (nodes with `config.values`, edges with handles)
- Preconditions: STRICT validation PASS; `current_sync_status` → compile 후 `IN_SYNC` (S6)
- Secret: compile output에도 **ref only**; runtime credential resolve

### 9.3 MVP 4-node pipeline compile 순서 (개념)

```
CRON(schedule_config) ─trigger→ REST(raw_rows) ─→ TRANSFORM(transformed_rows) ─→ UPSERT(load_result)
```

Compile result는 R10 pipeline-definition / operation chain으로 materialize (S6-0 design, S6-1 PoC).

---

## 10. 단계별 구현 로드맵

| 단계 | 내용 | 산출 |
|------|------|------|
| **R11-S5-0** | Inspector Config Form **설계** (본 문서) | design doc |
| **R11-S5-1** | Config schema registry + TS types + normalize helper | FE utils, fixtures |
| **R11-S5-1A** | (optional) catalog config_schema section/enriched endpoint | BE catalog only |
| **R11-S5-2** | REST API Source Inspector Form | VpRestSourceConfigForm |
| **R11-S5-3** | Transform Inspector Form | VpTransformConfigForm |
| **R11-S5-4** | Upsert Load + CRON Inspector Form | VpUpsertConfigForm, VpCronConfigForm |
| **R11-S5-5** | Config validation API 확장 + Inspector badge | graph_validation_service |
| **R11-S5-6** | Config round-trip tests + Studio E2E config smoke | tests, check-visual-pipeline-studio |
| **R11-S6-0** | Compile design doc | compile mapping 상세 |
| **R11-S6-1** | Compile API PoC | compile endpoint |

---

## 11. Risk / Decision Log

| ID | 주제 | 옵션 | **S5-0 권장** | 비고 |
|----|------|------|---------------|------|
| D1 | config 저장 위치 | config vs config_values | **`node.data.config`** | flowToGraph 이미 사용 |
| D2 | values 구조 | flat vs nested | **flat `values{}`** | catalog 1:1 |
| D3 | schema 위치 | FE registry vs BE endpoint | **S5-1: FE mirror**; S5-1A optional | API 무변경 시작 |
| D4 | secret | inline vs ref | **credential_ref only** | catalog `secret: true` |
| D5 | schedule activation | S5 vs S6 | **S6+** | S5 config only |
| D6 | compile mapping depth | shallow vs full R10 | **MVP: catalog execution_adapter 기준** | S6 상세화 |
| D7 | BASIC required missing | WARNING vs ERROR | **WARNING** | 저장 차단 없음 |
| D8 | STRICT required missing | ERROR | **ERROR** | compile gate |
| D9 | Form field types | minimal vs rich | **MVP: catalog ui_component subset** | mapping_table 등 단계적 |
| D10 | existing connector reuse | operation_name ref vs inline | **S5-2: data_source + operation_name** | INLINE_CONFIG 후순위 |
| D11 | validation cache in graph | persist vs ephemeral | **optional cache in graph** | authoritative=API |
| D12 | legacy flat config | upgrade on load | **normalize on load** | S5-1 helper |

---

## 12. Non-goals (R11-S5-0)

- Inspector Config Form **UI 구현**
- Backend API **신규 구현**
- DB / schema / migration 변경
- package 추가
- compile / run / schedule **activation** 구현
- secret 원문 graph 저장
- R10 / Pipeline Builder **본기능 수정**
- S4 graph validation **정책 변경**
- graph edge/handle 저장 shape 변경
- 저장/버전 저장 UX 변경

---

## 부록 A. node.data.config 전체 예시 (4-node MVP)

```json
{
  "nodes": [
    {
      "id": "n-cron",
      "type": "VP_CRON_SCHEDULE",
      "data": {
        "label": "CRON Schedule",
        "config": {
          "schema_version": "R11-S5-0",
          "values": {
            "schedule_type": "CRON",
            "cron_expression": "0 6 * * *",
            "timezone": "Asia/Seoul",
            "active_yn": false
          },
          "validation": { "status": "NOT_VALIDATED", "last_validated_at": null, "issue_count": 0 }
        }
      }
    },
    {
      "id": "n-rest",
      "type": "VP_REST_API_SOURCE",
      "data": {
        "label": "REST API Source",
        "config": {
          "schema_version": "R11-S5-0",
          "values": {
            "data_source_id": "DS-SAMPLE",
            "operation_name": "sample_fetch",
            "endpoint_path": "/api/v1/sample",
            "http_method": "GET",
            "response_item_path": "$.items",
            "credential_ref": "CRED-SAMPLE"
          },
          "validation": { "status": "OK", "last_validated_at": "2026-07-21T06:00:00Z", "issue_count": 0 }
        }
      }
    },
    {
      "id": "n-xform",
      "type": "VP_TRANSFORM",
      "data": {
        "label": "Transform",
        "config": {
          "schema_version": "R11-S5-0",
          "values": {
            "transform_type": "WIDE_HOUR_TO_LONG",
            "mapping_config": {}
          },
          "validation": { "status": "NOT_VALIDATED", "last_validated_at": null, "issue_count": 0 }
        }
      }
    },
    {
      "id": "n-load",
      "type": "VP_UPSERT_LOAD",
      "data": {
        "label": "Upsert Load",
        "config": {
          "schema_version": "R11-S5-0",
          "values": {
            "standard_dataset_id": "SD-001",
            "target_table": "tb_sample_fact",
            "write_mode": "UPSERT",
            "conflict_key_columns_json": ["entity_id", "measured_at"]
          },
          "validation": { "status": "NOT_VALIDATED", "last_validated_at": null, "issue_count": 0 }
        }
      }
    }
  ],
  "edges": []
}
```

---

## 부록 B. 참조 파일

| 영역 | 경로 |
|------|------|
| Inspector (placeholder) | `frontend/src/components/visualPipeline/VpNodeInspector.tsx` |
| graph round-trip | `frontend/src/utils/visualPipelineGraph.ts` |
| catalog | `backend/app/services/visual_pipeline/component_catalog_service.py` |
| graph validation | `backend/app/services/visual_pipeline/graph_validation_service.py` |
| graph storage | `backend/app/services/visual_pipeline/visual_pipeline_service.py` |

---

*문서 끝.*
