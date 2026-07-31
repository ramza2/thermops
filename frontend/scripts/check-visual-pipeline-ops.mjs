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
 *
 * B26 / R11-S8-9-7:
 *   Do not click the first run-detail-button without checking run_status.
 *   soft-cancel button is expected only for RUNNING; terminal/PENDING must not expose it.
 *   fail() throws so subsequent [ok] logs cannot mix after a failure.
 */
import { chromium } from "playwright";

const BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const EXPECT_ADMIN = process.env.CHECK_VP_OPS_EXPECT_ADMIN !== "0";
const API_BASE = process.env.THERMOOPS_API_BASE || "http://localhost:8000/api/v1";

const TERMINAL_STATUSES = new Set(["SUCCESS", "FAILED", "PARTIAL", "CANCELLED"]);
const DETAIL_PANEL = "visual-pipeline-ops-run-detail-panel";
const CANCEL_BUTTON = "visual-pipeline-ops-run-detail-cancel-button";
const CANCEL_UNAVAILABLE = "visual-pipeline-ops-run-detail-cancel-unavailable";

function fail(msg) {
  const full = `FAIL Visual Pipeline Ops: ${msg}`;
  console.error(full);
  process.exitCode = 1;
  throw new Error(full);
}

/**
 * Stuck table columns: reason, visual_run_id, pipeline_id, mode, run_status, ...
 * @returns {Promise<Array<{ row: import('playwright').Locator, runId: string, status: string, detailButton: import('playwright').Locator }>>}
 */
async function listStuckRunRows(page) {
  const table = page.getByTestId("visual-pipeline-ops-stuck-runs-table");
  if ((await table.count()) === 0) return [];
  const rows = table.locator("tbody tr");
  const count = await rows.count();
  const items = [];
  for (let i = 0; i < count; i += 1) {
    const row = rows.nth(i);
    const cells = row.locator("td");
    const runId = ((await cells.nth(1).innerText()) || "").trim();
    const status = ((await cells.nth(4).innerText()) || "").trim().toUpperCase();
    const detailButton = row.getByTestId("visual-pipeline-ops-run-detail-button");
    items.push({ row, runId, status, detailButton });
  }
  return items;
}

async function openRunDetail(page, detailButton) {
  await detailButton.click();
  await page.getByTestId(DETAIL_PANEL).waitFor({ state: "visible", timeout: 15000 });
}

async function closeRunDetail(page) {
  const panel = page.getByTestId(DETAIL_PANEL);
  if ((await panel.count()) === 0) return;
  await page.getByTestId("visual-pipeline-ops-run-detail-close").click();
  await panel.waitFor({ state: "hidden", timeout: 10000 }).catch(() => {});
}

async function assertDetailCommonSections(page) {
  const panel = page.getByTestId(DETAIL_PANEL);
  await panel.getByTestId("visual-pipeline-ops-run-detail-retry-section").waitFor({
    state: "visible",
    timeout: 10000,
  });
  await panel.getByTestId("visual-pipeline-ops-run-detail-cancel-section").waitFor({
    state: "visible",
    timeout: 10000,
  });
  if ((await page.getByTestId("visual-pipeline-schedule-catchup-button").count()) > 0) {
    fail("ops must not show schedule catch-up enqueue button");
  }
  if (
    (await panel.getByRole("button", { name: /누락 실행 보정 Run 생성/i }).count()) > 0
  ) {
    fail("ops run detail must not show catch-up enqueue action");
  }
}

/** RUNNING: soft-cancel action button is expected (do not submit cancel). */
async function assertSoftCancelForRunning(page, meta) {
  const panel = page.getByTestId(DETAIL_PANEL);
  const cancelBtn = panel.getByTestId(CANCEL_BUTTON);
  const count = await cancelBtn.count();
  if (count < 1) {
    fail(
      `RUNNING run detail must show soft-cancel button (run_id=${meta.runId}, status=${meta.status})`,
    );
  }
  console.log(
    `  [ok] B26 RUNNING soft-cancel visible (run_id=${meta.runId}, status=${meta.status})`,
  );
}

