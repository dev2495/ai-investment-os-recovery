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
  const snapshotResponse = page.waitForResponse((response) => response.url().includes("/api/integration-gateway/snapshot") && response.ok());
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  const snapshot = await (await snapshotResponse).json();
  await expect(page.getByRole("heading", { level: 2, name: "Register Data Source" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Register Model Provider" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Plug-in Readiness Board" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Strategy Data Readiness" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Schema Mapping" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Bounded Ingestion Jobs" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Model Route Matrix" })).toBeVisible();
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(snapshot.plugins.length);
  await expect(page.locator(".gateway-route-grid article")).toHaveCount(21);
  await expect(page.locator(".gateway-market-grid article")).toHaveCount(7);
  await expect(page.locator(".gateway-import-ledger article")).toHaveCount(6);
  await expect(page.getByText("1,038,214 rows", { exact: true })).toBeVisible();
  await expect(page.getByText("research ready with bias audit required", { exact: true })).toBeVisible();
  await expect(page.getByText("corporate actions", { exact: true })).toBeVisible();
  await expect(page.getByText("needs verification", { exact: true })).toBeVisible();
  await expect(page.getByText("point in time universe", { exact: true })).toBeVisible();
  await expect(page.getByText("current snapshot only", { exact: true })).toBeVisible();
});

test("gateway readiness filters distinguish sources and models", async ({ page }) => {
  const snapshotResponse = page.waitForResponse((response) => response.url().includes("/api/integration-gateway/snapshot") && response.ok());
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  const snapshot = await (await snapshotResponse).json();
  const dataSourceCount = snapshot.plugins.filter((row: Record<string, unknown>) => row.plugin_kind === "data_source").length;
  const modelProviderCount = snapshot.plugins.filter((row: Record<string, unknown>) => row.plugin_kind === "model_provider").length;
  const gatedModelCount = snapshot.plugins.filter((row: Record<string, unknown>) => row.plugin_kind === "model_provider" && row.gateway_status === "needs_provider_readiness").length;
  await page.getByLabel("Filter plugin kind").selectOption("data_source");
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(dataSourceCount);
  await page.getByLabel("Filter plugin kind").selectOption("model_provider");
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(modelProviderCount);
  await page.getByLabel("Filter gateway status").selectOption("needs_provider_readiness");
  await expect(page.locator(".gateway-plugin-row")).toHaveCount(gatedModelCount);
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

test("governed model runtime exposes complete assignments, privacy, cache, and escalation controls", async ({ page }) => {
  const snapshotResponse = page.waitForResponse((response) => response.url().includes("/api/integration-gateway/snapshot") && response.ok());
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  const snapshot = await (await snapshotResponse).json();
  const assignmentCount = snapshot.model_agent_assignments.length;
  await expect(page.getByRole("heading", { level: 2, name: "Governed Model Runtime" })).toBeVisible();
  await expect(page.getByText(`${assignmentCount}/${assignmentCount}`, { exact: true })).toBeVisible();
  await expect(page.getByText("Autonomous cloud", { exact: true })).toBeVisible();
  await expect(page.getByText("must remain zero", { exact: true })).toBeVisible();
  await expect(page.getByText("Raw prompts are not stored", { exact: false })).toBeVisible();
  await expect(page.locator(".model-policy-list article")).toHaveCount(snapshot.model_privacy_policies.length);
  await expect(page.locator(".model-assignment-table article")).toHaveCount(assignmentCount);
  await expect(page.locator(".gateway-route-grid article")).toHaveCount(snapshot.model_routes.length);
  await expect(page.getByRole("heading", { level: 2, name: "Recent Model Decisions" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Escalation Queue" })).toBeVisible();
  await page.screenshot({ path: "/tmp/ai-os-model-runtime-desktop.png", fullPage: true });
});

test("Data and Model Gateway has no page-level mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=models", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { level: 2, name: "Data & Model Gateway" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Governed Model Runtime" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: "/tmp/ai-os-model-runtime-mobile.png", fullPage: true });
});
