# THERMOps R11-S6-0 Visual Pipeline Compile 설계

> **문서 유형**: 설계 (구현 없음)  
> **작성 기준**: `master` @ R11-S5-6 (`3706bdc`) 완료 시점  
> **범위**: Visual Pipeline graph → R10 Data Load / API Connector / Transform / Write Policy / Schedule 변환(Compile) 계층 설계  
> **후속**: R11-S6-1 Compile Preview API PoC

---

## 1. 배경과 목적

### 1.1 배경

R11-S5까지 Visual Pipeline Studio는 graph 편집·config 입력·검증·저장·스냅샷까지 안정화했다.

| 단계 | 내용 | 커밋 (대표) |
|------|------|-------------|
| S5-0 | Inspector Config Form 설계 | `79079c6` |
| S5-1 | Config schema registry + normalize | `7abbcce` |
| S5-2 | REST Inspector Form | `1960749` |
| S5-3 | Transform Inspector Form | `ae4c849` |
| S5-4 | Upsert + CRON Inspector Form | `fbdb259` |
| S5-5 | Config Validation + Inspector badge | `3117d3a` |
| S5-6 | Config round-trip + E2E smoke | `3706bdc` |

현재 상태:

- `node.data.config = { schema_version, values, validation }` 저장·로드·version snapshot 보존
- Graph Validation BASIC/STRICT + CONFIG phase (`NODE_CONFIG_*`)
- Studio 저장은 validation으로 차단하지 않음 (S4-0 / S5 정책)
- `current_sync_status`는 생성·graph PUT 시 `NOT_COMPILED`로 리셋만 수행 (`IN_SYNC` 등 미전이)
- version snapshot에 `compiled_target: null` placeholder 존재
- Catalog에 `compile_role` / `execution_adapter` 힌트 존재

아직 **graph → 실행 가능한 R10 Data Load 구조로 변환하는 Compile 계층**은 없다.

### 1.2 목적

Compile은 Visual Pipeline graph와 기존 R10 실행 구조 사이의 **변환 계층**이다.

| 계층 | 역할 |
|------|------|
| Studio Graph | 사람이 편집하는 노드/엣지/config |
| **Compile** | STRICT gate + traversal + R10 mapping → compiled artifact |
| R10 Runtime | API Connector load / Transform / Write / Schedule / due worker |

**S6-0 산출물**: 구현 없이 설계 문서로 S6-1+ 구현 기준을 확정한다.

### 1.3 S6-0 범위 선언

- Compile API / Run / Schedule activation **구현 없음**
- DB migration / package / R10 본기능 수정 **없음**
- docs + README만

---

## 2. 용어 정의

| 용어 | 정의 |
|------|------|
| **Visual Pipeline** | `pipeline_kind=VISUAL_DATA_LOAD` 인 Studio graph 파이프라인. MLOps Pipeline Builder와 분리. |
| **Graph** | `nodes` + `edges` + `viewport` JSON (`current_graph_json`). |
| **Node** | React Flow 노드. `type` / `data.component_type`, `data.config`. |
| **Edge / Handle / Port** | 연결. `sourceHandle`/`targetHandle` (`output:{port}` / `input:{port}`), `edge.data.{source_port,target_port,data_type}`. |
| **Config values** | `node.data.config.values` — catalog `config_schema[].name` 키. |
| **Compile** | Graph(+STRICT validation) → **compiled artifact** 변환. 실행이 아님. |
| **Compile target** | 노드별 R10 대응 구조 (operation / transform_config / write_policy / schedule). |
| **Compiled artifact** | Compile 결과 JSON (steps / schedule / write_policy / metadata / hashes). |
| **Sync status** | `current_sync_status` — graph와 compile 결과의 동기화 상태. |
| **Compile preview** | DB write 없이 artifact를 미리보기하는 응답. |
| **Activation** | Schedule/worker를 실제로 등록·활성화하는 단계. Compile과 분리. |
| **Run** | 적재/변환/쓰기 실행. Compile 이후 (또는 별도) 단계. |
| **Schedule activation** | CRON due worker가 잡을 수 있도록 schedule을 active로 등록. Compile ≠ activation. |

