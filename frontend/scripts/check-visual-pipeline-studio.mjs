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
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const FRONTEND_BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const API_BASE = process.env.THERMOOPS_API_BASE || "http://localhost:8000/api/v1";
const INTERNAL_API =
  process.env.THERMOOPS_INTERNAL_API_BASE || "http://127.0.0.1:8000/api/v1";
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

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
  const status = page.getByTestId("visual-pipeline-graph-status");
  if (await status.getByText("Graph JSON Preview").isVisible().catch(() => false)) {
    await status.getByRole("button").filter({ hasText: "Graph Status Panel" }).click();
  }
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
    await inspector.getByTestId(`visual-pipeline-inspector-config-field-${fieldKey}`).waitFor({
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

async function runGraphValidationAndWait(page) {
  const validation = page.getByTestId("visual-pipeline-validation-panel");
  await page.getByTestId("visual-pipeline-validate-button").click();
  await validation.getByText(/OK|WARNING|ERROR|INFO/).first().waitFor({ state: "visible", timeout: 30000 });
  return validation;
}

async function runCompilePreviewAndWait(page) {
  const panel = page.getByTestId("visual-pipeline-compile-panel");
  await page.getByTestId("visual-pipeline-compile-preview-button").click();
  await panel.getByTestId("visual-pipeline-compile-status").waitFor({ state: "visible", timeout: 30000 });
  return panel;
}

async function runCompileAndWait(page) {
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
  const panel = page.getByTestId("visual-pipeline-materialization-panel");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("visual-pipeline-materialize-button").click();
  await panel.getByTestId("visual-pipeline-materialization-status").waitFor({ state: "visible", timeout: 45000 });
  return panel;
}

async function runManualAndWait(page) {
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

    const status = page.getByTestId("visual-pipeline-graph-status");
    await status.getByText("nodes 4").first().waitFor({ state: "visible", timeout: 10000 });
    const validation = page.getByTestId("visual-pipeline-validation-panel");
    await validation.getByText("아직 Graph 검증을 실행하지 않았습니다.").waitFor({
      state: "visible",
      timeout: 10000,
    });
    console.log("  [ok] status + validation initial");

    // --- MVP 4 Form visibility smoke ---
    await selectNodeById(page, "e2e-rest");
    await inspector.getByText("VP_REST_API_SOURCE").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["operation_name", "endpoint_path", "http_method"]);
    console.log("  [ok] REST config form visible");

    await selectNodeById(page, "e2e-transform");
    await inspector.getByText("VP_TRANSFORM").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["transform_type"]);
    console.log("  [ok] Transform config form visible");

    await selectNodeById(page, "e2e-cron");
    await inspector.getByText("VP_CRON_SCHEDULE").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["cron_expression", "timezone", "active_yn"]);
    console.log("  [ok] CRON config form visible");

    await selectNodeById(page, "e2e-load");
    await inspector.getByText("VP_UPSERT_LOAD").first().waitFor({ state: "visible", timeout: 10000 });
    await assertConfigFormVisible(page, ["target_table", "write_mode", "conflict_key_columns_json"]);
    console.log("  [ok] Upsert config form visible");

    // --- Representative input + dirty/save ---
    await fillTextField(page, "target_table", "tb_e2e_dirty_smoke");
    await selectFieldOption(page, "write_mode", "UPSERT");
    await fillTextField(page, "conflict_key_columns_json", "entity_id, measured_at");
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
    await materializeBtn.scrollIntoViewIfNeeded();
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
    await page.getByTestId("visual-pipeline-run-panel").waitFor({ state: "visible", timeout: 15000 });
    const runBtn = page.getByTestId("visual-pipeline-run-now-button");
    await runBtn.scrollIntoViewIfNeeded();
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

    // --- R11-S7-8 Schedule Activation smoke (panel only; due enqueue in backend tests) ---
    await page.getByTestId("visual-pipeline-schedule-activation-panel").waitFor({ state: "visible", timeout: 15000 });
    const activateBtn = page.getByTestId("visual-pipeline-schedule-activation-button");
    await activateBtn.scrollIntoViewIfNeeded();
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
    const severityBadge = validation.locator("span").filter({ hasText: /^(OK|WARNING|ERROR|INFO)$/ }).first();
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
