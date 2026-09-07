import { expect, test } from "@playwright/test";

const generatedAt = new Date().toISOString();

function systemHealth() {
  return {
    generated_at: generatedAt,
    runtime_daemons: [], data_sources: [], data_source_checks: [], source_freshness: [],
    metrics: [], blueprint_summary: [], blueprint_domains: [], blueprint_sync_runs: [],
    source_freshness_scheduler_runs: [], model_routes: [], model_endpoints: [],
    provider_readiness_summary: [], provider_readiness_board: [], connector_health_checks: [],
    browser_session_checks: [], execution_control: [], report_scheduler_health: [], pipeline_readiness: [],
  };
}

function departmentTerminal() {
  return {
    generated_at: generatedAt, workspace: "models", execution_control: [], widgets: [], summary: [],
    primary: [{ route_name: "local_analysis", default_model: "qwen-local", default_provider: "local", runtime_status: "ready" }],
    secondary: [], tertiary: [], canaries: [],
  };
}

async function routeSharedSnapshots(page: import("@playwright/test").Page) {
  await page.route("**/api/system-health/snapshot", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(systemHealth()) }));
  await page.route("**/api/department-terminal/snapshot**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(departmentTerminal()) }));
}

test("Models & Routes keeps disabled proposals visible and review-gates qualified promotion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await routeSharedSnapshots(page);
  const posts: Array<{ path: string; body: Record<string, unknown> }> = [];
  let promoted = false;
  await page.route("**/api/v1/model-bindings**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      const current = promoted
        ? { binding_key: "company-analyst", version_id: 12, version: 3, enabled: true, selector_kind: "agent", selector_value: "company_analyst", task_class: "filing_analysis", primary_route: "local_analysis", reasoning_profile: "none", qualification_id: 55, qualification_state: "passed" }
        : { binding_key: "company-analyst", version_id: 7, version: 2, enabled: false, selector_kind: "agent", selector_value: "company_analyst", task_class: "filing_analysis", primary_route: "local_analysis", reasoning_profile: "none", qualification_id: 55, qualification_state: "passed" };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        available: true,
        bindings: [current],
        history: [
          { binding_key: "company-analyst", version_id: 12, version: 3, selector_kind: "agent", selector_value: "company_analyst", primary_route: "local_analysis", task_class: "filing_analysis", reasoning_profile: "none" },
          { binding_key: "risk-sentinel", version_id: 21, version: 1, selector_kind: "agent", selector_value: "risk_sentinel", primary_route: "unqualified_local", task_class: "risk_review", reasoning_profile: "none" },
          { binding_key: "company-analyst", version_id: 7, version: 2, selector_kind: "agent", selector_value: "company_analyst", primary_route: "local_analysis", task_class: "filing_analysis", reasoning_profile: "none" },
          { binding_key: "company-analyst", version_id: 3, version: 1, selector_kind: "agent", selector_value: "company_analyst", primary_route: "local_analysis", task_class: "filing_analysis", reasoning_profile: "none" },
        ],
        qualifications: [
          { id: 55, route_name: "local_analysis", task_class: "filing_analysis", model_name: "qwen-local", state: "passed" },
          { id: 56, route_name: "unqualified_local", task_class: "risk_review", model_name: "qwen-risk", state: "failed" },
        ],
        recent_calls: [{ id: 1, status: "failed", degraded: true }],
        audit: [
          { binding_key: "company-analyst", version_id: 12, action: promoted ? "promoted" : "proposed" },
          { binding_key: "risk-sentinel", version_id: 21, action: "proposed" },
          { binding_key: "company-analyst", version_id: 7, action: "disabled" },
          { binding_key: "company-analyst", version_id: 7, action: "promoted" },
          { binding_key: "company-analyst", version_id: 3, action: "promoted" },
        ],
        broker_write_allowed: false,
      }) });
      return;
    }
    posts.push({ path, body: request.postDataJSON() });
    if (path.endsWith("/promote")) promoted = true;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: path.endsWith("/promote") ? "promoted" : "completed", broker_write_allowed: false }) });
  });

  await page.goto("/firm/models");
  const console = page.getByRole("region", { name: "Governed model fabric" });
  await expect(console.getByText("Governed binding registry is available")).toBeVisible();

  const disabledHead = console.getByRole("article", { name: "company-analyst current head" });
  await expect(disabledHead.getByText("disabled", { exact: true })).toBeVisible();
  await expect(disabledHead.getByText(/Qualification passed/)).toBeVisible();
  await expect(disabledHead.getByRole("button", { name: "Review promote" })).toBeEnabled();

  const proposal = console.getByRole("article", { name: "company-analyst version 3" });
  await expect(proposal.getByText("Disabled proposal", { exact: true })).toBeVisible();
  await expect(proposal.getByText(/Qualification passed/)).toBeVisible();
  await expect(proposal.getByRole("button", { name: "Review promote" })).toBeEnabled();
  const unqualified = console.getByRole("article", { name: "risk-sentinel version 1" });
  await expect(unqualified.getByText(/Qualification failed/)).toBeVisible();
  await expect(unqualified.getByRole("button", { name: "Review promote" })).toBeDisabled();
  expect(posts).toEqual([]);

  await proposal.getByRole("button", { name: "Review promote" }).click();
  const drawer = page.getByRole("dialog", { name: "Review promote" });
  await drawer.getByLabel("Approved change receipt ID").fill("42");
  await drawer.getByLabel("Type PROMOTE to confirm").fill("PROMOTE");
  await drawer.getByRole("button", { name: "Submit reviewed action" }).click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toEqual({ path: "/api/v1/model-bindings/promote", body: { version_id: 12, approval_id: 42, confirmed: true } });
  await expect(console.getByText("Recorded outcome: promoted.")).toBeVisible();
  await expect(proposal.getByText("Current head", { exact: true })).toBeVisible();
});