---

## 3. Compile 범위와 Non-goals

### 3.1 Compile 범위 (설계)

- `current_graph_json` 읽기 (및 optional transient graph)
- STRICT validation PASS 여부 확인
- DAG traversal / execution order 산정
- REST / Transform / Upsert / CRON → R10 구조 매핑
- compile result / preview / sync status 설계
- idempotency / stale 판단
- error / issue code 설계

### 3.2 Non-goals (S6-0 및 S6-1 PoC 공통 경계)

| 금지 | 설명 |
|------|------|
| 실제 Run | API load / transform / write 실행 없음 |
| Schedule activation | due worker 등록·`active` schedule 생성 없음 |
| Upsert DB write | target table 실쓰기 없음 |
| 외부 REST 호출 | connector call 없음 |
| R10 본기능 변경 | API Connector / Scheduler / Worker 수정 없음 |
| 대규모 UI | S6-0 구현 없음; UI는 방향만 |
| DB migration 구현 | S6-0에서 migration 스크립트 작성 금지 |
| package 추가 | 금지 |
| Auth | 1차 범위 외 |

---

## 4. Compile 전제 조건

### 4.1 Pipeline / 노드

- `pipeline_kind = VISUAL_DATA_LOAD`
- MVP ACTIVE 노드 4종만 compile 대상:
  - `VP_REST_API_SOURCE`
  - `VP_TRANSFORM`
  - `VP_UPSERT_LOAD`
  - `VP_CRON_SCHEDULE`
- DISABLED / unknown component → compile fail (`COMPILE_GRAPH_UNSUPPORTED_SHAPE` 등)

### 4.2 Required graph pattern (MVP)

| 패턴 | MVP | 비고 |
|------|-----|------|
| REST → Transform → Upsert | **권장** | 표준 적재 흐름 |
| REST → Upsert (direct) | **허용** | catalog ALLOW + validation INFO `TRANSFORM_RECOMMENDED` |
| CRON → REST (`schedule_config` → `trigger`) | **optional** | schedule config로 취급; 없으면 Manual/unscheduled artifact |
| 다중 REST / 다중 Upsert | **비허용 (MVP)** | unsupported shape |
| Cycle / dangling / disallowed edge | **거부** | S4 validation ERROR와 정렬 |

### 4.3 STRICT validation gate

| 단계 | 정책 |
|------|------|
| Studio 저장 / 버전 저장 | validation으로 **차단하지 않음** (S4-0/S5 유지) |
| Compile / Compile Preview | **STRICT** 실행; ERROR 있으면 compile 거부 (`COMPILE_VALIDATION_FAILED`) |
| BASIC | 편집 중 안내용; compile gate로 사용하지 않음 |

### 4.4 Secret

- graph / compiled artifact / issue / log에 **secret 원문 금지**
- `credential_ref` / `credential_id` / `data_source_id` 참조만 전달
- catalog 규칙: `credential values must not appear in compiled_target_json`

---

## 5. Compile input 설계

### 5.1 Input source

| Source | 용도 | 권장 |
|--------|------|------|
| `tb_pipeline_definition.current_graph_json` | 저장된 권위 graph | **Compile(persist) 기본** |
| Request body `graph` | transient preview | **optional** — Preview API만 |
| 특정 version snapshot | 과거 버전 compile | S6-2+ (이번 MVP 비필수) |

**D1 결정:** Compile input 기본 = `current_graph_json`.  
Transient preview는 optional body. Persist compile은 **저장된 graph만**.

### 5.2 Graph shape (필수 필드)

