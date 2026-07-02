import { chromium } from "playwright";

const BASE = "http://127.0.0.1:5173";
const PATHS = [
  "/dashboard",
  "/data/sources",
  "/standard-datasets",
  "/data/mappings",
  "/features",
  "/feature-recipes",
  "/feature-recipes/new",
  "/feature-sets",
  "/feature-sets/FS-TPL-LAG-ROLL",
  "/models/training-jobs",
  "/predictions/jobs",
  "/predictions/results",
  "/predictions/errors",
  "/ops/pipeline-runs",
  "/pipeline-builder",
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
    await page.getByText("Recipe Engine").first().waitFor({ state: "visible", timeout: 30000 });
    await page.locator("th", { hasText: "등록 유형" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.locator("th", { hasText: "계산식 메모" }).first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/feature-recipes") {
    await page.getByText("Feature Recipe").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("R6").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("최근 Build").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview/Build 비교").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/feature-recipes/new") {
    await page.getByText("Feature Recipe Builder").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("R6").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview/Build 비교").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/standard-datasets") {
    await page.getByText("표준 데이터셋").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("학습 데이터셋 유형 등록").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("물리 테이블을 자동 생성하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/data/mappings") {
    await page.getByText("대상 테이블은 표준 대상 테이블 목록에서 선택합니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Column Role").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("컬럼 역할").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("사용 가능한 Recipe 템플릿").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Recipe Builder는 후속 단계").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("row step 기반").first().waitFor({ state: "visible", timeout: 30000 });
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
    const recipeBuildDetail = await page.getByText("Recipe Engine Build 상세").count();
    const lagNullNote = await page.getByText("LAG/ROLLING Feature의 초기 null").count();
    if (!recipeBuildDetail || !lagNullNote) {
      errors.push(`${path}: Recipe Engine Build detail / LAG null notice missing`);
    }
  }
  if (path === "/pipeline-builder") {
    await page.getByText("Pipeline Builder").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("새 Pipeline 만들기").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Flow Chart").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("trigger할 수 있습니다").first().waitFor({ state: "visible", timeout: 30000 });
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
    await page.getByText("Pipeline Builder에서 실행 설정").first().waitFor({ state: "visible", timeout: 30000 });
    await page.locator("th", { hasText: "실행 출처" }).first().waitFor({ state: "visible", timeout: 30000 });
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
