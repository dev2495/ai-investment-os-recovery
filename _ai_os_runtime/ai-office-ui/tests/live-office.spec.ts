import { expect, test } from "@playwright/test";

test("Live Office exposes warehouse-backed operating walls and employee detail", async ({ page }) => {
  const officeRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) officeRequests.push(request.url());
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=office&workspace=command", { waitUntil: "networkidle" });

  await expect(page.locator(".live-office-shell")).toBeVisible();
  await expect(page.getByText("Global execution locked", { exact: true })).toBeVisible();
  await expect(page.getByText("Risk Wall", { exact: true })).toBeVisible();
  await expect(page.getByText("Data Alerts", { exact: true })).toBeVisible();
  await expect(page.getByText("Priority Tasks", { exact: true })).toBeVisible();

  const runtimeRoom = page.getByRole("button", { name: /Runtime Operations.*active/ });
  await runtimeRoom.click();
  await expect(runtimeRoom).toHaveAttribute("aria-pressed", "true");

  await page.getByLabel("Focus employee").selectOption({ label: "Jarvis" });
  await expect(page.getByRole("heading", { level: 1, name: "Runtime Operator" })).toBeVisible();
  await expect(page.getByText("Jarvis / Runtime Operator", { exact: true })).toBeVisible();
  await expect(page.locator(".office-agent-metrics")).toContainText("Open tasks");
  await expect(page.locator(".office-agent-metrics")).toContainText("Unread");

  expect(officeRequests.some((url) => url.includes("/api/office/snapshot"))).toBe(true);
  expect(officeRequests.some((url) => /\/api\/snapshot(?:\?|$)/.test(url))).toBe(false);
});

test("Live Office room workspace action opens the mapped command workspace", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=office&workspace=command", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Open Runtime Operations workspace" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "System Health" })).toBeVisible();
});

test("animated office renders a nonblank WebGL canvas", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/?mode=office&workspace=command", { waitUntil: "networkidle" });
  const rendererToggle = page.getByRole("button", { name: /Use static office|Use animated office/ });
  if (await rendererToggle.getAttribute("aria-label") === "Use animated office") await rendererToggle.click();

  const canvas = page.locator(".office-stage canvas");
  await expect(canvas).toBeVisible();
  await page.waitForTimeout(1200);
  const pixels = await canvas.evaluate((element: HTMLCanvasElement) => {
    const gl = element.getContext("webgl2") || element.getContext("webgl");
    if (!gl) return { colored: 0, opaque: 0, sampled: 0 };
    const width = gl.drawingBufferWidth;
    const height = gl.drawingBufferHeight;
    const buffer = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, buffer);
    let colored = 0;
    let opaque = 0;
    for (let index = 0; index < buffer.length; index += 16) {
      if (buffer[index + 3] > 0) opaque += 1;
      if (buffer[index] + buffer[index + 1] + buffer[index + 2] > 24) colored += 1;
    }
    return { colored, opaque, sampled: buffer.length / 16 };
  });
  expect(pixels.opaque).toBeGreaterThan(1000);
  expect(pixels.colored).toBeGreaterThan(1000);
});

test("mobile static office keeps room, employee, and operations controls accessible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=office&workspace=command", { waitUntil: "networkidle" });
  const rendererToggle = page.getByRole("button", { name: /Use static office|Use animated office/ });
  if (await rendererToggle.getAttribute("aria-label") === "Use static office") await rendererToggle.click();

  await expect(page.locator("canvas")).toHaveCount(0);
  await page.getByRole("button", { name: /Runtime Operations.*active/ }).first().click();
  await page.getByLabel("Focus employee").selectOption({ label: "Jarvis" });
  await expect(page.getByRole("heading", { level: 1, name: "Runtime Operator" })).toBeVisible();
  await expect(page.getByText("Global execution locked", { exact: true })).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