```
graph.nodes[].id
graph.nodes[].type | data.component_type
graph.nodes[].data.config.schema_version   (normalize 후)
graph.nodes[].data.config.values
graph.edges[].source / target
graph.edges[].sourceHandle / targetHandle
graph.edges[].data.source_port / target_port / data_type
```

### 5.3 Legacy / missing config

| 상태 | Compile 전 | Compile |
|------|-----------|--------|
| legacy flat / missing schema_version | FE/BE normalize 권장 | STRICT에서 INFO/WARNING → ERROR로 승격되는 required 누락 시 fail |
| `config` 없음 / values empty | — | STRICT `NODE_CONFIG_*` ERROR → `COMPILE_VALIDATION_FAILED` |
| unknown values keys | **삭제하지 않음** | metadata/passthrough; materialization 시 ignore |

S6 compile은 **S5 normalize + STRICT validation을 전제**로 한다.

---

## 6. Graph traversal / execution order

### 6.1 알고리즘 (개념)

1. STRICT `validate_visual_pipeline_graph` (topology + port + CONFIG)
2. ERROR 있으면 중단
3. DAG topological sort (cycle은 validation에서 이미 ERROR)
4. 노드 역할 분류:
   - **CRON** → `schedule` 섹션 (execution step 아님)
   - **REST** → `steps[]` type=`source`
   - **Transform** → `steps[]` type=`transform`
   - **Upsert** → `steps[]` type=`load`
5. Edge port로 lineage 연결:
   - `raw_rows` → source output
   - `transformed_rows` → transform output
   - `load_result` → load output
   - `schedule_config` → schedule binding to REST trigger

### 6.2 CRON 취급

- CRON은 **실행 step이 아니라 schedule trigger/config**
- `active_yn`은 artifact의 schedule 필드에만 반영
- **Compile만으로 due worker / schedule row 활성화 금지** (D5)

### 6.3 MVP cardinality

| 규칙 | MVP |
|------|-----|
| source (REST) 개수 | 정확히 1 |
| load (Upsert) 개수 | 정확히 1 |
| transform 개수 | 0 또는 1 |
| cron 개수 | 0 또는 1 |
| 위반 | `COMPILE_GRAPH_UNSUPPORTED_SHAPE` |

---

## 7. Node별 Compile mapping

Catalog 기준:

| Node | compile_role | execution_adapter |
|------|--------------|-------------------|
| VP_REST_API_SOURCE | OPERATION_BASE | api_connector_operation |
| VP_TRANSFORM | TRANSFORM_CONFIG | connector_transform_config |
| VP_UPSERT_LOAD | WRITE_POLICY | api_connector_load_write_policy |
| VP_CRON_SCHEDULE | DATA_LOAD_SCHEDULE | data_load_scheduler |

**S6-1 PoC:** compiled artifact JSON만 생성.  
**S6-4:** R10 table materialization PoC.

### 7.A VP_REST_API_SOURCE

**values → R10**

| values key | R10 대상 |
|------------|----------|
| `data_source_id` | `tb_api_connector_operation.data_source_id` |
| `operation_name` | `operation_name` (참조 또는 생성 hint) |
| `endpoint_path` | `endpoint_path` |
| `http_method` | `http_method` |
| `request_params` | `tb_api_connector_param` (또는 params JSON hint) |
| `pagination` | `tb_api_connector_pagination` |
| `response_item_path` | `response_item_path` |
| `credential_ref` | credential lookup id (원문 금지) |

**결정:** S6-1은 operation을 **artifact hint**로 둔다. 기존 connector operation 자동 바인딩/생성(materialize)은 S6-4.

**step 예시**

