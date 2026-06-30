import { chromium } from "playwright";

const BASE = "http://127.0.0.1:5173";
const PATHS = [
  "/dashboard",
  "/data/sources",
  "/features",
  "/feature-sets",
  "/feature-sets/FS-TPL-LAG-ROLL",
  "/models/training-jobs",
  "/predictions/jobs",
  "/predictions/results",
  "/predictions/errors",
  "/ops/pipeline-runs",
  "/ops/model-monitoring",
  "/ops/drift-reports",
  "/ops/retraining-candidates",
  "/system/configs",
];

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`${page.url()}: ${e.message}`));

for (const path of PATHS) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(path === "/features" ? 4000 : 1500);
  const h1 = await page.locator("h1").first().innerText().catch(() => "");
  console.log(`OK ${path} -> ${h1.slice(0, 30)}`);
  if (path === "/features") {
    await page.getByText("신규 Feature 사용 절차").first().waitFor({ state: "visible", timeout: 60000 });
    await page.locator("th", { hasText: "등록 유형" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.locator("th", { hasText: "계산식 메모" }).first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/feature-sets/FS-TPL-LAG-ROLL") {
    await page.waitForTimeout(2000);
    const lineage = await page.getByText("Feature Lineage").count();
    const buildHistory = await page.getByText("최근 Feature Build 이력").count();
    const quality = await page.getByText("Feature 품질 검증").count();
    const regCol = await page.locator("th", { hasText: "등록 유형" }).count();
    const tplGuard = await page.getByText("공식 템플릿 Feature Set").count();
    if (!lineage || !buildHistory) {
      errors.push(`${path}: Feature Lineage / Build history section missing`);
    }
    if (!quality) {
      errors.push(`${path}: Feature Quality section missing`);
    }
    if (!regCol) {
      errors.push(`${path}: Feature list registration column missing`);
    }
    if (!tplGuard) {
      errors.push(`${path}: TPL protection notice missing`);
    }
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
