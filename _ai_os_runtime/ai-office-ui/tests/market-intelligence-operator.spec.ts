import { expect, test } from "@playwright/test";

test("Mission Control exposes ranked news, filings, results, and holidays", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=mission", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "What Matters Now" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Filing Intelligence" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Results & Event Calendar" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Market Holidays" })).toBeVisible();
  await expect(page.getByText("Ganesh Chaturthi", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("Research intelligence is usable on mobile without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=research", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "What Matters Now" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Filing Intelligence" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Results & Corporate Events" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