```json
{
  "step_id": "source-n-rest",
  "type": "source",
  "component_type": "VP_REST_API_SOURCE",
  "node_id": "n-rest",
  "adapter": "api_connector_operation",
  "config": {
    "data_source_id": "DS-SAMPLE",
    "operation_name": "sample_fetch",
    "endpoint_path": "/api/v1/sample",
    "http_method": "GET",
    "request_params": { "branch": "P001" },
    "pagination": { "type": "NONE" },
    "response_item_path": "$.items",
    "credential_ref": "CRED-SAMPLE"
  },
  "outputs": [{ "port": "raw_rows", "data_type": "RAW_ROWS" }]
}
```

### 7.B VP_TRANSFORM

**values → R10**

| values key | R10 대상 |
|------------|----------|
| `transform_type` | `tb_api_connector_transform_config.transform_type` / adapter id |
| `mapping_config` | metadata / value_field_mappings 계열 hint |
| `unmapped_policy` | `unmapped_policy` (R10 기본 `FAIL_LOAD` 등과 매핑 테이블 필요) |
| `hour_policy` | hour_* / timestamp_policy 계열 hint |
| `target_schema_preview` | **compile 제외** (`store_in_graph=false`) |

**transform_type → adapter (MVP)**

| transform_type | Adapter / R10 의미 |
|----------------|-------------------|
| `NONE` | no-op transform |
| `WIDE_HOUR_TO_LONG` | wide-hour heat demand adapter |
| `ASOS_HOURLY_TO_CANONICAL` | ASOS hourly adapter |
| `CALENDAR_SPECIAL_DAY_TO_DATE` | calendar date adapter |
| `CALENDAR_DATE_TO_HOUR` | calendar hour adapter |
| 그 외 | `COMPILE_TRANSFORM_UNSUPPORTED` |

**step 예시**

```json
{
  "step_id": "transform-n-xform",
  "type": "transform",
  "component_type": "VP_TRANSFORM",
  "node_id": "n-xform",
  "adapter": "connector_transform_config",
  "config": {
    "transform_type": "WIDE_HOUR_TO_LONG",
    "mapping_config": { "mappings": [] },
    "unmapped_policy": "KEEP",
    "hour_policy": {}
  },
  "inputs": [{ "port": "input_rows", "data_type": "RAW_ROWS", "from_step": "source-n-rest" }],
  "outputs": [{ "port": "transformed_rows", "data_type": "TRANSFORMED_ROWS" }]
}
```

### 7.C VP_UPSERT_LOAD

**values → R10 (`tb_api_connector_write_policy`)**

| values key | R10 column |
|------------|------------|
| `target_table` | `target_table` |
| `standard_dataset_id` | operation / metadata 참조 |
| `write_mode` | `write_mode` (`INSERT_ONLY` / `DEDUPLICATE` / `UPSERT`) |
| `conflict_key_columns_json` | `conflict_key_columns_json` |
| `duplicate_within_batch_policy` | `duplicate_within_batch_policy` |
| `null_update_policy` | `null_update_policy` |
| `save_dedup_summary_yn` | load 시 `tb_api_connector_load_dedup_summary` 사용 여부 hint |

**write_mode required**

| write_mode | conflict_key_columns_json |
|------------|---------------------------|
| `INSERT_ONLY` | optional |
| `DEDUPLICATE` / `UPSERT` | **required non-empty** (STRICT) |

**step + write_policy 예시**

```json
{
  "step_id": "load-n-load",
  "type": "load",
  "component_type": "VP_UPSERT_LOAD",
  "node_id": "n-load",
  "adapter": "api_connector_load_write_policy",
  "config": {
    "standard_dataset_id": "SD-001",
    "target_table": "tb_sample_fact",
    "write_mode": "UPSERT",
    "conflict_key_columns_json": ["entity_id", "measured_at"],
    "duplicate_within_batch_policy": "KEEP_LAST",
    "null_update_policy": "KEEP_EXISTING",
    "save_dedup_summary_yn": true
  },
  "inputs": [{ "port": "input_rows", "data_type": "TRANSFORMED_ROWS", "from_step": "transform-n-xform" }],
  "outputs": [{ "port": "load_result", "data_type": "LOAD_RESULT" }]
}
```

