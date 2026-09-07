import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { routePhase2Base, routePhase2Controls } from "./phase2-ui-fixtures";

const screens = [
  { key: "office", path: "/firm/office", ready: ".office-fallback" },
  { key: "models", path: "/firm/models", heading: "Model Router & Cost Control" },
  { key: "system", path: "/firm/system", heading: "System Health" },
] as const;

const viewports = [
  { key: "desktop", width: 1440, height: 1000 },
  { key: "mobile", width: 390, height: 844 },
] as const;

async function expectNoSeriousOrCriticalViolations(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blockers = result.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => ({
      help: violation.help,
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => ({ target: node.target, summary: node.failureSummary })),
    }));
  expect(blockers, JSON.stringify(blockers, null, 2)).toEqual([]);
}

for (const viewport of viewports) {
  for (const screen of screens) {
    test(`${screen.key} ${viewport.key} reduced-motion has no serious or critical Axe violations`, async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        reducedMotion: "reduce",
      });
      await context.addInitScript(() => {
        window.localStorage.clear();
        window.sessionStorage.clear();
      });
      const page = await context.newPage();
      await routePhase2Base(page);
      await routePhase2Controls(page);
      await page.goto(screen.path);

      if ("ready" in screen) {
        await expect(page.locator(screen.ready)).toBeVisible();
        await expect(page.locator("canvas")).toHaveCount(0);
      } else {
        await expect(page.getByRole("heading", { level: 1, name: screen.heading })).toBeVisible();
      }
      await expect.poll(() => page.evaluate(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
      await expectNoSeriousOrCriticalViolations(page);
      await context.close();
    });
  }
}
