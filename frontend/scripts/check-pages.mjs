import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const API_BASE = process.env.THERMOOPS_API_BASE || "http://localhost:8000/api/v1";
const FRONTEND_SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src");
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const PATHS = [
  "/dashboard",
  "/data/sources",
  "/prediction-entities",
  "/external-code-mappings",
  "/standard-datasets",
  "/data/mappings",
  "/features",
  "/feature-recipes",
  "/feature-recipes/new",
  "/feature-sets",
  "/dataset-versions",
  "/models/training-jobs",
  "/predictions/jobs",
  "/predictions/results",
  "/predictions/errors",
  "/ops/pipeline-runs",
  "/pipeline-builder",
  "/ops/model-monitoring",
  "/ops/drift-reports",
  "/ops/retraining-candidates",
  "/data-load-schedules",
  "/notifications",
  "/visual-pipelines",
  "/visual-pipeline-ops",
  "/system/configs",
];

/** B25: GET /data-sources size must be <= 100 (API max). Do not flag /pipeline-runs size: 200. */
function assertNoDataSourcesSizeOver100() {
  const files = [];
  function walk(dir) {
    for (const name of fs.readdirSync(dir)) {
      const full = path.join(dir, name);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(name)) files.push(full);
    }
  }
  walk(FRONTEND_SRC);
  const bad = [];
  for (const file of files) {
    const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (!line.includes('"/data-sources"') && !line.includes("'/data-sources'")) continue;
      if (/\/data-sources[/$`]/.test(line)) continue;
      const window = lines.slice(Math.max(0, i - 2), Math.min(lines.length, i + 4)).join("\n");
      const m = window.match(/\bsize:\s*(\d+)/);
      if (m && Number(m[1]) > 100) {
        bad.push(`${path.relative(FRONTEND_SRC, file)}:${i + 1} size=${m[1]}`);
      }
    }
  }
  if (bad.length) {
    throw new Error(
      `B25 regression: /data-sources list size must be <= 100 (got >100):\n  ${bad.join("\n  ")}`,
    );
  }
}

/** B24: Standard dataset archive UI must use existing archive API and safe copy. */
function assertStandardDatasetArchiveUi() {
  const pageFile = path.join(FRONTEND_SRC, "pages/StandardDatasetsPage.tsx");
  const content = fs.readFileSync(pageFile, "utf8");
  if (!content.includes("archiveStandardDatasetType")) {
    throw new Error("B24 regression: StandardDatasetsPage must call archiveStandardDatasetType");
  }
  if (!content.includes("standard-dataset-archive-button-")) {
    throw new Error("B24 regression: row archive button testid missing");
  }
  if (!content.includes("standard-dataset-archive-detail-button")) {
    throw new Error("B24 regression: detail archive button testid missing");
  }
  if (!content.includes("물리 테이블 또는 적재 데이터는 삭제하지 않습니다")) {
    throw new Error("B24 regression: archive confirm must mention physical table retention");
  }
  const apiClient = fs.readFileSync(path.join(FRONTEND_SRC, "api/standardDatasets.ts"), "utf8");
  if (!apiClient.includes("/standard-dataset-types/") || !apiClient.includes("/archive")) {
    throw new Error("B24 regression: standardDatasets API client must expose /standard-dataset-types/{id}/archive");
  }
  for (const phrase of ["영구 삭제", "테이블 삭제"]) {
    if (content.includes(phrase)) {
      throw new Error(`B24 regression: StandardDatasetsPage must not contain '${phrase}'`);
    }
  }
}

/** B11: Data Source select UX must keep size<=100 and expose search/load-more/refresh. */
function assertDataSourcePagedSelectUx() {
  const constFile = fs.readFileSync(path.join(FRONTEND_SRC, "constants/dataSourceList.ts"), "utf8");
  if (!constFile.includes("DATA_SOURCE_LIST_PAGE_SIZE = 100")) {
    throw new Error("B11 regression: DATA_SOURCE_LIST_PAGE_SIZE must remain 100");
  }
  if (!constFile.includes("fetchDataSourcesPage") || !constFile.includes("filterDataSourcesLocal")) {
    throw new Error("B11 regression: dataSourceList helpers missing");
  }
  if (!constFile.includes("현재 로드된 항목 내에서만 검색합니다")) {
    throw new Error("B11 regression: client-side search limitation hint missing");
  }
  const wizard = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/ApiConnectorOperationWizard.tsx"),
    "utf8",
  );
  for (const token of [
    "data-source-search-input",
    "data-source-load-more",
    "data-source-refresh-button",
    "data-source-list-hint",
    "data-source-search-hint",
    "selectedDataSourceMissingLabel",
  ]) {
    if (!wizard.includes(token)) {
      throw new Error(`B11 regression: Wizard missing ${token}`);
    }
  }
  const panel = fs.readFileSync(path.join(FRONTEND_SRC, "components/ApiConnectorPanel.tsx"), "utf8");
  if (!panel.includes("fetchDataSourcesPage") || !panel.includes("onLoadMoreSources")) {
    throw new Error("B11 regression: ApiConnectorPanel must page-load Data Sources");
  }
  if (panel.includes("size: 200") || /size:\s*([2-9]\d{2,}|\d{4,})/.test(panel)) {
    throw new Error("B11 regression: ApiConnectorPanel must not request size>100");
  }
  const mappings = fs.readFileSync(path.join(FRONTEND_SRC, "pages/DataMappingsPage.tsx"), "utf8");
  if (!mappings.includes("fetchDataSourcesPage") || !mappings.includes("mapping-data-source-search-input")) {
    throw new Error("B11 regression: DataMappingsPage must reuse paged Data Source UX");
  }
}

/** B19: Studio REST Inspector Data Source select + REST_API-only inline create (no secret UI). */
function assertStudioRestDataSourceInlineCreate() {
  const constFile = fs.readFileSync(path.join(FRONTEND_SRC, "constants/dataSourceList.ts"), "utf8");
  if (!constFile.includes("createRestDataSource") || !constFile.includes('source_type: "REST_API"')) {
    throw new Error("B19 regression: createRestDataSource REST_API helper missing");
  }
  if (!constFile.includes('auth_type: "NONE"')) {
    throw new Error("B19 regression: inline create must default auth_type NONE");
  }
  if (!constFile.includes("DATA_SOURCE_CREDENTIAL_REF_HELP") || !constFile.includes("CRED-")) {
    throw new Error("B19 regression: credential_ref help constant missing");
  }
  if (!constFile.includes("DATA_SOURCE_INLINE_CREATE_AUTH_HINT")) {
    throw new Error("B19 regression: inline create auth hint constant missing");
  }
  if (constFile.includes("DATA_SOURCE_LIST_PAGE_SIZE = 200") || /size:\s*([2-9]\d{2,}|\d{4,})/.test(constFile)) {
    throw new Error("B19 regression: dataSourceList must not reintroduce size>100");
  }
  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpRestApiSourceConfigForm.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-data-source-picker",
    "visual-pipeline-data-source-select",
    "visual-pipeline-data-source-search-input",
    "visual-pipeline-data-source-refresh-button",
    "visual-pipeline-data-source-load-more",
    "visual-pipeline-data-source-create-form",
    "createRestDataSource",
    "DATA_SOURCE_CREDENTIAL_REF_HELP",
    "DATA_SOURCE_INLINE_CREATE_AUTH_HINT",
    "고급: ID 직접 입력",
  ]) {
    if (!form.includes(token)) {
      throw new Error(`B19 regression: VpRestApiSourceConfigForm missing ${token}`);
    }
  }
  if (form.includes("api_key") || form.includes("password") || form.includes("type=\"password\"")) {
    throw new Error("B19 regression: Studio inline create must not add secret/api_key/password fields");
  }
  if (form.includes("size: 200") || /size:\s*([2-9]\d{2,}|\d{4,})/.test(form)) {
    throw new Error("B19 regression: Studio REST form must not request size>100");
  }
}

/** B20: Studio Upsert Inspector Standard Dataset select + DRAFT-only inline create. */
function assertStudioUpsertStandardDatasetInlineCreate() {
  const constFile = fs.readFileSync(path.join(FRONTEND_SRC, "constants/standardDatasetList.ts"), "utf8");
  if (!constFile.includes("createInlineStandardDataset") || !constFile.includes('status: "DRAFT"')) {
    throw new Error("B20 regression: createInlineStandardDataset DRAFT helper missing");
  }
  if (!constFile.includes("fetchActiveStandardDatasets") || !constFile.includes("STANDARD_DATASET_LIST_HINT")) {
    throw new Error("B20 regression: standardDatasetList helpers missing");
  }
  if (constFile.includes("createPhysicalTable") || constFile.includes("/create-physical-table")) {
    throw new Error("B20 regression: helpers must not create physical tables");
  }
  if (constFile.includes("더 보기") || constFile.includes("load-more") || constFile.includes("LOAD_MORE")) {
    throw new Error("B20 regression: standard dataset list must not reintroduce load-more");
  }
  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpUpsertLoadConfigForm.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-standard-dataset-picker",
    "visual-pipeline-standard-dataset-select",
    "visual-pipeline-standard-dataset-search-input",
    "visual-pipeline-standard-dataset-refresh-button",
    "visual-pipeline-standard-dataset-create-form",
    "createInlineStandardDataset",
    "standard_dataset_id",
    "target_table",
    "고급: ID 직접 입력",
  ]) {
    if (!form.includes(token)) {
      throw new Error(`B20 regression: VpUpsertLoadConfigForm missing ${token}`);
    }
  }
  if (form.includes("target_dataset_type_id") || form.includes("target_table_name")) {
    throw new Error("B20 regression: must use standard_dataset_id + target_table only");
  }
  if (form.includes("createPhysicalTable") || form.includes("activateStandardDatasetType")) {
    throw new Error("B20 regression: Upsert form must not activate or create physical tables");
  }
  for (const banned of ["영구 삭제", "테이블 삭제", "DROP TABLE", "unarchive", "schema inference", "auto proposal"]) {
    if (form.includes(banned)) {
      throw new Error(`B20 regression: Upsert form must not contain '${banned}'`);
    }
  }
  if (form.includes("visual-pipeline-standard-dataset-load-more")) {
    throw new Error("B20 regression: Upsert form must not expose load-more button");
  }
}

/** B21: Transform output → Standard Dataset column draft proposal in Upsert inline create. */
function assertStudioUpsertTransformColumnProposal() {
  const proposal = fs.readFileSync(
    path.join(FRONTEND_SRC, "utils/transformOutputColumnProposal.ts"),
    "utf8",
  );
  for (const token of [
    "proposeTransformOutputColumns",
    "proposedColumnsToCreatePayload",
    "WIDE_HOUR_TO_LONG",
    "heat_demand",
    "measured_at",
    "isRestDirectUpsertInput",
    "TRANSFORM_COLUMN_PROPOSAL_HINT",
  ]) {
    if (!proposal.includes(token)) {
      throw new Error(`B21 regression: transformOutputColumnProposal missing ${token}`);
    }
  }
  if (proposal.includes("conflict_key") || proposal.includes("schema inference")) {
    throw new Error("B21 regression: proposal must not auto-recommend conflict keys or run schema inference");
  }

  const graph = fs.readFileSync(path.join(FRONTEND_SRC, "utils/visualPipelineGraph.ts"), "utf8");
  if (!graph.includes("findUpstreamTransformForUpsert")) {
    throw new Error("B21 regression: findUpstreamTransformForUpsert helper missing");
  }

  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpUpsertLoadConfigForm.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-standard-dataset-propose-columns",
    "visual-pipeline-standard-dataset-column-editor",
    "visual-pipeline-standard-dataset-column-add",
    "visual-pipeline-standard-dataset-column-delete",
    "proposeTransformOutputColumns",
    "studioGraph",
    "컬럼 후보 제안",
  ]) {
    if (!form.includes(token)) {
      throw new Error(`B21 regression: VpUpsertLoadConfigForm missing ${token}`);
    }
  }
  for (const banned of ["auto proposal", "conflict key 추천", "source↔target", "column normalization"]) {
    if (form.includes(banned)) {
      throw new Error(`B21 regression: Upsert form must not contain '${banned}'`);
    }
  }

  const inspector = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpNodeInspector.tsx"),
    "utf8",
  );
  if (!inspector.includes("studioNodes") || !inspector.includes("studioEdges") || !inspector.includes("studioGraph")) {
    throw new Error("B21 regression: VpNodeInspector must pass studio graph to Upsert form");
  }
}

/** B15: Source ↔ Target column match preview (FE diagnosis only, no mapping save). */
function assertStudioUpsertColumnMatchPreview() {
  const helper = fs.readFileSync(
    path.join(FRONTEND_SRC, "utils/columnNormalizationPreview.ts"),
    "utf8",
  );
  for (const token of [
    "normalizeColumnName",
    "buildColumnMatchPreview",
    "EXACT",
    "NORMALIZED",
    "UNMATCHED_SOURCE",
    "MISSING_TARGET",
    "TYPE_MISMATCH",
    "AMBIGUOUS",
    "COLUMN_MATCH_PREVIEW_HINT",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B15 regression: columnNormalizationPreview missing ${token}`);
    }
  }
  if (helper.includes("conflict_key") && /recommend|auto.?conflict/i.test(helper)) {
    throw new Error("B15 regression: helper must not auto-recommend conflict keys");
  }

  const listHelper = fs.readFileSync(path.join(FRONTEND_SRC, "constants/standardDatasetList.ts"), "utf8");
  if (!listHelper.includes("fetchStandardDatasetColumns") || !listHelper.includes("include_columns: true")) {
    throw new Error("B15 regression: fetchStandardDatasetColumns helper missing");
  }

  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpUpsertLoadConfigForm.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-column-match-preview",
    "visual-pipeline-column-match-compare-button",
    "visual-pipeline-column-match-summary",
    "buildColumnMatchPreview",
    "컬럼 정합성 미리보기",
    "Source ↔ Target 컬럼 비교",
  ]) {
    if (!form.includes(token)) {
      throw new Error(`B15 regression: VpUpsertLoadConfigForm missing ${token}`);
    }
  }
  for (const banned of [
    "column_mapping:",
    "field_mapping:",
    "conflict_keys recommend",
    "auto conflict",
    "영구 삭제",
    "테이블 삭제",
    "DROP TABLE",
    "createPhysicalTable",
  ]) {
    if (form.includes(banned)) {
      throw new Error(`B15 regression: Upsert form must not contain '${banned}'`);
    }
  }
  // Preview must be local-state only — no config.values mapping write.
  if (/onChange\(\s*\{\s*[^}]*column_mapping/.test(form) || /onChange\(\s*\{\s*[^}]*field_mapping/.test(form)) {
    throw new Error("B15 regression: must not save column_mapping/field_mapping via onChange");
  }
}

/** B27: Upsert conflict_key_columns_json select / validate / recommend (no auto-confirm). */
function assertStudioUpsertConflictKeysUx() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/conflictKeyValidation.ts"), "utf8");
  for (const token of [
    "suggestConflictKeyCandidates",
    "validateConflictKeys",
    "parseConflictKeyColumns",
    "CONFLICT_KEYS_RECOMMEND_HINT",
    "entity_id",
    "measured_at",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B27 regression: conflictKeyValidation missing ${token}`);
    }
  }
  if (/auto.?apply|autosave|자동 저장/.test(helper) && /recommend/.test(helper)) {
    // soft check — recommend hint must say not auto-saved
  }
  if (!helper.includes("자동 저장되지 않습니다")) {
    throw new Error("B27 regression: recommend hint must state recommendations are not auto-saved");
  }
  for (const banned of ["CREATE INDEX", "create index", "unique index", "migration"]) {
    if (helper.includes(banned)) {
      throw new Error(`B27 regression: helper must not contain '${banned}'`);
    }
  }

  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpUpsertLoadConfigForm.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-conflict-keys-panel",
    "visual-pipeline-conflict-keys-recommend-toggle",
    "visual-pipeline-conflict-keys-recommend-item",
    "visual-pipeline-conflict-keys-selected",
    "visual-pipeline-conflict-keys-validation",
    "conflict_key_columns_json",
    "suggestConflictKeyCandidates",
    "validateConflictKeys",
  ]) {
    if (!form.includes(token)) {
      throw new Error(`B27 regression: VpUpsertLoadConfigForm missing ${token}`);
    }
  }
  for (const banned of [
    "CREATE INDEX",
    "unique index",
    "영구 삭제",
    "DROP TABLE",
    "conflict_keys:",
    "auto confirm",
    "자동 확정",
  ]) {
    if (form.includes(banned)) {
      throw new Error(`B27 regression: Upsert form must not contain '${banned}'`);
    }
  }
  // Must save via existing contract field only
  if (!form.includes("onChange({ conflict_key_columns_json:")) {
    throw new Error("B27 regression: must persist via conflict_key_columns_json onChange");
  }
}

/** B18: Target Table sample rows read-only preview. */
function assertStudioTargetTableSamplePreview() {
  const apiClient = fs.readFileSync(path.join(FRONTEND_SRC, "api/standardDatasets.ts"), "utf8");
  if (!apiClient.includes("previewTargetTableSample") || !apiClient.includes("target-table-preview")) {
    throw new Error("B18 regression: previewTargetTableSample client missing");
  }

  const backendService = fs.readFileSync(
    path.join(REPO_ROOT, "backend/app/services/target_table_preview_service.py"),
    "utf8",
  );
  for (const token of ["preview_target_table_sample", "quote_ident", "MAX_PREVIEW_LIMIT = 100", "SELECT COUNT(*)"]) {
    if (!backendService.includes(token)) {
      throw new Error(`B18 regression: target_table_preview_service missing ${token}`);
    }
  }
  for (const banned of ["DROP TABLE", "TRUNCATE", "DELETE FROM", "UPDATE ", "INSERT INTO"]) {
    if (backendService.includes(banned)) {
      throw new Error(`B18 regression: preview service must not contain '${banned.trim()}'`);
    }
  }

  const backendApi = fs.readFileSync(
    path.join(REPO_ROOT, "backend/app/api/v1/standard_dataset.py"),
    "utf8",
  );
  if (!backendApi.includes('"/standard-dataset-types/target-table-preview"')) {
    throw new Error("B18 regression: target-table-preview endpoint missing");
  }

  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpUpsertLoadConfigForm.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-target-table-preview",
    "visual-pipeline-target-table-preview-query-button",
    "visual-pipeline-target-table-preview-limit",
    "previewTargetTableSample",
    "읽기 전용",
  ]) {
    if (!form.includes(token)) {
      throw new Error(`B18 regression: VpUpsertLoadConfigForm missing ${token}`);
    }
  }
  if (!form.includes("option value={50}") && !form.includes("value={50}")) {
    throw new Error("B18 regression: preview limit options incomplete");
  }
  for (const banned of ["DROP TABLE", "TRUNCATE TABLE", "DELETE FROM", "INSERT INTO"]) {
    if (form.includes(banned)) {
      throw new Error(`B18 regression: Upsert form must not contain '${banned}'`);
    }
  }
}

/** B12: Visual Pipeline E2E smoke script (journey regression). */
function assertVisualPipelineE2eSmoke() {
  const e2ePath = path.join(path.dirname(fileURLToPath(import.meta.url)), "check-visual-pipeline-e2e.mjs");
  if (!fs.existsSync(e2ePath)) {
    throw new Error("B12 regression: frontend/scripts/check-visual-pipeline-e2e.mjs missing");
  }
  const text = fs.readFileSync(e2ePath, "utf8");
  for (const token of ["E2E_B12_", "[B12][", "실행 설정 반영", "fail(", "throw new Error"]) {
    if (!text.includes(token)) {
      throw new Error(`B12 regression: e2e script missing ${token}`);
    }
  }
  if (text.includes("R10 설정 반영")) {
    throw new Error("B12 regression: e2e script must not re-expose 「R10 설정 반영」");
  }
  if (!/function fail\([\s\S]*?throw new Error/.test(text)) {
    throw new Error("B12 regression: fail() must throw");
  }
  for (const banned of ["DROP TABLE", "TRUNCATE TABLE", "DELETE FROM", "UPDATE ", "INSERT INTO"]) {
    if (text.includes(banned)) {
      throw new Error(`B12 regression: e2e script must not contain physical DML '${banned.trim()}'`);
    }
  }
}

/** B6: Run Detail failure summary helper + panel card. */
function assertRunFailureSummaryUx() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/runFailureSummary.ts"), "utf8");
  for (const token of [
    "buildRunFailureSummary",
    "mapRunStepName",
    'severity: "none"',
    "FALLBACK_REASON",
    "Traceback",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B6 regression: runFailureSummary missing ${token}`);
    }
  }
  if (helper.includes("R10 설정 반영")) {
    throw new Error("B6 regression: helper must not re-expose R10 label");
  }

  const panel = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpRunDetailPanel.tsx"),
    "utf8",
  );
  for (const token of [
    "buildRunFailureSummary",
    "failure-summary",
    "실패 원인 요약",
    "showFailureSummary",
  ]) {
    if (!panel.includes(token)) {
      throw new Error(`B6 regression: VpRunDetailPanel missing ${token}`);
    }
  }
  if (!panel.includes('failureSummary.severity !== "none"')) {
    throw new Error("B6 regression: SUCCESS/RUNNING must hide failure summary card");
  }
  if (panel.includes("R10 설정 반영")) {
    throw new Error("B6 regression: Run Detail must not re-expose R10 label");
  }
  // Must not dump raw Traceback into the summary card JSX as a template.
  if (/failure-summary[\s\S]{0,400}Traceback/.test(panel)) {
    throw new Error("B6 regression: failure summary card must not embed Traceback dumps");
  }
}

