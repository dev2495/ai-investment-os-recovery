for (const includeHandoff of [false, true]) {
  test(`3D connections use durable handoffs only: ${includeHandoff}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.route("**/api/office/snapshot", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(officeSnapshot({ includeHandoff })) }));
    await page.goto("/firm/office");
    await expect(page.locator("[data-handoff-links]")).toHaveAttribute("data-handoff-links", includeHandoff ? "1" : "0");
  });
}

test("shared inspector submits bounded task controls and displays safe-boundary receipt", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const requests: { action: string; body: unknown }[] = [];
  await page.route("**/api/v1/tasks/81/*", async (route) => {
    requests.push({ action: route.request().url().split("/").pop()!, body: route.request().postDataJSON() });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ task_id: 81, waiting_for_safe_boundary: true }) });
  });
  await page.goto("/firm/office");
  await page.locator(".office-fallback__room-button", { hasText: "Runtime Operations" }).click();
  await page.locator(".office-fallback__agent", { hasText: "Asha Verma" }).click();
  const panel = page.getByRole("region", { name: "Asha Verma agent inspector" });
  for (const action of ["pause", "resume", "cancel", "redirect"]) {
    await panel.getByRole("button", { name: `${action[0].toUpperCase() + action.slice(1)} task`, exact: true }).click();
    if (action === "redirect") await panel.getByLabel("Updated objective").fill("Verify the latest filing using primary sources only");
    await panel.getByRole("button", { name: `Confirm ${action}`, exact: true }).click();
    await expect(panel.getByRole("button", { name: `Confirm ${action}`, exact: true })).toHaveCount(0);
  }
  expect(requests).toEqual([
    { action: "pause", body: {} }, { action: "resume", body: {} }, { action: "cancel", body: {} },
    { action: "redirect", body: { objective: "Verify the latest filing using primary sources only", source_policy: "primary_only" } },
  ]);
  await expect(page.getByText("The worker will apply this change at its next safe boundary.").first()).toBeVisible();
});

import { expect, test, type Locator } from "@playwright/test";
import { officeSnapshot, routePhase2Base } from "./phase2-ui-fixtures";

async function expectInspectorTruth(panel: Locator, lowPower: boolean) {
  await expect(panel).toHaveCount(1);
  await expect(panel).toBeFocused();
  await expect(panel).toHaveAttribute("data-low-power", String(lowPower));
  await expect(panel.getByText("Live worker lease")).toBeVisible();
  await expect(panel.getByText("Verify lease recovery").first()).toBeVisible();
  await expect(panel.getByText("REPLAY_EVENTS")).toBeVisible();
  await expect(panel.getByText("local_reasoning_v2")).toBeVisible();
  await expect(panel.getByText("qwen-local").first()).toBeVisible();
  await expect(panel.getByText("runtime_event_reader").first()).toBeVisible();
  await expect(panel.getByText("3", { exact: true }).first()).toBeVisible();
  await expect(panel.getByText("₹1.25")).toBeVisible();
  await expect(panel.getByText("Waiting for replay receipt")).toBeVisible();
  await expect(panel.getByText("Recovery ledger").first()).toBeVisible();
  await expect(panel.getByText("Worker health sweep").first()).toBeVisible();
  await expect(panel.getByText("62%")).toBeVisible();
  for (const action of ["Pause", "Resume", "Cancel", "Redirect"]) {
    await expect(panel.getByRole("button", { name: `${action} task`, exact: true })).toBeVisible();
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
  await routePhase2Base(page);
});

test("animated 3D Office renders real pixels and opens the shared truthful inspector", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/firm/office");

  const canvas = page.locator(".office-canvas-wrap canvas");
  await expect(canvas).toBeVisible();
  await page.getByLabel("Inspect employee in animated office").selectOption("Asha Verma");
  await expectInspectorTruth(page.getByRole("region", { name: "Asha Verma agent inspector" }), false);

  await page.waitForTimeout(500);
  const pixels = await canvas.evaluate((element: HTMLCanvasElement) => new Promise<{colored: number; opaque: number}>((resolve) => requestAnimationFrame(() => {
    const gl = element.getContext("webgl2") || element.getContext("webgl");
    if (!gl) { resolve({ colored: 0, opaque: 0 }); return; }
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
    resolve({ colored, opaque });
  })));
  expect(pixels.opaque).toBeGreaterThan(1000);
  expect(pixels.colored).toBeGreaterThan(1000);
  await page.screenshot({ path: "output/playwright/phase2-office-3d.png", fullPage: true });
});

test("reduced motion forces the 2D Office and preserves shared inspector truth", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/firm/office");

  await expect(page.locator(".office-fallback")).toBeVisible();
  await expect(page.locator(".office-canvas-wrap canvas")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Use animated office" })).toBeDisabled();
  await expect.poll(() => page.evaluate(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);

  const room = page.locator(".office-fallback__room-button", { hasText: "Runtime Operations" });
  await room.focus();
  await room.press("Enter");
  const employee = page.locator(".office-fallback__agent", { hasText: "Asha Verma" });
  await employee.focus();
  await employee.press("Enter");
  await expectInspectorTruth(page.getByRole("region", { name: "Asha Verma agent inspector" }), true);
});

test("Charlie opens by keyboard and returns a tracked durable-job entry without inventing live state", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  let chatPosts = 0;
  await page.route("**/api/chat", async (route) => {
    chatPosts += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        chat_turn: { id: 41 },
        message: "I queued the durable replay check.",
        assistant_identity: { agent_name: "Charlie Munger", display_title: "Chief of Staff · Orchestrator" },
        conversation_mode: "orchestrator",
        route: { route_name: "local_reasoning" },
        model_status: "completed",
        retrieval_status: "not_requested",
        retrieval_hits: [], widget_intents: [], dashboard_widgets: [], tool_intents: [],
        agent_jobs: [{ agent_key: "Asha", task_name: "Verify lease recovery" }],
        phase2_control: { action: "inspect", status: "recorded" },
      }),
    });
  });
  await page.goto("/firm/office");

  const toggle = page.getByRole("button", { name: "Toggle Charlie assistant (⌘J)" });
  const assistant = page.getByRole("complementary", { name: "Charlie assistant" });
  await expect(assistant).toBeVisible();
  await toggle.focus();
  await toggle.press("Enter");
  await expect(assistant).toHaveCount(0);
  await expect(toggle).toBeFocused();
  await toggle.press("Enter");
  await expect(assistant).toBeVisible();
  await expect(assistant.getByText(/not verified ·/)).toBeVisible();
  await expect(assistant.locator(".aios-assistant__avatar-status")).toHaveClass(/is-unverified/);

  await assistant.getByPlaceholder("Message Charlie…").fill("Ask Asha to verify the replay boundary");
  await assistant.getByPlaceholder("Message Charlie…").press("Enter");
  await expect(assistant.getByText("I queued the durable replay check.")).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Track Asha" })).toBeVisible();
  expect(chatPosts).toBe(1);
});

test("mobile reduced-motion Office stays keyboard-operable without horizontal overflow", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/firm/office");

  await expect(page.getByRole("complementary", { name: "Charlie assistant" })).toHaveCount(0);
  await expect(page.locator(".office-fallback")).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  const room = page.locator(".office-fallback__room-button", { hasText: "Runtime Operations" });
  await room.focus();
  await room.press("Enter");
  const employee = page.locator(".office-fallback__agent", { hasText: "Asha Verma" });
  await employee.focus();
  await employee.press("Enter");
  await expectInspectorTruth(page.getByRole("region", { name: "Asha Verma agent inspector" }), true);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: "output/playwright/phase2-office-mobile.png", fullPage: true });
});
