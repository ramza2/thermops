/**
 * R11-S4-3 / S5-6 / S6-6 / S7-4 Visual Pipeline Studio detail route browser smoke.
 *
 * Env:
 *   CHECK_PAGES_BASE     frontend base (default http://localhost:5173)
 *   THERMOOPS_API_BASE   API base including /api/v1 (default http://localhost:8000/api/v1)
 *   THERMOOPS_INTERNAL_API_BASE  backend self-call base for Manual Run fixture
 *     (default http://127.0.0.1:8000/api/v1 — sample-external, no external APIs)
 */
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const FRONTEND_BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const API_BASE = process.env.THERMOOPS_API_BASE || "http://localhost:8000/api/v1";
const INTERNAL_API =
  process.env.THERMOOPS_INTERNAL_API_BASE || "http://127.0.0.1:8000/api/v1";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const FRONTEND_SRC = path.join(REPO_ROOT, "frontend", "src");

/** B25: GET /data-sources size must be <= 100. Do not flag /pipeline-runs size: 200. */
function assertNoDataSourcesSizeOver100() {
  const files = [];
  function walk(dir) {
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(name)) files.push(full);
    }
  }
  walk(FRONTEND_SRC);
  const bad = [];
  for (const file of files) {
    const lines = readFileSync(file, "utf8").split(/\r?\n/);
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

/** B16: Graph 검증 must not mutate nodes via applyConfigValidationCache (dirtymaking). */
function assertNoValidationCacheNodeMutation() {
  const pageFile = path.join(FRONTEND_SRC, "pages", "VisualPipelineStudioPage.tsx");
  const text = readFileSync(pageFile, "utf8");
  if (/setNodes\s*\([\s\S]*applyConfigValidationCache/.test(text) || /applyConfigValidationCache\s*\(/.test(text)) {
    throw new Error(
      "B16 regression: VisualPipelineStudioPage must not call applyConfigValidationCache (use UI cache / buildConfigValidationByNodeId)",
    );
  }
  if (!text.includes("buildConfigValidationByNodeId") || !text.includes("serializeGraphBodyForDirty")) {
    throw new Error(
      "B16 regression: expected buildConfigValidationByNodeId + serializeGraphBodyForDirty in Studio page",
    );
  }
}

/** B13: schema defaults for new nodes; PLACEHOLDER must not feed getDefaultConfigValues. */
function assertSchemaDefaultsSeparatedFromPlaceholder() {
  const registry = readFileSync(path.join(FRONTEND_SRC, "utils/visualPipelineConfigRegistry.ts"), "utf8");
  const graphUtil = readFileSync(path.join(FRONTEND_SRC, "utils/visualPipelineGraph.ts"), "utf8");
  if (!registry.includes("getSchemaDefaultConfigValues") || !registry.includes("applySchemaDefaultValues")) {
    throw new Error("B13 regression: expected getSchemaDefaultConfigValues + applySchemaDefaultValues");
  }
  const defaultFn = registry.match(
    /export function getDefaultConfigValues\([\s\S]*?\n\}/,
  );
  if (!defaultFn || !defaultFn[0].includes("getSchemaDefaultConfigValues")) {
    throw new Error("B13 regression: getDefaultConfigValues must delegate to getSchemaDefaultConfigValues");
  }
  if (/PLACEHOLDER_VALUES/.test(defaultFn[0])) {
    throw new Error("B13 regression: getDefaultConfigValues must not use PLACEHOLDER_VALUES");
  }
  if (!graphUtil.includes("createDefaultNodeConfig(componentType)")) {
    throw new Error("B13 regression: defaultNodeData must use createDefaultNodeConfig");
  }
  for (const rel of [
    "components/visualPipeline/config/VpRestApiSourceConfigForm.tsx",
    "components/visualPipeline/config/VpTransformConfigForm.tsx",
  ]) {
    const form = readFileSync(path.join(FRONTEND_SRC, rel), "utf8");
    if (/http_method"\)\s*\|\|\s*"GET"|transform_type"\)\s*\|\|\s*"WIDE_HOUR_TO_LONG"/.test(form)) {
      throw new Error(`B13 regression: ${rel} still uses display-only select fallback`);
    }
  }
}

/** B14: Transform unmapped_policy options must be backend enums only. */
function assertUnmappedPolicyEnumAligned() {
  const constFile = readFileSync(path.join(FRONTEND_SRC, "constants/transformUnmappedPolicy.ts"), "utf8");
  const form = readFileSync(
    path.join(FRONTEND_SRC, "components/visualPipeline/config/VpTransformConfigForm.tsx"),
    "utf8",
  );
  const registry = readFileSync(path.join(FRONTEND_SRC, "utils/visualPipelineConfigRegistry.ts"), "utf8");
  if (!constFile.includes("FAIL_LOAD") || !constFile.includes("SKIP_UNMAPPED") || !constFile.includes("LOG_ONLY")) {
    throw new Error("B14 regression: transformUnmappedPolicy constants missing backend enums");
  }
  if (!constFile.includes('ERROR: "FAIL_LOAD"') || !constFile.includes('DROP: "SKIP_UNMAPPED"')) {
    throw new Error("B14 regression: legacy ERROR/DROP auto-map missing");
  }
  if (/KEEP\s*:\s*"LOG_ONLY"/.test(constFile)) {
    throw new Error("B14 regression: KEEP must not auto-map to LOG_ONLY");
  }
  if (/UNMAPPED_POLICY_OPTIONS\s*=\s*\[[^\]]*"KEEP"/.test(form) || form.includes('["KEEP", "DROP", "ERROR"]')) {
    throw new Error("B14 regression: VpTransformConfigForm still lists KEEP/DROP/ERROR");
  }
  if (!form.includes("UNMAPPED_POLICY_SELECT_OPTIONS")) {
    throw new Error("B14 regression: Transform form must use UNMAPPED_POLICY_SELECT_OPTIONS");
  }
  if (!registry.includes("DEFAULT_UNMAPPED_POLICY") || !registry.includes("UNMAPPED_POLICY_VALUES")) {
    throw new Error("B14 regression: registry must use shared unmapped_policy constants");
  }
}

function resolveScriptsDir() {
  const fromRepo = path.join(REPO_ROOT, "scripts");
  if (existsSync(fromRepo)) return fromRepo;
  if (existsSync("/scripts")) return "/scripts";
  return fromRepo;
}

const PIPELINE_NAME_PREFIX = "E2E R11-S4-3 Visual Pipeline";
const PIPELINE_DESCRIPTION = "Created by R11-S4-3 Studio route E2E";
const RELOAD_OPERATION_NAME = "e2e_reload_fetch";

const S5_CONFIG_SAMPLE_REST = {
  schema_version: "R11-S5-0",
  values: {
    data_source_id: "DS-SAMPLE",
    operation_name: "sample_fetch",
    endpoint_path: "/api/v1/sample",
    http_method: "GET",
    response_item_path: "$.items",
    credential_ref: "CRED-SAMPLE",
  },
  validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
};

const S5_CONFIG_LEGACY_FLAT_CRON = {
  schedule_type: "CRON",
  cron_expression: "0 6 * * *",
  timezone: "Asia/Seoul",
  active_yn: false,
};

const S5_CONFIG_SAMPLE_TRANSFORM = {
  schema_version: "R11-S5-0",
  values: {
    transform_type: "WIDE_HOUR_TO_LONG",
    mapping_config: {},
  },
  validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
};

const S5_CONFIG_SAMPLE_UPSERT = {
  schema_version: "R11-S5-0",
  values: {
    standard_dataset_id: "SD-SAMPLE",
    target_table: "tb_e2e_fact",
    write_mode: "UPSERT",
    conflict_key_columns_json: ["entity_id", "measured_at"],
  },
  validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
};

const FIXTURE_GRAPH = {
  nodes: [
    {
      id: "e2e-cron",
      type: "VP_CRON_SCHEDULE",
      position: { x: 80, y: 220 },
      data: {
        label: "CRON Schedule",
        component_type: "VP_CRON_SCHEDULE",
        config: S5_CONFIG_LEGACY_FLAT_CRON,
      },
    },
    {
      id: "e2e-rest",
      type: "VP_REST_API_SOURCE",
      position: { x: 320, y: 220 },
      data: {
        label: "REST API Source",
        component_type: "VP_REST_API_SOURCE",
        config: S5_CONFIG_SAMPLE_REST,
      },
    },
    {
      id: "e2e-transform",
      type: "VP_TRANSFORM",
      position: { x: 600, y: 220 },
      data: {
        label: "Transform",
        component_type: "VP_TRANSFORM",
        config: S5_CONFIG_SAMPLE_TRANSFORM,
      },
    },
    {
      id: "e2e-load",
      type: "VP_UPSERT_LOAD",
      position: { x: 880, y: 220 },
      data: {
        label: "Upsert Load",
        component_type: "VP_UPSERT_LOAD",
        config: S5_CONFIG_SAMPLE_UPSERT,
      },
    },
  ],
  edges: [
    {
      id: "e2e-edge-1",
      source: "e2e-cron",
      target: "e2e-rest",
      sourceHandle: "output:schedule_config",
      targetHandle: "input:trigger",
      label: "schedule_config → trigger",
      data: {
        source_port: "schedule_config",
        target_port: "trigger",
        data_type: "SCHEDULE_CONFIG",
      },
    },
    {
      id: "e2e-edge-2",
      source: "e2e-rest",
      target: "e2e-transform",
      sourceHandle: "output:raw_rows",
      targetHandle: "input:input_rows",
      label: "raw_rows → input_rows",
      data: {
        source_port: "raw_rows",
        target_port: "input_rows",
        data_type: "RAW_ROWS",
      },
    },
    {
      id: "e2e-edge-3",
      source: "e2e-transform",
      target: "e2e-load",
      sourceHandle: "output:transformed_rows",
      targetHandle: "input:input_rows",
      label: "transformed_rows → input_rows",
      data: {
        source_port: "transformed_rows",
        target_port: "input_rows",
        data_type: "TRANSFORMED_ROWS",
      },
    },
  ],
  viewport: { x: 0, y: 0, zoom: 1 },
};

function fail(message) {
  console.error(`FAIL ${message}`);
  process.exitCode = 1;
  throw new Error(message);
}

async function api(method, path, body, { soft = false } = {}) {
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
    const msg = `API ${method} ${path} -> ${res.status}: ${text.slice(0, 400)}`;
    if (soft) throw new Error(msg);
    fail(msg);
  }
  if (data && typeof data === "object" && "data" in data && data.success !== undefined) {
    if (data.success === false) {
      const msg = `API ${method} ${path} success=false: ${text.slice(0, 400)}`;
      if (soft) throw new Error(msg);
      fail(msg);
    }
    return data.data;
  }
  return data;
}

async function createFixture() {
  const suffix = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const pipeline_name = `${PIPELINE_NAME_PREFIX} ${suffix}`;
  const created = await api("POST", "/visual-pipelines", {
    pipeline_name,
    description: PIPELINE_DESCRIPTION,
    graph: FIXTURE_GRAPH,
  });
  if (!created?.pipeline_id) fail("fixture create missing pipeline_id");
  console.log(`  [ok] fixture created ${created.pipeline_id} (${pipeline_name})`);
  return created;
}

function ensureMaterializeSeedData() {
  const scriptsDir = resolveScriptsDir();
  const r = spawnSync(
    "python",
    ["-c", "from test_fixtures import ensure_test_standard_datasets; ensure_test_standard_datasets()"],
    { cwd: scriptsDir, env: process.env, encoding: "utf8" },
  );
  if (r.status !== 0) {
    console.warn(`  [warn] ensure_test_standard_datasets failed: ${(r.stderr || r.stdout || "").slice(0, 300)}`);
    return false;
  }
  console.log("  [ok] materialize seed datasets ensured");
  return true;
}

async function createRestDataSource() {
  const tag = Date.now().toString(36);
  const created = await api("POST", "/data-sources", {
    source_name: `E2E R11-S7-4 REST ${tag}`,
    source_type: "REST_API",
    data_domain: "HEAT_DEMAND",
    connection_info: {
      base_url: INTERNAL_API,
      timeout_seconds: 30,
    },
    active_yn: true,
  });
  if (!created?.source_id) fail("REST data source create missing source_id");
  console.log(`  [ok] REST data source ${created.source_id}`);
  return created.source_id;
}

async function ensureHeatDemandMapping(sourceId) {
  const listed = await api("GET", "/mappings?page=1&size=100");
  const items = listed?.items ?? [];
  const existing = items.find((m) => m.source_id === sourceId && m.target_table === "heat_demand_actual");
  if (existing?.mapping_id) return existing.mapping_id;
  await api("POST", "/mappings", {
    source_id: sourceId,
    mapping_name: `E2E R11-S7-4 mapping ${Date.now().toString(36)}`,
    target_table: "heat_demand_actual",
    columns: [
      { source_column: "site_id", target_column: "site_id", required_yn: true },
      { source_column: "measured_at", target_column: "measured_at", required_yn: true },
      { source_column: "heat_demand", target_column: "heat_demand", required_yn: true },
      { source_column: "supply_temp", target_column: "supply_temp", required_yn: false },
    ],
  });
  const again = await api("GET", "/mappings?page=1&size=100");
  const created = (again?.items ?? []).find(
    (m) => m.source_id === sourceId && m.target_table === "heat_demand_actual",
  );
  if (!created?.mapping_id) fail("mapping create failed for Manual Run fixture");
  return created.mapping_id;
}

function patchNodeConfigValues(graph, nodeId, valuesPatch) {
  const nodes = (graph?.nodes ?? []).map((node) => {
    if (node.id !== nodeId) return node;
    const config = node.data?.config ?? {};
    const isWrapped = config.schema_version != null || config.values != null;
    if (isWrapped) {
      return {
        ...node,
        data: {
          ...node.data,
          config: {
            ...config,
            values: { ...(config.values ?? {}), ...valuesPatch },
          },
        },
      };
    }
    return {
      ...node,
      data: {
        ...node.data,
        config: { ...config, ...valuesPatch },
      },
    };
  });
  return { ...graph, nodes };
}

async function ensureMaterializeReadyViaApi(pipelineId) {
  const sourceId = await createRestDataSource();
  await ensureHeatDemandMapping(sourceId);
  const detail = await api("GET", `/visual-pipelines/${pipelineId}`);
  let graph = detail.graph ?? FIXTURE_GRAPH;
  graph = patchNodeConfigValues(graph, "e2e-rest", {
    data_source_id: sourceId,
    operation_name: "vp-manual-run-op",
    endpoint_path: "/sample-external/heat-demand",
    http_method: "GET",
    response_item_path: "data.items",
    credential_ref: "CRED-REF-1",
  });
  graph = patchNodeConfigValues(graph, "e2e-load", {
    standard_dataset_id: "TEST-DST-HEAT",
    target_table: "heat_demand_actual",
    write_mode: "UPSERT",
    conflict_key_columns_json: ["site_id", "measured_at"],
  });
  await api("PUT", `/visual-pipelines/${pipelineId}`, { graph, create_version: false });
  console.log(`  [ok] materialize-ready graph patched (source=${sourceId})`);
  return sourceId;
}

async function archiveFixture(pipelineId) {
  try {
    const archived = await api("POST", `/visual-pipelines/${pipelineId}/archive`, undefined, { soft: true });
    if (archived?.status !== "ARCHIVED") {
      console.warn(`  [warn] archive returned unexpected status: ${archived?.status ?? "unknown"}`);
      return false;
    }
    console.log(`  [ok] fixture archived ${pipelineId}`);
    return true;
  } catch (err) {
    console.warn(`  [warn] archive cleanup failed for ${pipelineId}: ${err.message}`);
    return false;
  }
}

/** Prefer pointer events for clipped RF nodes (e.g. leftmost CRON). */
async function selectNodeById(page, nodeId) {
  const testId = `visual-pipeline-node-${nodeId}`;
  const toolbar = page.getByTestId("visual-pipeline-toolbar");
  await toolbar.getByRole("button", { name: "Fit View" }).click();
  await page.waitForTimeout(300);

  const clicked = await page.evaluate((id) => {
    const node = document.querySelector(`.react-flow__node[data-id="${id}"]`);
    if (!node) return false;
    const r = node.getBoundingClientRect();
    const x = r.left + Math.min(40, Math.max(8, r.width / 2));
    const y = r.top + Math.min(24, Math.max(8, r.height / 2));
    const opts = {
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      pointerId: 1,
      pointerType: "mouse",
      buttons: 1,
    };
    node.dispatchEvent(new PointerEvent("pointerdown", opts));
    node.dispatchEvent(new MouseEvent("mousedown", opts));
    node.dispatchEvent(new PointerEvent("pointerup", { ...opts, buttons: 0 }));
    node.dispatchEvent(new MouseEvent("mouseup", { ...opts, buttons: 0 }));
    node.dispatchEvent(new MouseEvent("click", { ...opts, buttons: 0 }));
    return true;
  }, nodeId);

  if (!clicked) {
    await page.getByTestId(testId).click({ force: true });
  }
}

async function assertConfigFormVisible(page, fieldKeys) {
  const inspector = page.getByTestId("visual-pipeline-inspector");
  await inspector.getByTestId("visual-pipeline-inspector-config-form").waitFor({
    state: "visible",
    timeout: 10000,
  });
  for (const fieldKey of fieldKeys) {
    const field = inspector.getByTestId(`visual-pipeline-inspector-config-field-${fieldKey}`);
    await field.scrollIntoViewIfNeeded();
    await field.waitFor({
      state: "visible",
      timeout: 10000,
    });
  }
}

async function fillTextField(page, fieldKey, value) {
  const inspector = page.getByTestId("visual-pipeline-inspector");
  await inspector.getByTestId(`visual-pipeline-inspector-config-field-${fieldKey}`).locator("input").fill(value);
}

async function selectFieldOption(page, fieldKey, value) {
  const inspector = page.getByTestId("visual-pipeline-inspector");
  await inspector
    .getByTestId(`visual-pipeline-inspector-config-field-${fieldKey}`)
    .locator("select")
    .selectOption(value);
}

async function saveGraphAndWait(page) {
  const toolbar = page.getByTestId("visual-pipeline-toolbar");
  await toolbar.getByRole("button", { name: "저장", exact: true }).click();
  await page.getByText("현재 Graph가 저장되었습니다.").first().waitFor({ state: "visible", timeout: 30000 });
  await toolbar.getByText("● 저장되지 않음").waitFor({ state: "hidden", timeout: 10000 });
}

async function openDockTab(page, tabId) {
  const dock = page.getByTestId("visual-studio-operations-dock");
  await dock.waitFor({ state: "visible", timeout: 15000 });
  const expanded = (await dock.getAttribute("data-expanded")) === "true";
  if (!expanded) {
    await dock.getByTestId("visual-studio-operations-dock-toggle").click();
  }
  await dock.getByTestId(`visual-studio-operations-dock-tab-${tabId}`).click();
  await dock.getByTestId("visual-studio-operations-dock-body").waitFor({ state: "visible", timeout: 10000 });
}

async function assertStudioLayoutNoDoubleScroll(page) {
  const metrics = await page.evaluate(() => {
    const root = document.querySelector('[data-testid="visual-studio-root"]');
    const main = document.querySelector("main");
    const dock = document.querySelector('[data-testid="visual-studio-operations-dock"]');
    const paletteBody = document.querySelector('[data-testid="visual-studio-palette-body"]');
    const inspectorBody = document.querySelector('[data-testid="visual-studio-inspector-body"]');
    return {
      rootClientHeight: root?.clientHeight ?? 0,
      rootScrollHeight: root?.scrollHeight ?? 0,
      mainScrollHeight: main?.scrollHeight ?? 0,
      mainClientHeight: main?.clientHeight ?? 0,
      dockExpanded: dock?.getAttribute("data-expanded") === "true",
      paletteOverflow: paletteBody ? getComputedStyle(paletteBody).overflowY : "",
      inspectorOverflow: inspectorBody ? getComputedStyle(inspectorBody).overflowY : "",
    };
  });
  if (metrics.rootScrollHeight > metrics.rootClientHeight + 4) {
    fail(
      `expected studio root without vertical overflow, scroll=${metrics.rootScrollHeight} client=${metrics.rootClientHeight}`,
    );
  }
  if (metrics.paletteOverflow !== "auto" && metrics.paletteOverflow !== "scroll") {
    fail(`expected palette inner scroll, got overflowY=${metrics.paletteOverflow}`);
  }
  console.log(
    `  [ok] studio layout metrics root=${metrics.rootClientHeight}px dockExpanded=${metrics.dockExpanded}`,
  );
}

async function runGraphValidationAndWait(page) {
  await openDockTab(page, "validation");
  const validation = page.getByTestId("visual-pipeline-validation-panel");
  await page.getByTestId("visual-pipeline-validate-button").click();
  await validation.getByTestId("visual-pipeline-validation-severity").waitFor({ state: "visible", timeout: 30000 });
  return validation;
}

async function runCompilePreviewAndWait(page) {
  await openDockTab(page, "compile");
  const panel = page.getByTestId("visual-pipeline-compile-panel");
  await page.getByTestId("visual-pipeline-compile-preview-button").click();
  await panel.getByTestId("visual-pipeline-compile-status").waitFor({ state: "visible", timeout: 30000 });
  return panel;
}

async function runCompileAndWait(page) {
  await openDockTab(page, "compile");
  const panel = page.getByTestId("visual-pipeline-compile-panel");
  await page.getByTestId("visual-pipeline-compile-button").click();
  await panel.getByTestId("visual-pipeline-compile-persisted").filter({ hasText: "true" }).waitFor({
    state: "visible",
    timeout: 30000,
  });
  await panel.getByTestId("visual-pipeline-compile-result-id").waitFor({ state: "visible", timeout: 15000 });
  await panel.getByTestId("visual-pipeline-compile-status").waitFor({ state: "visible", timeout: 10000 });
  return panel;
}

async function runMaterializeAndWait(page) {
  await openDockTab(page, "materialization");
  const panel = page.getByTestId("visual-pipeline-materialization-panel");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("visual-pipeline-materialize-button").click();
  await panel.getByTestId("visual-pipeline-materialization-status").waitFor({ state: "visible", timeout: 45000 });
  return panel;
}

async function runManualAndWait(page) {
  await openDockTab(page, "run");
  const panel = page.getByTestId("visual-pipeline-run-panel");
  page.once("dialog", (dialog) => dialog.accept());
  const runBtn = page.getByTestId("visual-pipeline-run-now-button");
  await runBtn.scrollIntoViewIfNeeded();
  if (await runBtn.isDisabled()) {
    fail("expected Run Now button enabled after SUCCESS materialization");
  }
  await runBtn.click();
  await panel.getByTestId("visual-pipeline-run-status").waitFor({ state: "visible", timeout: 30000 });
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    const status = (await panel.getByTestId("visual-pipeline-run-status").innerText()).trim();
    if (status === "SUCCESS" || status === "FAILED" || status === "PARTIAL") {
      return { panel, status };
    }
    await page.waitForTimeout(1000);
  }
  const last = (await panel.getByTestId("visual-pipeline-run-status").innerText()).trim();
  fail(`expected Manual Run terminal status within 90s, last=${last}`);
}