/** B10: Ops action-required card (FE-only, no auto actions / notification badge). */
function assertOpsActionRequiredCard() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/opsActionRequired.ts"), "utf8");
  for (const token of ["buildOpsActionRequired", "stuck", "failed", "partial", "catchup_hint"]) {
    if (!helper.includes(token)) {
      throw new Error(`B10 regression: opsActionRequired missing ${token}`);
    }
  }
  for (const banned of ["function autoRetry", "autoRetry(", "autoCatchup(", "autoCancel(", "enqueueAuto"]) {
    if (helper.includes(banned)) {
      throw new Error(`B10 regression: helper must not implement ${banned}`);
    }
  }

  const card = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpActionRequiredCard.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-ops-action-required",
    "조치 필요",
    "visual-pipeline-ops-action-required-empty",
    "visual-pipeline-ops-action-required-detail-button",
  ]) {
    if (!card.includes(token)) {
      throw new Error(`B10 regression: VpActionRequiredCard missing ${token}`);
    }
  }
  if (card.includes("notification") && /badge|read.?unread|readAt/i.test(card)) {
    throw new Error("B10 regression: must not implement notification badge/read-unread");
  }
  if (card.includes("R10 설정 반영")) {
    throw new Error("B10 regression: must not re-expose R10 label");
  }
  for (const banned of ["자동 재시도 실행", "자동 Catch-up 실행", "자동 중단 실행", "autoRetry(", "autoCatchup("]) {
    if (card.includes(banned)) {
      throw new Error(`B10 regression: card must not advertise ${banned}`);
    }
  }

  const page = fs.readFileSync(path.join(FRONTEND_SRC, "pages/VisualPipelineOpsPage.tsx"), "utf8");
  if (!page.includes("VpActionRequiredCard") || !page.includes("buildOpsActionRequired")) {
    throw new Error("B10 regression: VisualPipelineOpsPage must mount action-required card");
  }
  if (page.includes("R10 설정 반영")) {
    throw new Error("B10 regression: Ops page must not re-expose R10 label");
  }
}

