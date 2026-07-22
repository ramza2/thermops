/**
 * R11-S4-3 Visual Pipeline Studio detail route browser smoke.
 *
 * Env:
 *   CHECK_PAGES_BASE     frontend base (default http://localhost:5173)
 *   THERMOOPS_API_BASE   API base including /api/v1 (default http://localhost:8000/api/v1)
 */
import { chromium } from "playwright";

const FRONTEND_BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const API_BASE = process.env.THERMOOPS_API_BASE || "http://localhost:8000/api/v1";

const PIPELINE_NAME_PREFIX = "E2E R11-S4-3 Visual Pipeline";
const PIPELINE_DESCRIPTION = "Created by R11-S4-3 Studio route E2E";

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
      data: { label: "Transform", component_type: "VP_TRANSFORM" },
    },
    {
      id: "e2e-load",
      type: "VP_UPSERT_LOAD",
      position: { x: 880, y: 220 },
      data: { label: "Upsert Load", component_type: "VP_UPSERT_LOAD" },
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
  // THERMOps API envelope: { success, data, ... }
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

async function runBrowserSmoke(pipeline) {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));

  try {
    const studioPath = `/visual-pipelines/${pipeline.pipeline_id}`;
    await page.goto(`${FRONTEND_BASE}${studioPath}`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1500);

    const studio = page.getByTestId("visual-pipeline-studio-page");
    try {
      await studio.waitFor({ state: "visible", timeout: 60000 });
    } catch (err) {
      const bodyText = (await page.locator("body").innerText().catch(() => "")).slice(0, 1200);
      const url = page.url();
      console.error(`  [debug] url=${url}`);
      console.error(`  [debug] body=\n${bodyText}`);
      if (pageErrors.length) console.error(`  [debug] pageErrors=${pageErrors.join(" | ")}`);
      throw err;
    }
    await page.getByTestId("visual-pipeline-name").filter({ hasText: PIPELINE_NAME_PREFIX }).waitFor({
      state: "visible",
      timeout: 30000,
    });
    console.log("  [ok] studio detail route loaded");

    const toolbar = page.getByTestId("visual-pipeline-toolbar");
    await toolbar.waitFor({ state: "visible", timeout: 15000 });
    for (const label of ["목록", "저장", "버전 저장", "Fit View", "Graph 검증"]) {
      await toolbar.getByRole("button", { name: label }).first().waitFor({ state: "visible", timeout: 15000 });
    }
    await toolbar.getByText("Compile").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] toolbar controls visible");

    const palette = page.getByTestId("visual-pipeline-palette");
    await palette.waitFor({ state: "visible", timeout: 30000 });
    for (const name of ["REST API Source", "Transform", "Upsert Load", "CRON Schedule"]) {
      await palette.getByText(name, { exact: true }).first().waitFor({ state: "visible", timeout: 15000 });
    }
    console.log("  [ok] palette ACTIVE components visible");

    const canvas = page.getByTestId("visual-pipeline-canvas");
    await canvas.waitFor({ state: "visible", timeout: 15000 });
    await canvas.locator(".react-flow").first().waitFor({ state: "visible", timeout: 15000 });
    for (const nodeId of ["e2e-cron", "e2e-rest", "e2e-transform", "e2e-load"]) {
      await page.getByTestId(`visual-pipeline-node-${nodeId}`).waitFor({ state: "visible", timeout: 20000 });
    }
    console.log("  [ok] canvas + 4 flow nodes visible");

    await page.getByTestId("visual-pipeline-inspector").getByText("노드를 선택하세요").waitFor({
      state: "visible",
      timeout: 10000,
    });
    console.log("  [ok] inspector empty state");

    const status = page.getByTestId("visual-pipeline-graph-status");
    await status.getByText("VISUAL_DATA_LOAD").first().waitFor({ state: "visible", timeout: 10000 });
    await status.getByText("nodes 4").first().waitFor({ state: "visible", timeout: 10000 });
    await status.getByText("edges 3").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] graph status panel counts");

    const validation = page.getByTestId("visual-pipeline-validation-panel");
    await validation.getByText("아직 Graph 검증을 실행하지 않았습니다.").waitFor({
      state: "visible",
      timeout: 10000,
    });
    console.log("  [ok] validation panel initial state");

    await toolbar.getByRole("button", { name: "Fit View" }).click();
    console.log("  [ok] Fit View clicked");

    await status.getByRole("button").filter({ hasText: "Graph Status Panel" }).click();
    await status.getByText("Graph JSON Preview").waitFor({ state: "visible", timeout: 10000 });
    await status.getByText("sourceHandle").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] graph JSON expanded (handle metadata visible)");

    await page.getByTestId("visual-pipeline-node-e2e-rest").click();
    await page.getByTestId("visual-pipeline-inspector").getByText("VP_REST_API_SOURCE").first().waitFor({
      state: "visible",
      timeout: 10000,
    });
    const inspector = page.getByTestId("visual-pipeline-inspector");
    await inspector.getByTestId("visual-pipeline-inspector-config-form").waitFor({
      state: "visible",
      timeout: 10000,
    });
    await inspector.getByTestId("visual-pipeline-inspector-config-field-operation_name").waitFor({
      state: "visible",
      timeout: 10000,
    });
    console.log("  [ok] REST config form visible (regression)");

    await page.getByTestId("visual-pipeline-node-e2e-transform").click();
    await inspector.getByText("VP_TRANSFORM").first().waitFor({ state: "visible", timeout: 10000 });
    await inspector.getByTestId("visual-pipeline-inspector-config-field-transform_type").waitFor({
      state: "visible",
      timeout: 10000,
    });
    console.log("  [ok] Transform config form visible (regression)");

    // Collapse Graph JSON + Fit View, then select CRON via pointer events
    // (leftmost node can be clipped; Playwright scrollIntoView hits parent flex).
    if (await status.getByText("Graph JSON Preview").isVisible().catch(() => false)) {
      await status.getByRole("button").filter({ hasText: "Graph Status Panel" }).click();
    }
    await toolbar.getByRole("button", { name: "Fit View" }).click();
    await page.waitForTimeout(400);
    await page.evaluate(() => {
      const node = document.querySelector('.react-flow__node[data-id="e2e-cron"]');
      if (!node) throw new Error("e2e-cron RF node missing");
      const r = node.getBoundingClientRect();
      const x = r.left + Math.min(40, r.width / 2);
      const y = r.top + Math.min(24, r.height / 2);
      const opts = { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1, pointerType: "mouse", buttons: 1 };
      node.dispatchEvent(new PointerEvent("pointerdown", opts));
      node.dispatchEvent(new MouseEvent("mousedown", opts));
      node.dispatchEvent(new PointerEvent("pointerup", { ...opts, buttons: 0 }));
      node.dispatchEvent(new MouseEvent("mouseup", { ...opts, buttons: 0 }));
      node.dispatchEvent(new MouseEvent("click", { ...opts, buttons: 0 }));
    });
    await inspector.getByText("VP_CRON_SCHEDULE").first().waitFor({ state: "visible", timeout: 10000 });
    await inspector.getByTestId("visual-pipeline-inspector-config-form").waitFor({
      state: "visible",
      timeout: 10000,
    });
    for (const fieldKey of [
      "schedule_type",
      "cron_expression",
      "timezone",
      "active_yn",
      "retry_enabled_yn",
      "max_retry_count",
      "retry_interval_minutes",
    ]) {
      await inspector.getByTestId(`visual-pipeline-inspector-config-field-${fieldKey}`).waitFor({
        state: "visible",
        timeout: 10000,
      });
    }
    console.log("  [ok] CRON config form fields visible");

    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-cron_expression")
      .locator("input")
      .fill("0 7 * * *");
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-timezone")
      .locator("select")
      .selectOption("Asia/Seoul");
    const activeCheckbox = inspector
      .getByTestId("visual-pipeline-inspector-config-field-active_yn")
      .locator("input[type='checkbox']");
    await activeCheckbox.uncheck();
    const retryCheckbox = inspector
      .getByTestId("visual-pipeline-inspector-config-field-retry_enabled_yn")
      .locator("input[type='checkbox']");
    await retryCheckbox.check();
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-max_retry_count")
      .locator("input")
      .fill("3");
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-retry_interval_minutes")
      .locator("input")
      .fill("10");
    await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] CRON config edit -> graph dirty");

    await page.getByTestId("visual-pipeline-node-e2e-load").click();
    await inspector.getByText("VP_UPSERT_LOAD").first().waitFor({ state: "visible", timeout: 10000 });
    await inspector.getByTestId("visual-pipeline-inspector-config-form").waitFor({
      state: "visible",
      timeout: 10000,
    });
    for (const fieldKey of ["target_table", "write_mode", "conflict_key_columns_json", "save_dedup_summary_yn"]) {
      await inspector.getByTestId(`visual-pipeline-inspector-config-field-${fieldKey}`).waitFor({
        state: "visible",
        timeout: 10000,
      });
    }
    console.log("  [ok] Upsert config form fields visible");

    await inspector.getByTestId("visual-pipeline-inspector-config-field-target_table").locator("input").fill("tb_e2e_fact");
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-write_mode")
      .locator("select")
      .selectOption("UPSERT");
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-conflict_key_columns_json")
      .locator("input")
      .fill("entity_id, measured_at");
    const dedupCheckbox = inspector
      .getByTestId("visual-pipeline-inspector-config-field-save_dedup_summary_yn")
      .locator("input[type='checkbox']");
    if (!(await dedupCheckbox.isChecked())) {
      await dedupCheckbox.check();
    }
    await toolbar.getByText("● 저장되지 않음").first().waitFor({ state: "visible", timeout: 10000 });
    console.log("  [ok] Upsert config edit -> graph dirty");

    await toolbar.getByRole("button", { name: "저장", exact: true }).click();
    await page.getByText("현재 Graph가 저장되었습니다.").first().waitFor({ state: "visible", timeout: 30000 });
    await toolbar.getByText("● 저장되지 않음").waitFor({ state: "hidden", timeout: 10000 });
    console.log("  [ok] graph save toast + dirty cleared");

    await page.getByTestId("visual-pipeline-validate-button").click();
    await validation.getByText(/OK|WARNING|ERROR|INFO/).first().waitFor({ state: "visible", timeout: 30000 });
    const severityBadge = validation.locator("span").filter({ hasText: /^(OK|WARNING|ERROR|INFO)$/ }).first();
    await severityBadge.waitFor({ state: "visible", timeout: 10000 });
    const severity = (await severityBadge.innerText()).trim();
    if (severity === "ERROR") {
      fail(`expected no ERROR for valid 4-node fixture, got ${severity}`);
    }
    await validation.getByText(/errors \d+/).first().waitFor({ state: "visible", timeout: 10000 });
    const errorsText = await validation.getByText(/errors \d+/).first().innerText();
    const errorCount = Number((errorsText.match(/errors\s+(\d+)/) || [])[1] ?? "1");
    if (errorCount > 0) {
      fail(`expected errors 0 for valid fixture, got ${errorsText}`);
    }
    console.log(`  [ok] Graph 검증 result severity=${severity}, ${errorsText}`);

    // R11-S5-5: clear REST operation_name → config WARNING + badge
    await page.getByTestId("visual-pipeline-node-e2e-rest").click();
    await inspector.getByTestId("visual-pipeline-inspector-config-field-operation_name").waitFor({
      state: "visible",
      timeout: 10000,
    });
    await inspector
      .getByTestId("visual-pipeline-inspector-config-field-operation_name")
      .locator("input")
      .fill("");
    await page.getByTestId("visual-pipeline-validate-button").click();
    await validation.getByText("NODE_CONFIG_REST_OPERATION_MISSING").first().waitFor({
      state: "visible",
      timeout: 30000,
    });
    await validation.getByText("CONFIG").first().waitFor({ state: "visible", timeout: 10000 });
    await validation.getByText(/field=operation_name/).first().waitFor({ state: "visible", timeout: 10000 });
    const badge = inspector.getByTestId("visual-pipeline-inspector-validation-badge");
    await badge.waitFor({ state: "visible", timeout: 10000 });
    const badgeText = (await badge.innerText()).trim();
    if (badgeText !== "WARNING" && badgeText !== "ERROR") {
      fail(`expected REST config badge WARNING/ERROR after clearing operation_name, got ${badgeText}`);
    }
    const fieldWarn = inspector
      .getByTestId("visual-pipeline-inspector-config-field-operation_name")
      .locator("p")
      .filter({ hasText: /operation_name/i });
    await fieldWarn.first().waitFor({ state: "visible", timeout: 10000 });
    console.log(`  [ok] S5-5 config issue + badge=${badgeText} + field warning`);

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
  console.log("THERMOps R11-S4-3 Visual Pipeline Studio E2E");
  console.log(`  frontend=${FRONTEND_BASE}`);
  console.log(`  api=${API_BASE}`);

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