### 7.D VP_CRON_SCHEDULE

**values → R10 (`tb_data_load_schedule` 대응)**

| values key | R10 column |
|------------|------------|
| `schedule_type` | `schedule_type` (`CRON` only MVP) |
| `cron_expression` | `cron_expression` (R10-S11 5-field) |
| `timezone` | `timezone` |
| `start_at` / `end_at` | `start_at` / `end_at` |
| `active_yn` | artifact flag only — **Compile ≠ activation** |
| `retry_*` | `retry_enabled_yn` / `max_retry_count` / `retry_interval_minutes` |

**schedule 섹션 예시**

```json
{
  "enabled": true,
  "component_type": "VP_CRON_SCHEDULE",
  "node_id": "n-cron",
  "adapter": "data_load_scheduler",
  "schedule_type": "CRON",
  "cron_expression": "0 6 * * *",
  "timezone": "Asia/Seoul",
  "start_at": null,
  "end_at": null,
  "active_yn": false,
  "retry_enabled_yn": true,
  "max_retry_count": 2,
  "retry_interval_minutes": 15,
  "binds_to_node_id": "n-rest",
  "activation": "NOT_REQUESTED"
}
```

`active_yn=true`여도 Compile 결과는 `activation: "NOT_REQUESTED"` (또는 동등). 실제 registration은 별도 Activation API/단계.

---

## 8. Compile output 설계

### 8.1 Response envelope

```json
{
  "pipeline_id": "PIPE-...",
  "compile_status": "SUCCESS",
  "validation_level": "STRICT",
  "graph_version_hash": "sha256:...",
  "config_hash": "sha256:...",
  "compiled_at": "2026-07-22T04:00:00Z",
  "compile_version": "R11-S6-0",
  "compiled_artifact": {
    "version": "R11-S6-0",
    "kind": "VISUAL_DATA_LOAD",
    "steps": [],
    "schedule": null,
    "write_policy": {},
    "lineage": [],
    "metadata": {
      "source_node_id": "n-rest",
      "load_node_id": "n-load",
      "has_transform": true,
      "has_schedule": true
    }
  },
  "issues": [],
  "persisted": false
}
```

`compile_status`: `SUCCESS` | `FAILED` | `PARTIAL` (PARTIAL는 materialization 단계; S6-1에서는 미사용 권장).

### 8.2 Preview vs persisted result

| | Preview | Persisted compile |
|--|---------|-------------------|
| DB write | 없음 | sync_status / artifact 저장 (S6-2+) |
| Input | current 또는 transient graph | **current_graph_json only** |
| `persisted` | `false` | `true` |
| S6-1 | **이 경로** | 미구현 |

### 8.3 write_policy top-level

Load step config를 `compiled_artifact.write_policy`에도 복제해 Run/materialize 소비를 단순화한다 (단일 load MVP).

### 8.4 Secret in output

- `credential_ref`만
- masked 값·원문·Authorization header 금지

---

## 9. Compile persistence 전략

### 9.1 옵션 비교

| Option | 내용 | 장점 | 단점 |
|--------|------|------|------|
| **A** | `tb_pipeline_definition.current_compiled_json` (+ optional hash/at) | 단순 lookup; FE sync 표시 쉬움 | migration 필요; 이력 약함 |
| **B** | version `snapshot_json.compiled_target` 채움 | snapshot 이미 placeholder 있음 | 매 compile마다 version? 정책 충돌; PUT false와 어긋날 수 있음 |
| **C** | `tb_visual_pipeline_compile_result` (또는 pipeline_id FK 테이블) | 이력·감사·rollback | migration + API 증가 |
| **D** | persistence 없음, preview response만 | 리스크 최저; S6-1 적합 | 운영 sync/stale 불가 |

### 9.2 권장

