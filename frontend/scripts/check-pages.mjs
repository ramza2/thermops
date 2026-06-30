import { chromium } from "playwright";

const BASE = "http://localhost:5173";
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
  await page.waitForTimeout(1500);
  const h1 = await page.locator("h1").first().innerText().catch(() => "");
  console.log(`OK ${path} -> ${h1.slice(0, 30)}`);
  if (path === "/feature-sets/FS-TPL-LAG-ROLL") {
    const lineage = await page.getByText("Feature Lineage").count();
    const buildHistory = await page.getByText("최근 Feature Build 이력").count();
    if (!lineage || !buildHistory) {
      errors.push(`${path}: Feature Lineage / Build history section missing`);
    }
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
