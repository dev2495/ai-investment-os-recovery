import { expect, test } from "@playwright/test";

test("source-bound portfolio widgets render live preview rows", async ({ page }) => {
  await page.goto("/?mode=command&workspace=portfolio");
  const rail = page.getByRole("region", { name: "Portfolio Office live widgets" });
  await expect(rail).toBeVisible();
  await expect(rail.getByText("Latest Client Positions")).toBeVisible();
  await expect(rail.getByText(/5 live rows/).first()).toBeVisible();
  await expect(rail.locator(".workspace-widget-preview > div").first()).toBeVisible();
});

test("global shell controls route and collapse without losing workspace state", async ({ page }) => {
  await page.goto("/?mode=command&workspace=portfolio");
  await page.getByRole("button", { name: "Toggle sidebar" }).click();
  await expect(page.locator(".app-shell")).toHaveClass(/sidebar-is-collapsed/);
  await page.getByRole("button", { name: "Search memory" }).click();
  await expect(page).toHaveURL(/workspace=reports/);
  await page.getByRole("button", { name: "Open approval queue" }).click();
  await expect(page).toHaveURL(/workspace=approvals/);
});

test("workspace manager changes widget size and restores it", async ({ page }) => {
  await page.goto("/?mode=command&workspace=portfolio");
  await page.getByTitle("Customize workspace").click();
  const manager = page.getByRole("dialog", { name: "Workspace manager" });
  await expect(manager).toBeVisible();
  const widget = manager.locator(".workspace-widget-list article").filter({ hasText: "Latest Client Positions" });
  await widget.getByRole("button", { name: "wide" }).click();
  await expect(widget.getByRole("button", { name: "wide" })).toHaveClass(/active/);
  await widget.getByRole("button", { name: "standard" }).click();
  await expect(widget.getByRole("button", { name: "standard" })).toHaveClass(/active/);
  await manager.getByRole("button", { name: "Close workspace manager" }).click();
});

test("Charlie materializes a source-bound widget from the scoped command bar", async ({ page }) => {
  await page.goto("/?mode=command&workspace=portfolio");
  const input = page.getByRole("textbox", { name: "Command Charlie Munger" });
  await input.fill("Show my latest client portfolio positions as a dashboard widget");
  await page.getByRole("button", { name: "Assign" }).click();
  await expect(page.locator(".success-strip")).toContainText(/Charlie (materialized|checked|updated)/i, { timeout: 20_000 });
  await expect(page.getByText("Latest Client Positions")).toBeVisible();
});
