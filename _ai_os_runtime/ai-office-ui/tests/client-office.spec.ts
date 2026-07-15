import { expect, test } from "@playwright/test";

test("Client Folios exposes governed lifecycle and live reconciliation controls", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.goto("/?mode=command&workspace=clients", { waitUntil: "networkidle" });

  await expect(page.getByRole("heading", { level: 2, name: "Governed Client Onboarding" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Onboarding Approval Queue" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Suitability & Mandate Control" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Account Maintenance" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Holding Update Queue" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Multi-Source Reconciliation" })).toBeVisible();
  await expect(page.getByText("No onboarding cases. Existing clients were imported, not seeded through this queue.", { exact: true })).toBeVisible();
  await expect(page.getByText("broker writes disabled", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Stage onboarding" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Stage account change" })).toBeDisabled();
  expect(apiRequests.some((url) => url.includes("/api/portfolio-office/snapshot"))).toBe(true);
  await page.screenshot({ path: "/tmp/ai-os-client-office-control-plane.png", fullPage: true });
});

test("Client Folios has no page-level mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=clients", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Governed Client Onboarding" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: "/tmp/ai-os-client-office-control-plane-mobile.png", fullPage: true });
});
