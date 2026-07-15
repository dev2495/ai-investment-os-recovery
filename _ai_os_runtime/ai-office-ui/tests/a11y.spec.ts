import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const workspaces = [
  ["command", "Command Center"],
  ["approvals", "Approval Board"],
  ["agents", "Agent Office"],
  ["departments", "Department Desks"],
  ["committees", "Committee Rooms"],
  ["governance", "Governance & Safety"],
  ["portfolio", "Portfolio Office"],
  ["clients", "Client Folios"],
  ["research", "Holdings Research"],
  ["ideas", "Idea Pipeline"],
  ["arsenal", "Strategy Arsenal"],
  ["trading", "Trading Desk"],
  ["quant", "Quant Lab"],
  ["risk", "Risk Center"],
  ["capital", "Capital Allocation"],
  ["treasury", "Treasury & Macro"],
  ["models", "Data & Model Gateway"],
  ["reports", "Reports"],
  ["system", "System Health"]
] as const;

const viewports = [
  ["desktop", { width: 1440, height: 1000 }],
  ["mobile", { width: 390, height: 844 }]
] as const;

async function expectNoSeriousViolations(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const violations = result.violations.map((violation) => ({
    help: violation.help,
    id: violation.id,
    impact: violation.impact,
    nodes: violation.nodes.map((node) => node.target)
  }));
  expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
}

for (const [viewportName, viewport] of viewports) {
  for (const [workspace, heading] of workspaces) {
    test(`${workspace} ${viewportName} passes WCAG A/AA automation`, async ({ browser }) => {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      await page.goto(`/?mode=command&workspace=${workspace}`, { waitUntil: "networkidle" });
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await expect(page.locator(".workspace-freshness")).toContainText(/Live snapshot fresh|Snapshot stale/);
      await expectNoSeriousViolations(page);
      await context.close();
    });
  }
}

test("approval evidence drawer traps and restores keyboard focus", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=command", { waitUntil: "networkidle" });
  const approvalPanel = page.locator(".panel").filter({ has: page.getByRole("heading", { level: 2, name: "Approval Queue" }) });
  const approvalRow = approvalPanel.locator(".evidence-open-row").first();
  await approvalRow.focus();
  await approvalRow.press("Enter");
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(page.getByRole("button", { name: "Close evidence drawer" })).toBeFocused();
  await expectNoSeriousViolations(page);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(approvalRow).toBeFocused();
});

for (const [viewportName, viewport] of viewports) {
  test(`Live Office static fallback ${viewportName} passes WCAG A/AA automation`, async ({ browser }) => {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    await page.goto("/?mode=office&workspace=command", { waitUntil: "networkidle" });
    await expect(page.locator(".live-office-shell")).toBeVisible();
    const rendererToggle = page.getByRole("button", { name: /Use static office|Use animated office/ });
    if (await rendererToggle.getAttribute("aria-label") === "Use static office") await rendererToggle.click();
    await expect(page.locator("canvas")).toHaveCount(0);
    await expectNoSeriousViolations(page);
    await context.close();
  });
}
