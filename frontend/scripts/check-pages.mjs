import { chromium } from "playwright";

const BASE = process.env.CHECK_PAGES_BASE || "http://localhost:5173";
const PATHS = [
  "/dashboard",
  "/data/sources",
  "/prediction-entities",
  "/external-code-mappings",
  "/standard-datasets",
  "/data/mappings",
  "/features",
  "/feature-recipes",
  "/feature-recipes/new",
  "/feature-sets",
  "/dataset-versions",
  "/models/training-jobs",
  "/predictions/jobs",
  "/predictions/results",
  "/predictions/errors",
  "/ops/pipeline-runs",
  "/pipeline-builder",
  "/ops/model-monitoring",
  "/ops/drift-reports",
  "/ops/retraining-candidates",
  "/data-load-schedules",
  "/notifications",
  "/system/configs",
];

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`${page.url}: ${e.message}`));

async function waitMainHeading(name, timeout = 60000) {
  await page.locator("main h1").filter({ hasText: new RegExp(`^${name}$`) }).first().waitFor({ state: "visible", timeout });
}

async function hasEmptyOrTable(emptyPattern) {
  const hasEmpty = await page.getByText(emptyPattern).count();
  const hasRows = await page.locator("main table tbody tr").count();
  return hasEmpty > 0 || hasRows > 0;
}

