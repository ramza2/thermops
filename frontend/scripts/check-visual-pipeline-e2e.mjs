/**
 * R11-S8-9-15 / B12 Visual Pipeline E2E smoke scenario.
 *
 * Operator journey (generic sample naming, platform seed load target):
 *   REST → Transform → Upsert → Validate → Compile → 실행 설정 반영
 *   → 즉시 실행 → Run History/Detail → Target Table Preview → cleanup
 *
 * Env:
 *   CHECK_PAGES_BASE     frontend base (default http://localhost:5173)
 *   THERMOOPS_API_BASE   API base including /api/v1 (default http://localhost:8000/api/v1)
 *   THERMOOPS_INTERNAL_API_BASE  backend self-call base for sample-external
 *     (default http://127.0.0.1:8000/api/v1)
 *
 * Product / backend / migration / package: not modified by this script.
 * Physical table DROP/TRUNCATE/DELETE/UPDATE/INSERT: not performed.
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

const PIPELINE_NAME_PREFIX = "E2E_B12_ Visual Pipeline";
const PIPELINE_DESCRIPTION = "Created by R11-S8-9-15 / B12 E2E smoke";

const NODE_CRON = "b12-cron";
const NODE_REST = "b12-rest";
const NODE_TRANSFORM = "b12-transform";
const NODE_LOAD = "b12-load";

/** Platform sample ACTIVE SDS (seed). Documented as supported sample, not product hardcoding. */
const SEED_DATASET_ID = "TEST-DST-HEAT";
const SEED_TARGET_TABLE = "heat_demand_actual";
const SAMPLE_ENDPOINT = "/sample-external/heat-demand";

