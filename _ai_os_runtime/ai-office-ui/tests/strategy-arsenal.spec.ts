import { expect, test } from "@playwright/test";

test("Strategy Arsenal loads from its scoped live endpoint with execution locked", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(request.url()); });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=command&workspace=arsenal", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { level: 2, name: "Strategy Arsenal" })).toBeVisible();
  await expect(page.getByText("LOCKED", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Lifecycle Control Board" })).toBeVisible();
  await expect(page.locator(".arsenal-candidate-row").first()).toBeVisible();
  expect(apiRequests.some((url) => url.includes("/api/strategy-arsenal/snapshot"))).toBe(true);
  expect(apiRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("Strategy Arsenal separates operator and system provenance", async ({ page }) => {
  await page.goto("/?mode=command&workspace=arsenal", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Filter by origin").selectOption("operator_submitted");
  await expect(page.locator(".arsenal-candidate-row").first()).toContainText("operator submitted");
  await page.getByLabel("Filter by origin").selectOption("system_discovery");
  await expect(page.locator(".arsenal-candidate-row").first()).toContainText("system discovery");
  await expect(page.locator(".arsenal-gates").first()).toHaveAttribute("aria-label", /\d of 8 gates passed/);
});

test("strategy evidence drawer resolves the linked lifecycle records", async ({ page }) => {
  await page.goto("/?mode=command&workspace=arsenal", { waitUntil: "domcontentloaded" });
  await page.locator(".arsenal-candidate-main").first().click();
  const drawer = page.getByRole("dialog", { name: /evidence chain/i });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Intake and hypothesis", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Backtest runs", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Optimization runs", { exact: true })).toBeVisible();
});

test("Strategy Arsenal intake and discovery controls are operationally complete", async ({ page }) => {
  await page.goto("/?mode=command&workspace=arsenal", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 2, name: "Add Strategy Idea" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save hypothesis" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Run full research test" })).toBeEnabled();
  await expect(page.getByRole("heading", { level: 2, name: "Operator Test Runs" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run discovery" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Validate gates" })).toBeEnabled();
  await expect(page.getByText("must remain zero", { exact: true })).toBeVisible();
});

test("Strategy Arsenal canonicalizes repeated discoveries and exposes governed gate actions", async ({ page, request }) => {
  const response = await request.get("http://127.0.0.1:8765/api/strategy-arsenal/snapshot");
  expect(response.ok()).toBe(true);
  const snapshot = await response.json();
  const fingerprints = snapshot.discovery_triage.map((row: Record<string, unknown>) => String(row.opportunity_fingerprint));
  expect(new Set(fingerprints).size).toBe(fingerprints.length);
  const suppressed = snapshot.discovery_governance.find((row: Record<string, unknown>) => row.metric === "suppressed_duplicates");
  expect(Number(suppressed?.value ?? 0)).toBeGreaterThan(0);
  expect(snapshot.control_board.every((row: Record<string, unknown>) => Number(row.canonical_rank ?? 1) === 1)).toBe(true);

  await page.goto("/?mode=command&workspace=arsenal", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 2, name: "Selected Strategy Gate Operator" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Backtest", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Optimize", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Validate", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open committee", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start paper", exact: true })).toBeVisible();
  await expect(page.getByText(/unique · \d+ suppressed/)).toBeVisible();
});

test("Strategy Arsenal has no page-level mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=command&workspace=arsenal", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 2, name: "Strategy Arsenal" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
