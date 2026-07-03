import { chromium } from "playwright";

const BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
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

async function waitHeading(name, timeout = 60000) {
  await page.getByRole("heading", { name }).first().waitFor({ state: "visible", timeout });
}

for (const path of PATHS) {
  await page.goto(`${BASE}${path}`, { waitUntil: "load", timeout: 60000 });
  await page.waitForTimeout(500);
  if (path === "/dashboard") {
    await waitHeading("대시보드");
  } else if (path === "/data/sources") {
    await waitHeading("데이터 소스 관리");
  } else if (path === "/standard-datasets") {
    await waitHeading("표준 데이터셋");
  } else if (path === "/data/mappings") {
    await waitHeading("데이터 매핑 설정");
  } else if (path === "/features") {
    await page.getByText("신규 Feature 사용 절차").first().waitFor({ state: "visible", timeout: 60000 });
  } else {
    await page.locator("h1").first().waitFor({ state: "visible", timeout: 60000 });
  }
  const h1 = await page.locator("h1").first().innerText().catch(() => "");
  console.log(`OK ${path} -> ${h1.slice(0, 30)}`);

  if (path === "/features") {
    await page.getByText("Recipe Engine").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/데이터가 없습니다|등록된 Feature/).first().waitFor({ state: "visible", timeout: 30000 });
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
    await page.getByText("표준 데이터셋 생성").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("등록된 표준 데이터셋이 없습니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("R9-S2-1").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "표준 데이터셋 생성" }).click();
    await page.getByText("표준 데이터셋 생성 Wizard").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "닫기" }).click();
  }
  if (path === "/data/sources") {
    await page.getByRole("button", { name: "신규 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("등록된 데이터 소스가 없습니다").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/data/mappings") {
    await page.getByText(/표준 데이터셋|대상 테이블을 먼저 생성/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/등록된 데이터 매핑이 없습니다|표준 데이터셋 물리 테이블/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Column Role").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("컬럼 역할").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("사용 가능한 Recipe 템플릿").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Recipe Builder는 후속 단계").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("row step 기반").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/feature-sets") {
    await page.getByText("신규 Feature Set").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/데이터가 없습니다|등록된 Feature Set/).first().waitFor({ state: "visible", timeout: 30000 });
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
    await page.getByText(/데이터가 없습니다/).first().waitFor({ state: "visible", timeout: 30000 });
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
