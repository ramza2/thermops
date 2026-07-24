/**
 * R11-S7-12/S7-13/S7-14 Visual Pipeline Admin Ops UI smoke (+ Audit + mark-failed).
 *
 * Expects:
 *   frontend at CHECK_PAGES_BASE (default http://localhost:5173)
 *   backend ops API at THERMOOPS_API_BASE (default http://localhost:8000/api/v1)
 *   VITE_USER_ROLE=ADMIN on the running frontend (menu + page data)
 *
 * Optional:
 *   CHECK_VP_OPS_EXPECT_ADMIN=0  — assert admin-required notice instead of data panels
 */
import { chromium } from "playwright";

const BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const EXPECT_ADMIN = process.env.CHECK_VP_OPS_EXPECT_ADMIN !== "0";

function fail(msg) {
  console.error(`FAIL Visual Pipeline Ops: ${msg}`);
  process.exitCode = 1;
}

const browser = await chromium.launch();
const page = await browser.newPage();
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(e.message));

console.log("THERMOps R11-S7-14 Visual Pipeline Ops smoke");
console.log(`  frontend=${BASE}`);
console.log(`  expectAdmin=${EXPECT_ADMIN}`);

try {
  await page.goto(`${BASE}/visual-pipeline-ops`, { waitUntil: "load", timeout: 60000 });
  await page.getByTestId("visual-pipeline-ops-page").waitFor({ state: "visible", timeout: 30000 });
  await page.locator("main h1").filter({ hasText: "Visual Pipeline 운영 현황" }).first().waitFor({
    state: "visible",
    timeout: 30000,
  });
  console.log("  [ok] page title");

  if (!EXPECT_ADMIN) {
    await page.getByTestId("visual-pipeline-ops-admin-required").waitFor({
      state: "visible",
      timeout: 15000,
    });
    const refreshCount = await page.getByTestId("visual-pipeline-ops-refresh-button").count();
    if (refreshCount > 0) fail("non-admin should not show refresh button");
    const markCount = await page.getByTestId("visual-pipeline-ops-mark-failed-button").count();
    if (markCount > 0) fail("non-admin should not show mark-failed buttons");
    console.log("  [ok] admin-required notice (non-ADMIN mode)");
  } else {
    await page.getByTestId("visual-pipeline-ops-read-only-notice").waitFor({
      state: "visible",
      timeout: 15000,
    });
    console.log("  [ok] read-only notice");

    const refresh = page.getByTestId("visual-pipeline-ops-refresh-button");
    await refresh.waitFor({ state: "visible", timeout: 15000 });
    console.log("  [ok] refresh button");

    await page.getByTestId("visual-pipeline-ops-run-counts").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("visual-pipeline-ops-activation-counts").waitFor({ state: "visible" });
    await page.getByTestId("visual-pipeline-ops-stuck-summary").waitFor({ state: "visible" });
    await page.getByTestId("visual-pipeline-ops-worker-config").waitFor({ state: "visible" });
    await page.getByTestId("visual-pipeline-ops-activity-hints").waitFor({ state: "visible" });
    console.log("  [ok] summary cards + activity hints");

    const stuckTable = page.getByTestId("visual-pipeline-ops-stuck-runs-table");
    const stuckEmpty = page.getByText("현재 stuck run이 없습니다.");
    const stuckVisible =
      (await stuckTable.count()) > 0 || (await stuckEmpty.count()) > 0;
    if (!stuckVisible) fail("stuck runs table or empty message expected");
    console.log("  [ok] stuck runs section");

    const failTable = page.getByTestId("visual-pipeline-ops-recent-failures-table");
    const failEmpty = page.getByText("최근 실패 Run이 없습니다.");
    const failVisible =
      (await failTable.count()) > 0 || (await failEmpty.count()) > 0;
    if (!failVisible) fail("recent failures table or empty message expected");
    console.log("  [ok] recent failures section");

    // Non-stuck destructive actions must not exist
    const badActions = await page.getByRole("button", {
      name: /pause|resume|deactivate|cancel|retry|정리 적용/i,
    }).count();
    if (badActions > 0) fail("unexpected destructive action buttons present");
    console.log("  [ok] no pause/resume/deactivate/cancel/retry buttons");

    const markButtons = page.getByTestId("visual-pipeline-ops-mark-failed-button");
    const markCount = await markButtons.count();
    if (markCount > 0) {
      await markButtons.first().click();
      await page.getByTestId("visual-pipeline-ops-mark-failed-dialog").waitFor({
        state: "visible",
        timeout: 10000,
      });
      const confirmBtn = page.getByTestId("visual-pipeline-ops-mark-failed-confirm-button");
      if (await confirmBtn.isEnabled()) fail("confirm should be disabled before id/reason");
      await page.getByTestId("visual-pipeline-ops-mark-failed-confirm-input").fill("VPR-WRONG");
      await page.getByTestId("visual-pipeline-ops-mark-failed-reason-input").fill("smoke reason ok");
      if (await confirmBtn.isEnabled()) fail("confirm should stay disabled for wrong id");
      const targetText = await page
        .getByTestId("visual-pipeline-ops-mark-failed-dialog")
        .locator("p.font-mono")
        .innerText();
      const targetId = targetText.replace("target:", "").trim();
      await page.getByTestId("visual-pipeline-ops-mark-failed-confirm-input").fill(targetId);
      await page.waitForTimeout(200);
      if (!(await confirmBtn.isEnabled())) fail("confirm should enable with matching id + reason");
      await page.getByTestId("visual-pipeline-ops-mark-failed-cancel-button").click();
      await page.waitForTimeout(300);
      console.log("  [ok] mark-failed dialog confirm gating");
    } else {
      console.log("  [skip] no stuck rows — mark-failed dialog smoke skipped");
    }

    await page.getByTestId("visual-pipeline-ops-audit-section").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("visual-pipeline-ops-audit-event-filter").waitFor({ state: "visible" });
    await page.getByTestId("visual-pipeline-ops-audit-refresh-button").waitFor({ state: "visible" });
    const auditTable = page.getByTestId("visual-pipeline-ops-audit-table");
    const auditEmpty = page.getByText("표시할 audit log가 없습니다.");
    const auditLoading = page.getByText("Audit logs 로딩 중…");
    const auditVisible =
      (await auditTable.count()) > 0 ||
      (await auditEmpty.count()) > 0 ||
      (await auditLoading.count()) > 0;
    if (!auditVisible) fail("audit table, empty message, or loading expected");
    console.log("  [ok] audit logs section");

    await refresh.click();
    await page.waitForTimeout(800);
    await page.getByTestId("visual-pipeline-ops-run-counts").waitFor({ state: "visible", timeout: 30000 });
    console.log("  [ok] refresh reloads summary");

    const opsGroup = page.getByText("운영 모니터링", { exact: true });
    await opsGroup.click();
    await page.waitForTimeout(300);
    const menuLink = page.getByRole("link", { name: "Visual Pipeline 운영" });
    if ((await menuLink.count()) < 1) {
      fail("ADMIN menu should include Visual Pipeline 운영");
    } else {
      console.log("  [ok] sidebar menu visible for ADMIN");
    }
  }

  if (pageErrors.length) {
    fail(`pageerrors: ${pageErrors.slice(0, 3).join(" | ")}`);
  }

  if (!process.exitCode) {
    console.log("PASS Visual Pipeline Ops smoke");
  }
} catch (err) {
  fail(err instanceof Error ? err.message : String(err));
} finally {
  await browser.close();
}
