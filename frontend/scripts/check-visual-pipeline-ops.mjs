/**
 * R11-S7-12/S7-13 Visual Pipeline Admin Ops UI smoke (+ Audit Logs section).
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

console.log("THERMOps R11-S7-12 Visual Pipeline Ops smoke");
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

    const markFailedButtons = await page.getByRole("button", { name: /mark-failed|실패 처리|정리 적용/i }).count();
    if (markFailedButtons > 0) fail("mark-failed / destructive action buttons must not exist");
    console.log("  [ok] no mark-failed action buttons");

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

    // 운영 모니터링 그룹은 기본 접힘 — toggle 후 메뉴 확인
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