/** B9: Ops Schedule Skip history panel (read-only API + FE mapping, no auto actions). */
function assertScheduleSkipHistoryUx() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/scheduleSkipReason.ts"), "utf8");
  for (const token of [
    "describeScheduleSkipReason",
    "ACTIVE_RUN_EXISTS",
    "STALE_OR_INVALID",
    "DUPLICATE_DEDUP_KEY",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B9 regression: scheduleSkipReason missing ${token}`);
    }
  }

  const panel = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpScheduleSkipHistoryPanel.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-ops-schedule-skip-history",
    "스케줄 Skip 이력",
    "visual-pipeline-ops-schedule-skip-empty",
    "visual-pipeline-ops-schedule-skip-refresh",
    "describeScheduleSkipReason",
  ]) {
    if (!panel.includes(token)) {
      throw new Error(`B9 regression: VpScheduleSkipHistoryPanel missing ${token}`);
    }
  }
  for (const banned of [
    "자동 Catch-up 실행",
    "자동 재시도 실행",
    "자동 중단 실행",
    "autoCatchup(",
    "autoRetry(",
    "autoCancel(",
  ]) {
    if (panel.includes(banned)) {
      throw new Error(`B9 regression: skip panel must not advertise ${banned}`);
    }
  }
  if (panel.includes("R10 설정 반영")) {
    throw new Error("B9 regression: must not re-expose R10 label");
  }
  if (panel.includes("notification") && /badge|read.?unread|readAt/i.test(panel)) {
    throw new Error("B9 regression: must not implement notification badge/read-unread");
  }

  const api = fs.readFileSync(path.join(FRONTEND_SRC, "api/visualPipelineOps.ts"), "utf8");
  if (!api.includes("getVisualPipelineOpsScheduleSkips") || !api.includes("/schedule-skips")) {
    throw new Error("B9 regression: visualPipelineOps client must call /schedule-skips");
  }

  const page = fs.readFileSync(path.join(FRONTEND_SRC, "pages/VisualPipelineOpsPage.tsx"), "utf8");
  if (!page.includes("VpScheduleSkipHistoryPanel") || !page.includes("getVisualPipelineOpsScheduleSkips")) {
    throw new Error("B9 regression: VisualPipelineOpsPage must mount skip history panel");
  }
  if (page.includes("R10 설정 반영")) {
    throw new Error("B9 regression: Ops page must not re-expose R10 label");
  }

  const card = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpActionRequiredCard.tsx"),
    "utf8",
  );
  if (!card.includes("visual-pipeline-ops-action-required-skip-history-link")) {
    throw new Error("B9 regression: B10 card should expose Skip 이력 anchor link");
  }
}

/** B4: Catch-up guidance copy (FE-only, no auto recovery / policy change). */
function assertCatchupGuidanceUx() {
  const guidance = fs.readFileSync(path.join(FRONTEND_SRC, "utils/catchupGuidance.ts"), "utf8");
  for (const token of [
    "CATCHUP_SUMMARY",
    "CATCHUP_NOT_AUTO_RECOVERY",
    "CATCHUP_TERM_DEFINITIONS",
    "CATCHUP_PRE_RUN_CHECKLIST",
    "CATCHUP_OPS_SKIP_BRIDGE",
    "missed",
    "candidate",
    "window",
    "skip_reason",
    "자동 복구가 아니",
  ]) {
    if (!guidance.includes(token)) {
      throw new Error(`B4 regression: catchupGuidance missing ${token}`);
    }
  }
  for (const banned of ["자동 복구됨", "자동 처리", "autoCatchup(", "enqueueAutoCatchup"]) {
    if (guidance.includes(banned)) {
      throw new Error(`B4 regression: catchupGuidance must not imply ${banned}`);
    }
  }

  const skipHelper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/scheduleSkipReason.ts"), "utf8");
  if (!skipHelper.includes("nextChecksForScheduleSkipReason")) {
    throw new Error("B4 regression: scheduleSkipReason must export nextChecksForScheduleSkipReason");
  }

  const card = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpCatchupGuidance.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-catchup-guidance",
    "visual-pipeline-catchup-guidance-toggle",
    "visual-pipeline-catchup-guidance-details",
    "visual-pipeline-catchup-guidance-terms",
    "visual-pipeline-catchup-guidance-checklist",
    "CATCHUP_NOT_AUTO_RECOVERY",
  ]) {
    if (!card.includes(token)) {
      throw new Error(`B4 regression: VpCatchupGuidance missing ${token}`);
    }
  }
  if (card.includes("R10 설정 반영")) {
    throw new Error("B4 regression: must not re-expose R10 label");
  }

  const panel = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpScheduleActivationPanel.tsx"),
    "utf8",
  );
  if (!panel.includes("VpCatchupGuidance") || !panel.includes("visual-pipeline-schedule-catchup-section")) {
    throw new Error("B4 regression: Schedule Activation Catch-up section must mount VpCatchupGuidance");
  }

  const skipPanel = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpScheduleSkipHistoryPanel.tsx"),
    "utf8",
  );
  if (!skipPanel.includes("visual-pipeline-ops-schedule-skip-catchup-bridge") || !skipPanel.includes("CATCHUP_OPS_SKIP_BRIDGE")) {
    throw new Error("B4 regression: Ops skip panel must include Catch-up bridge copy");
  }
}

/** B8: PARTIAL impact / retry-precheck card (FE-only, no auto dedup). */
function assertPartialImpactUx() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/partialImpactSummary.ts"), "utf8");
  for (const token of [
    "buildPartialImpactSummary",
    "extractUpsertHintsFromGraph",
    "PARTIAL_IMPACT_CHECKLIST",
    "duplicateRisk",
    "확인 필요",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B8 regression: partialImpactSummary missing ${token}`);
    }
  }
  for (const banned of [
    "중복이 발생했습니다",
    "안전하게 재실행",
    "자동으로 중복 제거",
    "autoDedup(",
    "autoRetry(",
  ]) {
    if (helper.includes(banned)) {
      throw new Error(`B8 regression: helper must not use ${banned}`);
    }
  }

  const card = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpPartialImpactCard.tsx"),
    "utf8",
  );
  for (const token of [
    "partial-impact",
    "partial-impact-checklist",
    "partial-impact-duplicate-risk",
    "partial-impact-preview-hint",
    "Target Preview",
    "summary.title",
  ]) {
    if (!card.includes(token)) {
      throw new Error(`B8 regression: VpPartialImpactCard missing ${token}`);
    }
  }
  for (const banned of ["중복이 발생했습니다", "자동으로 중복 제거", "autoDedup("]) {
    if (card.includes(banned)) {
      throw new Error(`B8 regression: card must not claim ${banned}`);
    }
  }
  if (card.includes("R10 설정 반영")) {
    throw new Error("B8 regression: must not re-expose R10 label");
  }

  const panel = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpRunDetailPanel.tsx"),
    "utf8",
  );
  if (!panel.includes("VpPartialImpactCard") || !panel.includes("buildPartialImpactSummary")) {
    throw new Error("B8 regression: VpRunDetailPanel must mount PARTIAL impact card");
  }
  if (panel.includes("R10 설정 반영")) {
    throw new Error("B8 regression: Run Detail must not re-expose R10 label");
  }

  const opsHelper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/opsActionRequired.ts"), "utf8");
  if (!opsHelper.includes("PARTIAL") || !opsHelper.includes("Retry")) {
    throw new Error("B8 regression: B10 PARTIAL reason should mention PARTIAL / Retry precheck");
  }
  if (!opsHelper.includes("영향") && !opsHelper.includes("Run Detail")) {
    throw new Error("B8 regression: B10 PARTIAL reason should point to Run Detail impact check");
  }
  if (!helper.includes("Schema/Key Helper")) {
    throw new Error("B8 regression: PARTIAL checklist should mention Schema/Key Helper (B3 bridge)");
  }
}