| 단계 | 권장 |
|------|------|
| **S6-1 PoC** | **D** — `compile-preview` only, `persisted=false` |
| **장기** | **C 권장** (이력/감사). 단순 PoC 확장 시 **A**도 허용. |
| **B** | version과 compile을 묶지 않음. snapshot의 `compiled_target`은 **optional copy**로만 검토 (기본 저장소로 쓰지 않음). |

**근거:** 저장 UX(S4-0)는 graph version과 compile을 분리해야 한다. Compile 이력은 graph version과 1:1이 아닐 수 있다 → C가 장기적으로 적합.

---

## 10. current_sync_status 설계

### 10.1 코드 값 (기존 + 설계)

| Status | 의미 |
|--------|------|
| `NOT_COMPILED` | 한 번도 성공 compile 없음 (현재 생성/PUT 기본) |
| `IN_SYNC` | 마지막 성공 compile의 graph hash == current hash |
| `STALE` | graph 변경으로 compile 결과와 불일치 |
| `COMPILE_FAILED` | 마지막 compile 시도 실패 |
| `PARTIAL` | materialization 일부 성공 (S6-4+) |

### 10.2 현재 구현

- create / update graph → 항상 `NOT_COMPILED`
- `IN_SYNC` / `STALE` / `COMPILE_FAILED` / `PARTIAL` **미사용**

### 10.3 목표 전이

```
[create/PUT graph] → NOT_COMPILED 또는 STALE
       │
       ├─ compile-preview (S6-1) → status 변경 없음
       │
       └─ compile success (S6-2) → IN_SYNC
              compile fail → COMPILE_FAILED
              materialize partial → PARTIAL
```

| 이벤트 | 권장 status |
|--------|-------------|
| Graph PUT / 버전과 무관한 config 변경 | `STALE` if 이전 IN_SYNC else `NOT_COMPILED` |
| Compile preview | **변경 없음** |
| Compile persist success | `IN_SYNC` + hash 저장 |
| Compile persist fail | `COMPILE_FAILED` |
| Label/position/viewport only | hash 제외 → **STALE 아님** (D6) |

**D4:** S6-1은 status 미갱신. S6-2에서 persist + status 전이.

저장 UX와 충돌 없음: 저장은 계속 허용, sync는 표시/게이트용.

---

## 11. API 설계안 (문서만)

### 11.1 후보

| Method | Path | 목적 | DB |
|--------|------|------|-----|
| POST | `/api/v1/visual-pipelines/{pipeline_id}/compile-preview` | 저장된 graph STRICT compile preview | 없음 |
| POST | `/api/v1/visual-pipelines/compile-graph` | transient graph preview | 없음 |
| POST | `/api/v1/visual-pipelines/{pipeline_id}/compile` | persist compile + status | 있음 (S6-2) |
| GET | `/api/v1/visual-pipelines/{pipeline_id}/compile-result` | 최근 result | 있음 (S6-2) |

### 11.2 S6-1 권장

1. **`POST .../{pipeline_id}/compile-preview`** (필수)
2. **`POST .../compile-graph`** (optional, Studio dirty preview)

Request (preview):

```json
{
  "validation_level": "STRICT"
}
```

또는 compile-graph:

```json
{
  "graph": { "nodes": [], "edges": [], "viewport": {} },
  "validation_level": "STRICT"
}
```

Response: §8 envelope (`persisted: false`).

기존 validation endpoint는 유지·재사용 (내부에서 STRICT 호출).

---

## 12. Error / Issue 설계

### 12.1 Compile issue codes

