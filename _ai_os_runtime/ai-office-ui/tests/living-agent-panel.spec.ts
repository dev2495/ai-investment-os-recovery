import { expect, test } from "@playwright/test";

function officeSnapshot() {
  const now = Date.now();
  const generatedAt = new Date(now).toISOString();
  const expiresAt = new Date(now + 90_000).toISOString();
  const agent = {
    agent_name: "Asha Verma",
    display_title: "Runtime Reliability Analyst",
    role_scope: "Own worker recovery evidence",
    department: "runtime",
    department_key: "runtime",
    department_name: "Runtime Operations",
    presence_state: "WORKING",
    has_live_lease: true,
    lease_expires_at: expiresAt,
    presence_started_at: new Date(now - 75_000).toISOString(),
    current_task_id: 81,
    current_task_title: "Verify lease recovery",
    current_step_key: "REPLAY_EVENTS",
    progress_percent: 62,
    resolved_model_route: "local_reasoning_v2",
    current_model: "qwen-local",
    current_tool: "runtime_event_reader",
    current_source_count: 3,
    current_task_cost_inr: 1.25,
    blocker_title: "Waiting for replay receipt",
    last_artifact_title: "Recovery ledger",
    next_routine_name: "Worker health sweep",
    open_task_count: 1,
    open_inbox_count: 2,
  };
  return {
    generated_at: generatedAt,
    runtime: { available: true, event_cursor: 17, tasks: [{ id: 81, status: "in_progress", progress_percent: 62 }] },
    projection_meta: { source_status: "fresh", latest_record_at: generatedAt, redacted_record_count: 0 },
    agents: [agent],
    live_office_agent_activity: [agent],
    live_office_rooms: [{ room_key: "runtime", room_name: "Runtime Operations", agent_count: 1, executing_agent_count: 1, queued_agent_count: 0, open_task_count: 1, open_inbox_count: 2, room_state: "working" }],
    office_operability_acceptance: [],
    priority_tasks: [{ id: 81, agent_name: "Asha Verma", title: "Verify lease recovery", status: "in_progress" }],
    agent_messages: [{ id: 901, from_agent: "Jarvis", to_agent: "Asha Verma", related_task_id: 81, subject: "Check replay boundary", created_at: generatedAt }],
    task_steps: [{ id: 301, task_id: 81, agent_name: "Asha Verma", step_key: "REPLAY_EVENTS", state: "running", started_at: generatedAt }],
    agent_handoffs: [{ id: 401, to_agent: "Asha Verma", child_task_id: 81, title: "Runtime recovery handoff", state: "accepted", created_at: generatedAt }],
    agent_sources: [{ id: 501, agent_name: "Asha Verma", task_id: 81, source_name: "Task event ledger", source_kind: "postgres" }],
    agent_artifacts: [{ id: 601, agent_name: "Asha Verma", task_id: 81, artifact_name: "Recovery ledger", status: "writing" }],
    agent_model_calls: [{ id: 701, agent_name: "Asha Verma", task_id: 81, model: "qwen-local", resolved_route: "local_reasoning_v2", status: "completed" }],
    agent_tool_calls: [{ id: 801, agent_name: "Asha Verma", task_id: 81, tool_name: "runtime_event_reader", status: "running" }],
    agent_approvals: [],
    agent_incidents: [],
    agent_routines: [{ id: 1001, agent_name: "Asha Verma", routine_name: "Worker health sweep", status: "scheduled" }],
    agent_scorecards: [],
    committee_room_items: [],
    issues: [],
    risk_events: [],
    source_freshness: [],
    execution_control: [],
    long_term_committee_queue: [],
    strategy_committee_queue: [],
    graph_runs: [],
    graph_node_runs: [],
    graph_attention: [],
  };
}

test("the same truthful agent inspector is available in 2D and low-power Office views", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.route("**/api/office/snapshot", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(officeSnapshot()) });
  });
  await page.goto("/firm/office");

  await page.getByRole("button", { name: "Inspect Asha Verma" }).click();
  let panel = page.getByRole("region", { name: "Asha Verma agent inspector" });
  await expect(panel).toHaveCount(1);
  await expect(panel.getByText("Live worker lease")).toBeVisible();
  await expect(panel.getByText("REPLAY_EVENTS")).toBeVisible();
  await expect(panel.getByText("local_reasoning_v2")).toBeVisible();
  await expect(panel.getByText("₹1.25")).toBeVisible();
  await expect(panel.getByText("Recovery ledger").first()).toBeVisible();
  await expect(panel.getByText("62%")).toBeVisible();
  await panel.getByRole("button", { name: "Close agent inspector" }).click();

  const staticOffice = page.locator(".office-fallback");
  await expect(staticOffice).toBeVisible();
  await staticOffice.locator(".office-fallback__room-button", { hasText: "Runtime Operations" }).click();
  await staticOffice.locator(".office-fallback__agent", { hasText: "Asha Verma" }).click();
  panel = staticOffice.getByRole("region", { name: "Asha Verma agent inspector" });
  await expect(panel).toHaveCount(1);
  await expect(panel.getByText("Live worker lease")).toBeVisible();
  await expect(panel.getByText("local_reasoning_v2")).toBeVisible();
  await expect(panel.getByText("₹1.25")).toBeVisible();
  await expect(panel).toHaveAttribute("data-low-power", "true");
});

test("agent inspector expires a stale lease locally and never invents missing fields", async ({ page }) => {
  const snapshot = officeSnapshot();
  snapshot.agents[0].lease_expires_at = new Date(Date.now() - 1_000).toISOString();
  snapshot.live_office_agent_activity[0].lease_expires_at = snapshot.agents[0].lease_expires_at;
  delete (snapshot.agents[0] as Record<string, unknown>).current_tool;
  delete (snapshot.live_office_agent_activity[0] as Record<string, unknown>).current_tool;
  snapshot.agent_tool_calls = [];
  await page.route("**/api/office/snapshot", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(snapshot) });
  });
  await page.goto("/firm/office");
  await page.getByRole("button", { name: "Inspect Asha Verma" }).click();
  const panel = page.getByRole("region", { name: "Asha Verma agent inspector" });
  await expect(panel.getByText("Worker lease expired")).toBeVisible();
  await expect(panel.locator(".living-agent-panel__fact", { hasText: "Current tool" })).toContainText("Not recorded");
});
