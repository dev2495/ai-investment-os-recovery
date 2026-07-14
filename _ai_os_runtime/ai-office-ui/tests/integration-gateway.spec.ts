import { expect, test } from "@playwright/test";

test("Data and Model Gateway uses its scoped live endpoint and preserves safety locks", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Data & Model Gateway" })).toBeVisible();
  await expect(page.getByText(/REFERENCES ONLY · LOCKED/)).toBeVisible();
  await expect(page.getByText("arbitrary allowed", { exact: true })).toBeVisible();
  expect(apiRequests.some((url) => url.includes("/api/integration-gateway/snapshot"))).toBe(true);
  expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("gateway exposes source, model, mapping, job, readiness, and route controls", async ({ page }) => {
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Register Data Source" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Register Model Provider" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Plug-in Readiness Board" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Schema Mapping" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Bounded Ingestion Jobs" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Model Route Matrix" })).toBeVisible();
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(39);
  await expect(page.locator(".gateway-route-grid article")).toHaveCount(21);
});

test("gateway readiness filters distinguish sources and models", async ({ page }) => {
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  await page.getByLabel("Filter plugin kind").selectOption("data_source");
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(18);
  await page.getByLabel("Filter plugin kind").selectOption("model_provider");
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(21);
  await page.getByLabel("Filter gateway status").selectOption("needs_provider_readiness");
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(5);
});

test("integration evidence resolves checks, mappings, jobs, and readiness", async ({ page }) => {
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  await page.getByLabel("Search integration plugins").fill("global news");
  await page.locator(".gateway-plugin-main").first().click();
  const drawer = page.getByRole("dialog", { name: /evidence chain/i });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Health and configuration checks", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Warehouse schema mappings", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Ingestion and provider jobs", { exact: true })).toBeVisible();
});

test("Data and Model Gateway has no page-level mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Data & Model Gateway" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