/**
 * PENDING / terminal: soft-cancel action button must not appear.
 * Product policy: only RUNNING exposes cancel-button; others show cancel-unavailable.
 */
async function assertNoSoftCancelForNonRunning(page, meta) {
  const panel = page.getByTestId(DETAIL_PANEL);
  const cancelBtnCount = await panel.getByTestId(CANCEL_BUTTON).count();
  if (cancelBtnCount > 0) {
    fail(
      `non-RUNNING run detail must not show soft-cancel button (run_id=${meta.runId || "?"}, status=${meta.status})`,
    );
  }
  const unavailable = panel.getByTestId(CANCEL_UNAVAILABLE);
  if ((await unavailable.count()) < 1) {
    fail(
      `non-RUNNING run detail should show cancel-unavailable hint (run_id=${meta.runId || "?"}, status=${meta.status})`,
    );
  }
  console.log(
    `  [ok] B26 non-RUNNING soft-cancel absent (run_id=${meta.runId || "?"}, status=${meta.status})`,
  );
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

    // --- B10: action-required card (+ B5 badge/anchor) ---
    {
      const actionCard = page.getByTestId("visual-pipeline-ops-action-required");
      await actionCard.waitFor({ state: "visible", timeout: 15000 });
      const isEmpty = (await actionCard.getAttribute("data-empty")) === "true";
      if (isEmpty) {
        await page.getByTestId("visual-pipeline-ops-action-required-empty").waitFor({
          state: "visible",
          timeout: 5000,
        });
        console.log("  [ok] B10 action-required empty state");
      } else {
        await page.getByTestId("visual-pipeline-ops-action-required-groups").waitFor({
          state: "visible",
          timeout: 5000,
        });
        const total = Number((await actionCard.getAttribute("data-total")) || "0");
        if (!(total > 0)) fail("B10: non-empty action-required card must have data-total > 0");
        console.log(`  [ok] B10 action-required groups total=${total}`);
      }
      // No auto-action controls on the card
      const cardText = (await actionCard.innerText()).toLowerCase();
      if (cardText.includes("auto retry") || cardText.includes("auto-retry")) {
        fail("B10: action-required card must not expose auto retry");
      }
      // B5: hash anchor id + title badge show/hide
      const anchorId = await actionCard.getAttribute("id");
      if (anchorId !== "visual-pipeline-ops-action-required") {
        fail("B5: action-required card must have id=visual-pipeline-ops-action-required");
      }
      const titleBadge = page.getByTestId("visual-pipeline-ops-title-action-badge");
      const titleBadgeErr = page.getByTestId("visual-pipeline-ops-title-action-badge-error");
      const titleBadgeBtn = page.getByTestId("visual-pipeline-ops-title-action-badge-button");
      const badgeNodes =
        (await titleBadge.count()) + (await titleBadgeErr.count()) + (await titleBadgeBtn.count());
      console.log(`  [ok] B5 title badge show_or_hide nodes=${badgeNodes}`);
      if ((await titleBadgeBtn.count()) > 0) {
        await titleBadgeBtn.click();
        await page.waitForTimeout(300);
        console.log("  [ok] B5 title badge click toward action-required");
      }
      await page.getByTestId("visual-pipeline-ops-action-required-refresh").waitFor({
        state: "visible",
        timeout: 5000,
      });

      const failedGroup = page.getByTestId("visual-pipeline-ops-action-required-group-failed");
      const failedDetailBtn = failedGroup.getByTestId("visual-pipeline-ops-action-required-detail-button");
      if ((await failedGroup.count()) > 0 && (await failedDetailBtn.count()) > 0) {
        await failedDetailBtn.first().click();
        await page.getByTestId("visual-pipeline-ops-run-detail-panel").waitFor({
          state: "visible",
          timeout: 15000,
        });
        await assertDetailCommonSections(page);
        await page.getByTestId("visual-pipeline-ops-run-detail-failure-summary").waitFor({
          state: "visible",
          timeout: 10000,
        });
        const reason = (
          await page.getByTestId("visual-pipeline-ops-run-detail-failure-summary-reason").innerText()
        ).trim();
        if (!reason) fail("B10->B6: FAILED detail opened from action card must have summary reason");
        console.log("  [ok] B10 detail from failed group + B6 failure summary");
        await closeRunDetail(page);
      } else {
        const detailBtns = page.getByTestId("visual-pipeline-ops-action-required-detail-button");
        if ((await detailBtns.count()) > 0) {
          await detailBtns.first().click();
          await page.getByTestId("visual-pipeline-ops-run-detail-panel").waitFor({
            state: "visible",
            timeout: 15000,
          });
          await assertDetailCommonSections(page);
          console.log("  [ok] B10 detail from action card (count-only items skipped)");
          await closeRunDetail(page);
        } else {
          console.log("  [ok] B10 action-required has no detail buttons (count-only / empty items)");
        }
      }
    }

    // --- B9: Schedule Skip history ---
    {
      const skipPanel = page.getByTestId("visual-pipeline-ops-schedule-skip-history");
      await skipPanel.waitFor({ state: "visible", timeout: 15000 });
      // Wait until loading finishes (empty or table)
      await page
        .getByTestId("visual-pipeline-ops-schedule-skip-loading")
        .waitFor({ state: "hidden", timeout: 20000 })
        .catch(() => {});
      const isEmpty = (await skipPanel.getAttribute("data-empty")) === "true";
      if (isEmpty) {
        await page.getByTestId("visual-pipeline-ops-schedule-skip-empty").waitFor({
          state: "visible",
          timeout: 5000,
        });
        console.log("  [ok] B9 schedule-skip empty state");
      } else {
        await page.getByTestId("visual-pipeline-ops-schedule-skip-table").waitFor({
          state: "visible",
          timeout: 5000,
        });
        const row = page.getByTestId("visual-pipeline-ops-schedule-skip-row").first();
        await row.waitFor({ state: "visible", timeout: 5000 });
        const code = (
          await row.getByTestId("visual-pipeline-ops-schedule-skip-reason-code").innerText()
        ).trim();
        const desc = (
          await row.getByTestId("visual-pipeline-ops-schedule-skip-reason-desc").innerText()
        ).trim();
        if (!code) fail("B9: skip row must show reason code");
        if (!desc) fail("B9: skip row must show reason description");
        console.log(`  [ok] B9 schedule-skip item reason=${code}`);
      }
      const skipText = (await skipPanel.innerText()).toLowerCase();
      if (
        skipText.includes("자동 catch-up 실행") ||
        skipText.includes("자동 재시도 실행") ||
        skipText.includes("auto retry")
      ) {
        fail("B9: skip history must not expose auto actions");
      }
      await page.getByTestId("visual-pipeline-ops-schedule-skip-refresh").waitFor({
        state: "visible",
        timeout: 5000,
      });
      await page.getByTestId("visual-pipeline-ops-schedule-skip-refresh").click();
      await skipPanel.waitFor({ state: "visible", timeout: 15000 });
      await page
        .getByTestId("visual-pipeline-ops-schedule-skip-loading")
        .waitFor({ state: "hidden", timeout: 20000 })
        .catch(() => {});
      console.log("  [ok] B9 schedule-skip refresh keeps panel");
      await page.getByTestId("visual-pipeline-ops-schedule-skip-catchup-bridge").waitFor({
        state: "visible",
        timeout: 5000,
      });
      const bridge = (
        await page.getByTestId("visual-pipeline-ops-schedule-skip-catchup-bridge").innerText()
      ).trim();
      if (!bridge.includes("자동 복구가 아닙니다") && !bridge.includes("원인 확인용")) {
        fail("B4: Ops skip panel should include Catch-up bridge guidance");
      }
      console.log("  [ok] B4 Ops skip↔Catch-up bridge copy");
    }

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

    // --- B26: status-aware soft-cancel assertions (never click first detail blindly) ---
    const stuckRows = await listStuckRunRows(page);
    const runningStuck = stuckRows.find((r) => r.status === "RUNNING");
    const pendingStuck = stuckRows.find((r) => r.status === "PENDING");
    const terminalStuck = stuckRows.find((r) => TERMINAL_STATUSES.has(r.status));

    let openedDetail = false;

    // 1) RUNNING positive check
    if (runningStuck) {
      await openRunDetail(page, runningStuck.detailButton);
      openedDetail = true;
      await assertDetailCommonSections(page);
      // B6: RUNNING must not show failure summary card
      if ((await page.getByTestId("visual-pipeline-ops-run-detail-failure-summary").count()) > 0) {
        fail("B6: RUNNING run detail must not show failure-summary card");
      // B8: RUNNING must not show PARTIAL impact card
      if ((await page.getByTestId("visual-pipeline-ops-run-detail-partial-impact").count()) > 0) {
        fail("B8: RUNNING run detail must not show partial-impact card");
      }
      }
      await assertSoftCancelForRunning(page, runningStuck);
      await closeRunDetail(page);
      openedDetail = false;
    } else {
      console.log("  [skip] B26 no RUNNING stuck run for soft-cancel positive check");
    }

    // --- B6: FAILED recent-failure detail must show failure summary ---
    if ((await failTable.count()) > 0) {
      const failDetail = failTable.getByTestId("visual-pipeline-ops-run-detail-button").first();
      if ((await failDetail.count()) > 0) {
        await openRunDetail(page, failDetail);
        openedDetail = true;
        await assertDetailCommonSections(page);
        const summary = page.getByTestId("visual-pipeline-ops-run-detail-failure-summary");
        await summary.waitFor({ state: "visible", timeout: 10000 });
        const reason = (
          await page.getByTestId("visual-pipeline-ops-run-detail-failure-summary-reason").innerText()
        ).trim();
        if (!reason) fail("B6: failure summary reason must be non-empty for FAILED run");
        const title = (
          await page.getByTestId("visual-pipeline-ops-run-detail-failure-summary-title").innerText()
        ).trim();
        if (!title) fail("B6: failure summary title must be non-empty for FAILED run");
        // B8: FAILED must not show PARTIAL impact card
        if ((await page.getByTestId("visual-pipeline-ops-run-detail-partial-impact").count()) > 0) {
          fail("B8: FAILED run detail must not show partial-impact card");
        }
        console.log(`  [ok] B6 failure summary on FAILED detail (title=${title.slice(0, 80)})`);
        console.log("  [ok] B8 FAILED detail has no PARTIAL impact card");
        await closeRunDetail(page);
        openedDetail = false;
      } else {
        console.log("  [skip] B6 no recent-failure detail button");
      }
    } else {
      console.log("  [skip] B6 no recent failures table for failure-summary check");
    }

    // --- B8: PARTIAL impact card (conditional; stay on Ops page) ---
    {
      const stuckForPartial = await listStuckRunRows(page);
      const partialStuck = stuckForPartial.find((r) => r.status === "PARTIAL");
      if (partialStuck) {
        await openRunDetail(page, partialStuck.detailButton);
        const impact = page.getByTestId("visual-pipeline-ops-run-detail-partial-impact");
        await impact.waitFor({ state: "visible", timeout: 15000 });
        await page.getByTestId("visual-pipeline-ops-run-detail-partial-impact-duplicate-risk").waitFor({
          state: "visible",
          timeout: 5000,
        });
        await page.getByTestId("visual-pipeline-ops-run-detail-partial-impact-checklist").waitFor({
          state: "visible",
          timeout: 5000,
        });
        const impactText = await impact.innerText();
        if (impactText.includes("중복이 발생했습니다") || impactText.includes("자동으로 중복 제거")) {
          fail("B8: PARTIAL impact must not assert duplicate occurred / auto-dedup");
        }
        console.log(`  [ok] B8 PARTIAL impact card (run_id=${partialStuck.runId})`);
        await closeRunDetail(page);
      } else {
        let apiPartial = false;
        try {
          const pipesRes = await fetch(`${API_BASE}/visual-pipelines?limit=30`);
          const pipesJson = await pipesRes.json();
          const pipes = pipesJson?.data?.items || pipesJson?.items || [];
          for (const pipe of pipes.slice(0, 15)) {
            const pid = pipe.pipeline_id;
            if (!pid) continue;
            const runsRes = await fetch(
              `${API_BASE}/visual-pipelines/${encodeURIComponent(pid)}/runs?run_status=PARTIAL&limit=1`,
            );
            if (!runsRes.ok) continue;
            const runsJson = await runsRes.json();
            const runs = runsJson?.data?.items || runsJson?.items || [];
            if (runs.length > 0) {
              apiPartial = true;
              break;
            }
          }
        } catch {
          /* ignore */
        }
        if (apiPartial) {
          console.log(
            "  [skip] B8 PARTIAL exists via API but not in Ops stuck list (conditional pass; e2e checks SUCCESS hide)",
          );
        } else {
          console.log("  [skip] B8 no PARTIAL run available (conditional pass)");
        }
      }
    }

    // 2) non-RUNNING negative check: prefer recent failure (terminal), then PENDING, then other terminal stuck
    let nonRunningTarget = null;
    let nonRunningMeta = null;
    if ((await failTable.count()) > 0) {
      const failDetail = failTable.getByTestId("visual-pipeline-ops-run-detail-button").first();
      if ((await failDetail.count()) > 0) {
        const failRow = failTable.locator("tbody tr").first();
        const failRunId = ((await failRow.locator("td").nth(0).innerText()) || "").trim();
        nonRunningTarget = failDetail;
        nonRunningMeta = { runId: failRunId, status: "FAILED" };
      }
    }
    if (!nonRunningTarget && pendingStuck) {
      nonRunningTarget = pendingStuck.detailButton;
      nonRunningMeta = pendingStuck;
    }
    if (!nonRunningTarget && terminalStuck) {
      nonRunningTarget = terminalStuck.detailButton;
      nonRunningMeta = terminalStuck;
    }

    if (nonRunningTarget && nonRunningMeta) {
      await openRunDetail(page, nonRunningTarget);
      openedDetail = true;
      await assertDetailCommonSections(page);
      await assertNoSoftCancelForNonRunning(page, nonRunningMeta);
      await closeRunDetail(page);
      openedDetail = false;
      console.log("  [ok] ops run detail panel (retry + cancel section; no catch-up enqueue)");
    } else if (!runningStuck) {
      console.log(
        "  [skip] B26 no terminal/PENDING/FAILED run for soft-cancel negative check; no detail buttons exercised",
      );
    } else {
      console.log(
        "  [skip] B26 no terminal/PENDING/FAILED run for soft-cancel negative check (RUNNING-only environment)",
      );
    }

    if (openedDetail) {
      await closeRunDetail(page);
    }

    // Non-stuck destructive actions must not exist at page level (detail-panel retry is separate)
    const badActions = await page.getByRole("button", {
      name: /pause|resume|deactivate|cancel|정리 적용/i,
    }).count();
    if (badActions > 0) fail("unexpected destructive action buttons present");
    // After detail closed, no retry-button should remain on the page
    if ((await page.getByTestId("visual-pipeline-ops-run-detail-retry-button").count()) > 0) {
      fail("detail retry button should be closed");
    }
    console.log("  [ok] no pause/resume/deactivate/cancel/global-retry buttons");

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
    }
    console.log("  [ok] sidebar menu visible for ADMIN");
  }

  if (pageErrors.length) {
    fail(`pageerrors: ${pageErrors.slice(0, 3).join(" | ")}`);
  }

  console.log("PASS Visual Pipeline Ops smoke");
} catch (err) {
  process.exitCode = 1;
  const msg = err instanceof Error ? err.message : String(err);
  if (!String(msg).startsWith("FAIL Visual Pipeline Ops:")) {
    console.error(`FAIL Visual Pipeline Ops: ${msg}`);
  }
} finally {
  await browser.close();
}

process.exit(process.exitCode || 0);