| Code | 언제 |
|------|------|
| `COMPILE_VALIDATION_FAILED` | STRICT ERROR 존재 (상세는 nested `NODE_*` / `NODE_CONFIG_*`) |
| `COMPILE_GRAPH_UNSUPPORTED_SHAPE` | 다중 source/load, 비허용 패턴 |
| `COMPILE_NODE_CONFIG_MISSING` | values 공백 (STRICT 이후에도 방어) |
| `COMPILE_REST_SOURCE_UNRESOLVED` | data_source/operation 해석 실패 (materialize 단계) |
| `COMPILE_TRANSFORM_UNSUPPORTED` | 알 수 없는 transform_type |
| `COMPILE_UPSERT_TARGET_MISSING` | target_table / dataset 누락 |
| `COMPILE_SCHEDULE_INVALID` | cron/timezone (STRICT와 중복 가능) |
| `COMPILE_SECRET_REF_UNRESOLVED` | credential_ref 미존재 (깊이 있는 확인은 S6-2+) |
| `COMPILE_TARGET_MAPPING_FAILED` | adapter mapping 실패 |

### 12.2 Severity / 관계

- Compile gate: STRICT validation ERROR → compile `FAILED` + `COMPILE_VALIDATION_FAILED`
- Compile-specific ERROR: mapping/unsupported shape
- Validation Panel vs Compile Panel: validation issue는 기존 Panel; compile issue는 Compile Panel/응답
- `NODE_CONFIG_*`를 사용자에게 그대로 노출 가능 (field_key 포함). Compile code는 요약 래퍼

### 12.3 메시지

- 사용자: 한국어 짧은 안내 + `code` + `field_key`/`node_id`
- 로그: secret 원문 금지

---

## 13. Idempotency / Stale detection

### 13.1 Graph hash 입력 (D6)

**포함:**

- `nodes[].id`, `type`/`component_type`
- `nodes[].data.config.values` (정규화 JSON)
- `edges[].id?`, `source`, `target`, handles, port metadata

**제외:**

- `viewport`
- `nodes[].position`
- `nodes[].data.label` (metadata)
- `nodes[].data.config.validation` (UI cache)
- `schema_version`는 **포함 권장** (계약 버전 영향)

Canonical JSON + SHA-256 → `graph_version_hash`.  
`config_hash`는 values-only 하위 해시로 선택적.

### 13.2 Idempotency

동일 `graph_version_hash`로 재 compile → 동일 artifact (byte-stable canonicalization).

### 13.3 Stale

- values/edges/handles/component_type 변경 → STALE
- label/position/viewport만 변경 → STALE 아님
- 저장/버전 저장은 stale과 독립 (저장은 항상 가능)

---

## 14. Security / Secret handling

| 규칙 | 내용 |
|------|------|
| Input | secret-like key/value는 STRICT에서 issue; compile은 원문 복사 금지 |
| Output | `credential_ref`만 |
| Unresolved ref | S6-1: WARNING 또는 INFO 가능; S6-2+ materialize 시 ERROR |
| Preview credential existence | S6-1 **미필수** (D8: 얕은 검사) |
| Logs / issues | secret 값 금지; key name만 |

---

## 15. UI/UX 설계안 (후속, S6-0 미구현)

### 15.1 Toolbar

| 버튼 | S6-1 | S6-3 | 비고 |
|------|------|------|------|
| Graph 검증 | 유지 (BASIC) | STRICT 유도 옵션 | |
| Compile Preview | — | 추가 | preview API |
| Compile | — | S6-2 후 | persist |
| Run / Schedule | disabled | disabled until activation | |

### 15.2 Graph Status Panel

- `current_sync_status`
- last compiled at / hash (S6-2+)
- compile issues summary

### 15.3 Validation vs Compile

- Validation Panel: topology + CONFIG
- Compile Preview panel/modal: artifact steps + compile issues

### 15.4 Dirty graph (D10)

| 동작 | 권장 |
|------|------|
| Compile Preview | transient `compile-graph` **허용** (저장 안 해도 preview) |
| Compile (persist) | **저장 후** current_graph_json만 |

---

## 16. 테스트 전략 (S6-1+)