async function openStudio(page, pipelineId) {
  const studioPath = `/visual-pipelines/${pipelineId}`;
  await page.goto(`${FRONTEND_BASE}${studioPath}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1200);
  await page.getByTestId("visual-pipeline-studio-page").waitFor({ state: "visible", timeout: 60000 });
  await page.getByTestId("visual-pipeline-name").filter({ hasText: PIPELINE_NAME_PREFIX }).waitFor({
    state: "visible",
    timeout: 30000,
  });
}

async function runBrowserSmoke(pipeline) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));

  try {
    await openStudio(page, pipeline.pipeline_id);
    console.log("  [ok] studio detail route loaded");

    await page.getByTestId("visual-studio-root").waitFor({ state: "visible", timeout: 15000 });
    const dock = page.getByTestId("visual-studio-operations-dock");
    await dock.waitFor({ state: "visible", timeout: 15000 });
    if ((await dock.getAttribute("data-expanded")) === "true") {
      fail("expected operations dock collapsed by default");
    }
    console.log("  [ok] operations dock collapsed by default");

    const toolbar = page.getByTestId("visual-pipeline-toolbar");
    await toolbar.waitFor({ state: "visible", timeout: 15000 });
    for (const label of ["목록", "저장", "버전 저장", "Fit View", "Graph 검증"]) {
      await toolbar.getByRole("button", { name: label }).first().waitFor({ state: "visible", timeout: 15000 });
    }
    console.log("  [ok] toolbar controls visible");

    const palette = page.getByTestId("visual-pipeline-palette");
    await palette.waitFor({ state: "visible", timeout: 30000 });
    for (const name of ["REST API Source", "Transform", "Upsert Load", "CRON Schedule"]) {
      await palette.getByText(name, { exact: true }).first().waitFor({ state: "visible", timeout: 15000 });
    }
    console.log("  [ok] palette ACTIVE components visible");

    const canvas = page.getByTestId("visual-pipeline-canvas");
    await canvas.waitFor({ state: "visible", timeout: 15000 });
    for (const nodeId of ["e2e-cron", "e2e-rest", "e2e-transform", "e2e-load"]) {
      await page.getByTestId(`visual-pipeline-node-${nodeId}`).waitFor({ state: "visible", timeout: 20000 });
    }
    console.log("  [ok] canvas + 4 flow nodes visible");

    const inspector = page.getByTestId("visual-pipeline-inspector");
    await inspector.getByText("노드를 선택하세요").waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] inspector empty state");

    await openDockTab(page, "graph");
    const status = page.getByTestId("visual-pipeline-graph-status");
    await status.getByText("nodes 4").first().waitFor({ state: "visible", timeout: 10000 });
    await openDockTab(page, "validation");
    const validation = page.getByTestId("visual-pipeline-validation-panel");
    await validation.getByText("아직 Graph 검증을 실행하지 않았습니다.").waitFor({
      state: "visible",
      timeout: 10000,
    });
    console.log("  [ok] status + validation initial (dock tabs)");

    await assertStudioLayoutNoDoubleScroll(page);

    // --- MVP 4 Form visibility smoke ---
    await selectNodeById(page, "e2e-rest");
    await inspector.getByText("VP_REST_API_SOURCE").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["operation_name", "endpoint_path", "http_method"]);
    console.log("  [ok] REST config form visible");

    // --- R11-S8-9-9 / B19: Studio REST Data Source select + inline create ---
    {
      await assertConfigFormVisible(page, ["data_source_id", "credential_ref"]);
      await inspector.getByTestId("visual-pipeline-data-source-picker").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-data-source-list-hint").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-data-source-search-hint").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-data-source-search-input").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-data-source-refresh-button").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-data-source-select").waitFor({ state: "visible", timeout: 10000 });
      const searchHint = await inspector.getByTestId("visual-pipeline-data-source-search-hint").innerText();
      if (!searchHint.includes("현재 로드된 항목 내에서만 검색")) {
        fail("B19: search hint must mention client-side loaded-items limitation");
      }
      const listHint = await inspector.getByTestId("visual-pipeline-data-source-list-hint").innerText();
      if (!listHint.includes("최대 100건")) {
        fail("B19: list hint must mention size≤100 paging");
      }
      const credHelp = await inspector
        .getByTestId("visual-pipeline-inspector-config-field-credential_ref")
        .locator("p")
        .first()
        .innerText();
      if (!credHelp.includes("CRED-") || !credHelp.includes("원문을 입력하지 말고")) {
        fail(`B19: credential_ref help must warn against secret paste, got ${credHelp}`);
      }

      const createName = `B19 Studio REST ${Date.now().toString(36)}`;
      await inspector.getByTestId("visual-pipeline-data-source-create-toggle").click();
      await inspector.getByTestId("visual-pipeline-data-source-create-form").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-data-source-create-auth-hint").waitFor({ state: "visible", timeout: 10000 });
      const authHint = await inspector.getByTestId("visual-pipeline-data-source-create-auth-hint").innerText();
      if (!authHint.includes("REST API 연결 Wizard") || !authHint.includes("인증 정보")) {
        fail(`B19: create auth hint must point to Data Sources Wizard, got ${authHint}`);
      }
      if ((await inspector.getByTestId("visual-pipeline-data-source-create-form").locator('input[type="password"]').count()) > 0) {
        fail("B19: inline create must not expose password/secret inputs");
      }
      await inspector.getByTestId("visual-pipeline-data-source-create-name").fill(createName);
      await inspector.getByTestId("visual-pipeline-data-source-create-base-url").fill(INTERNAL_API);
      await inspector.getByTestId("visual-pipeline-data-source-create-domain").selectOption("HEAT_DEMAND");
      await inspector.getByTestId("visual-pipeline-data-source-create-submit").click();
      await inspector.getByTestId("visual-pipeline-data-source-create-success").waitFor({ state: "visible", timeout: 30000 });
      const selectedAfterCreate = await inspector.getByTestId("visual-pipeline-data-source-select").inputValue();
      if (!selectedAfterCreate || selectedAfterCreate === "DS-SAMPLE") {
        fail(`B19: expected new data_source_id after inline create, got ${selectedAfterCreate}`);
      }
      await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
      await saveGraphAndWait(page);
      const afterB19 = await api("GET", `/visual-pipelines/${pipeline.pipeline_id}`);
      const restAfterB19 = (afterB19.graph?.nodes ?? []).find((n) => n.id === "e2e-rest");
      const savedSourceId = restAfterB19?.data?.config?.values?.data_source_id;
      if (savedSourceId !== selectedAfterCreate) {
        fail(
          `B19: saved config.values.data_source_id expected ${selectedAfterCreate}, got ${savedSourceId}`,
        );
      }
      console.log(`  [ok] B19 inline create → select → save data_source_id=${savedSourceId}`);
    }

    await selectNodeById(page, "e2e-transform");
    await inspector.getByText("VP_TRANSFORM").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["transform_type"]);
    console.log("  [ok] Transform config form visible");

    // --- R11-S8-9-5 / B14: unmapped_policy backend enum options ---
    {
      await assertConfigFormVisible(page, ["unmapped_policy"]);
      const policySelect = inspector.getByTestId("visual-pipeline-unmapped-policy-select");
      await policySelect.waitFor({ state: "visible", timeout: 10000 });
      const optionValues = await policySelect.locator("option").evaluateAll((opts) =>
        opts.map((o) => o.value).filter((v) => v !== ""),
      );
      for (const banned of ["KEEP", "DROP", "ERROR"]) {
        if (optionValues.includes(banned)) {
          fail(`B14: unmapped_policy must not expose legacy option ${banned}`);
        }
      }
      for (const required of ["FAIL_LOAD", "SKIP_UNMAPPED", "LOG_ONLY"]) {
        if (!optionValues.includes(required)) {
          fail(`B14: unmapped_policy missing backend option ${required}, got ${JSON.stringify(optionValues)}`);
        }
      }
      await policySelect.selectOption("SKIP_UNMAPPED");
      await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
      await saveGraphAndWait(page);
      const afterPolicy = await api("GET", `/visual-pipelines/${pipeline.pipeline_id}`);
      const xform = (afterPolicy.graph?.nodes ?? []).find((n) => n.id === "e2e-transform");
      const savedPolicy = xform?.data?.config?.values?.unmapped_policy;
      if (savedPolicy !== "SKIP_UNMAPPED") {
        fail(`B14: saved unmapped_policy expected SKIP_UNMAPPED, got ${savedPolicy}`);
      }
      console.log("  [ok] B14 unmapped_policy options + saved SKIP_UNMAPPED");
    }

    await selectNodeById(page, "e2e-cron");
    await inspector.getByText("VP_CRON_SCHEDULE").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["cron_expression", "timezone", "active_yn"]);
    console.log("  [ok] CRON config form visible");

    await selectNodeById(page, "e2e-load");
    await inspector.getByText("VP_UPSERT_LOAD").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["target_table", "write_mode", "conflict_key_columns_json"]);
    console.log("  [ok] Upsert config form visible");

    // --- R11-S8-9-14 / B18: Target Table sample rows preview ---
    {
      const previewPanel = inspector.getByTestId("visual-pipeline-target-table-preview");
      await previewPanel.scrollIntoViewIfNeeded();
      await previewPanel.waitFor({ state: "visible", timeout: 10000 });
      const targetValue = await inspector.getByTestId("visual-pipeline-target-table-input").inputValue();
      if (!targetValue) {
        fail("B18: expected target_table to be set on fixture Upsert node");
      }
      await inspector.getByTestId("visual-pipeline-target-table-preview-limit").selectOption("20");
      await inspector.getByTestId("visual-pipeline-target-table-preview-query-button").click();
      await page.waitForTimeout(1200);
      const hasSummary = (await inspector.getByTestId("visual-pipeline-target-table-preview-summary").count()) > 0;
      const hasEmpty = (await inspector.getByTestId("visual-pipeline-target-table-preview-empty").count()) > 0;
      const hasNotFound = (await inspector.getByTestId("visual-pipeline-target-table-preview-not-found").count()) > 0;
      const hasError = (await inspector.getByTestId("visual-pipeline-target-table-preview-error").count()) > 0;
      const hasTable = (await inspector.getByTestId("visual-pipeline-target-table-preview-table").count()) > 0;
      if (!(hasSummary || hasEmpty || hasNotFound || hasError || hasTable)) {
        fail("B18: preview query must show summary/empty/not-found/error/table state");
      }
      if (hasSummary && !hasEmpty && !hasTable) {
        // summary with row_count 0 should show empty; with rows should show table
        const summaryText = await inspector.getByTestId("visual-pipeline-target-table-preview-summary").innerText();
        if (!summaryText.includes("row count") || !summaryText.includes("sample limit")) {
          fail(`B18: summary missing metadata, got ${summaryText}`);
        }
      }
      console.log(
        `  [ok] B18 target table preview (table=${targetValue}, summary=${hasSummary}, empty=${hasEmpty}, notFound=${hasNotFound}, error=${hasError}, rowsTable=${hasTable})`,
      );
    }

    // --- R11-S8-9-10 / B20: Studio Upsert Standard Dataset select + inline create ---
    {
      await assertConfigFormVisible(page, ["standard_dataset_id", "target_table"]);
      await inspector.getByTestId("visual-pipeline-standard-dataset-picker").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-list-hint").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-search-hint").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-search-input").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-refresh-button").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-select").waitFor({ state: "visible", timeout: 10000 });
      const listHint = await inspector.getByTestId("visual-pipeline-standard-dataset-list-hint").innerText();
      if (!listHint.includes("보관된 표준 데이터셋")) {
        fail("B20: list hint must mention archived datasets excluded");
      }
      const searchHint = await inspector.getByTestId("visual-pipeline-standard-dataset-search-hint").innerText();
      if (!searchHint.includes("서버 keyword") || searchHint.includes("더 보기")) {
        fail(`B20: search hint must mention server keyword and not load-more, got ${searchHint}`);
      }
      if ((await inspector.getByTestId("visual-pipeline-standard-dataset-load-more").count()) > 0) {
        fail("B20: must not expose B11-style load-more (API has no page/size)");
      }

      const tag = Date.now().toString(36).toUpperCase();
      const createName = `B21 Studio Upsert ${tag}`;
      const createCode = `B21UP${tag}`.slice(0, 32);
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-toggle").click();
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-form").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-hint").waitFor({ state: "visible", timeout: 10000 });
      const createHint = await inspector.getByTestId("visual-pipeline-standard-dataset-create-hint").innerText();
      if (!createHint.includes("DRAFT") || !createHint.includes("물리 테이블")) {
        fail(`B20: create hint must clarify DRAFT metadata only, got ${createHint}`);
      }

      // --- R11-S8-9-11 / B21: Transform output column draft proposal ---
      await inspector.getByTestId("visual-pipeline-standard-dataset-column-editor").waitFor({ state: "visible", timeout: 10000 });
      await inspector.getByTestId("visual-pipeline-standard-dataset-propose-columns").click();
      await inspector.getByTestId("visual-pipeline-standard-dataset-proposal-info").waitFor({
        state: "visible",
        timeout: 10000,
      });
      const proposalInfo = await inspector.getByTestId("visual-pipeline-standard-dataset-proposal-info").innerText();
      if (!proposalInfo.includes("WIDE_HOUR_TO_LONG")) {
        fail(`B21: proposal info should mention WIDE_HOUR_TO_LONG, got ${proposalInfo}`);
      }
      const columnRowCount = await inspector
        .locator('[data-testid^="visual-pipeline-standard-dataset-column-row-"]')
        .count();
      if (columnRowCount < 2) {
        fail(`B21: expected column rows after proposal, got ${columnRowCount}`);
      }
      const columnNames = await inspector
        .getByTestId("visual-pipeline-standard-dataset-column-name")
        .evaluateAll((inputs) => inputs.map((i) => i.value));
      if (!columnNames.includes("heat_demand")) {
        fail(`B21: expected heat_demand in column proposals, got ${JSON.stringify(columnNames)}`);
      }
      if (!columnNames.includes("measured_at")) {
        fail(`B21: expected measured_at in column proposals, got ${JSON.stringify(columnNames)}`);
      }

      // --- R11-S8-9-12 / B15: Source ↔ Target column match preview ---
      {
        const measuredAtIdx = columnNames.indexOf("measured_at");
        await inspector
          .getByTestId("visual-pipeline-standard-dataset-column-name")
          .nth(measuredAtIdx)
          .fill("Measured At");
        await inspector.getByTestId("visual-pipeline-column-match-preview").waitFor({
          state: "visible",
          timeout: 10000,
        });
        const dirtyBeforeCompare = (await toolbar.getByText("● 저장되지 않음").count()) > 0;
        await inspector.getByTestId("visual-pipeline-column-match-compare-button").click();
        await inspector.getByTestId("visual-pipeline-column-match-summary").waitFor({
          state: "visible",
          timeout: 10000,
        });
        const dirtyAfterCompare = (await toolbar.getByText("● 저장되지 않음").count()) > 0;
        if (dirtyBeforeCompare !== dirtyAfterCompare) {
          fail(
            `B15: compare preview must not change dirty state (before=${dirtyBeforeCompare}, after=${dirtyAfterCompare})`,
          );
        }
        const summaryText = await inspector.getByTestId("visual-pipeline-column-match-summary").innerText();
        if (!summaryText.includes("정규화 일치") || !/\d+/.test(summaryText)) {
          fail(`B15: summary should include normalized count, got ${summaryText}`);
        }
        const matchLevels = await inspector
          .locator('[data-testid^="visual-pipeline-column-match-row-"]')
          .evaluateAll((rows) => rows.map((r) => r.getAttribute("data-match-level")));
        if (!matchLevels.includes("NORMALIZED")) {
          fail(`B15: expected NORMALIZED match for Measured At, got ${JSON.stringify(matchLevels)}`);
        }
        if (!matchLevels.includes("EXACT")) {
          fail(`B15: expected EXACT match for heat_demand, got ${JSON.stringify(matchLevels)}`);
        }
        const heatIdxForType = (
          await inspector
            .getByTestId("visual-pipeline-standard-dataset-column-name")
            .evaluateAll((inputs) => inputs.map((i) => i.value))
        ).indexOf("heat_demand");
        if (heatIdxForType >= 0) {
          await inspector
            .getByTestId("visual-pipeline-standard-dataset-column-type")
            .nth(heatIdxForType)
            .selectOption("VARCHAR");
          await inspector.getByTestId("visual-pipeline-column-match-compare-button").click();
          await page.waitForTimeout(400);
          const levelsAfterType = await inspector
            .locator('[data-testid^="visual-pipeline-column-match-row-"]')
            .evaluateAll((rows) => rows.map((r) => r.getAttribute("data-match-level")));
          if (!levelsAfterType.includes("TYPE_MISMATCH")) {
            fail(`B15: expected TYPE_MISMATCH after VARCHAR on heat_demand, got ${JSON.stringify(levelsAfterType)}`);
          }
          // Restore NUMERIC for subsequent create smoke
          await inspector
            .getByTestId("visual-pipeline-standard-dataset-column-type")
            .nth(heatIdxForType)
            .selectOption("NUMERIC");
        }
        console.log(
          `  [ok] B15 column match preview (NORMALIZED Measured At, EXACT heat_demand, TYPE_MISMATCH check)`,
        );
      }

      const typeSelects = inspector.getByTestId("visual-pipeline-standard-dataset-column-type");
      const measuredAtIdx = (
        await inspector
          .getByTestId("visual-pipeline-standard-dataset-column-name")
          .evaluateAll((inputs) => inputs.map((i) => i.value))
      ).indexOf("Measured At");
      if (measuredAtIdx >= 0) {
        await typeSelects.nth(measuredAtIdx).selectOption("TIMESTAMP");
      }
      const heatIdx = (
        await inspector
          .getByTestId("visual-pipeline-standard-dataset-column-name")
          .evaluateAll((inputs) => inputs.map((i) => i.value))
      ).indexOf("heat_demand");
      if (heatIdx >= 0) {
        await inspector.getByTestId("visual-pipeline-standard-dataset-column-name").nth(heatIdx).fill("heat_demand_kw");
      }
      console.log(`  [ok] B21 column proposal (${columnRowCount} rows, heat_demand/measured_at visible, editable)`);

      // --- R11-S8-9-13 / B27: conflict_key_columns_json select + validate ---
      {
        await inspector.getByTestId("visual-pipeline-conflict-keys-panel").waitFor({
          state: "visible",
          timeout: 10000,
        });
        await page.waitForTimeout(600);
        const dirtyBeforeRecommend = (await toolbar.getByText("● 저장되지 않음").count()) > 0;
        await inspector.getByTestId("visual-pipeline-conflict-keys-recommend-toggle").click();
        await inspector.getByTestId("visual-pipeline-conflict-keys-recommend-list").waitFor({
          state: "visible",
          timeout: 10000,
        });
        const dirtyAfterToggle = (await toolbar.getByText("● 저장되지 않음").count()) > 0;
        if (dirtyBeforeRecommend !== dirtyAfterToggle) {
          fail("B27: opening recommend list must not change dirty state");
        }
        const recommendText = await inspector.getByTestId("visual-pipeline-conflict-keys-recommend-list").innerText();
        if (!recommendText.includes("entity_id") || !/measured_at|Measured At/i.test(recommendText)) {
          fail(`B27: expected entity_id + measured_at recommend candidate, got ${recommendText}`);
        }
        // Clear keys via advanced input to assert UPSERT empty warning
        await inspector.getByTestId("visual-pipeline-conflict-keys-advanced-toggle").click();
        const advancedInput = inspector.locator(
          '[data-testid="visual-pipeline-conflict-keys-panel"] input[type="text"]',
        );
        await advancedInput.waitFor({ state: "visible", timeout: 10000 });
        await advancedInput.fill("");
        await inspector.getByTestId("visual-pipeline-conflict-keys-empty-error").waitFor({
          state: "visible",
          timeout: 10000,
        });
        // Apply first recommend candidate
        await inspector
          .getByTestId("visual-pipeline-conflict-keys-recommend-item")
          .first()
          .getByRole("button", { name: "적용" })
          .click();
        const selectedKeysText = await inspector.getByTestId("visual-pipeline-conflict-keys-selected").innerText();
        if (!selectedKeysText.includes("entity_id")) {
          fail(`B27: selected keys should include entity_id, got ${selectedKeysText}`);
        }
        const validation = inspector.getByTestId("visual-pipeline-conflict-keys-validation");
        await validation.waitFor({ state: "visible", timeout: 10000 });
        const overall = await validation.getAttribute("data-overall");
        if (overall === "ERROR") {
          const validationText = await validation.innerText();
          fail(`B27: expected non-ERROR validation after recommend apply, got ${overall}: ${validationText}`);
        }
        // INSERT_ONLY should not show empty-keys required error
        const writeModeSelect = inspector.locator('select').filter({ has: page.locator('option[value="UPSERT"]') }).first();
        await writeModeSelect.selectOption("INSERT_ONLY");
        await advancedInput.fill("");
        await page.waitForTimeout(300);
        if ((await inspector.getByTestId("visual-pipeline-conflict-keys-empty-error").count()) > 0) {
          fail("B27: INSERT_ONLY must not show conflict_keys required empty error");
        }
        await writeModeSelect.selectOption("UPSERT");
        await inspector
          .getByTestId("visual-pipeline-conflict-keys-recommend-item")
          .first()
          .getByRole("button", { name: "적용" })
          .click();
        console.log(`  [ok] B27 conflict keys recommend/select/validate (${selectedKeysText})`);
      }

      await inspector.getByTestId("visual-pipeline-standard-dataset-create-name").fill(createName);
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-code").fill(createCode);
      await inspector.getByTestId("visual-pipeline-standard-dataset-suggest-table").click();
      await page.waitForTimeout(800);
      const suggestedTable = await inspector
        .getByTestId("visual-pipeline-standard-dataset-create-target-table")
        .inputValue();
      if (!suggestedTable || !suggestedTable.startsWith("std_")) {
        // Fallback if suggest is slow/unavailable
        await inspector
          .getByTestId("visual-pipeline-standard-dataset-create-target-table")
          .fill(`std_b20_${tag.toLowerCase()}`);
      }
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-submit").click();
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-success").waitFor({
        state: "visible",
        timeout: 30000,
      });
      const selectedAfterCreate = await inspector
        .getByTestId("visual-pipeline-standard-dataset-select")
        .inputValue();
      if (!selectedAfterCreate || selectedAfterCreate === "SD-SAMPLE") {
        fail(`B20: expected new standard_dataset_id after inline create, got ${selectedAfterCreate}`);
      }
      const targetAfterCreate = await inspector.getByTestId("visual-pipeline-target-table-input").inputValue();
      if (!targetAfterCreate) {
        fail("B20: expected target_table filled after inline create");
      }
      await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
      await saveGraphAndWait(page);
      const afterB20 = await api("GET", `/visual-pipelines/${pipeline.pipeline_id}`);
      const loadAfterB20 = (afterB20.graph?.nodes ?? []).find((n) => n.id === "e2e-load");
      const savedDatasetId = loadAfterB20?.data?.config?.values?.standard_dataset_id;
      const savedTargetTable = loadAfterB20?.data?.config?.values?.target_table;
      if (savedDatasetId !== selectedAfterCreate) {
        fail(
          `B20: saved config.values.standard_dataset_id expected ${selectedAfterCreate}, got ${savedDatasetId}`,
        );
      }
      if (savedTargetTable !== targetAfterCreate) {
        fail(
          `B20: saved config.values.target_table expected ${targetAfterCreate}, got ${savedTargetTable}`,
        );
      }
      const savedConflictKeys = loadAfterB20?.data?.config?.values?.conflict_key_columns_json;
      if (!Array.isArray(savedConflictKeys) || !savedConflictKeys.includes("entity_id")) {
        fail(
          `B27: saved conflict_key_columns_json should include entity_id, got ${JSON.stringify(savedConflictKeys)}`,
        );
      }
      const hasMeasured = savedConflictKeys.some((k) => /measured_at/i.test(String(k).replace(/\s+/g, "_")));
      if (!hasMeasured) {
        fail(
          `B27: saved conflict_key_columns_json should include measured_at variant, got ${JSON.stringify(savedConflictKeys)}`,
        );
      }
      console.log(
        `  [ok] B20/B21 inline create → select → save standard_dataset_id=${savedDatasetId} target_table=${savedTargetTable}`,
      );
      console.log(`  [ok] B27 saved conflict_key_columns_json=${JSON.stringify(savedConflictKeys)}`);

      try {
        const detail = await api(
          "GET",
          `/standard-dataset-types/${encodeURIComponent(selectedAfterCreate)}?include_columns=true`,
        );
        const savedCols = detail?.columns ?? detail?.column_definitions ?? [];
        if (Array.isArray(savedCols) && savedCols.length > 0) {
          const savedColNames = savedCols.map((c) => c.column_name);
          if (!savedColNames.includes("heat_demand_kw")) {
            fail(`B21: created dataset columns expected heat_demand_kw, got ${JSON.stringify(savedColNames)}`);
          }
          console.log(`  [ok] B21 created dataset columns verified (${savedColNames.length} cols)`);
        } else {
          console.warn("  [warn] B21 include_columns=true returned no columns — skipped column payload verify");
        }
      } catch (err) {
        console.warn(`  [warn] B21 include_columns verify skipped: ${String(err).slice(0, 200)}`);
      }

      try {
        await api("POST", `/standard-dataset-types/${encodeURIComponent(selectedAfterCreate)}/archive`);
        console.log(`  [ok] B21 smoke dataset archived ${selectedAfterCreate}`);
      } catch (err) {
        console.warn(`  [warn] B20 archive cleanup failed: ${String(err).slice(0, 200)}`);
      }
    }

    // --- R11-S8-9-4 / B13: schema defaults fill missing Type A values (normalize + UI) ---
    {
      const before = await api("GET", `/visual-pipelines/${pipeline.pipeline_id}`);
      const graph = before.graph ?? FIXTURE_GRAPH;
      const b13Nodes = [
        {
          id: "b13-rest",
          type: "VP_REST_API_SOURCE",
          position: { x: 80, y: 360 },
          data: {
            label: "B13 REST",
            component_type: "VP_REST_API_SOURCE",
            config: {
              schema_version: "R11-S5-0",
              values: {},
              validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
            },
            input_ports: ["trigger"],
            output_ports: ["raw_rows"],
          },
        },
        {
          id: "b13-transform",
          type: "VP_TRANSFORM",
          position: { x: 320, y: 360 },
          data: {
            label: "B13 Transform",
            component_type: "VP_TRANSFORM",
            config: {
              schema_version: "R11-S5-0",
              values: {},
              validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
            },
            input_ports: ["input_rows"],
            output_ports: ["transformed_rows"],
          },
        },
      ];
      await api("PUT", `/visual-pipelines/${pipeline.pipeline_id}`, {
        graph: { ...graph, nodes: [...(graph.nodes ?? []), ...b13Nodes] },
        create_version: false,
      });
      await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForTimeout(1200);
      await page.getByTestId("visual-pipeline-studio-page").waitFor({ state: "visible", timeout: 60000 });

      await selectNodeById(page, "b13-rest");
      await assertConfigFormVisible(page, ["http_method"]);
      const httpUi = await inspector
        .getByTestId("visual-pipeline-inspector-config-field-http_method")
        .locator("select")
        .inputValue();
      if (httpUi !== "GET") {
        fail(`B13: expected b13-rest http_method UI=GET after normalize, got ${httpUi}`);
      }

      await selectNodeById(page, "b13-transform");
      await assertConfigFormVisible(page, ["transform_type"]);
      const transformUi = await inspector
        .getByTestId("visual-pipeline-inspector-config-field-transform_type")
        .locator("select")
        .inputValue();
      if (transformUi !== "WIDE_HOUR_TO_LONG") {
        fail(`B13: expected b13-transform transform_type UI=WIDE_HOUR_TO_LONG, got ${transformUi}`);
      }

      // Dirty + save so normalize-filled defaults are persisted (load baseline is already filled → not dirty).
      await selectNodeById(page, "b13-rest");
      await fillTextField(page, "operation_name", "b13_defaults_op");
      await saveGraphAndWait(page);

      const saved = await api("GET", `/visual-pipelines/${pipeline.pipeline_id}`);
      const restNode = (saved.graph?.nodes ?? []).find((n) => n.id === "b13-rest");
      const xformNode = (saved.graph?.nodes ?? []).find((n) => n.id === "b13-transform");
      const savedHttp = restNode?.data?.config?.values?.http_method;
      const savedTransform = xformNode?.data?.config?.values?.transform_type;
      if (savedHttp !== "GET") {
        fail(`B13: saved config.values.http_method expected GET, got ${savedHttp}`);
      }
      if (savedTransform !== "WIDE_HOUR_TO_LONG") {
        fail(`B13: saved config.values.transform_type expected WIDE_HOUR_TO_LONG, got ${savedTransform}`);
      }
      if (restNode?.data?.config?.values?.data_source_id === "DS-SAMPLE") {
        fail("B13: PLACEHOLDER data_source_id must not be injected");
      }

      const validateRes = await api("POST", "/visual-pipelines/validate-graph", {
        graph: saved.graph,
        pipeline_id: pipeline.pipeline_id,
        validation_level: "BASIC",
      });
      const requiredMiss = (validateRes.issues ?? []).filter(
        (i) =>
          i.phase === "CONFIG" &&
          i.code === "NODE_CONFIG_REQUIRED_FIELD_MISSING" &&
          (i.field_key === "http_method" || i.field_key === "transform_type") &&
          (i.node_id === "b13-rest" || i.node_id === "b13-transform"),
      );
      if (requiredMiss.length) {
        fail(
          `B13: Graph 검증 must not report required missing for http_method/transform_type: ${JSON.stringify(requiredMiss)}`,
        );
      }

      // Remove B13 probe nodes so later Compile/Materialize fixture stays 4-node MVP.
      await api("PUT", `/visual-pipelines/${pipeline.pipeline_id}`, {
        graph: {
          ...saved.graph,
          nodes: (saved.graph?.nodes ?? []).filter((n) => n.id !== "b13-rest" && n.id !== "b13-transform"),
        },
        create_version: false,
      });
      await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForTimeout(1200);
      await page.getByTestId("visual-pipeline-studio-page").waitFor({ state: "visible", timeout: 60000 });
      console.log("  [ok] B13 schema defaults UI=values + no http_method/transform_type required missing");
    }

    // --- Representative input + dirty/save ---
    await selectNodeById(page, "e2e-load");
    await assertConfigFormVisible(page, ["target_table", "write_mode"]);
    await fillTextField(page, "target_table", "tb_e2e_dirty_smoke");
    await selectFieldOption(page, "write_mode", "UPSERT");
    const conflictPanel = inspector.getByTestId("visual-pipeline-conflict-keys-panel");
    await conflictPanel.scrollIntoViewIfNeeded();
    if ((await conflictPanel.locator('input[type="text"]').count()) === 0) {
      await inspector.getByTestId("visual-pipeline-conflict-keys-advanced-toggle").click();
    }
    await conflictPanel.locator('input[type="text"]').fill("entity_id, measured_at");
    await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] Upsert field smoke -> dirty");

    await selectNodeById(page, "e2e-rest");
    await assertConfigFormVisible(page, ["operation_name"]);
    await fillTextField(page, "operation_name", RELOAD_OPERATION_NAME);
    await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] REST operation_name edit -> dirty");

    await saveGraphAndWait(page);
    console.log("  [ok] graph save toast + dirty cleared");

    // --- Reload / re-enter: REST operation_name preserved ---
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1200);
    await page.getByTestId("visual-pipeline-studio-page").waitFor({ state: "visible", timeout: 60000 });
    await selectNodeById(page, "e2e-rest");
    await assertConfigFormVisible(page, ["operation_name"]);
    const opValue = await inspector
      .getByTestId("visual-pipeline-inspector-config-field-operation_name")
      .locator("input")
      .inputValue();
    if (opValue !== RELOAD_OPERATION_NAME) {
      fail(`expected REST operation_name=${RELOAD_OPERATION_NAME} after reload, got ${opValue}`);
    }
    console.log("  [ok] S5-6 reload preserves REST operation_name");

    // --- R11-S6-6 materialize fixture (API) before Compile ---
    await ensureMaterializeReadyViaApi(pipeline.pipeline_id);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1200);
    await page.getByTestId("visual-pipeline-studio-page").waitFor({ state: "visible", timeout: 60000 });
    console.log("  [ok] materialize-ready graph via API + reload");

    // --- R11-S8-9-3 / B16: Graph 검증 must not re-dirty / block Compile ---
    {
      // Dock expand can resize the canvas and nudge RF positions → dirty.
      // Settle layout first so this assert isolates validation-cache dirty only.
      await openDockTab(page, "validation");
      await page.waitForTimeout(800);
      if (await toolbar.getByText("● 저장되지 않음").count()) {
        await saveGraphAndWait(page);
      }
      if (await toolbar.getByText("● 저장되지 않음").count()) {
        fail("B16 precondition: expected clean graph after dock settle + save");
      }
      const validationB16 = page.getByTestId("visual-pipeline-validation-panel");
      await page.getByTestId("visual-pipeline-validate-button").click();
      await validationB16.getByTestId("visual-pipeline-validation-severity").waitFor({
        state: "visible",
        timeout: 30000,
      });
      if (await toolbar.getByText("● 저장되지 않음").count()) {
        fail("B16: Graph 검증 직후 dirty(● 저장되지 않음)가 재발하면 안 됩니다");
      }
      const compileBtnB16 = page.getByTestId("visual-pipeline-compile-button");
      await compileBtnB16.waitFor({ state: "visible", timeout: 10000 });
      if (await compileBtnB16.isDisabled()) {
        const title = (await compileBtnB16.getAttribute("title")) || "";
        if (title.includes("저장되지 않은")) {
          fail(`B16: Compile must not be dirty-blocked after Graph 검증 (title=${title})`);
        }
      }
      await selectNodeById(page, "e2e-rest");
      const badgeB16 = (await inspector.getByTestId("visual-pipeline-inspector-validation-badge").innerText()).trim();
      if (!badgeB16 || badgeB16 === "NOT_VALIDATED") {
        fail(`B16: expected Inspector validation badge after Graph 검증, got ${badgeB16}`);
      }
      console.log(`  [ok] B16 validate→no dirty, Compile not dirty-blocked, badge=${badgeB16}`);
    }

    // --- R11-S6-3 Compile Preview / Compile smoke ---
    await page.getByTestId("visual-pipeline-compile-preview-button").waitFor({ state: "visible", timeout: 10000 });
    await page.getByTestId("visual-pipeline-compile-button").waitFor({ state: "visible", timeout: 10000 });
    const compilePanel = await runCompilePreviewAndWait(page);
    const previewStatus = (await compilePanel.getByTestId("visual-pipeline-compile-status").innerText()).trim();
    if (previewStatus !== "SUCCESS") {
      fail(`expected Compile Preview SUCCESS, got ${previewStatus}`);
    }
    const previewPersisted = (await compilePanel.getByTestId("visual-pipeline-compile-persisted").innerText()).trim();
    if (previewPersisted !== "false") {
      fail(`expected Compile Preview persisted=false, got ${previewPersisted}`);
    }
    await compilePanel.getByTestId("visual-pipeline-compile-steps").waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] Compile Preview SUCCESS persisted=false + steps");

    // Ensure clean saved state before persist Compile (dirty disables Compile).
    const dirtyChip = toolbar.getByText("● 저장되지 않음");
    if (await dirtyChip.count()) {
      await saveGraphAndWait(page);
      console.log("  [ok] cleared dirty before Compile");
    }

    await runCompileAndWait(page);
    const compileStatus = (await compilePanel.getByTestId("visual-pipeline-compile-status").innerText()).trim();
    if (compileStatus !== "SUCCESS") {
      fail(`expected Compile SUCCESS, got ${compileStatus}`);
    }
    const compilePersisted = (await compilePanel.getByTestId("visual-pipeline-compile-persisted").innerText()).trim();
    if (compilePersisted !== "true") {
      fail(`expected Compile persisted=true, got ${compilePersisted}`);
    }
    const resultId = (await compilePanel.getByTestId("visual-pipeline-compile-result-id").innerText()).trim();
    if (!resultId.startsWith("VPC-")) {
      fail(`expected compile_result_id VPC-*, got ${resultId}`);
    }
    await openDockTab(page, "graph");
    const syncBadge = page.getByTestId("visual-pipeline-sync-status");
    await syncBadge.waitFor({ state: "visible", timeout: 15000 });
    const syncText = (await syncBadge.innerText()).trim();
    const syncCode = (await syncBadge.getAttribute("data-status")) || "";
    if (syncCode !== "IN_SYNC" && syncText !== "컴파일 최신") {
      fail(`expected sync IN_SYNC / 컴파일 최신 after Compile, got status=${syncCode} text=${syncText}`);
    }
    console.log(`  [ok] Compile persisted=true result_id=${resultId} sync=${syncText}`);

    // --- R11-S6-6 Materialization smoke ---
    const materializeBtn = page.getByTestId("visual-pipeline-materialize-button");
    await materializeBtn.waitFor({ state: "visible", timeout: 30000 });
    if (await materializeBtn.isDisabled()) {
      fail("expected materialize button enabled after persisted SUCCESS Compile + IN_SYNC");
    }
    const matPanel = await runMaterializeAndWait(page);
    const matStatus = (await matPanel.getByTestId("visual-pipeline-materialization-status").innerText()).trim();
    if (matStatus !== "SUCCESS") {
      fail(`expected Materialization SUCCESS, got ${matStatus}`);
    }
    const matResultId = (await matPanel.getByTestId("visual-pipeline-materialization-result-id").innerText()).trim();
    if (!matResultId.startsWith("VPM-")) {
      fail(`expected materialization_result_id VPM-*, got ${matResultId}`);
    }
    const activation = (await matPanel.getByTestId("visual-pipeline-materialization-activation").innerText()).trim();
    if (activation !== "NOT_REQUESTED") {
      fail(`expected activation=NOT_REQUESTED, got ${activation}`);
    }
    const runCreated = (await matPanel.getByTestId("visual-pipeline-materialization-run-created").innerText()).trim();
    if (runCreated !== "false") {
      fail(`expected run_created=false, got ${runCreated}`);
    }
    console.log(`  [ok] Materialization SUCCESS result_id=${matResultId} activation=${activation} run_created=${runCreated}`);

    // --- R11-S7-4 Manual Run smoke ---
    await openDockTab(page, "run");
    await page.getByTestId("visual-pipeline-run-panel").waitFor({ state: "visible", timeout: 15000 });
    const runBtn = page.getByTestId("visual-pipeline-run-now-button");
    if (await runBtn.isDisabled()) {
      fail("expected Run Now button enabled after Compile+Materialize SUCCESS");
    }
    const { panel: runPanel, status: runStatus } = await runManualAndWait(page);
    if (runStatus !== "SUCCESS") {
      const issuesText = await runPanel
        .getByTestId("visual-pipeline-run-issues")
        .innerText()
        .catch(() => "(no issues panel)");
      fail(`expected Manual Run SUCCESS, got ${runStatus}; issues=${issuesText.slice(0, 400)}`);
    }
    const visualRunId = (await runPanel.getByTestId("visual-pipeline-run-id").innerText()).trim();
    if (!visualRunId.startsWith("VPR-")) {
      fail(`expected visual_run_id VPR-*, got ${visualRunId}`);
    }
    const loadRunId = (await runPanel.getByTestId("visual-pipeline-run-load-run-id").innerText()).trim();
    if (!loadRunId.startsWith("ACLR-")) {
      fail(`expected load_run_id ACLR-*, got ${loadRunId}`);
    }
    await runPanel.getByTestId("visual-pipeline-run-result").waitFor({ state: "visible", timeout: 10000 });
    await runPanel.getByTestId("visual-pipeline-run-safety").waitFor({ state: "visible", timeout: 10000 });
    const runMode = (await runPanel.getByTestId("visual-pipeline-run-mode").innerText()).trim();
    if (runMode !== "MANUAL") {
      fail(`expected Manual Run mode=MANUAL, got ${runMode}`);
    }
    console.log(`  [ok] Manual Run SUCCESS visual_run_id=${visualRunId} load_run_id=${loadRunId}`);

    // --- R11-S8-2 Run History smoke ---
    await openDockTab(page, "history");
    const historySection = page.getByTestId("visual-pipeline-run-history-section");
    await historySection.waitFor({ state: "visible", timeout: 15000 });
    await historySection.getByTestId("visual-pipeline-run-history-refresh").click();
    await historySection.getByTestId("visual-pipeline-run-history-status-filter").waitFor({
      state: "visible",
      timeout: 5000,
    });
    await historySection.getByTestId("visual-pipeline-run-history-mode-filter").waitFor({
      state: "visible",
      timeout: 5000,
    });
    const historyRows = historySection.getByTestId("visual-pipeline-run-history-row");
    await historyRows.first().waitFor({ state: "visible", timeout: 15000 });
    await historySection.getByTestId("visual-pipeline-run-history-detail-button").first().click();
    await page.getByTestId("visual-pipeline-run-detail-panel").waitFor({ state: "visible", timeout: 10000 });
    await page.getByTestId("visual-pipeline-run-detail-progress-section").waitFor({
      state: "visible",
      timeout: 10000,
    });
    await page.getByTestId("visual-pipeline-run-detail-retry-section").waitFor({
      state: "visible",
      timeout: 10000,
    });
    // After successful Manual Run the latest detail is SUCCESS — retry action must be hidden.
    const statusText = await page.getByTestId("visual-pipeline-run-detail-panel").innerText();
    if (/상태[\s\S]*SUCCESS/i.test(statusText) || statusText.includes("SUCCESS")) {
      const retryBtn = page.getByTestId("visual-pipeline-run-detail-retry-button");
      if ((await retryBtn.count()) > 0) {
        fail("SUCCESS run detail must not show Retry action button");
      }
      const unavailable = page.getByTestId("visual-pipeline-run-detail-retry-unavailable");
      if ((await unavailable.count()) === 0) {
        fail("expected retry-unavailable notice for SUCCESS run");
      }
    }
    // Global interrupt action buttons must not appear for SUCCESS; cancel section is allowed.
    await page.getByTestId("visual-pipeline-run-detail-cancel-section").waitFor({
      state: "visible",
      timeout: 10000,
    });
    const interruptBtn = page.getByTestId("visual-pipeline-run-detail-cancel-button");
    if ((await interruptBtn.count()) > 0) {
      fail("SUCCESS run detail must not show soft-cancel action button");
    }
    const cancelUnavailable = page.getByTestId("visual-pipeline-run-detail-cancel-unavailable");
    if ((await cancelUnavailable.count()) === 0) {
      fail("expected cancel-unavailable notice for SUCCESS run");
    }
    await page.getByTestId("visual-pipeline-run-detail-close").click();
    console.log("  [ok] Run History list/filter/detail (progress + retry + cancel section)");

    // --- R11-S7-8 Schedule Activation smoke (panel only; due enqueue in backend tests) ---
    await openDockTab(page, "run");
    await page.getByTestId("visual-pipeline-schedule-activation-panel").waitFor({ state: "visible", timeout: 15000 });
    const activateBtn = page.getByTestId("visual-pipeline-schedule-activation-button");
    if (await activateBtn.isDisabled()) {
      fail(
        "expected Schedule Activation button enabled after SUCCESS materialization (set THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED=true on backend)",
      );
    }
    page.once("dialog", (dialog) => dialog.accept());
    await activateBtn.click();
    const actPanel = page.getByTestId("visual-pipeline-schedule-activation-panel");
    await actPanel.getByTestId("visual-pipeline-schedule-activation-status").waitFor({
      state: "visible",
      timeout: 30000,
    });
    const actStatus = (await actPanel.getByTestId("visual-pipeline-schedule-activation-status").innerText()).trim();
    if (actStatus !== "ACTIVE") {
      const actErr = await actPanel.locator("p.text-red-600").innerText().catch(() => "");
      fail(`expected activation ACTIVE, got ${actStatus}; err=${actErr.slice(0, 300)}`);
    }
    const actId = (await actPanel.getByTestId("visual-pipeline-schedule-activation-id").innerText()).trim();
    if (!actId.startsWith("VPA-")) {
      fail(`expected activation_id VPA-*, got ${actId}`);
    }
    if (!(await page.getByTestId("visual-pipeline-schedule-activation-button").isDisabled())) {
      fail("expected Schedule Activation button disabled while ACTIVE");
    }

    // R11-S8-6 Catch-up section (candidate may be empty — section must still render)
    await actPanel.getByTestId("visual-pipeline-schedule-catchup-section").waitFor({
      state: "visible",
      timeout: 15000,
    });

    // --- B4: Catch-up guidance ---
    {
      const guidance = actPanel.getByTestId("visual-pipeline-catchup-guidance");
      await guidance.waitFor({ state: "visible", timeout: 10000 });
      const summary = (
        await actPanel.getByTestId("visual-pipeline-catchup-guidance-summary").innerText()
      ).trim();
      if (!summary.includes("누락 후보") && !summary.toLowerCase().includes("catch-up")) {
        fail("B4: Catch-up guidance summary missing");
      }
      const notAuto = (
        await actPanel.getByTestId("visual-pipeline-catchup-guidance-not-auto").innerText()
      ).trim();
      if (!notAuto.includes("자동 복구가 아닙니다")) {
        fail("B4: must state Catch-up is not automatic recovery");
      }
      await actPanel.getByTestId("visual-pipeline-catchup-guidance-toggle").click();
      await actPanel.getByTestId("visual-pipeline-catchup-guidance-details").waitFor({
        state: "visible",
        timeout: 5000,
      });
      for (const termId of ["missed", "candidate", "window", "skip_reason"]) {
        await actPanel
          .getByTestId(`visual-pipeline-catchup-guidance-term-${termId}`)
          .waitFor({ state: "visible", timeout: 3000 });
      }
      await actPanel.getByTestId("visual-pipeline-catchup-guidance-checklist").waitFor({
        state: "visible",
        timeout: 3000,
      });
      const guidanceText = (await guidance.innerText()).toLowerCase();
      if (
        guidanceText.includes("자동 catch-up 실행") ||
        guidanceText.includes("자동 복구됨") ||
        guidanceText.includes("auto catchup")
      ) {
        fail("B4: guidance must not advertise auto catch-up / auto recovery done");
      }
      console.log("  [ok] B4 Catch-up guidance (terms + checklist + not auto recovery)");
    }

    await actPanel.getByTestId("visual-pipeline-schedule-catchup-refresh").click();
    const catchupEligible = actPanel.getByTestId("visual-pipeline-schedule-catchup-eligible");
    const catchupUnavailable = actPanel.getByTestId("visual-pipeline-schedule-catchup-unavailable");
    const catchupReason = actPanel.getByTestId("visual-pipeline-schedule-catchup-reason");
    await Promise.race([
      catchupEligible.waitFor({ state: "visible", timeout: 15000 }),
      catchupUnavailable.waitFor({ state: "visible", timeout: 15000 }),
      catchupReason.waitFor({ state: "visible", timeout: 15000 }),
    ]);
    console.log("  [ok] Schedule Catch-up section visible");

    // Pause → Resume → Deactivate
    const pauseBtn = actPanel.getByTestId("visual-pipeline-schedule-pause-button");
    page.once("dialog", (dialog) => dialog.accept());
    await pauseBtn.click();
    await page.waitForTimeout(1200);
    const pausedStatus = (await actPanel.getByTestId("visual-pipeline-schedule-activation-status").innerText()).trim();
    if (pausedStatus !== "PAUSED") {
      fail(`expected activation PAUSED, got ${pausedStatus}`);
    }
    const resumeBtn = actPanel.getByTestId("visual-pipeline-schedule-resume-button");
    page.once("dialog", (dialog) => dialog.accept());
    await resumeBtn.click();
    await page.waitForTimeout(1200);
    const resumedStatus = (
      await actPanel.getByTestId("visual-pipeline-schedule-activation-status").innerText()
    ).trim();
    if (resumedStatus !== "ACTIVE") {
      fail(`expected activation ACTIVE after resume, got ${resumedStatus}`);
    }

    const deactivateBtn = actPanel.getByTestId("visual-pipeline-schedule-deactivate-button");
    page.once("dialog", (dialog) => dialog.accept());
    await deactivateBtn.click();
    await page.waitForTimeout(1500);
    const actStatus2 = (await actPanel.getByTestId("visual-pipeline-schedule-activation-status").innerText()).trim();
    if (actStatus2 !== "INACTIVE") {
      fail(`expected activation INACTIVE after deactivate, got ${actStatus2}`);
    }
    console.log(`  [ok] Schedule Activation ACTIVE→PAUSED→ACTIVE→INACTIVE activation_id=${actId}`);

    // --- Graph validation smoke (errors 0) ---
    await runGraphValidationAndWait(page);
    const severityBadge = validation.getByTestId("visual-pipeline-validation-severity");
    await severityBadge.waitFor({ state: "visible", timeout: 10000 });
    const severity = (await severityBadge.innerText()).trim();
    if (severity === "ERROR") {
      fail(`expected no ERROR for valid 4-node fixture, got ${severity}`);
    }
    const errorsText = await validation.getByText(/errors \d+/).first().innerText();
    const errorCount = Number((errorsText.match(/errors\s+(\d+)/) || [])[1] ?? "1");
    if (errorCount > 0) {
      fail(`expected errors 0 for valid fixture, got ${errorsText}`);
    }
    console.log(`  [ok] Graph 검증 result severity=${severity}, ${errorsText}`);

    // --- CONFIG issue + badge + field warning ---
    await selectNodeById(page, "e2e-rest");
    await fillTextField(page, "operation_name", "");
    await runGraphValidationAndWait(page);
    await validation.locator("summary").filter({ hasText: /Issues/ }).click();
    await validation.getByText("NODE_CONFIG_REST_OPERATION_MISSING").first().waitFor({
      state: "visible",
      timeout: 30000,
    });
    await validation.getByText("CONFIG").first().waitFor({ state: "visible", timeout: 10000 });
    await validation.getByText(/field=operation_name/).first().waitFor({ state: "visible", timeout: 10000 });
    const badge = inspector.getByTestId("visual-pipeline-inspector-validation-badge");
    const badgeText = (await badge.innerText()).trim();
    if (badgeText !== "WARNING" && badgeText !== "ERROR") {
      fail(`expected REST config badge WARNING/ERROR after clearing operation_name, got ${badgeText}`);
    }
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-operation_name")
      .locator("p")
      .filter({ hasText: /operation_name/i })
      .first()
      .waitFor({ state: "visible", timeout: 10000 });
    console.log(`  [ok] CONFIG issue + badge=${badgeText} + field warning`);

    await toolbar.getByRole("button", { name: "이력" }).click();
    await page.getByText("버전 이력").first().waitFor({ state: "visible", timeout: 15000 });
    await page.getByRole("button", { name: "닫기" }).click();
    console.log("  [ok] version history modal open/close");

    page.once("dialog", (dialog) => dialog.accept());
    await toolbar.getByRole("button", { name: "목록" }).click();
    await page.waitForURL(/\/visual-pipelines\/?$/, { timeout: 30000 });
    await page.locator("main h1").filter({ hasText: /^Visual Pipeline Studio$/ }).first().waitFor({
      state: "visible",
      timeout: 30000,
    });
    console.log("  [ok] list navigation");

    if (pageErrors.length) {
      const filtered = pageErrors.filter(
        (msg) => !/Cannot read properties of null \(reading 'document'\)/.test(msg),
      );
      if (filtered.length) {
        fail(`page errors: ${filtered.join(" | ")}`);
      }
      if (pageErrors.length !== filtered.length) {
        console.log("  [ok] ignored React Flow teardown pageerror on navigation");
      }
    }
  } finally {
    await browser.close();
  }
}

async function main() {
  console.log("THERMOps R11-S7-4 Visual Pipeline Studio E2E");
  console.log(`  frontend=${FRONTEND_BASE}`);
  console.log(`  api=${API_BASE}`);

  assertNoDataSourcesSizeOver100();
  assertNoValidationCacheNodeMutation();
  assertSchemaDefaultsSeparatedFromPlaceholder();
  assertUnmappedPolicyEnumAligned();
  ensureMaterializeSeedData();

  let pipelineId = null;
  let archived = false;
  try {
    const created = await createFixture();
    pipelineId = created.pipeline_id;
    await runBrowserSmoke(created);
    console.log("PASS Studio detail route E2E");
  } catch (err) {
    console.error(`FAIL Studio E2E: ${err.message}`);
    process.exitCode = 1;
  } finally {
    if (pipelineId) {
      archived = await archiveFixture(pipelineId);
      if (!archived) {
        console.warn("  [warn] fixture left unarchived (prefix searchable in include_archived=true)");
      }
    }
  }

  if (process.exitCode && process.exitCode !== 0) {
    process.exit(process.exitCode);
  }
  console.log(`CLEANUP archive=${archived ? "ok" : "warn"}`);
}

await main();
