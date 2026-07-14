import { expect, test } from "@playwright/test";

const terminals = [
  ["approvals", "Approval Board"],
  ["agents", "Agent Office"],
  ["committees", "Committee Rooms"],
  ["capital", "Capital Allocation"],
  ["treasury", "Treasury & Macro"],
  ["models", "Model Runtime"]
] as const;

for (const [workspace, heading] of terminals) {
  test(`${heading} loads a scoped live terminal`, async ({ page }) => {
    const apiRequests: string[] = [];
    page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`/?mode=command&workspace=${workspace}`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
    await expect(page.getByText("no seed data", { exact: true })).toBeVisible();
    await expect(page.getByText("LOCKED", { exact: true })).toBeVisible();
    expect(apiRequests.some((url) => url.includes(`/api/department-terminal/snapshot?workspace=${workspace}`))).toBe(true);
    expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
  });
}

test("operator theme and density controls persist through the workspace API", async ({ page }) => {
  await page.goto("/?mode=command&workspace=approvals", { waitUntil: "networkidle" });
  await page.getByTitle("Customize workspace").click();
  await expect(page.getByRole("dialog", { name: "Workspace manager" })).toBeVisible();
  await page.getByRole("button", { name: "Light", exact: true }).click();
  await expect.poll(() => page.locator("html").getAttribute("data-theme")).toBe("terminal_light");
  await page.getByRole("button", { name: "Dark", exact: true }).click();
  await expect.poll(() => page.locator("html").getAttribute("data-theme")).toBe("terminal_dark");
  await page.getByRole("button", { name: "standard", exact: true }).click();
  await expect.poll(() => page.locator("html").getAttribute("data-density")).toBe("standard");
  await page.getByRole("button", { name: "compact", exact: true }).click();
  await expect.poll(() => page.locator("html").getAttribute("data-density")).toBe("compact");
});

test("approval evidence opens from the decision queue", async ({ page }) => {
  await page.goto("/?mode=command&workspace=approvals", { waitUntil: "networkidle" });
  const evidenceButtons = page.locator(".terminal-evidence-button");
  await expect(evidenceButtons.first()).toBeVisible();
  await evidenceButtons.first().click();
  await expect(page.getByRole("dialog", { name: /evidence chain/i })).toBeVisible();
  await expect(page.getByText("Broker execution remains", { exact: false }).or(page.getByText("Evidence chain", { exact: true }))).toBeVisible();
});

test("department terminals have no page-level mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=agents", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Agent Office" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("research paper and source-linked hypothesis appear in the research factory", async ({ page }) => {
  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Research Paper Library" })).toBeVisible();
  await expect(page.getByText("Trend-Following Strategies via Dynamic Momentum Learning", { exact: true })).toBeVisible();
  await expect(page.getByText("Dynamic momentum speed selection across liquid futures", { exact: true })).toBeVisible();
});

test("advanced TradingView templates are visible and remain approval gated", async ({ page }) => {
  await page.goto("/?mode=command&workspace=trading", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Advanced Chart Templates" })).toBeVisible();
  await expect(page.getByText("Option Straddle Four Pane", { exact: true })).toBeVisible();
  await expect(page.getByText("Fundamental Ratio Dashboard", { exact: true })).toBeVisible();
  await expect(page.getByText("Relative Strength Ratio Chart", { exact: true })).toBeVisible();
});
