import { expect, test } from "@playwright/test";

test("Research exposes the live Long-Term Decision Lab without broad polling", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Long-Term Decision Lab" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Monte Carlo Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Valuation Modules" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Thesis Checklists" })).toBeVisible();
  await expect(page.getByText("USHAMART · USHAMART", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("[object Object]", { exact: true })).toHaveCount(0);
  expect(apiRequests.some((url) => url.includes("/api/research-ideas/snapshot"))).toBe(true);
  expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("Decision Lab blocks an unsourced explicit starting multiple before API submission", async ({ page }) => {
  const monteCarloPosts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/portfolio/long-term-thesis/monte-carlo")) {
      monteCarloPosts.push(request.url());
    }
  });

  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  const lab = page.locator(".panel").filter({ has: page.getByRole("heading", { level: 2, name: "Long-Term Decision Lab" }) });
  await lab.getByLabel("Holding thesis").selectOption({ label: "USHAMART · USHAMART" });
  await lab.getByRole("spinbutton", { name: "Starting multiple", exact: true }).fill("35");
  await lab.getByRole("button", { name: "Run decision simulation" }).click();
  await expect(page.locator(".error-strip")).toContainText("Starting multiple source is required");
  expect(monteCarloPosts).toEqual([]);
});

test("Long-Term Decision Lab remains usable without mobile horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Long-Term Decision Lab" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
