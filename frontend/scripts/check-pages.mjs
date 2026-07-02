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
    // 운영 seed가 비어 있을 때는 테이블 자체가 렌더링되지 않을 수 있으므로,
    // 컬럼 헤더(th)는 고정 값으로 검증하지 않고 빈 상태 문구만 확인한다.
    await page.getByText(/데이터가 없습니다/).first().waitFor({ state: "visible", timeout: 30000 });
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
  if (path === "/data/sources") {
    await page.getByText("신규 등록").first().waitFor({ state: "visible", timeout: 30000 });
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
  if (path === "/feature-sets") {
    await page.getByText("신규 Feature Set").first().waitFor({ state: "visible", timeout: 30000 });
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
    // seed가 비어 있을 때는 목록 테이블이 렌더링되지 않을 수 있어,
    // 컬럼 헤더(th)보다 빈 상태 문구만 확인한다.
    await page.getByText(/데이터가 없습니다/).first().waitFor({ state: "visible", timeout: 30000 });
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
