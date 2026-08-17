import { test, expect } from "@playwright/test";

test("Charlie review click never approves or starts a research case", async ({ page }) => {
  let approveRequests = 0;
  let startRequests = 0;
  let confirmationText = "";

  await page.route("**/api/research/cases/propose", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "proposed",
        detail: "Entity resolved; explicit Start is still required.",
        research_case: {
          id: 991,
          ticker: "INFY",
          exchange: "NSE",
          company_name: "Infosys Limited",
          horizon: "5-10 years",
        },
        model_preflight: {
          id: 881,
          status: "awaiting_approval",
          estimated_cost_usd: 0.12,
          hard_max_cost_usd: 0.15,
          exchange_rate_inr_per_usd: 87,
          source_count: 0,
        },
      }),
    });
  });
  await page.route("**/api/research/model-runs/preflight/approve", async (route) => {
    approveRequests += 1;
    await route.abort();
  });
  await page.route("**/api/research/cases/start", async (route) => {
    startRequests += 1;
    await route.abort();
  });
  page.on("dialog", async (dialog) => {
    confirmationText = dialog.message();
    await dialog.dismiss();
  });

  await page.goto(process.env.AI_OS_E2E_BASE_URL || "/");
  const rail = page.getByRole("complementary", { name: "Charlie assistant" });
  if (!(await rail.isVisible())) {
    await page.getByRole("button", { name: /Toggle Charlie assistant/ }).click();
  }
  const input = page.getByRole("textbox", { name: "Message Charlie…" });
  await input.fill("Start long-term research on Infosys");
  await input.press("Enter");

  const review = page.getByRole("button", { name: /Review cost & start Research Case #991/ });
  await expect(review).toBeVisible();
  await review.click();
  await expect.poll(() => confirmationText).toContain("Infosys Limited · Research Case #991");
  expect(confirmationText).toContain("Estimated: INR 10.44 / USD 0.120");
  expect(confirmationText).toContain("Hard stop: INR 13.05 / USD 0.150");
  expect(confirmationText).toContain("Private and client data remain on the external SSD");
  expect(approveRequests).toBe(0);
  expect(startRequests).toBe(0);
});