| 영역 | 케이스 |
|------|--------|
| Preview unit | valid 4-node artifact shape |
| Fail | missing config STRICT, invalid edge, unsupported transform |
| Pattern | REST→Upsert direct, CRON schedule section |
| Secret | inline rejected; output no secret |
| Hash | idempotent; viewport/label ignore |
| Status | S6-2: STALE/IN_SYNC/FAILED |
| FE | compile preview smoke |
| Regression | S5 catalog/storage/validation/E2E 유지 |

---

## 17. 단계별 구현 로드맵

| 단계 | 내용 | 산출 |
|------|------|------|
| **R11-S6-0** | Compile 설계 (본 문서) | design doc |
| **R11-S6-1** | Compile Preview API PoC (no persistence) | `compile-preview` (+ optional `compile-graph`) |
| **R11-S6-2** | Persistence + `current_sync_status` 전이 | table 또는 column + GET compile-result |
| **R11-S6-3** | Studio Compile Preview UI | toolbar/panel |
| **R11-S6-4** | R10 operation/write/schedule materialization PoC | adapter writers (R10 API 호출, worker activation 없음) |
| **R11-S6-5** | compile/run boundary + tests | regression, docs |

순서 조정 시 Decision Log에 근거를 남긴다.

---

## 18. Decision Log

| ID | 주제 | 옵션 | **S6-0 권장** | 적용 |
|----|------|------|---------------|------|
| D1 | Compile input | current vs body | **current_graph_json 기본**; body는 preview only | S6-1 |
| D2 | Persistence | A/B/C/D | **S6-1=D**; **장기=C (차선 A)**; B는 비권장 | S6-1/2 |
| D3 | S6-1 API | preview vs compile | **`compile-preview` 우선** | S6-1 |
| D4 | sync_status timing | preview updates? | **S6-1 미갱신**; S6-2 persist 시 전이 | S6-2 |
| D5 | CRON active_yn | activate on compile? | **schedule config only; no activation** | 전 단계 |
| D6 | graph hash fields | include label/viewport? | **values/edges/handles/type; exclude viewport/label/validation** | S6-1 |
| D7 | REST→Upsert | allow? | **허용 + Transform 권장** | MVP |
| D8 | secret ref depth | resolve existence? | **S6-1 shallow**; deep resolve S6-2+ | S6-1 |
| D9 | materialization | with preview? | **S6-4**; S6-1 artifact only | S6-4 |
| D10 | dirty compile | block? | **preview optional transient; persist requires saved graph** | S6-1/3 |

---

## 19. Non-goals (재확인)

- Compile / Preview **API 구현** (S6-0)
- Run / Schedule activation / due worker 등록
- 외부 REST 호출 / Upsert 실쓰기
- R10 본기능·Pipeline Builder 수정
- DB/schema/migration/package 변경
- Auth/User management
- S5 validation 정책·config shape breaking change

---

## 20. 관련 문서 / 코드 앵커

| 문서·코드 | 역할 |
|-----------|------|
| `docs/md/THERMOps_R11-S5-0_...설계.md` §9 | compile 연계 초안 |
| `component_catalog_service.py` | compile_role, execution_adapter, connection rules |
| `config_validation_service.py` / `graph_validation_service.py` | STRICT gate |
| `visual_pipeline_service.py` | `NOT_COMPILED`, snapshot `compiled_target: null` |
| R10 entities | `ApiConnectorOperation`, `ApiConnectorTransformConfig`, `ApiConnectorWritePolicy`, `DataLoadSchedule` |

---

## 21. S6-1 진입 체크리스트

- [ ] STRICT validation 재사용
- [ ] MVP cardinality + REST→Upsert
- [ ] Artifact envelope + steps/schedule/write_policy
- [ ] graph_version_hash (D6)
- [ ] secret ref-only output
- [ ] `persisted: false`
- [ ] status 미변경
- [ ] catalog/storage/validation/E2E regression 유지