/** B3: Schema / Key Mapping Helper (FE-only diagnosis + recommend apply to form state). */
function assertSchemaKeyMappingHelper() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/schemaKeyMappingHelper.ts"), "utf8");
  for (const token of [
    "buildSchemaKeyMappingSummary",
    "SCHEMA_KEY_HELPER_HINT",
    "buildColumnMatchPreview",
    "suggestConflictKeyCandidates",
    "validateConflictKeys",
    "canApplyRecommendedKeys",
    "recommendedConflictKeys",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B3 regression: schemaKeyMappingHelper missing ${token}`);
    }
  }
  for (const banned of [
    "autoSave",
    "autoCompile",
    "autoMaterialize",
    "CREATE UNIQUE",
    "unique index",
    "DROP TABLE",
    "TRUNCATE",
    "R10 설정 반영",
    "tb_visual_pipeline_notification",
  ]) {
    if (helper.includes(banned)) {
      throw new Error(`B3 regression: helper must not include '${banned}'`);
    }
  }
  if (!helper.includes("자동 저장되지 않으며")) {
    throw new Error("B3 regression: helper hint must state no auto-save");
  }

  const card = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpSchemaKeyMappingHelper.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-schema-key-helper",
    "visual-pipeline-schema-key-helper-summary",
    "visual-pipeline-schema-key-helper-apply",
    "Schema / Key Helper",
    "추천 기준키 적용",
  ]) {
    if (!card.includes(token)) {
      throw new Error(`B3 regression: VpSchemaKeyMappingHelper missing ${token}`);
    }
  }
  if (card.includes("R10 설정 반영") || card.includes("CREATE UNIQUE") || card.includes("autoCompile")) {
    throw new Error("B3 regression: card must not include R10 / unique index / autoCompile");
  }

  const form = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpUpsertLoadConfigForm.tsx"),
    "utf8",
  );
  if (!form.includes("VpSchemaKeyMappingHelper") || !form.includes("buildSchemaKeyMappingSummary")) {
    throw new Error("B3 regression: Upsert form must mount Schema/Key Helper");
  }
  if (!form.includes("onApplyRecommendedKeys")) {
    throw new Error("B3 regression: Upsert form must wire recommend apply");
  }
  for (const banned of ["CREATE UNIQUE", "unique index", "DROP TABLE", "R10 설정 반영", "autoMaterialize("]) {
    if (form.includes(banned)) {
      throw new Error(`B3 regression: Upsert form must not contain '${banned}'`);
    }
  }
}

/** B1: Visual Pipeline Starter Template (FE-only skeleton, no fake Type B ids). */
function assertStarterTemplateUx() {
  const catalog = fs.readFileSync(path.join(FRONTEND_SRC, "utils/starterTemplateCatalog.ts"), "utf8");
  for (const token of [
    "STARTER_TEMPLATE_CATALOG",
    "cron-full",
    "rest-upsert",
    "Scheduled REST Data Load",
    "Manual REST Data Load",
    "STARTER_TEMPLATE_APPLY_TOAST",
    "STARTER_TEMPLATE_TYPE_B_FIELDS",
  ]) {
    if (!catalog.includes(token)) {
      throw new Error(`B1 regression: starterTemplateCatalog missing ${token}`);
    }
  }
  for (const banned of [
    "DS-SAMPLE",
    "SDS-SAMPLE",
    "CRED-SAMPLE",
    "즉시 실행 가능",
    "자동으로 저장",
    "자동으로 설정",
    "R10 설정 반영",
  ]) {
    if (catalog.includes(banned)) {
      throw new Error(`B1 regression: catalog must not include '${banned}'`);
    }
  }

  const graphUtil = fs.readFileSync(path.join(FRONTEND_SRC, "utils/visualPipelineGraph.ts"), "utf8");
  if (!graphUtil.includes("buildStarterTemplateFlow") || !graphUtil.includes("buildTemplateGraph")) {
    throw new Error("B1 regression: buildStarterTemplateFlow must reuse buildTemplateGraph");
  }
  if (!graphUtil.includes("newNodeId")) {
    throw new Error("B1 regression: starter apply must remap with newNodeId");
  }

  const modal = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpStarterTemplateModal.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-starter-template-modal",
    "visual-pipeline-starter-template-apply",
    "visual-pipeline-starter-template-option-",
  ]) {
    if (!modal.includes(token)) {
      throw new Error(`B1 regression: VpStarterTemplateModal missing ${token}`);
    }
  }

  const page = fs.readFileSync(path.join(FRONTEND_SRC, "pages/VisualPipelineStudioPage.tsx"), "utf8");
  for (const token of [
    "VpStarterTemplateModal",
    "buildStarterTemplateFlow",
    "visual-pipeline-starter-template-button",
    "visual-pipeline-canvas-empty-starter-cta",
    "STARTER_TEMPLATE_APPLY_TOAST",
  ]) {
    if (!page.includes(token)) {
      throw new Error(`B1 regression: Studio page missing ${token}`);
    }
  }
  for (const banned of [
    "즉시 실행 가능합니다",
    "자동으로 저장되었습니다",
    "자동으로 설정되었습니다",
    "R10 설정 반영",
  ]) {
    if (page.includes(banned)) {
      throw new Error(`B1 regression: Studio must not advertise '${banned}'`);
    }
  }
  if (/createVisualPipeline\(|updateVisualPipeline\(/.test(page) && /applyStarterTemplate[\s\S]{0,800}updateVisualPipeline/.test(page)) {
    throw new Error("B1 regression: starter apply must not auto-save via updateVisualPipeline");
  }
}

/** B2: Domain Preset Framework (FE-only hints, no Type B auto-fill). */
function assertDomainPresetFramework() {
  const catalog = fs.readFileSync(path.join(FRONTEND_SRC, "utils/domainPresetCatalog.ts"), "utf8");
  for (const token of [
    "DOMAIN_PRESET_CATALOG",
    "generic_time_series_load",
    "heat_demand_forecast",
    "Generic Time-Series Load",
    "Heat Demand Forecast Data Load",
    "열수요 예측 데이터 적재 예시",
    "DOMAIN_PRESET_APPLY_TOAST",
    "DOMAIN_PRESET_TYPE_B_FIELDS",
    "WIDE_HOUR_TO_LONG",
  ]) {
    if (!catalog.includes(token)) {
      throw new Error(`B2 regression: domainPresetCatalog missing ${token}`);
    }
  }
  for (const banned of [
    "DS-SAMPLE",
    "SDS-SAMPLE",
    "CRED-SAMPLE",
    "즉시 실행 가능",
    "자동으로 적재",
    "자동으로 저장",
    "한국지역난방",
    "R10 설정 반영",
  ]) {
    if (catalog.includes(banned)) {
      throw new Error(`B2 regression: catalog must not include '${banned}'`);
    }
  }

  const applyHelper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/applyDomainPreset.ts"), "utf8");
  if (!applyHelper.includes("applyDomainPresetToFlow") || !applyHelper.includes("recommendedTransformType")) {
    throw new Error("B2 regression: applyDomainPresetToFlow must patch recommendedTransformType only");
  }
  if (
    /data_source_id\s*:/.test(applyHelper) ||
    /standard_dataset_id\s*:/.test(applyHelper) ||
    /credential_ref\s*:/.test(applyHelper) ||
    /conflict_key_columns_json\s*:/.test(applyHelper)
  ) {
    throw new Error("B2 regression: apply helper must not touch Type B / conflict keys");
  }

  const modal = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpStarterTemplateModal.tsx"),
    "utf8",
  );
  for (const token of [
    "visual-pipeline-domain-preset-section",
    "visual-pipeline-domain-preset-option-none",
    "visual-pipeline-domain-preset-option-",
    "domainPresetId",
    "DOMAIN_PRESET_CATALOG",
  ]) {
    if (!modal.includes(token)) {
      throw new Error(`B2 regression: VpStarterTemplateModal missing ${token}`);
    }
  }
  if (!modal.includes("generic_time_series_load") && !modal.includes("DOMAIN_PRESET_CATALOG")) {
    throw new Error("B2 regression: modal must render domain preset catalog options");
  }

  const page = fs.readFileSync(path.join(FRONTEND_SRC, "pages/VisualPipelineStudioPage.tsx"), "utf8");
  for (const token of ["applyDomainPresetToFlow", "DOMAIN_PRESET_APPLY_TOAST", "activeDomainPresetId"]) {
    if (!page.includes(token)) {
      throw new Error(`B2 regression: Studio page missing ${token}`);
    }
  }
  if (/applyStarterTemplate[\s\S]{0,1200}updateVisualPipeline/.test(page)) {
    throw new Error("B2 regression: starter+preset apply must not auto-save");
  }
  for (const banned of ["즉시 실행 가능합니다", "자동으로 적재됩니다", "R10 설정 반영"]) {
    if (page.includes(banned)) {
      throw new Error(`B2 regression: Studio must not advertise '${banned}'`);
    }
  }

  const helper = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpSchemaKeyMappingHelper.tsx"),
    "utf8",
  );
  if (!helper.includes("visual-pipeline-schema-key-helper-domain-preset-hint")) {
    throw new Error("B2 regression: B3 helper must show domain preset hint testid");
  }
  if (helper.includes("onChange({ conflict_key_columns_json") && /domainPreset[\s\S]{0,200}onChange/.test(helper)) {
    throw new Error("B2 regression: preset hint must not auto-write conflict keys");
  }
}

/** B7: Data Load → ML Workflow Handoff Guide (docs only, no ML implementation claims). */
function assertDataLoadMlHandoffGuide() {
  const guidePath = path.join(
    REPO_ROOT,
    "docs/md/THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md",
  );
  if (!fs.existsSync(guidePath)) {
    throw new Error("B7 regression: Handoff Guide markdown missing");
  }
  const guide = fs.readFileSync(guidePath, "utf8");
  for (const token of [
    "운영·설계 가이드",
    "신규 ML 학습/예측 기능을 구현하지 않는다",
    "Handoff 대상 산출물",
    "Handoff 전 검증",
    "Run 상태별 handoff",
    "Domain Preset",
    "backend source of truth가 아니다",
    "후속 구현 Roadmap",
    "예시",
  ]) {
    if (!guide.includes(token)) {
      throw new Error(`B7 regression: Handoff Guide missing '${token}'`);
    }
  }
  for (const banned of [
    "자동 학습 실행",
    "ML Workflow가 이미 구현",
    "즉시 예측 실행",
    "자동 예측 실행",
    "R10 설정 반영",
  ]) {
    if (guide.includes(banned)) {
      throw new Error(`B7 regression: Handoff Guide must not claim '${banned}'`);
    }
  }

  const readme = fs.readFileSync(path.join(REPO_ROOT, "README.md"), "utf8");
  if (!readme.includes("THERMOps_R11-S8-9-25_Data_Load_to_ML_Workflow_Handoff_Guide.md")) {
    throw new Error("B7 regression: README must link Handoff Guide");
  }
  if (!readme.includes("R11-S8-9-25")) {
    throw new Error("B7 regression: README must mention R11-S8-9-25");
  }

  const backlog = fs.readFileSync(path.join(REPO_ROOT, "docs/md/THERMOps_R11-S8-9_Backlog.md"), "utf8");
  if (!backlog.includes("R11-S8-9-25") || !backlog.includes("B7(done)")) {
    throw new Error("B7 regression: Backlog must reflect B7 done / R11-S8-9-25");
  }
  if (!/\|\s*B7\s*\|[\s\S]*?\|\s*\*\*done\*\*\s*\|\s*\*\*R11-S8-9-25\*\*/.test(backlog)) {
    throw new Error("B7 regression: Backlog table row B7 must be done with R11-S8-9-25");
  }
}

/** B22: DISABLED Components Implementation Roadmap (docs only, no enablement). */
function assertDisabledComponentsRoadmap() {
  const guidePath = path.join(
    REPO_ROOT,
    "docs/md/THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md",
  );
  if (!fs.existsSync(guidePath)) {
    throw new Error("B22 regression: DISABLED Components Roadmap markdown missing");
  }
  const guide = fs.readFileSync(guidePath, "utf8");
  for (const token of [
    "기획·설계 roadmap",
    "활성화하거나 신규 node를 구현하지 않는다",
    "VP_REST_API_SOURCE",
    "VP_DATA_QUALITY",
    "VP_FEATURE_BUILD",
    "VP_MODEL_TRAINING",
    "VP_BATCH_PREDICTION",
    "VP_NOTIFICATION",
    "R12-A",
    "Coming later",
  ]) {
    if (!guide.includes(token)) {
      throw new Error(`B22 regression: Roadmap missing '${token}'`);
    }
  }
  for (const banned of [
    "DISABLED 컴포넌트 활성화 완료",
    "신규 node 구현 완료",
    "자동 학습 실행",
    "즉시 예측 실행",
    "자동 예측 실행",
    "R10 설정 반영",
  ]) {
    if (guide.includes(banned)) {
      throw new Error(`B22 regression: Roadmap must not claim '${banned}'`);
    }
  }

  const readme = fs.readFileSync(path.join(REPO_ROOT, "README.md"), "utf8");
  if (!readme.includes("THERMOps_R11-S8-9-26_DISABLED_Components_Implementation_Roadmap.md")) {
    throw new Error("B22 regression: README must link DISABLED Components Roadmap");
  }
  if (!readme.includes("R11-S8-9-26")) {
    throw new Error("B22 regression: README must mention R11-S8-9-26");
  }

  const backlog = fs.readFileSync(path.join(REPO_ROOT, "docs/md/THERMOps_R11-S8-9_Backlog.md"), "utf8");
  if (!backlog.includes("R11-S8-9-26") || !backlog.includes("B22(done)")) {
    throw new Error("B22 regression: Backlog must reflect B22 done / R11-S8-9-26");
  }
  if (!/\|\s*B22\s*\|[\s\S]*?\|\s*\*\*done\*\*\s*\|\s*\*\*R11-S8-9-26\*\*/.test(backlog)) {
    throw new Error("B22 regression: Backlog table row B22 must be done with R11-S8-9-26");
  }
}

/** B23: Product Branding Generalization (docs + Header tagline; no ID/route changes). */
function assertProductBrandingGeneralization() {
  const guidePath = path.join(
    REPO_ROOT,
    "docs/md/THERMOps_R11-S8-9-27_Product_Branding_Generalization.md",
  );
  if (!fs.existsSync(guidePath)) {
    throw new Error("B23 regression: Product Branding Generalization markdown missing");
  }
  const guide = fs.readFileSync(guidePath, "utf8");
  for (const token of [
    "THERMOps 제품명은 유지",
    "대표 적용 예시",
    "Data Load / Workflow",
    "route / API / component ID",
  ]) {
    if (!guide.includes(token)) {
      throw new Error(`B23 regression: Branding guide missing '${token}'`);
    }
  }
  for (const banned of [
    "열수요 전용 플랫폼",
    "열수요 예측 전용 시스템",
    "자동 학습 실행",
    "자동 예측 실행",
    "즉시 예측 실행",
    "ML Workflow가 이미 구현",
    "DISABLED 컴포넌트 활성화 완료",
    "신규 node 구현 완료",
    "R10 설정 반영",
  ]) {
    if (guide.includes(banned)) {
      throw new Error(`B23 regression: Branding guide must not claim '${banned}'`);
    }
  }

  const readme = fs.readFileSync(path.join(REPO_ROOT, "README.md"), "utf8");
  if (!readme.includes("THERMOps_R11-S8-9-27_Product_Branding_Generalization.md")) {
    throw new Error("B23 regression: README must link Branding Generalization guide");
  }
  if (!readme.includes("R11-S8-9-27")) {
    throw new Error("B23 regression: README must mention R11-S8-9-27");
  }
  const readmeHead = readme.slice(0, 800);
  for (const banned of [
    "열수요 전용 플랫폼",
    "열수요 예측 전용 시스템",
    "한국지역난방공사",
  ]) {
    if (readmeHead.includes(banned)) {
      throw new Error(`B23 regression: README intro must not include '${banned}'`);
    }
  }

  const header = fs.readFileSync(path.join(FRONTEND_SRC, "components/Header.tsx"), "utf8");
  if (header.includes("한국지역난방공사")) {
    throw new Error("B23 regression: Header must not hardcode customer name");
  }
  if (!header.includes("Data Load / Workflow")) {
    throw new Error("B23 regression: Header tagline should use generic Data Load / Workflow wording");
  }

  const backlog = fs.readFileSync(path.join(REPO_ROOT, "docs/md/THERMOps_R11-S8-9_Backlog.md"), "utf8");
  if (!backlog.includes("R11-S8-9-27") || !backlog.includes("B23(done)")) {
    throw new Error("B23 regression: Backlog must reflect B23 done / R11-S8-9-27");
  }
  if (!/\|\s*B23\s*\|[\s\S]*?\|\s*\*\*done\*\*\s*\|\s*\*\*R11-S8-9-27\*\*/.test(backlog)) {
    throw new Error("B23 regression: Backlog table row B23 must be done with R11-S8-9-27");
  }
}

/** R11-S8-9-28: Visual Pipeline Closeout Release Note (docs only; not a feature implementation). */
function assertVisualPipelineCloseoutReleaseNote() {
  const guidePath = path.join(
    REPO_ROOT,
    "docs/md/THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md",
  );
  if (!fs.existsSync(guidePath)) {
    throw new Error("S8-9-28 regression: Closeout Release Note markdown missing");
  }
  const guide = fs.readFileSync(guidePath, "utf8");
  for (const token of [
    "신규 기능 구현 문서가 아니며",
    "ML Workflow / 학습·예측 실행 경로는 구현하지 않음",
    "DISABLED components는 활성화되지 않음",
    "후속 후보",
    "Data Load / Workflow",
    "check-visual-pipeline-e2e",
    "Studio Onboarding",
  ]) {
    if (!guide.includes(token)) {
      throw new Error(`S8-9-28 regression: Closeout note missing '${token}'`);
    }
  }
  for (const banned of [
    "자동 학습 실행",
    "자동 예측 실행",
    "즉시 예측 실행",
    "ML Workflow가 이미 구현",
    "DISABLED 컴포넌트 활성화 완료",
    "신규 node 구현 완료",
    "R10 설정 반영",
  ]) {
    if (guide.includes(banned)) {
      throw new Error(`S8-9-28 regression: Closeout note must not claim '${banned}'`);
    }
  }

  const readme = fs.readFileSync(path.join(REPO_ROOT, "README.md"), "utf8");
  if (!readme.includes("THERMOps_R11-S8-9-28_Visual_Pipeline_Closeout_Release_Note.md")) {
    throw new Error("S8-9-28 regression: README must link Closeout Release Note");
  }
  if (!readme.includes("R11-S8-9-28")) {
    throw new Error("S8-9-28 regression: README must mention R11-S8-9-28");
  }

  const backlog = fs.readFileSync(path.join(REPO_ROOT, "docs/md/THERMOps_R11-S8-9_Backlog.md"), "utf8");
  if (!backlog.includes("R11-S8-9-28")) {
    throw new Error("S8-9-28 regression: Backlog must record R11-S8-9-28");
  }
  if (!backlog.includes("Closeout Release Note")) {
    throw new Error("S8-9-28 regression: Backlog must mention Closeout Release Note");
  }
  if (!backlog.includes("신규 기능 구현 아님")) {
    throw new Error("S8-9-28 regression: Backlog closeout note must state docs-only / not a feature implementation");
  }
}

/** R12: Candidate Prioritization Draft (docs only; not an implementation kickoff). */
function assertR12CandidatePrioritizationDraft() {
  const guidePath = path.join(REPO_ROOT, "docs/md/THERMOps_R12_Candidate_Prioritization_Draft.md");
  if (!fs.existsSync(guidePath)) {
    throw new Error("R12 regression: Candidate Prioritization Draft markdown missing");
  }
  const guide = fs.readFileSync(guidePath, "utf8");
  for (const token of [
    "구현 착수 문서가 아니며",
    "별도 승인",
    "R12-A",
    "R12-B",
    "R12-C",
    "R12-D",
    "R12-E",
    "R13",
    "Data Quality Gate",
    "Feature Dataset Builder",
    "추천 우선순위 초안",
  ]) {
    if (!guide.includes(token)) {
      throw new Error(`R12 regression: Prioritization Draft missing '${token}'`);
    }
  }
  for (const banned of [
    "R12 착수 확정",
    "R12 일정 확정",
    "자동 학습 실행",
    "자동 예측 실행",
    "즉시 예측 실행",
    "ML Workflow가 이미 구현",
    "DISABLED 컴포넌트 활성화 완료",
    "신규 node 구현 완료",
    "R10 설정 반영",
  ]) {
    if (guide.includes(banned)) {
      throw new Error(`R12 regression: Prioritization Draft must not claim '${banned}'`);
    }
  }

  const readme = fs.readFileSync(path.join(REPO_ROOT, "README.md"), "utf8");
  if (!readme.includes("THERMOps_R12_Candidate_Prioritization_Draft.md")) {
    throw new Error("R12 regression: README must link Candidate Prioritization Draft");
  }
  if (!readme.includes("R12 Candidate Prioritization Draft")) {
    throw new Error("R12 regression: README must mention R12 Candidate Prioritization Draft");
  }
}

/** B5: Ops action badge PoC (read-model, no notification table / read-unread). */
function assertOpsActionBadgePoC() {
  const helper = fs.readFileSync(path.join(FRONTEND_SRC, "utils/opsActionRequired.ts"), "utf8");
  for (const token of [
    "buildOpsActionBadgeSummary",
    "OPS_ACTION_REQUIRED_ANCHOR",
    "OPS_ACTION_REQUIRED_HREF",
    "retryable",
  ]) {
    if (!helper.includes(token)) {
      throw new Error(`B5 regression: opsActionRequired missing ${token}`);
    }
  }
  if (!helper.includes("errorCount") || !helper.includes("warningCount")) {
    throw new Error("B5 regression: badge summary must expose errorCount / warningCount");
  }
  for (const banned of [
    "readAt",
    "read_at",
    "read_unread",
    "새 알림",
    "읽지 않음",
    "미확인 알림",
    "tb_visual_pipeline_notification",
  ]) {
    if (helper.includes(banned)) {
      throw new Error(`B5 regression: helper must not include '${banned}'`);
    }
  }

  if (!helper.includes("99+") || !helper.includes("displayCount")) {
    throw new Error("B5 regression: badge summary must format 99+ displayCount");
  }

  const badge = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpOpsActionBadge.tsx"),
    "utf8",
  );
  for (const token of [
    "VpOpsActionBadge",
    "visual-pipeline-ops-action-badge",
    "확인 필요",
    "displayCount",
  ]) {
    if (!badge.includes(token)) {
      throw new Error(`B5 regression: VpOpsActionBadge missing ${token}`);
    }
  }
  for (const banned of ["새 알림", "읽지 않음", "미확인 알림", "readAt", "read_unread"]) {
    if (badge.includes(banned)) {
      throw new Error(`B5 regression: badge must not include '${banned}'`);
    }
  }

  const hook = fs.readFileSync(path.join(FRONTEND_SRC, "hooks/useOpsActionBadge.ts"), "utf8");
  if (!hook.includes("getVisualPipelineOpsSummary") || !hook.includes("getVisualPipelineOpsStuckRuns")) {
    throw new Error("B5 regression: useOpsActionBadge must use summary + stuck-runs APIs only");
  }
  if (hook.includes("schedule-skips") || hook.includes("/notifications") || hook.includes("getNotification")) {
    throw new Error("B5 regression: hook must not call schedule-skips or notification APIs");
  }
  if (/setInterval|setTimeout\([^,]*,\s*[0-9]{4,}/.test(hook)) {
    throw new Error("B5 regression: default hook must not poll (no setInterval)");
  }

  const card = fs.readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/VpActionRequiredCard.tsx"),
    "utf8",
  );
  if (!card.includes('id="visual-pipeline-ops-action-required"')) {
    throw new Error("B5 regression: action-required card must expose id for hash navigation");
  }

  const sidebar = fs.readFileSync(path.join(FRONTEND_SRC, "components/Sidebar.tsx"), "utf8");
  if (!sidebar.includes("VpOpsActionBadge") || !sidebar.includes("useOpsActionBadge")) {
    throw new Error("B5 regression: Sidebar must mount Ops action badge");
  }
  if (!sidebar.includes("visual-pipeline-ops-sidebar-action-badge")) {
    throw new Error("B5 regression: Sidebar badge testid missing");
  }

  const opsPage = fs.readFileSync(path.join(FRONTEND_SRC, "pages/VisualPipelineOpsPage.tsx"), "utf8");
  if (!opsPage.includes("buildOpsActionBadgeSummary") || !opsPage.includes("visual-pipeline-ops-title-action-badge")) {
    throw new Error("B5 regression: Ops page title must show action badge");
  }
  if (!opsPage.includes("OPS_ACTION_REQUIRED_ANCHOR")) {
    throw new Error("B5 regression: Ops page must scroll to action-required anchor");
  }

  const studio = fs.readFileSync(path.join(FRONTEND_SRC, "pages/VisualPipelineStudioPage.tsx"), "utf8");
  if (!studio.includes("visual-pipeline-studio-ops-link") || !studio.includes("VpOpsActionBadge")) {
    throw new Error("B5 regression: Studio must expose Ops link + badge");
  }
  for (const banned of ["새 알림", "읽지 않음", "미확인 알림", "R10 설정 반영"]) {
    if (sidebar.includes(banned) || opsPage.includes(banned) || studio.includes(banned) || badge.includes(banned)) {
      throw new Error(`B5 regression: must not use banned phrase '${banned}'`);
    }
  }
}

async function api(method, path, body) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    throw new Error(`API ${method} ${path} -> ${res.status}: ${text.slice(0, 400)}`);
  }
  if (data && typeof data === "object" && "data" in data && data.success !== undefined) {
    if (data.success === false) {
      throw new Error(`API ${method} ${path} success=false: ${text.slice(0, 400)}`);
    }
    return data.data;
  }
  return data;
}

assertNoDataSourcesSizeOver100();
assertStandardDatasetArchiveUi();
assertDataSourcePagedSelectUx();
assertStudioRestDataSourceInlineCreate();
assertStudioUpsertStandardDatasetInlineCreate();
assertStudioUpsertTransformColumnProposal();
assertStudioUpsertColumnMatchPreview();
assertStudioUpsertConflictKeysUx();
assertStudioTargetTableSamplePreview();
assertVisualPipelineE2eSmoke();
assertRunFailureSummaryUx();
assertOpsActionRequiredCard();
assertScheduleSkipHistoryUx();
assertCatchupGuidanceUx();
assertPartialImpactUx();
assertSchemaKeyMappingHelper();
assertOpsActionBadgePoC();
assertStarterTemplateUx();
assertDomainPresetFramework();
assertDataLoadMlHandoffGuide();
assertDisabledComponentsRoadmap();
assertProductBrandingGeneralization();
assertVisualPipelineCloseoutReleaseNote();
assertR12CandidatePrioritizationDraft();

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`${page.url}: ${e.message}`));

async function waitMainHeading(name, timeout = 60000) {
  await page.locator("main h1").filter({ hasText: new RegExp(`^${name}$`) }).first().waitFor({ state: "visible", timeout });
}

async function hasEmptyOrTable(emptyPattern) {
  const hasEmpty = await page.getByText(emptyPattern).count();
  const hasRows = await page.locator("main table tbody tr").count();
  return hasEmpty > 0 || hasRows > 0;
}

for (const path of PATHS) {
  await page.goto(`${BASE}${path}`, { waitUntil: "load", timeout: 60000 });
  await page.waitForTimeout(500);
  if (path === "/dashboard") {
    await waitMainHeading("대시보드");
  } else if (path === "/data/sources") {
    await waitMainHeading("데이터 소스");
  } else if (path === "/prediction-entities") {
    await waitMainHeading("예측 대상");
  } else if (path === "/external-code-mappings") {
    await waitMainHeading("외부 코드 매핑");
  } else if (path === "/standard-datasets") {
    await waitMainHeading("표준 데이터셋");
  } else if (path === "/data/mappings") {
    await waitMainHeading("데이터 매핑");
  } else if (path === "/features") {
    await page.getByText("신규 학습 변수 사용 절차").first().waitFor({ state: "visible", timeout: 60000 });
    await waitMainHeading("학습 변수");
  } else if (path === "/feature-recipes") {
    await waitMainHeading("변수 생성 규칙");
  } else if (path === "/feature-recipes/new") {
    await waitMainHeading("변수 생성 규칙 작성");
  } else if (path === "/feature-sets") {
    await waitMainHeading("변수 구성");
  } else if (path === "/dataset-versions") {
    await waitMainHeading("학습 데이터 버전");
  } else if (path === "/models/training-jobs") {
    await waitMainHeading("모델 학습");
  } else if (path === "/predictions/jobs") {
    await waitMainHeading("예측 작업");
  } else if (path === "/predictions/results") {
    await waitMainHeading("예측 결과");
  } else if (path === "/pipeline-builder") {
    await waitMainHeading("작업 흐름 구성");
  } else if (path === "/ops/pipeline-runs") {
    await waitMainHeading("작업 실행 이력");
  } else if (path === "/ops/drift-reports") {
    await waitMainHeading("데이터 변화 리포트");
  } else if (path === "/system/configs") {
    await waitMainHeading("시스템 설정");
  } else if (path === "/data-load-schedules") {
    await waitMainHeading("데이터 적재 일정");
  } else if (path === "/notifications") {
    await waitMainHeading("알림 / 장애 통보");
  } else if (path === "/visual-pipelines") {
    await waitMainHeading("Visual Pipeline Studio");
    await page.getByRole("button", { name: "새 Visual Pipeline" }).first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/아직 생성된 Visual Pipeline이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  } else if (path === "/visual-pipeline-ops") {
    await waitMainHeading("Visual Pipeline 운영 현황");
    const hasOps =
      (await page.getByTestId("visual-pipeline-ops-read-only-notice").count()) > 0 ||
      (await page.getByTestId("visual-pipeline-ops-admin-required").count()) > 0;
    if (!hasOps) {
      errors.push(`${path}: read-only notice or admin-required expected`);
    }
    // B5: action-required anchor id must exist when admin panels are shown
    if ((await page.getByTestId("visual-pipeline-ops-read-only-notice").count()) > 0) {
      const actionCard = page.getByTestId("visual-pipeline-ops-action-required");
      await actionCard.waitFor({ state: "visible", timeout: 30000 });
      const anchorId = await actionCard.getAttribute("id");
      if (anchorId !== "visual-pipeline-ops-action-required") {
        errors.push(`${path}: B5 action-required card missing id=visual-pipeline-ops-action-required`);
      }
      // title badge may be hidden when count=0 — never crash
      const titleBadge = page.getByTestId("visual-pipeline-ops-title-action-badge");
      const titleBadgeErr = page.getByTestId("visual-pipeline-ops-title-action-badge-error");
      const badgeCount = (await titleBadge.count()) + (await titleBadgeErr.count());
      console.log(`  [ok] B5 ops title badge visible_or_hidden count=${badgeCount}`);
    }
  } else {
    await page.locator("main h1").first().waitFor({ state: "visible", timeout: 60000 });
  }
  const h1 = await page.locator("main h1").first().innerText().catch(() => "");
  console.log(`OK ${path} -> ${h1.slice(0, 40)}`);

  const forbiddenH1 = ["Feature Recipe", "Pipeline Builder", "Feature Set", "드리프트 리포트", "Dataset Version"];
  for (const term of forbiddenH1) {
    if (h1.includes(term)) errors.push(`${path}: h1 must not contain '${term}' (got: ${h1})`);
  }

  if (path === "/features") {
    await page.getByText(/등록된 학습 변수가 없습니다|table/).first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
  }
  if (path === "/feature-recipes") {
    await page.getByText("미리보기/생성 비교").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 변수 생성 규칙이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/feature-recipes/new") {
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("미리보기/생성 비교").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/standard-datasets") {
    await page.getByText("표준 데이터셋 생성").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 표준 데이터셋이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    if (await page.getByText(/등록된 표준 데이터셋이 없습니다/).count()) {
      await page.getByText("학습과 예측에 사용할 내부 데이터 구조를 먼저 정의").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByText("R9-S2-3").first().waitFor({ state: "visible", timeout: 30000 });
    await page.locator("select").filter({ has: page.locator('option', { hasText: "전체 업무 영역" }) }).first().waitFor({ state: "visible", timeout: 30000 });
    for (const fixed of ["열수요", "기상", "기준정보", "설비"]) {
      const count = await page.locator("option").filter({ hasText: fixed }).count();
      if (count > 0) errors.push(`/standard-datasets: fixed domain option '${fixed}' must not appear`);
    }
    await page.getByRole("button", { name: "표준 데이터셋 생성" }).click();
    await page.getByText("표준 데이터셋 생성 Wizard").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("데이터 분류").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("업무 영역").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("태그").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "닫기" }).click();

    // --- R11-S8-9-6 / B24: archive UI smoke (test-only DRAFT dataset) ---
    try {
      const suffix = Date.now().toString(36);
      const code = `B24SMOKE${suffix.toUpperCase()}`;
      const created = await api("POST", "/standard-dataset-types", {
        dataset_type_code: code,
        dataset_type_name: `B24 smoke ${suffix}`,
        target_table: `std_b24_smoke_${suffix}`,
        status: "DRAFT",
        managed_table: true,
      });
      const dsId = created.dataset_type_id;
      await page.reload({ waitUntil: "load", timeout: 60000 });
      await page.getByText("표준 데이터셋").first().waitFor({ state: "visible", timeout: 30000 });
      const searchInput = page.getByPlaceholder("검색 (이름·코드·설명)");
      await searchInput.fill(code);
      await searchInput.press("Enter").catch(() => {});
      await page.waitForTimeout(1200);
      const row = page.locator("tbody tr").filter({ hasText: code });
      await row.first().waitFor({ state: "visible", timeout: 15000 });
      const archiveBtn = row.first().getByTestId(`standard-dataset-archive-button-${dsId}`);
      await archiveBtn.waitFor({ state: "visible", timeout: 10000 });
      let dialogMessage = "";
      page.once("dialog", async (dialog) => {
        dialogMessage = dialog.message();
        await dialog.accept();
      });
      await archiveBtn.click();
      await page.waitForTimeout(600);
      if (!dialogMessage.includes("물리 테이블 또는 적재 데이터는 삭제하지 않습니다")) {
        errors.push("B24: archive confirm dialog must mention physical table retention");
      }
      await archiveBtn.waitFor({ state: "hidden", timeout: 10000 }).catch(() => {
        errors.push("B24: archived dataset row should disappear from default list");
      });
      const listed = await api("GET", `/standard-dataset-types?keyword=${encodeURIComponent(code)}`);
      const stillVisible = (listed.items || []).some((item) => item.dataset_type_id === dsId);
      if (stillVisible) {
        errors.push("B24: archived dataset must not appear in default list (active_yn=Y)");
      }
      console.log("  [ok] B24 standard dataset archive UI smoke");
    } catch (err) {
      errors.push(`B24 archive smoke failed: ${err.message}`);
    }
  }
  if (path === "/data/sources") {
    await page.getByRole("button", { name: "신규 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("REST API 연결").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Decoding 키 입력을 권장").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("API 작업").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "새 API 작업 만들기" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "새 API 작업 만들기" }).click();
    await page.getByText("REST API 작업 만들기").first().waitFor({ state: "visible", timeout: 30000 });
    // --- R11-S8-9-8 / B11: Data Source search / hint UI ---
    await page.getByTestId("data-source-list-hint").waitFor({ state: "visible", timeout: 10000 });
    await page.getByTestId("data-source-search-hint").waitFor({ state: "visible", timeout: 10000 });
    await page.getByTestId("data-source-search-input").waitFor({ state: "visible", timeout: 10000 });
    await page.getByTestId("data-source-refresh-button").waitFor({ state: "visible", timeout: 10000 });
    const searchHint = await page.getByTestId("data-source-search-hint").innerText();
    if (!searchHint.includes("현재 로드된 항목 내에서만 검색")) {
      errors.push("B11: search hint must mention client-side loaded-items limitation");
    }
    console.log("  [ok] B11 Data Source search/refresh UI in Wizard");
    for (const label of ["기본 정보", "인증 정보", "요청 파라미터", "페이징 방식", "응답 데이터 경로", "변환 설정", "적재 대상", "테스트 호출", "검토 및 저장"]) {
      await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
    }
    const wizard = page.locator("div").filter({ hasText: "REST API 작업 만들기" }).last();
    const sourceSelect = wizard.locator("select").first();
    const optionCount = await sourceSelect.locator("option").count();
    if (optionCount > 1) {
      await sourceSelect.selectOption({ index: 1 });
      await wizard.locator("label", { hasText: "API 작업명" }).locator("..").locator("input").fill("check-pages-transform");
      await wizard.locator("label", { hasText: "Endpoint Path" }).locator("..").locator("input").fill("/sample-external/asos-hourly");
      for (let i = 0; i < 5; i += 1) {
        await page.getByRole("button", { name: "다음" }).click();
      }
      await page.getByText("변환 설정").first().waitFor({ state: "visible", timeout: 30000 });
      const transformSelect = wizard.locator("select").filter({ has: wizard.locator('option[value="ASOS_HOURLY_TO_CANONICAL"]') }).first();
      await transformSelect.locator('option[value="ASOS_HOURLY_TO_CANONICAL"]').waitFor({ state: "attached", timeout: 30000 });
      await transformSelect.locator('option[value="CALENDAR_SPECIAL_DAY_TO_DATE"]').waitFor({ state: "attached", timeout: 30000 });
      await transformSelect.locator('option[value="CALENDAR_DATE_TO_HOUR"]').waitFor({ state: "attached", timeout: 30000 });
      await transformSelect.selectOption("ASOS_HOURLY_TO_CANONICAL");
      for (const label of ["station_code", "observed_at"]) {
        await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
      }
      await transformSelect.selectOption("CALENDAR_SPECIAL_DAY_TO_DATE");
      for (const label of ["locdate", "dateName", "FULL_CALENDAR_WITH_OVERLAY", "SPECIAL_DAYS_ONLY"]) {
        await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
      }
      await page.getByText(/ASOS 관측 기상은 과거 학습용/).first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByRole("button", { name: "다음" }).click();
      await page.getByText("적재 방식").first().waitFor({ state: "visible", timeout: 30000 });
      for (const label of ["신규 행 추가", "중복 제외", "있으면 갱신, 없으면 추가", "중복 판단 키", "중복 처리 정책", "null 값 처리"]) {
        await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
      }
    }
    await page.getByText("요청 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("테스트 호출").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("적재 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("적재 실행").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "닫기" }).click();
    if (!(await hasEmptyOrTable(/등록된 데이터 소스가 없습니다|등록된 REST API 작업이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    if (await page.getByText(/등록된 데이터 소스가 없습니다/).count()) {
      await page.getByText("표준 데이터셋을 먼저 정의한 뒤").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByRole("link", { name: "예측 대상" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/Calendar\/특일 API는/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/기상청 단기예보 API 작업은/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/단기예보 입력 생성기/).first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/prediction-entities") {
    await page.getByRole("button", { name: "예측 대상 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("단기예보 격자").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("ASOS 관측소").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/nx\/ny/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/R10-S4 ASOS 관측 기상 적재/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/forecast_ready|단기예보 입력은/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/별도로 매핑|기상 매핑/).first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 예측 대상이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
      await page.getByText("단기예보 준비").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("관측 기상 준비").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByRole("button", { name: "상세" }).first().click();
      await page.getByRole("button", { name: "nx/ny 계산" }).first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByRole("button", { name: "닫기" }).click();
    }
    if (await page.getByText(/등록된 예측 대상이 없습니다/).count()) {
      await page.getByText("열수요 지점, 설비, 지역").first().waitFor({ state: "visible", timeout: 30000 });
    }
  }
  if (path === "/external-code-mappings") {
    await page.getByRole("button", { name: "외부 코드 매핑 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("매핑 목록").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("미매핑 코드").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("코드 변환 테스트").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("도움말").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/미매핑 코드는 자동으로 내부 기준정보를 만들지 않습니다/).first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 외부 코드 매핑이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    if (await page.getByText(/등록된 외부 코드 매핑이 없습니다/).count()) {
      await page.getByText("지점코드·관측소코드").first().waitFor({ state: "visible", timeout: 30000 });
    }
  }
  if (path === "/data/mappings") {
    await page.getByText(/표준 데이터셋|대상 테이블을 먼저 생성/).first().waitFor({ state: "visible", timeout: 30000 });
    if (await page.getByText(/등록된 데이터 매핑이 없습니다/).count()) {
      await page.getByText("표준 데이터셋과 데이터 소스를 만든 뒤").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByText("컬럼 역할").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("사용 가능한 생성 규칙 템플릿").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("변수 생성 규칙 작성 화면은 후속 단계").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/feature-sets") {
    await page.getByText("신규 변수 구성").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 변수 구성이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/dataset-versions") {
    await page.getByText("일부 생성 버전은 자동 학습/예측 선택에서 제외됩니다").first().waitFor({ state: "visible", timeout: 30000 });
    const emptyVersions = await page.getByText(/생성된 학습 데이터 버전이 없습니다/).count();
    if (emptyVersions) {
      await page.getByText("역할·상태 코드 참고").first().waitFor({ state: "visible", timeout: 30000 });
    } else {
      await page.getByText("대표").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("후보").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("일부 생성").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("보관됨").first().waitFor({ state: "visible", timeout: 30000 });
    }
    if (!(await hasEmptyOrTable(/생성된 학습 데이터 버전이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/models/training-jobs") {
    await page.getByText(/대표·학습 가능 버전을 자동 선택/).first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/predictions/jobs") {
    await page.getByText(/예측 사용 가능·대표 버전을 자동 선택/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("단기예보 입력").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("예측 시점 단기예보 호출").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("예보 발표 시각").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("기상 입력 스냅샷").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("단기예보 입력 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/pipeline-builder") {
    await page.getByText("새 작업 흐름").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 작업 흐름이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    const openCount = await page.getByRole("button", { name: "열기" }).count();
    if (openCount > 0) {
      await page.getByRole("button", { name: "열기" }).first().click();
      await page.waitForURL(/\/pipeline-builder\/[^/]+/, { timeout: 30000 });
      await page.getByText("노드 설정").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("최근 실행 이력").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("실행 전 conf 확인").first().waitFor({ state: "visible", timeout: 30000 });
      const hasRun = (await page.getByRole("button", { name: "실행" }).count())
        + (await page.getByText("검증 후 실행 가능").count());
      if (!hasRun) errors.push(`${path}: 실행/검증 후 실행 가능 UI missing`);
    }
  }
  if (path === "/ops/pipeline-runs") {
    await page.getByText("작업 흐름 구성").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/실행 이력이 없습니다|데이터가 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/data-load-schedules") {
    await page.getByText("일정 목록", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("실행 이력", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("실행 대상 일정", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Worker 상태", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("도움말", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 데이터 적재 일정이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    await page.getByText("Worker 상태", { exact: true }).click();
    await page.getByText("적재 일정 실행 Worker").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Worker 상태 신호").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("중복 실행 방지 잠금").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("1회 실행").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/등록된 적재 일정 실행 Worker가 없습니다|Worker명/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("도움말", { exact: true }).click();
    await page.getByText("재시도 정책").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("run-due").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("중복 실행 방지 잠금").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("실행 대상 일정", { exact: true }).click();
    await page.getByText("run-due").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("일정 목록", { exact: true }).click();
    await page.getByRole("button", { name: "일정 등록" }).click();
    await page.getByText("실행 파라미터 템플릿").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("재시도 정책").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("다음 실행 예정").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("스케줄 유형").first().waitFor({ state: "visible", timeout: 30000 });
    const scheduleTypeSelect = page.locator("select").filter({ has: page.locator('option[value="CRON"]') }).first();
    await scheduleTypeSelect.selectOption("CRON");
    await page.getByText("CRON 표현식").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("분 시 일 월 요일").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("매 5분").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("평일 09:00").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Quartz 문법").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("다음 실행 예정 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Worker가 다음 실행 예정 시각에 맞춰 자동 실행").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "취소" }).click();
    await page.getByText("도움말", { exact: true }).click();
    await page.getByText("5-field CRON").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/notifications") {
    for (const label of ["장애 현황", "알림 이벤트", "알림 규칙", "알림 채널", "수신 대상", "발송 이력", "도움말"]) {
      await page.getByRole("button", { name: label, exact: true }).waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByRole("button", { name: "도움말", exact: true }).click();
    await page.getByText("중복 알림 억제").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("장애 확인 처리").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("장애 해결 처리").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("장애 확인").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await page.getByText("장애 해결").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await page.getByText("적재 일정 실행 Worker").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await page.getByText("외부 발송 정보는 암호화").first().waitFor({ state: "visible", timeout: 30000 });
    const hasIncidentContent = (await page.getByText(/등록된 장애가 없습니다/).count()) > 0
      || (await page.locator("main table tbody tr").count()) > 0
      || (await page.getByText("미해결 장애").count()) > 0;
    if (!hasIncidentContent) errors.push(`${path}: incidents tab content missing`);
  }
}

// Sidebar menu groups (dashboard page has sidebar)
await page.goto(`${BASE}/dashboard`, { waitUntil: "load", timeout: 60000 });
await page.getByText("운영 모니터링", { exact: true }).click();
for (const group of ["데이터 준비", "학습 변수 관리", "모델 학습·예측", "운영 모니터링", "Visual Pipeline Studio", "시스템 관리"]) {
  const count = await page.getByText(group, { exact: true }).count();
  if (!count) errors.push(`sidebar: menu group '${group}' not found`);
}

const DATA_PREP_ORDER = ["표준 데이터셋", "데이터 소스", "예측 대상", "외부 코드 매핑", "데이터 매핑", "데이터 품질"];
const sidebarLinks = (await page.locator("aside nav a").allTextContents()).map((t) => t.trim());
const dataPrepIndices = DATA_PREP_ORDER.map((label) => sidebarLinks.indexOf(label));
for (const label of DATA_PREP_ORDER) {
  if (!sidebarLinks.includes(label)) errors.push(`sidebar: data prep item '${label}' not found`);
}
if (!sidebarLinks.includes("알림 / 장애 통보")) errors.push(`sidebar: operations item '알림 / 장애 통보' not found`);
for (let i = 1; i < dataPrepIndices.length; i++) {
  if (dataPrepIndices[i] >= 0 && dataPrepIndices[i - 1] >= 0 && dataPrepIndices[i] <= dataPrepIndices[i - 1]) {
    errors.push(`sidebar: data prep order must be ${DATA_PREP_ORDER.join(" → ")}`);
    break;
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