const FIXTURE_GRAPH = {
  nodes: [
    {
      id: NODE_CRON,
      type: "VP_CRON_SCHEDULE",
      position: { x: 80, y: 220 },
      data: {
        label: "CRON Schedule",
        component_type: "VP_CRON_SCHEDULE",
        config: {
          schedule_type: "CRON",
          cron_expression: "0 6 * * *",
          timezone: "Asia/Seoul",
          active_yn: false,
        },
      },
    },
    {
      id: NODE_REST,
      type: "VP_REST_API_SOURCE",
      position: { x: 320, y: 220 },
      data: {
        label: "REST API Source",
        component_type: "VP_REST_API_SOURCE",
        config: {
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
        },
      },
    },
    {
      id: NODE_TRANSFORM,
      type: "VP_TRANSFORM",
      position: { x: 600, y: 220 },
      data: {
        label: "Transform",
        component_type: "VP_TRANSFORM",
        config: {
          schema_version: "R11-S5-0",
          values: {
            transform_type: "WIDE_HOUR_TO_LONG",
            unmapped_policy: "SKIP_UNMAPPED",
            mapping_config: {},
          },
          validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
        },
      },
    },
    {
      id: NODE_LOAD,
      type: "VP_UPSERT_LOAD",
      position: { x: 880, y: 220 },
      data: {
        label: "Upsert Load",
        component_type: "VP_UPSERT_LOAD",
        config: {
          schema_version: "R11-S5-0",
          values: {
            standard_dataset_id: "SD-SAMPLE",
            target_table: "tb_e2e_b12_fact",
            write_mode: "UPSERT",
            conflict_key_columns_json: ["entity_id", "measured_at"],
          },
          validation: { status: "NOT_VALIDATED", last_validated_at: null, issue_count: 0 },
        },
      },
    },
  ],
  edges: [
    {
      id: "b12-edge-1",
      source: NODE_CRON,
      target: NODE_REST,
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
      id: "b12-edge-2",
      source: NODE_REST,
      target: NODE_TRANSFORM,
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
      id: "b12-edge-3",
      source: NODE_TRANSFORM,
      target: NODE_LOAD,
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

function stepOk(n, msg) {
  console.log(`  [B12][${String(n).padStart(2, "0")}] ${msg}`);
}

function fail(step, reason) {
  const full = `[B12][FAILED] step=${step} reason=${reason}`;
  console.error(full);
  process.exitCode = 1;
  throw new Error(full);
}

function resolveScriptsDir() {
  const fromRepo = path.join(REPO_ROOT, "scripts");
  if (existsSync(fromRepo)) return fromRepo;
  if (existsSync("/scripts")) return "/scripts";
  return fromRepo;
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

async function api(method, apiPath, body, { soft = false } = {}) {
  const url = `${API_BASE}${apiPath}`;
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
    const msg = `API ${method} ${apiPath} -> ${res.status}: ${text.slice(0, 400)}`;
    if (soft) {
      console.warn(`  [warn] ${msg}`);
      return null;
    }
    throw new Error(msg);
  }
  if (data && typeof data === "object" && "data" in data && data.success !== undefined) {
    if (data.success === false) {
      const msg = `API ${method} ${apiPath} success=false: ${text.slice(0, 400)}`;
      if (soft) {
        console.warn(`  [warn] ${msg}`);
        return null;
      }
      throw new Error(msg);
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
  if (!created?.pipeline_id) fail(2, "fixture create missing pipeline_id");
  stepOk(2, `fixture created ${created.pipeline_id} (${pipeline_name})`);
  return created;
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

async function createRestDataSource() {
  const tag = Date.now().toString(36);
  const created = await api("POST", "/data-sources", {
    source_name: `E2E_B12_ REST ${tag}`,
    source_type: "REST_API",
    data_domain: "HEAT_DEMAND",
    connection_info: {
      base_url: INTERNAL_API,
      timeout_seconds: 30,
    },
    active_yn: true,
  });
  if (!created?.source_id) fail("api-ready", "REST data source create missing source_id");
  return created.source_id;
}

async function ensureSampleMapping(sourceId) {
  const listed = await api("GET", "/mappings?page=1&size=100");
  const items = listed?.items ?? [];
  const existing = items.find((m) => m.source_id === sourceId && m.target_table === SEED_TARGET_TABLE);
  if (existing?.mapping_id) return existing.mapping_id;
  await api("POST", "/mappings", {
    source_id: sourceId,
    mapping_name: `E2E_B12_ mapping ${Date.now().toString(36)}`,
    target_table: SEED_TARGET_TABLE,
    columns: [
      { source_column: "site_id", target_column: "site_id", required_yn: true },
      { source_column: "measured_at", target_column: "measured_at", required_yn: true },
      { source_column: "heat_demand", target_column: "heat_demand", required_yn: true },
      { source_column: "supply_temp", target_column: "supply_temp", required_yn: false },
    ],
  });
  const again = await api("GET", "/mappings?page=1&size=100");
  const created = (again?.items ?? []).find(
    (m) => m.source_id === sourceId && m.target_table === SEED_TARGET_TABLE,
  );
  if (!created?.mapping_id) fail("api-ready", "mapping create failed for runnable fixture");
  return created.mapping_id;
}

async function ensureRunnableViaApi(pipelineId) {
  const sourceId = await createRestDataSource();
  await ensureSampleMapping(sourceId);
  const detail = await api("GET", `/visual-pipelines/${pipelineId}`);
  let graph = detail.graph ?? FIXTURE_GRAPH;
  graph = patchNodeConfigValues(graph, NODE_REST, {
    data_source_id: sourceId,
    operation_name: "vp-b12-manual-run-op",
    endpoint_path: SAMPLE_ENDPOINT,
    http_method: "GET",
    response_item_path: "data.items",
    credential_ref: "CRED-REF-1",
  });
  graph = patchNodeConfigValues(graph, NODE_TRANSFORM, {
    transform_type: "WIDE_HOUR_TO_LONG",
    unmapped_policy: "SKIP_UNMAPPED",
  });
  graph = patchNodeConfigValues(graph, NODE_LOAD, {
    standard_dataset_id: SEED_DATASET_ID,
    target_table: SEED_TARGET_TABLE,
    write_mode: "UPSERT",
    conflict_key_columns_json: ["site_id", "measured_at"],
  });
  await api("PUT", `/visual-pipelines/${pipelineId}`, { graph, create_version: false });
  return sourceId;
}

async function archiveFixture(pipelineId) {
  try {
    const archived = await api("POST", `/visual-pipelines/${pipelineId}/archive`, undefined, { soft: true });
    if (archived?.status !== "ARCHIVED") {
      console.warn(`  [warn] archive returned unexpected status: ${archived?.status ?? "unknown"}`);
      return false;
    }
    stepOk(21, `pipeline archived ${pipelineId}`);
    return true;
  } catch (err) {
    console.warn(`  [warn] archive cleanup failed for ${pipelineId}: ${err.message}`);
    return false;
  }
}

async function bestEffortDeleteDataSource(sourceId) {
  if (!sourceId) return;
  try {
    const blockers = await api("GET", `/data-sources/${encodeURIComponent(sourceId)}/delete-blockers`, undefined, {
      soft: true,
    });
    if (blockers && Array.isArray(blockers.blockers) && blockers.blockers.length > 0) {
      console.warn(`  [warn] DS ${sourceId} has delete blockers — skip DELETE`);
      return;
    }
    await api("DELETE", `/data-sources/${encodeURIComponent(sourceId)}`, undefined, { soft: true });
    console.log(`  [ok] best-effort deleted data source ${sourceId}`);
  } catch (err) {
    console.warn(`  [warn] DS delete skipped: ${String(err).slice(0, 200)}`);
  }
}

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
    await field.waitFor({ state: "visible", timeout: 10000 });
  }
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

async function runBrowserE2e(pipeline) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));

  let b19SourceId = null;
  let b20DatasetId = null;
  let runtimeSourceId = null;

  try {
    await openStudio(page, pipeline.pipeline_id);
    stepOk(1, "Studio opened");

    const toolbar = page.getByTestId("visual-pipeline-toolbar");
    await toolbar.waitFor({ state: "visible", timeout: 15000 });
    const inspector = page.getByTestId("visual-pipeline-inspector");

    // B5: Ops link/badge show-or-hide without crash
    {
      const opsLinkCount = await page.getByTestId("visual-pipeline-studio-ops-link").count();
      const badgeCount = await page.getByTestId("visual-pipeline-studio-ops-action-badge").count();
      const badgeErrCount = await page.getByTestId("visual-pipeline-studio-ops-action-badge-error").count();
      console.log(
        `  [ok] B5 studio Ops link/badge show_or_hide (link=${opsLinkCount}, badge=${badgeCount}, err=${badgeErrCount})`,
      );
    }

    // B1/B2: Starter Template + Domain Preset section show without crash
    {
      const starterBtn = page.getByTestId("visual-pipeline-starter-template-button");
      if ((await starterBtn.count()) > 0) {
        await starterBtn.first().waitFor({ state: "visible", timeout: 10000 });
        console.log("  [ok] B1 Starter Template button visible");
        await starterBtn.first().click();
        const modal = page.getByTestId("visual-pipeline-starter-template-modal");
        await modal.waitFor({ state: "visible", timeout: 10000 });
        await page.getByTestId("visual-pipeline-domain-preset-section").waitFor({
          state: "visible",
          timeout: 5000,
        });
        console.log("  [ok] B2 Domain Preset section visible");
        await page.keyboard.press("Escape").catch(() => {});
        // close via cancel if still open
        const cancel = page.getByRole("button", { name: "취소" });
        if ((await cancel.count()) > 0 && (await modal.count()) > 0) {
          await cancel.first().click().catch(() => {});
        }
      } else {
        console.log("  [ok] B1 Starter Template button absent (conditional)");
      }
    }

    for (const nodeId of [NODE_CRON, NODE_REST, NODE_TRANSFORM, NODE_LOAD]) {
      await page.getByTestId(`visual-pipeline-node-${nodeId}`).waitFor({ state: "visible", timeout: 20000 });
    }
    stepOk(3, "CRON/REST/Transform/Upsert nodes visible");

    const detail = await api("GET", `/visual-pipelines/${pipeline.pipeline_id}`);
    const edges = detail.graph?.edges ?? [];
    if (edges.length < 3) fail(7, `expected >=3 edges, got ${edges.length}`);
    const hasScheduleEdge = edges.some((e) => e.source === NODE_CRON && e.target === NODE_REST);
    const hasRestEdge = edges.some((e) => e.source === NODE_REST && e.target === NODE_TRANSFORM);
    const hasLoadEdge = edges.some((e) => e.source === NODE_TRANSFORM && e.target === NODE_LOAD);
    if (!hasScheduleEdge || !hasRestEdge || !hasLoadEdge) {
      fail(8, "expected CRON→REST, REST→Transform, Transform→Upsert edges");
    }
    stepOk(8, "Graph edges connected");

    // --- Forms ---
    await selectNodeById(page, NODE_REST);
    await assertConfigFormVisible(page, ["operation_name", "endpoint_path", "http_method", "data_source_id"]);
    stepOk(4, "REST config form visible");

    await selectNodeById(page, NODE_TRANSFORM);
    await assertConfigFormVisible(page, ["transform_type", "unmapped_policy"]);
    const transformType = await inspector
      .getByTestId("visual-pipeline-inspector-config-field-transform_type")
      .locator("select")
      .inputValue();
    if (!transformType || transformType === "") {
      fail(13, `B13: transform_type must be persisted in config, got ${transformType}`);
    }
    stepOk(5, `Transform form visible (transform_type=${transformType})`);

    await selectNodeById(page, NODE_CRON);
    await assertConfigFormVisible(page, ["cron_expression", "timezone", "active_yn"]);
    stepOk(6, "CRON config form visible");

    await selectNodeById(page, NODE_LOAD);
    await assertConfigFormVisible(page, ["target_table", "write_mode", "conflict_key_columns_json"]);
    stepOk(6, "Upsert config form visible");
    {
      const helperCount = await inspector.getByTestId("visual-pipeline-schema-key-helper").count();
      if (helperCount > 0) {
        await inspector.getByTestId("visual-pipeline-schema-key-helper").first().waitFor({
          state: "visible",
          timeout: 10000,
        });
      }
      console.log(`  [ok] B3 Schema/Key Helper show_or_hide (count=${helperCount})`);
    }

    // --- B19: REST Data Source inline create ---
    await selectNodeById(page, NODE_REST);
    {
      await inspector.getByTestId("visual-pipeline-data-source-picker").waitFor({ state: "visible", timeout: 10000 });
      const createName = `E2E_B12_ REST UI ${Date.now().toString(36)}`;
      await inspector.getByTestId("visual-pipeline-data-source-create-toggle").click();
      await inspector.getByTestId("visual-pipeline-data-source-create-form").waitFor({ state: "visible", timeout: 10000 });
      if ((await inspector.getByTestId("visual-pipeline-data-source-create-form").locator('input[type="password"]').count()) > 0) {
        fail(9, "B19: inline create must not expose password/secret inputs");
      }
      await inspector.getByTestId("visual-pipeline-data-source-create-name").fill(createName);
      await inspector.getByTestId("visual-pipeline-data-source-create-base-url").fill(INTERNAL_API);
      await inspector.getByTestId("visual-pipeline-data-source-create-domain").selectOption("HEAT_DEMAND");
      await inspector.getByTestId("visual-pipeline-data-source-create-submit").click();
      await inspector.getByTestId("visual-pipeline-data-source-create-success").waitFor({ state: "visible", timeout: 30000 });
      b19SourceId = await inspector.getByTestId("visual-pipeline-data-source-select").inputValue();
      if (!b19SourceId || b19SourceId === "DS-SAMPLE") {
        fail(9, `B19: expected new data_source_id, got ${b19SourceId}`);
      }
      await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
      await saveGraphAndWait(page);
      stepOk(9, `B19 inline create data_source_id=${b19SourceId}`);
    }

    // --- B20/B21/B15/B27 on Upsert ---
    await selectNodeById(page, NODE_LOAD);
    {
      await inspector.getByTestId("visual-pipeline-standard-dataset-picker").waitFor({ state: "visible", timeout: 10000 });
      const tag = Date.now().toString(36).toUpperCase();
      const createName = `E2E_B12_ SDS ${tag}`;
      const createCode = `B12${tag}`.slice(0, 32);

      await inspector.getByTestId("visual-pipeline-standard-dataset-create-toggle").click();
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-form").waitFor({ state: "visible", timeout: 10000 });
      const createHint = await inspector.getByTestId("visual-pipeline-standard-dataset-create-hint").innerText();
      if (!createHint.includes("DRAFT") || !createHint.includes("물리 테이블")) {
        fail(10, `B20: create hint must clarify DRAFT metadata only, got ${createHint}`);
      }

      await inspector.getByTestId("visual-pipeline-standard-dataset-propose-columns").click();
      await inspector.getByTestId("visual-pipeline-standard-dataset-proposal-info").waitFor({
        state: "visible",
        timeout: 10000,
      });
      const columnRowCount = await inspector
        .locator('[data-testid^="visual-pipeline-standard-dataset-column-row-"]')
        .count();
      if (columnRowCount < 2) fail(10, `B21: expected column rows after proposal, got ${columnRowCount}`);
      const columnNames = await inspector
        .getByTestId("visual-pipeline-standard-dataset-column-name")
        .evaluateAll((inputs) => inputs.map((i) => i.value));
      if (!columnNames.includes("heat_demand") || !columnNames.includes("measured_at")) {
        fail(10, `B21: expected heat_demand/measured_at proposals, got ${JSON.stringify(columnNames)}`);
      }
      stepOk(10, `B21 column proposal (${columnRowCount} rows)`);

      // B15: rename measured_at → Measured At and compare
      {
        const measuredAtIdx = columnNames.indexOf("measured_at");
        await inspector
          .getByTestId("visual-pipeline-standard-dataset-column-name")
          .nth(measuredAtIdx)
          .fill("Measured At");
        await inspector.getByTestId("visual-pipeline-column-match-compare-button").click();
        await inspector.getByTestId("visual-pipeline-column-match-summary").waitFor({
          state: "visible",
          timeout: 10000,
        });
        const matchLevels = await inspector
          .locator('[data-testid^="visual-pipeline-column-match-row-"]')
          .evaluateAll((rows) => rows.map((r) => r.getAttribute("data-match-level")));
        if (!matchLevels.includes("NORMALIZED") && !matchLevels.includes("EXACT")) {
          fail(12, `B15: expected NORMALIZED or EXACT match, got ${JSON.stringify(matchLevels)}`);
        }
        stepOk(12, `B15 column match preview levels=${JSON.stringify([...new Set(matchLevels)])}`);
      }

      // B27: conflict keys recommend apply
      {
        await inspector.getByTestId("visual-pipeline-conflict-keys-panel").waitFor({
          state: "visible",
          timeout: 10000,
        });
        await page.waitForTimeout(400);
        await inspector.getByTestId("visual-pipeline-conflict-keys-recommend-toggle").click();
        await inspector.getByTestId("visual-pipeline-conflict-keys-recommend-list").waitFor({
          state: "visible",
          timeout: 10000,
        });
        await inspector
          .getByTestId("visual-pipeline-conflict-keys-recommend-item")
          .first()
          .getByRole("button", { name: "적용" })
          .click();
        const selectedKeysText = await inspector.getByTestId("visual-pipeline-conflict-keys-selected").innerText();
        if (!selectedKeysText.includes("entity_id")) {
          fail(13, `B27: selected keys should include entity_id, got ${selectedKeysText}`);
        }
        stepOk(13, `B27 conflict keys selected (${selectedKeysText.replace(/\s+/g, " ").trim()})`);
      }

      await inspector.getByTestId("visual-pipeline-standard-dataset-create-name").fill(createName);
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-code").fill(createCode);
      await inspector.getByTestId("visual-pipeline-standard-dataset-suggest-table").click();
      await page.waitForTimeout(600);
      const suggestedTable = await inspector
        .getByTestId("visual-pipeline-standard-dataset-create-target-table")
        .inputValue();
      if (!suggestedTable || !suggestedTable.startsWith("std_")) {
        await inspector
          .getByTestId("visual-pipeline-standard-dataset-create-target-table")
          .fill(`std_b12_${tag.toLowerCase()}`);
      }
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-submit").click();
      await inspector.getByTestId("visual-pipeline-standard-dataset-create-success").waitFor({
        state: "visible",
        timeout: 30000,
      });
      b20DatasetId = await inspector.getByTestId("visual-pipeline-standard-dataset-select").inputValue();
      if (!b20DatasetId || b20DatasetId === "SD-SAMPLE") {
        fail(10, `B20: expected new standard_dataset_id, got ${b20DatasetId}`);
      }
      await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
      await saveGraphAndWait(page);
      stepOk(10, `B20 DRAFT created standard_dataset_id=${b20DatasetId}`);

      try {
        await api("POST", `/standard-dataset-types/${encodeURIComponent(b20DatasetId)}/archive`);
        console.log(`  [ok] B20 DRAFT archived ${b20DatasetId}`);
      } catch (err) {
        console.warn(`  [warn] B20 archive cleanup failed: ${String(err).slice(0, 200)}`);
      }
    }

    // --- API patch to runnable seed target ---
    runtimeSourceId = await ensureRunnableViaApi(pipeline.pipeline_id);
    stepOk(11, `runnable graph patched (source=${runtimeSourceId}, target=${SEED_TARGET_TABLE})`);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1200);
    await page.getByTestId("visual-pipeline-studio-page").waitFor({ state: "visible", timeout: 60000 });

    // --- B16 Validate ---
    {
      await openDockTab(page, "validation");
      await page.waitForTimeout(800);
      if (await toolbar.getByText("● 저장되지 않음").count()) {
        await saveGraphAndWait(page);
      }
      if (await toolbar.getByText("● 저장되지 않음").count()) {
        fail(14, "B16 precondition: expected clean graph after dock settle + save");
      }
      const validation = page.getByTestId("visual-pipeline-validation-panel");
      await page.getByTestId("visual-pipeline-validate-button").click();
      await validation.getByTestId("visual-pipeline-validation-severity").waitFor({
        state: "visible",
        timeout: 30000,
      });
      if (await toolbar.getByText("● 저장되지 않음").count()) {
        fail(14, "B16: Graph 검증 직후 dirty가 재발하면 안 됩니다");
      }
      const compileBtn = page.getByTestId("visual-pipeline-compile-button");
      await compileBtn.waitFor({ state: "visible", timeout: 10000 });
      if (await compileBtn.isDisabled()) {
        const title = (await compileBtn.getAttribute("title")) || "";
        if (title.includes("저장되지 않은")) {
          fail(14, `B16: Compile must not be dirty-blocked after Graph 검증 (title=${title})`);
        }
      }
      const severity = (await validation.getByTestId("visual-pipeline-validation-severity").innerText()).trim();
      if (severity === "ERROR") fail(14, `Graph validation severity ERROR`);
      stepOk(14, `Graph validation passed severity=${severity}`);
    }

    // --- Compile Preview + Persist ---
    {
      await openDockTab(page, "compile");
      const panel = page.getByTestId("visual-pipeline-compile-panel");
      await page.getByTestId("visual-pipeline-compile-preview-button").click();
      await panel.getByTestId("visual-pipeline-compile-status").waitFor({ state: "visible", timeout: 30000 });
      const previewStatus = (await panel.getByTestId("visual-pipeline-compile-status").innerText()).trim();
      if (previewStatus !== "SUCCESS") fail(15, `Compile Preview expected SUCCESS, got ${previewStatus}`);
      const previewPersisted = (await panel.getByTestId("visual-pipeline-compile-persisted").innerText()).trim();
      if (previewPersisted !== "false") fail(15, `Compile Preview persisted expected false, got ${previewPersisted}`);

      if (await toolbar.getByText("● 저장되지 않음").count()) {
        await saveGraphAndWait(page);
      }

      await page.getByTestId("visual-pipeline-compile-button").click();
      await panel.getByTestId("visual-pipeline-compile-persisted").filter({ hasText: "true" }).waitFor({
        state: "visible",
        timeout: 30000,
      });
      const compileStatus = (await panel.getByTestId("visual-pipeline-compile-status").innerText()).trim();
      if (compileStatus !== "SUCCESS") fail(15, `Compile expected SUCCESS, got ${compileStatus}`);
      const resultId = (await panel.getByTestId("visual-pipeline-compile-result-id").innerText()).trim();
      if (!resultId.startsWith("VPC-")) fail(15, `expected compile_result_id VPC-*, got ${resultId}`);

      await openDockTab(page, "graph");
      const syncBadge = page.getByTestId("visual-pipeline-sync-status");
      await syncBadge.waitFor({ state: "visible", timeout: 15000 });
      const syncText = (await syncBadge.innerText()).trim();
      const syncCode = (await syncBadge.getAttribute("data-status")) || "";
      if (syncCode !== "IN_SYNC" && syncText !== "컴파일 최신") {
        fail(15, `expected sync IN_SYNC / 컴파일 최신, got status=${syncCode} text=${syncText}`);
      }
      stepOk(15, `Compile persisted result_id=${resultId} sync=${syncText}`);
    }

    // --- 실행 설정 반영 ---
    {
      const materializeBtn = page.getByTestId("visual-pipeline-materialize-button");
      await materializeBtn.waitFor({ state: "visible", timeout: 30000 });
      const btnText = (await materializeBtn.innerText()).trim();
      const forbiddenR10Label = "R10" + " 설정 반영";
      if (btnText.includes(forbiddenR10Label)) {
        fail(16, "must not expose legacy R10 materialize label; expected 실행 설정 반영");
      }
      if (!btnText.includes("실행 설정 반영") && !btnText.includes("반영 중")) {
        fail(16, `expected 「실행 설정 반영」 button text, got ${btnText}`);
      }
      if (await materializeBtn.isDisabled()) {
        fail(16, "expected materialize button enabled after persisted Compile");
      }
      await openDockTab(page, "materialization");
      const matPanel = page.getByTestId("visual-pipeline-materialization-panel");
      page.once("dialog", (dialog) => dialog.accept());
      await materializeBtn.click();
      await matPanel.getByTestId("visual-pipeline-materialization-status").waitFor({ state: "visible", timeout: 45000 });
      const matStatus = (await matPanel.getByTestId("visual-pipeline-materialization-status").innerText()).trim();
      if (matStatus !== "SUCCESS") fail(16, `실행 설정 반영 expected SUCCESS, got ${matStatus}`);
      const activation = (await matPanel.getByTestId("visual-pipeline-materialization-activation").innerText()).trim();
      if (activation !== "NOT_REQUESTED") fail(16, `expected activation=NOT_REQUESTED, got ${activation}`);
      stepOk(16, `실행 설정 반영 SUCCESS activation=${activation}`);
    }

    // --- 즉시 실행 ---
    {
      await openDockTab(page, "run");
      const runPanel = page.getByTestId("visual-pipeline-run-panel");
      const runBtn = page.getByTestId("visual-pipeline-run-now-button");
      await runBtn.scrollIntoViewIfNeeded();
      const runBtnText = (await runBtn.innerText()).trim();
      if (!runBtnText.includes("즉시 실행") && !runBtnText.includes("접수") && !runBtnText.includes("실행")) {
        fail(17, `expected 즉시 실행 button, got ${runBtnText}`);
      }
      if (await runBtn.isDisabled()) fail(17, "expected 즉시 실행 enabled after 실행 설정 반영");
      page.once("dialog", (dialog) => dialog.accept());
      await runBtn.click();
      await runPanel.getByTestId("visual-pipeline-run-status").waitFor({ state: "visible", timeout: 30000 });
      let runStatus = "";
      const deadline = Date.now() + 90000;
      while (Date.now() < deadline) {
        runStatus = (await runPanel.getByTestId("visual-pipeline-run-status").innerText()).trim();
        if (runStatus === "SUCCESS" || runStatus === "FAILED" || runStatus === "PARTIAL") break;
        await page.waitForTimeout(1000);
      }
      if (runStatus !== "SUCCESS") {
        const issuesText = await runPanel
          .getByTestId("visual-pipeline-run-issues")
          .innerText()
          .catch(() => "(no issues)");
        fail(17, `즉시 실행 expected SUCCESS, got ${runStatus}; issues=${issuesText.slice(0, 400)}`);
      }
      const visualRunId = (await runPanel.getByTestId("visual-pipeline-run-id").innerText()).trim();
      if (!visualRunId.startsWith("VPR-")) fail(17, `expected visual_run_id VPR-*, got ${visualRunId}`);
      const loadRunId = (await runPanel.getByTestId("visual-pipeline-run-load-run-id").innerText()).trim();
      if (!loadRunId.startsWith("ACLR-")) fail(17, `expected load_run_id ACLR-*, got ${loadRunId}`);
      stepOk(17, `Manual run created: ${visualRunId} load=${loadRunId}`);
    }

    // --- Run History / Detail ---
    {
      await openDockTab(page, "history");
      const historySection = page.getByTestId("visual-pipeline-run-history-section");
      await historySection.waitFor({ state: "visible", timeout: 15000 });
      await historySection.getByTestId("visual-pipeline-run-history-refresh").click();
      const historyRows = historySection.getByTestId("visual-pipeline-run-history-row");
      await historyRows.first().waitFor({ state: "visible", timeout: 15000 });
      stepOk(18, "Run history visible");
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
      await page.getByTestId("visual-pipeline-run-detail-cancel-section").waitFor({
        state: "visible",
        timeout: 10000,
      });
      // B6: SUCCESS run must not show failure summary error card
      if ((await page.getByTestId("visual-pipeline-run-detail-failure-summary").count()) > 0) {
        fail(19, "B6: SUCCESS run detail must not show failure-summary card");
      }
      // B8: SUCCESS run must not show PARTIAL impact card
      if ((await page.getByTestId("visual-pipeline-run-detail-partial-impact").count()) > 0) {
        fail(19, "B8: SUCCESS run detail must not show partial-impact card");
      }
      await page.getByTestId("visual-pipeline-run-detail-close").click();
      stepOk(19, "Run Detail progress/retry/cancel sections visible (no failure summary / no PARTIAL impact)");
    }

    // --- B18 Target Table Preview (seed table after SUCCESS run) ---
    {
      await selectNodeById(page, NODE_LOAD);
      const previewPanel = inspector.getByTestId("visual-pipeline-target-table-preview");
      await previewPanel.scrollIntoViewIfNeeded();
      await previewPanel.waitFor({ state: "visible", timeout: 10000 });
      const targetValue = await inspector.getByTestId("visual-pipeline-target-table-input").inputValue();
      if (targetValue !== SEED_TARGET_TABLE) {
        fail(20, `B18: expected target_table=${SEED_TARGET_TABLE}, got ${targetValue}`);
      }
      await inspector.getByTestId("visual-pipeline-target-table-preview-limit").selectOption("20");
      await inspector.getByTestId("visual-pipeline-target-table-preview-query-button").click();
      await page.waitForTimeout(1500);
      const hasSummary = (await inspector.getByTestId("visual-pipeline-target-table-preview-summary").count()) > 0;
      const hasEmpty = (await inspector.getByTestId("visual-pipeline-target-table-preview-empty").count()) > 0;
      const hasTable = (await inspector.getByTestId("visual-pipeline-target-table-preview-table").count()) > 0;
      const hasNotFound = (await inspector.getByTestId("visual-pipeline-target-table-preview-not-found").count()) > 0;
      const hasError = (await inspector.getByTestId("visual-pipeline-target-table-preview-error").count()) > 0;
      if (!(hasSummary || hasEmpty || hasTable)) {
        fail(
          20,
          `B18: expected success/empty after seed load (summary/empty/table); notFound=${hasNotFound} error=${hasError}`,
        );
      }
      const status = hasEmpty ? "empty" : hasTable || hasSummary ? "success" : "unknown";
      stepOk(20, `Target preview status: ${status} (table=${targetValue})`);
    }

    if (pageErrors.length) {
      const filtered = pageErrors.filter(
        (msg) => !/Cannot read properties of null \(reading 'document'\)/.test(msg),
      );
      if (filtered.length) fail("pageerror", filtered.join(" | "));
    }
  } finally {
    await browser.close();
    if (b20DatasetId) {
      try {
        await api("POST", `/standard-dataset-types/${encodeURIComponent(b20DatasetId)}/archive`, undefined, {
          soft: true,
        });
      } catch {
        /* already archived */
      }
    }
    await bestEffortDeleteDataSource(b19SourceId);
    await bestEffortDeleteDataSource(runtimeSourceId);
  }
}

async function main() {
  console.log("THERMOps R11-S8-9-15 / B12 Visual Pipeline E2E");
  console.log(`  frontend=${FRONTEND_BASE}`);
  console.log(`  api=${API_BASE}`);

  ensureMaterializeSeedData();

  let pipelineId = null;
  let archived = false;
  try {
    const created = await createFixture();
    pipelineId = created.pipeline_id;
    await runBrowserE2e(created);
    console.log("PASS B12 Visual Pipeline E2E");
  } catch (err) {
    console.error(`FAIL B12 E2E: ${err.message}`);
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
