import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const liveBaseUrl = (process.env.AI_OS_LIVE_BASE_URL || "").trim().replace(/\/+$/, "");
const liveQaDir = (process.env.AI_OS_LIVE_QA_DIR || "").trim();
const systemChrome = (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").trim();
const liveEnabled = Boolean(liveBaseUrl && liveQaDir);

test.skip(!liveEnabled, "Set AI_OS_LIVE_BASE_URL and AI_OS_LIVE_QA_DIR to run read-only live acceptance.");
test.skip(liveEnabled && !existsSync(systemChrome), `System Chrome is unavailable at ${systemChrome}.`);
test.use({
  browserName: "chromium",
  headless: true,
  launchOptions: { executablePath: systemChrome },
});

type Diagnostics = {
  consoleErrors: string[];
  pageErrors: string[];
  requestFailures: string[];
  unexpectedResponses: string[];
  writeRequests: string[];
};

function redact(value: string) {
  return value
    .replace(/\/(?:Volumes|Users|private|var|tmp|Applications)\/[^\s"']+/g, "[local path hidden]")
    .replace(/\b(?:authorization|api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,;"']+/gi, "[credential hidden]");
}

function captureDiagnostics(page: Page): Diagnostics {
  const diagnostics: Diagnostics = {
    consoleErrors: [],
    pageErrors: [],
    requestFailures: [],
    unexpectedResponses: [],
    writeRequests: [],
  };
  page.on("console", (message) => {
    if (message.type() === "error") diagnostics.consoleErrors.push(redact(message.text()));
  });
  page.on("pageerror", (error) => diagnostics.pageErrors.push(redact(error.message)));
  page.on("requestfailed", (request) => {
    diagnostics.requestFailures.push(`${request.method()} ${request.url()} · ${request.failure()?.errorText || "failed"}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) diagnostics.unexpectedResponses.push(`${response.status()} ${response.request().method()} ${response.url()}`);
  });
  page.on("request", (request) => {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) diagnostics.writeRequests.push(`${request.method()} ${request.url()}`);
  });
  return diagnostics;
}

async function assertGlobalResearchNavigation(page: Page, mobile: boolean) {
  if (mobile) {
    const workspace = page.getByRole("combobox", { name: "Open primary workspace" });
    await expect(workspace).toBeVisible();
    await expect(workspace.locator("option", { hasText: "Research" })).toHaveCount(1);
    return;
  }
  const sidebar = page.getByRole("complementary", { name: "Terminal functions" });
  await expect(sidebar).toBeVisible();
  await expect(sidebar.getByRole("link", { name: /Company Dashboard/ })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: /Research Desk/ })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: /Workstreams/ })).toBeVisible();
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const width = Math.max(document.documentElement.scrollWidth, document.body?.scrollWidth || 0);
    return width - document.documentElement.clientWidth;
  });
  expect(overflow, `page has ${overflow}px horizontal overflow`).toBeLessThanOrEqual(1);
}

function assertCleanDiagnostics(diagnostics: Diagnostics) {
  expect(diagnostics.writeRequests, "live acceptance must remain GET/HEAD/OPTIONS only").toEqual([]);
  expect(diagnostics.consoleErrors, "browser console errors").toEqual([]);
  expect(diagnostics.pageErrors, "uncaught page errors").toEqual([]);
  expect(diagnostics.requestFailures, "failed browser requests").toEqual([]);
  expect(diagnostics.unexpectedResponses, "unexpected HTTP 4xx/5xx responses").toEqual([]);
}

const routes = [
  {
    key: "research-desk",
    route: "/research/desk",
    assertContent: async (page: Page) => {
      await expect(page.getByRole("heading", { level: 1, name: "One desk from question to decision-ready company pack." })).toBeVisible();
      const researchNav = page.getByRole("navigation", { name: "Company Research" });
      await expect(researchNav).toBeVisible();
      await expect(researchNav.getByRole("link", { name: "Desk" })).toBeVisible();
      await expect(researchNav.getByRole("link", { name: "Workstreams" })).toBeVisible();
      await expect(page.getByRole("heading", { level: 2, name: "Research requiring attention" })).toBeVisible();
    },
  },
  {
    key: "wipro-case-12",
    route: "/research/cases?case_id=12",
    assertContent: async (page: Page) => {
      await expect(page.getByRole("heading", { level: 2, name: /Wipro/i })).toBeVisible();
      await expect(page.getByText(/NSE:WIPRO · Case #12/)).toBeVisible();
      await expect(page.getByRole("link", { name: "Open company dashboard" })).toBeVisible();
      await expect(page.locator('.rc-next__actions a[href*="/api/research/case-reports/"][href$="/view"]')).toBeVisible();
    },
  },
  {
    key: "wipro-dashboard",
    route: "/fundamental/theses?symbol=WIPRO",
    assertContent: async (page: Page) => {
      await expect(page.locator(".ltw-masthead h1")).toContainText(/Wipro/i);
      await expect(page.getByText("NSE:WIPRO", { exact: true })).toBeVisible();
      await expect(page.getByText(/Executive investment brief/i).first()).toBeVisible();
      await expect(page.getByRole("region", { name: "Valuation and expected return" })).toBeVisible();
      await expect(page.locator('a.ltw-case-report-link[href*="/view"]').first()).toBeVisible();
    },
  },
  {
    key: "sbcl-dashboard",
    route: "/fundamental/theses?symbol=SBCL",
    assertContent: async (page: Page) => {
      await expect(page.locator(".ltw-masthead h1")).toContainText(/Shivalik Bimetal/i);
      await expect(page.getByText("NSE:SBCL", { exact: true })).toBeVisible();
      await expect(page.getByText(/Executive investment brief/i).first()).toBeVisible();
      await expect(page.getByRole("region", { name: "Valuation and expected return" })).toBeVisible();
      await expect(page.locator('a.ltw-case-report-link[href*="/view"]').first()).toBeVisible();
    },
  },
] as const;

const viewports = [
  { key: "desktop", width: 1440, height: 1000, mobile: false },
  { key: "mobile-390", width: 390, height: 844, mobile: true },
] as const;

test.beforeAll(() => {
  if (liveEnabled) mkdirSync(liveQaDir, { recursive: true });
});

for (const viewport of viewports) {
  for (const route of routes) {
    test(`${viewport.key} · ${route.key} is live, company-specific and read-only`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const diagnostics = captureDiagnostics(page);
      const response = await page.goto(`${liveBaseUrl}${route.route}`, { waitUntil: "domcontentloaded" });
      expect(response?.ok(), `navigation failed: ${route.route}`).toBe(true);

      await assertGlobalResearchNavigation(page, viewport.mobile);
      await route.assertContent(page);
      await assertNoHorizontalOverflow(page);
      await page.waitForTimeout(750);
      await page.screenshot({
        path: path.join(liveQaDir, `${route.key}-${viewport.key}.png`),
        fullPage: false,
      });
      assertCleanDiagnostics(diagnostics);
    });
  }
}
