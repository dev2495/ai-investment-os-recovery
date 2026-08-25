import { expect, test } from "@playwright/test";

test("Options Desk activates only explicitly confirmed governed valuation candidates", async ({ page }) => {
  let savedPolicy: Record<string, unknown> | null = null;

  await page.route("**/api/trading-quant-risk/snapshot", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        generated_at: "2026-08-09T04:30:00Z",
        option_valuation_source_candidates: [],
      }),
    });
  });
  await page.route("**/api/options/valuation-sources/refresh", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        candidates: [
          {
            underlying: "NIFTY",
            rate_observation_id: 101,
            risk_free_rate: 0.053542,
            rate_observed_at: "2026-08-08T12:00:00Z",
            rate_valid_until: "2026-09-01T12:00:00Z",
            rate_instrument_identifier: "TEST-TBILL",
            rate_source_url: "https://rate.example.test/source",
            rate_content_hash: "test-rate-artifact",
            rate_quality_status: "passed",
            dividend_observation_id: 202,
            dividend_yield: 0.0122,
            dividend_observed_at: "2026-07-31T12:00:00Z",
            dividend_valid_until: "2026-09-01T12:00:00Z",
            dividend_source_url: "https://dividend.example.test/source",
            dividend_content_hash: "test-dividend-artifact",
            dividend_quality_status: "warning",
            source_artifact_ref: "raw-artifact:1,raw-artifact:2",
            candidate_valid_until: "2026-09-01T12:00:00Z",
          },
        ],
      }),
    });
  });
  await page.route("**/api/options/valuation-policy/upsert", async (route) => {
    savedPolicy = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "active" }) });
  });

  await page.goto("/options/desk", { waitUntil: "domcontentloaded" });

  const rateInput = page.getByRole("spinbutton", { name: "Risk-free rate" });
  const dividendInput = page.getByRole("spinbutton", { name: "Dividend yield" });
  const saveButton = page.getByRole("button", { name: "Validate policy" });
  await expect(rateInput).toHaveValue("");
  await expect(dividendInput).toHaveValue("");
  await expect(saveButton).toBeDisabled();

  await page.getByRole("button", { name: "Refresh official inputs" }).click();
  await expect(page.getByText("Observation #101")).toBeVisible();
  await expect(page.getByText("Observation #202")).toBeVisible();

  await page.getByRole("button", { name: "Use candidate" }).click();
  await expect(rateInput).toHaveValue("0.053542");
  await expect(dividendInput).toHaveValue("0.0122");
  await expect(saveButton).toBeDisabled();

  await page.getByText("I confirm these exact source observations.").click();
  await expect(saveButton).toBeEnabled();
  await saveButton.click();

  expect(savedPolicy).not.toBeNull();
  expect(savedPolicy?.rate_observation_id).toBe(101);
  expect(savedPolicy?.dividend_observation_id).toBe(202);
  expect(savedPolicy?.operator_confirmed).toBe(true);
  expect(savedPolicy?.provider).toBe("Zerodha");
  expect(savedPolicy?.risk_free_rate).toBe(0.053542);
  expect(savedPolicy?.dividend_yield).toBe(0.0122);
  expect(savedPolicy).not.toHaveProperty("candidate_observation_ids");
  expect(savedPolicy).not.toHaveProperty("rate_source");
  expect(savedPolicy).not.toHaveProperty("rate_source_timestamp");
  expect(savedPolicy).not.toHaveProperty("dividend_source");
  expect(savedPolicy).not.toHaveProperty("dividend_source_timestamp");
});