test("System Health exposes Doctor evidence, one allowlisted fix, and five reviewed routine cards", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 1100 });
  await routeSharedSnapshots(page);
  const posts: Array<{ path: string; body: Record<string, unknown> }> = [];
  await page.route("**/api/v1/**doctor**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        available: true,
        latest_run: { status: "degraded", finished_at: generatedAt },
        registry: [{ check_key: "expired_task_leases", check_name: "Expired task leases", failure_severity: "high", safe_fix_key: "release_expired_leases" }],
        checks: [{ check_key: "expired_task_leases", status: "failed", headline: "Two expired leases remain active", observed_at: generatedAt, last_known_good_at: null, evidence: [{ source: "agent.task_leases" }] }],
        broker_write_allowed: false,
      }) });
      return;
    }
    posts.push({ path, body: request.postDataJSON() });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "applied", safe_fix_key: "release_expired_leases", broker_write_allowed: false }) });
  });
  await page.route("**/api/v1/routines**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      const keys = ["daily_system_health", "obsidian_incremental_index", "research_company_change_monitor", "stale_task_and_lease_reaper", "zerodha_session_and_stream_watch"];
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        available: true,
        routines: keys.map((routineKey, index) => ({ routine_key: routineKey, routine_name: routineKey.replace(/_/g, " "), owner_agent: "Jarvis", current_version: 1, trigger_kind: index === 2 ? "event" : "schedule", control_state: index === 0 ? "paused" : "enabled", cost_budget_usd: 0, stale_data_policy: "fail_closed" })),
        history: [{ routine_key: "daily_system_health", status: "completed", finished_at: generatedAt }], broker_write_allowed: false,
      }) });
      return;
    }
    posts.push({ path, body: request.postDataJSON() });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "enabled", control_state: "enabled", broker_write_allowed: false }) });
  });

  await page.goto("/firm/system");
  const console = page.getByRole("region", { name: "System operations controls" });
  await expect(console.getByText("Last recorded state: degraded")).toBeVisible();
  await expect(console.getByText("Two expired leases remain active")).toBeVisible();
  await expect(console.getByText("agent.task_leases")).toBeVisible();
  await expect(console.getByText("Not recorded")).toBeVisible();
  await expect(console.locator(".operator-console__routine")).toHaveCount(5);

  await console.getByRole("button", { name: "Review safe fix" }).click();
  let drawer = page.getByRole("dialog", { name: "Review allowlisted safe fix" });
  await drawer.getByLabel("Type RELEASE EXPIRED LEASES to confirm").fill("RELEASE EXPIRED LEASES");
  await drawer.getByRole("button", { name: "Apply safe fix" }).click();
  await expect.poll(() => posts.some((entry) => entry.path === "/api/v1/doctor/fixes")).toBe(true);

  const routine = console.getByRole("article", { name: "Daily system health routine" });
  await routine.getByRole("button", { name: "Review enable" }).click();
  drawer = page.getByRole("dialog", { name: "Review routine enable" });
  await drawer.getByLabel("Reason").fill("Reviewed after the Doctor evidence was checked.");
  await drawer.getByLabel("Type ENABLE to confirm").fill("ENABLE");
  await drawer.getByRole("button", { name: "Submit reviewed control" }).click();
  await expect.poll(() => posts.some((entry) => entry.path === "/api/v1/routines/daily_system_health/enable")).toBe(true);
});

test("unavailable control endpoints never turn legacy HTTP success into health", async ({ page }) => {
  await routeSharedSnapshots(page);
  await page.route("**/api/v1/model-bindings", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ available: false, reason: "not_live", bindings: [] }) }));
  await page.goto("/firm/models");
  const console = page.getByRole("region", { name: "Governed model fabric" });
  await expect(console.getByText("Model Fabric unavailable")).toBeVisible();
  await expect(console.getByRole("button", { name: "Propose binding" })).toBeDisabled();
  await expect(console.getByText("Current heads").locator("..")).toContainText("—");
});