for (const path of PATHS) {
  await page.goto(`${BASE}${path}`, { waitUntil: "load", timeout: 60000 });
  await page.waitForTimeout(500);
  if (path === "/dashboard") {
    await waitMainHeading("대시보드");
  } else if (path === "/data/sources") {
    await waitMainHeading("데이터 소스");
  } else if (path === "/prediction-entities") {
    await waitMainHeading("예측 대상");
  } else if (path === "/external-code-mappings") {
    await waitMainHeading("외부 코드 매핑");
  } else if (path === "/standard-datasets") {
    await waitMainHeading("표준 데이터셋");
  } else if (path === "/data/mappings") {
    await waitMainHeading("데이터 매핑");
  } else if (path === "/features") {
    await page.getByText("신규 학습 변수 사용 절차").first().waitFor({ state: "visible", timeout: 60000 });
    await waitMainHeading("학습 변수");
  } else if (path === "/feature-recipes") {
    await waitMainHeading("변수 생성 규칙");
  } else if (path === "/feature-recipes/new") {
    await waitMainHeading("변수 생성 규칙 작성");
  } else if (path === "/feature-sets") {
    await waitMainHeading("변수 구성");
  } else if (path === "/dataset-versions") {
    await waitMainHeading("학습 데이터 버전");
  } else if (path === "/models/training-jobs") {
    await waitMainHeading("모델 학습");
  } else if (path === "/predictions/jobs") {
    await waitMainHeading("예측 작업");
  } else if (path === "/predictions/results") {
    await waitMainHeading("예측 결과");
  } else if (path === "/pipeline-builder") {
    await waitMainHeading("작업 흐름 구성");
  } else if (path === "/ops/pipeline-runs") {
    await waitMainHeading("작업 실행 이력");
  } else if (path === "/ops/drift-reports") {
    await waitMainHeading("데이터 변화 리포트");
  } else if (path === "/system/configs") {
    await waitMainHeading("시스템 설정");
  } else if (path === "/data-load-schedules") {
    await waitMainHeading("데이터 적재 일정");
  } else if (path === "/notifications") {
    await waitMainHeading("알림 / 장애 통보");
  } else {
    await page.locator("main h1").first().waitFor({ state: "visible", timeout: 60000 });
  }
  const h1 = await page.locator("main h1").first().innerText().catch(() => "");
  console.log(`OK ${path} -> ${h1.slice(0, 40)}`);

  const forbiddenH1 = ["Feature Recipe", "Pipeline Builder", "Feature Set", "드리프트 리포트", "Dataset Version"];
  for (const term of forbiddenH1) {
    if (h1.includes(term)) errors.push(`${path}: h1 must not contain '${term}' (got: ${h1})`);
  }

  if (path === "/features") {
    await page.getByText(/등록된 학습 변수가 없습니다|table/).first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
  }
  if (path === "/feature-recipes") {
    await page.getByText("미리보기/생성 비교").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 변수 생성 규칙이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/feature-recipes/new") {
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("미리보기/생성 비교").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/standard-datasets") {
    await page.getByText("표준 데이터셋 생성").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 표준 데이터셋이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    if (await page.getByText(/등록된 표준 데이터셋이 없습니다/).count()) {
      await page.getByText("학습과 예측에 사용할 내부 데이터 구조를 먼저 정의").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByText("R9-S2-3").first().waitFor({ state: "visible", timeout: 30000 });
    await page.locator("select").filter({ has: page.locator('option', { hasText: "전체 업무 영역" }) }).first().waitFor({ state: "visible", timeout: 30000 });
    for (const fixed of ["열수요", "기상", "기준정보", "설비"]) {
      const count = await page.locator("option").filter({ hasText: fixed }).count();
      if (count > 0) errors.push(`/standard-datasets: fixed domain option '${fixed}' must not appear`);
    }
    await page.getByRole("button", { name: "표준 데이터셋 생성" }).click();
    await page.getByText("표준 데이터셋 생성 Wizard").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("데이터 분류").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("업무 영역").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("태그").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "닫기" }).click();
  }
  if (path === "/data/sources") {
    await page.getByRole("button", { name: "신규 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("REST API 연결").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Decoding 키 입력을 권장").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("API 작업").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "새 API 작업 만들기" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "새 API 작업 만들기" }).click();
    await page.getByText("REST API 작업 만들기").first().waitFor({ state: "visible", timeout: 30000 });
    for (const label of ["기본 정보", "인증 정보", "요청 파라미터", "페이징 방식", "응답 데이터 경로", "변환 설정", "적재 대상", "테스트 호출", "검토 및 저장"]) {
      await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
    }
    const wizard = page.locator("div").filter({ hasText: "REST API 작업 만들기" }).last();
    const sourceSelect = wizard.locator("select").first();
    const optionCount = await sourceSelect.locator("option").count();
    if (optionCount > 1) {
      await sourceSelect.selectOption({ index: 1 });
      await wizard.locator("label", { hasText: "API 작업명" }).locator("..").locator("input").fill("check-pages-transform");
      await wizard.locator("label", { hasText: "Endpoint Path" }).locator("..").locator("input").fill("/sample-external/asos-hourly");
      for (let i = 0; i < 5; i += 1) {
        await page.getByRole("button", { name: "다음" }).click();
      }
      await page.getByText("변환 설정").first().waitFor({ state: "visible", timeout: 30000 });
      const transformSelect = wizard.locator("select").filter({ has: wizard.locator('option[value="ASOS_HOURLY_TO_CANONICAL"]') }).first();
      await transformSelect.locator('option[value="ASOS_HOURLY_TO_CANONICAL"]').waitFor({ state: "attached", timeout: 30000 });
      await transformSelect.locator('option[value="CALENDAR_SPECIAL_DAY_TO_DATE"]').waitFor({ state: "attached", timeout: 30000 });
      await transformSelect.locator('option[value="CALENDAR_DATE_TO_HOUR"]').waitFor({ state: "attached", timeout: 30000 });
      await transformSelect.selectOption("ASOS_HOURLY_TO_CANONICAL");
      for (const label of ["station_code", "observed_at"]) {
        await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
      }
      await transformSelect.selectOption("CALENDAR_SPECIAL_DAY_TO_DATE");
      for (const label of ["locdate", "dateName", "FULL_CALENDAR_WITH_OVERLAY", "SPECIAL_DAYS_ONLY"]) {
        await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
      }
      await page.getByText(/ASOS 관측 기상은 과거 학습용/).first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByRole("button", { name: "다음" }).click();
      await page.getByText("적재 방식").first().waitFor({ state: "visible", timeout: 30000 });
      for (const label of ["신규 행 추가", "중복 제외", "있으면 갱신, 없으면 추가", "중복 판단 키", "중복 처리 정책", "null 값 처리"]) {
        await page.getByText(label).first().waitFor({ state: "visible", timeout: 30000 });
      }
    }
    await page.getByText("요청 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("테스트 호출").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("적재 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("적재 실행").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "닫기" }).click();
    if (!(await hasEmptyOrTable(/등록된 데이터 소스가 없습니다|등록된 REST API 작업이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    if (await page.getByText(/등록된 데이터 소스가 없습니다/).count()) {
      await page.getByText("표준 데이터셋을 먼저 정의한 뒤").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByRole("link", { name: "예측 대상" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/Calendar\/특일 API는/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/기상청 단기예보 API 작업은/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/단기예보 입력 생성기/).first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/prediction-entities") {
    await page.getByRole("button", { name: "예측 대상 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("단기예보 격자").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("ASOS 관측소").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/nx\/ny/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/R10-S4 ASOS 관측 기상 적재/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/forecast_ready|단기예보 입력은/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/별도로 매핑|기상 매핑/).first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 예측 대상이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
      await page.getByText("단기예보 준비").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("관측 기상 준비").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByRole("button", { name: "상세" }).first().click();
      await page.getByRole("button", { name: "nx/ny 계산" }).first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByRole("button", { name: "닫기" }).click();
    }
    if (await page.getByText(/등록된 예측 대상이 없습니다/).count()) {
      await page.getByText("열수요 지점, 설비, 지역").first().waitFor({ state: "visible", timeout: 30000 });
    }
  }
  if (path === "/external-code-mappings") {
    await page.getByRole("button", { name: "외부 코드 매핑 등록" }).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("매핑 목록").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("미매핑 코드").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("코드 변환 테스트").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("도움말").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/미매핑 코드는 자동으로 내부 기준정보를 만들지 않습니다/).first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 외부 코드 매핑이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    if (await page.getByText(/등록된 외부 코드 매핑이 없습니다/).count()) {
      await page.getByText("지점코드·관측소코드").first().waitFor({ state: "visible", timeout: 30000 });
    }
  }
  if (path === "/data/mappings") {
    await page.getByText(/표준 데이터셋|대상 테이블을 먼저 생성/).first().waitFor({ state: "visible", timeout: 30000 });
    if (await page.getByText(/등록된 데이터 매핑이 없습니다/).count()) {
      await page.getByText("표준 데이터셋과 데이터 소스를 만든 뒤").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByText("컬럼 역할").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("사용 가능한 생성 규칙 템플릿").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("변수 생성 규칙 작성 화면은 후속 단계").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Preview 결과는 저장하지 않습니다").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/feature-sets") {
    await page.getByText("신규 변수 구성").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 변수 구성이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/dataset-versions") {
    await page.getByText("일부 생성 버전은 자동 학습/예측 선택에서 제외됩니다").first().waitFor({ state: "visible", timeout: 30000 });
    const emptyVersions = await page.getByText(/생성된 학습 데이터 버전이 없습니다/).count();
    if (emptyVersions) {
      await page.getByText("역할·상태 코드 참고").first().waitFor({ state: "visible", timeout: 30000 });
    } else {
      await page.getByText("대표").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("후보").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("일부 생성").first().waitFor({ state: "visible", timeout: 30000 });
      await page.getByText("보관됨").first().waitFor({ state: "visible", timeout: 30000 });
    }
    if (!(await hasEmptyOrTable(/생성된 학습 데이터 버전이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/models/training-jobs") {
    await page.getByText(/대표·학습 가능 버전을 자동 선택/).first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/predictions/jobs") {
    await page.getByText(/예측 사용 가능·대표 버전을 자동 선택/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("단기예보 입력").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("예측 시점 단기예보 호출").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("예보 발표 시각").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("기상 입력 스냅샷").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("단기예보 입력 미리보기").first().waitFor({ state: "visible", timeout: 30000 });
  }
  if (path === "/pipeline-builder") {
    await page.getByText("새 작업 흐름").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 작업 흐름이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
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
    await page.getByText("작업 흐름 구성").first().waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/실행 이력이 없습니다|데이터가 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
  }
  if (path === "/data-load-schedules") {
    await page.getByText("일정 목록", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("실행 이력", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("실행 대상 일정", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Worker 상태", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("도움말", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    if (!(await hasEmptyOrTable(/등록된 데이터 적재 일정이 없습니다/))) {
      errors.push(`${path}: empty message or table rows expected`);
    }
    await page.getByText("Worker 상태", { exact: true }).click();
    await page.getByText("적재 일정 실행 Worker").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("Worker 상태 신호").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("중복 실행 방지 잠금").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("1회 실행").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(/등록된 적재 일정 실행 Worker가 없습니다|Worker명/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("도움말", { exact: true }).click();
    await page.getByText("재시도 정책").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("run-due").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("중복 실행 방지 잠금").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("실행 대상 일정", { exact: true }).click();
    await page.getByText("run-due").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("일정 목록", { exact: true }).click();
    await page.getByRole("button", { name: "일정 등록" }).click();
    await page.getByText("실행 파라미터 템플릿").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("재시도 정책").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("다음 실행 예정").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByRole("button", { name: "취소" }).click();
  }
  if (path === "/notifications") {
    for (const label of ["장애 현황", "알림 이벤트", "알림 규칙", "알림 채널", "수신 대상", "발송 이력", "도움말"]) {
      await page.getByRole("button", { name: label, exact: true }).waitFor({ state: "visible", timeout: 30000 });
    }
    await page.getByRole("button", { name: "도움말", exact: true }).click();
    await page.getByText("중복 알림 억제").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("장애 확인 처리").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("장애 해결 처리").first().waitFor({ state: "visible", timeout: 30000 });
    await page.getByText("장애 확인").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await page.getByText("장애 해결").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await page.getByText("적재 일정 실행 Worker").first().waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
    await page.getByText("외부 발송 정보는 암호화").first().waitFor({ state: "visible", timeout: 30000 });
    const hasIncidentContent = (await page.getByText(/등록된 장애가 없습니다/).count()) > 0
      || (await page.locator("main table tbody tr").count()) > 0
      || (await page.getByText("미해결 장애").count()) > 0;
    if (!hasIncidentContent) errors.push(`${path}: incidents tab content missing`);
  }
}

// Sidebar menu groups (dashboard page has sidebar)
await page.goto(`${BASE}/dashboard`, { waitUntil: "load", timeout: 60000 });
await page.getByText("운영 모니터링", { exact: true }).click();
for (const group of ["데이터 준비", "학습 변수 관리", "모델 학습·예측", "운영 모니터링", "시스템 관리"]) {
  const count = await page.getByText(group, { exact: true }).count();
  if (!count) errors.push(`sidebar: menu group '${group}' not found`);
}

const DATA_PREP_ORDER = ["표준 데이터셋", "데이터 소스", "예측 대상", "외부 코드 매핑", "데이터 매핑", "데이터 품질"];
const sidebarLinks = (await page.locator("aside nav a").allTextContents()).map((t) => t.trim());
const dataPrepIndices = DATA_PREP_ORDER.map((label) => sidebarLinks.indexOf(label));
for (const label of DATA_PREP_ORDER) {
  if (!sidebarLinks.includes(label)) errors.push(`sidebar: data prep item '${label}' not found`);
}
if (!sidebarLinks.includes("알림 / 장애 통보")) errors.push(`sidebar: operations item '알림 / 장애 통보' not found`);
for (let i = 1; i < dataPrepIndices.length; i++) {
  if (dataPrepIndices[i] >= 0 && dataPrepIndices[i - 1] >= 0 && dataPrepIndices[i] <= dataPrepIndices[i - 1]) {
    errors.push(`sidebar: data prep order must be ${DATA_PREP_ORDER.join(" → ")}`);
    break;
  }
}

if (errors.length) {
  console.error("ERRORS:", errors);
  process.exit(1);
}
await browser.close();
console.log("BROWSER CHECK PASSED");
