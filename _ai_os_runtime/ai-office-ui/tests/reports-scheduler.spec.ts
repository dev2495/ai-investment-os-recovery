import { expect, test } from "@playwright/test";

test("Reports exposes live schedules, runs, and task evidence without broad polling", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=reports", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { level: 2, name: "Report Schedule" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Recent Report Runs" })).toBeVisible();
  await expect(page.getByText("Daily Market Brief", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Monthly Client Report Drafts", { exact: true }).first()).toBeVisible();
  const schedulePanel = page.locator(".panel").filter({ has: page.getByRole("heading", { level: 2, name: "Report Schedule" }) });
  await expect(schedulePanel).toContainText("10 enabled");

  const recentRuns = page.locator(".panel").filter({ has: page.getByRole("heading", { level: 2, name: "Recent Report Runs" }) });
  const completedRun = recentRuns.locator(".evidence-open-row").first();
  await completedRun.focus();
  await completedRun.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("button", { name: "Close evidence drawer" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(completedRun).toBeFocused();

  expect(apiRequests.some((url) => url.includes("/api/reports/snapshot"))).toBe(true);
  expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("Reports schedule and run panels fit the mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=reports", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Report Schedule" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Recent Report Runs" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("System Health exposes the verified backup and isolated restore chain", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=system", { waitUntil: "networkidle" });
  const panel = page.locator(".panel").filter({ has: page.getByRole("heading", { level: 2, name: "Backup And Restore" }) });
  await expect(panel).toContainText("Critical state generations");
  await expect(panel).toContainText("Postgres custom archive");
  await expect(panel).toContainText("Qdrant full snapshot");
  await expect(panel).toContainText("Isolated restore drill");
  await expect(panel).toContainText(/passed/i);
  await expect(panel).toContainText("Unattended schedules");
  await expect(panel).toContainText(/configured/i);
  expect(apiRequests.some((url) => url.includes("/api/system-health/snapshot"))).toBe(true);
  expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("Recovery evidence remains readable without mobile horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=system", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Backup And Restore" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
