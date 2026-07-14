import { expect, test } from "@playwright/test";

test("Research exposes bounded live source intelligence evidence", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Source Intelligence" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Collector Runs" })).toBeVisible();
  await expect(page.getByText("Federal Reserve Press Releases", { exact: true })).toBeVisible();
  await expect(page.getByText("Reserve Bank of India Press Releases", { exact: true })).toBeVisible();
  await expect(page.getByText("European Central Bank Releases", { exact: true })).toBeVisible();
  expect(apiRequests.some((url) => url.includes("/api/research-ideas/snapshot"))).toBe(true);
  expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("Source loop sends filings and bounded material-first extraction settings", async ({ page }) => {
  let posted: Record<string, unknown> | null = null;
  await page.route("**/api/strategy/discovery/scheduler/run", async (route) => {
    posted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ status: "completed" })
    });
  });

  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Run source loop" }).click();
  await expect(page.locator(".success-strip")).toContainText("Source intelligence loop completed");
  expect(posted).toMatchObject({
    enable_filings: true,
    filing_lookback_days: 2,
    filing_limit: 250,
    enable_filing_extraction: true,
    filing_extraction_limit: 4,
    news_feed_limit: 12,
    route_top: 1
  });
});

test("Source Intelligence remains usable without mobile horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Source Intelligence" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
