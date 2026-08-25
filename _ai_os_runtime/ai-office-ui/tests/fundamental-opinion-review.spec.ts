import { expect, test } from "@playwright/test";

const liveBase = process.env.AI_OS_TEST_BASE_URL || "http://127.0.0.1:5177";

test("fundamental specialist opinions expose a governed review decision", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${liveBase}/fundamental/scorecards`, { waitUntil: "networkidle" });

  await expect(page.getByRole("main").getByText("Fundamental Research", { exact: true })).toBeVisible();
  await expect(page.getByText("Institutional Specialist Opinions", { exact: true })).toBeVisible();

  const thesisSelect = page.locator("select").filter({ has: page.locator("option", { hasText: "USHAMART" }) });
  const thesisValue = await thesisSelect.locator("option").filter({ hasText: "USHAMART" }).getAttribute("value");
  expect(thesisValue).toBeTruthy();
  await thesisSelect.selectOption(thesisValue!);
  const portfolioFit = page.getByRole("row").filter({ hasText: "portfolio fit" }).first();
  await expect(portfolioFit).toContainText("2 client");
  await portfolioFit.click();

  await expect(page.getByText("Review Specialist Opinion", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reject", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Preserve dissent", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark reviewed", exact: true })).toBeDisabled();
  await page.getByLabel("Operator review rationale").fill("The conclusion is supported, while the listed evidence gaps remain open.");
  await expect(page.getByRole("button", { name: "Mark reviewed", exact: true })).toBeEnabled();
});
