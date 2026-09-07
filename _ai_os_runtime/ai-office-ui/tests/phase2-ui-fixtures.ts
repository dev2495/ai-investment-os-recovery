import type { Page, Route } from "@playwright/test";

function now() {
  return Date.now();
}

export function officeSnapshot({ includeHandoff = true }: { includeHandoff?: boolean } = {}) {
  const timestamp = now();
  const generatedAt = new Date(timestamp).toISOString();
  const agent = {
    id: 1,
    agent_id: 1,
    agent_name: "Asha Verma",
    display_title: "Runtime Reliability Analyst",
    role_scope: "Own worker recovery evidence",
    department: "runtime",
    department_key: "runtime",
    department_name: "Runtime Operations",
    presence_state: "WORKING",
    has_live_lease: true,
    lease_expires_at: new Date(timestamp + 90_000).toISOString(),
    presence_started_at: new Date(timestamp - 75_000).toISOString(),
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
    runtime: { available: true, event_cursor: 17, tasks: [{ id: 81, title: "Verify lease recovery", status: "in_progress", progress_percent: 62 }] },
    projection_meta: { source_status: "fresh", latest_record_at: generatedAt, redacted_record_count: 0 },
    agents: [agent, { id: 2, agent_id: 2, agent_name: "Jarvis", department_key: "executive", department: "executive" }],
    live_office_agent_activity: [agent],
    live_office_rooms: [{ room_key: "runtime", room_name: "Runtime Operations", agent_count: 1, executing_agent_count: 1, queued_agent_count: 0, open_task_count: 1, open_inbox_count: 2, room_state: "working" }],
    office_operability_acceptance: [],
    priority_tasks: [{ id: 81, agent_name: "Asha Verma", title: "Verify lease recovery", status: "in_progress", progress_percent: 62 }],
    agent_messages: [{ id: 901, from_agent: "Jarvis", to_agent: "Asha Verma", related_task_id: 81, subject: "Check replay boundary", created_at: generatedAt }],
    task_steps: [{ id: 301, task_id: 81, agent_name: "Asha Verma", step_key: "REPLAY_EVENTS", state: "running", started_at: generatedAt }],
    agent_handoffs: includeHandoff ? [{ id: 401, from_agent_id: 2, to_agent_id: 1, child_task_id: 81, title: "Runtime recovery handoff", state: "accepted", created_at: generatedAt }] : [],
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

export function systemHealthSnapshot() {
  return {
    generated_at: new Date(now()).toISOString(),
    runtime_daemons: [], data_sources: [], data_source_checks: [], source_freshness: [],
    metrics: [], blueprint_summary: [], blueprint_domains: [], blueprint_sync_runs: [],
    source_freshness_scheduler_runs: [], model_routes: [], model_endpoints: [],
    provider_readiness_summary: [], provider_readiness_board: [], connector_health_checks: [],
    browser_session_checks: [], execution_control: [], report_scheduler_health: [], pipeline_readiness: [],
  };
}

export function departmentTerminalSnapshot(workspace = "models") {
  return {
    generated_at: new Date(now()).toISOString(),
    workspace, execution_control: [], widgets: [], summary: [],
    primary: workspace === "models"
      ? [{ route_name: "local_analysis", default_model: "qwen-local", default_provider: "local", runtime_status: "ready" }, { route_name: "unqualified_local", default_model: "qwen-risk", default_provider: "local", runtime_status: "ready" }]
      : [],
    secondary: [], tertiary: [], canaries: [],
  };
}

export function modelFabricSnapshot() {
  const generatedAt = new Date(now()).toISOString();
  return {
    available: true,
    bindings: [{
      binding_key: "company-analyst", version_id: 7, version: 2, enabled: false,
      selector_kind: "agent", selector_value: "company_analyst", task_class: "filing_analysis",
      primary_route: "local_analysis", reasoning_profile: "none", qualification_id: 55, qualification_state: "passed",
    }],
    history: [
      { binding_key: "company-analyst", version_id: 12, version: 3, selector_kind: "agent", selector_value: "company_analyst", task_class: "filing_analysis", primary_route: "local_analysis", reasoning_profile: "none", created_at: generatedAt },
      { binding_key: "risk-sentinel", version_id: 21, version: 1, selector_kind: "agent", selector_value: "risk_sentinel", task_class: "risk_review", primary_route: "unqualified_local", reasoning_profile: "none", created_at: generatedAt },
      { binding_key: "company-analyst", version_id: 7, version: 2, selector_kind: "agent", selector_value: "company_analyst", task_class: "filing_analysis", primary_route: "local_analysis", reasoning_profile: "none", created_at: generatedAt },
      { binding_key: "company-analyst", version_id: 3, version: 1, selector_kind: "agent", selector_value: "company_analyst", task_class: "filing_analysis", primary_route: "local_analysis", reasoning_profile: "none", created_at: generatedAt },
    ],
    qualifications: [
      { id: 55, route_name: "local_analysis", task_class: "filing_analysis", model_name: "qwen-local", state: "passed", reasoning_profiles: ["none"] },
      { id: 56, route_name: "unqualified_local", task_class: "risk_review", model_name: "qwen-risk", state: "failed", reasoning_profiles: ["none"] },
    ],
    recent_calls: [{ id: 1, status: "failed", degraded: true }],
    audit: [
      { binding_key: "company-analyst", version_id: 12, action: "proposed", actor: "operator", created_at: generatedAt },
      { binding_key: "risk-sentinel", version_id: 21, action: "proposed", actor: "operator", created_at: generatedAt },
      { binding_key: "company-analyst", version_id: 7, action: "disabled", actor: "operator", created_at: generatedAt },
      { binding_key: "company-analyst", version_id: 7, action: "promoted", actor: "operator", created_at: generatedAt },
      { binding_key: "company-analyst", version_id: 3, action: "promoted", actor: "operator", created_at: generatedAt },
    ],
    provider_calls_made: false, broker_write_allowed: false,
  };
}

export function doctorSnapshot() {
  const generatedAt = new Date(now()).toISOString();
  return {
    available: true,
    latest_run: { status: "degraded", finished_at: generatedAt },
    registry: [{ check_key: "expired_task_leases", check_name: "Expired task leases", failure_severity: "high", safe_fix_key: "release_expired_leases" }],
    checks: [{ check_key: "expired_task_leases", status: "failed", headline: "Two expired leases remain active", observed_at: generatedAt, last_known_good_at: null, evidence: [{ source: "agent.task_leases" }] }],
    broker_write_allowed: false,
  };
}

export function routinesSnapshot() {
  const generatedAt = new Date(now()).toISOString();
  const keys = ["daily_system_health", "obsidian_incremental_index", "research_company_change_monitor", "stale_task_and_lease_reaper", "zerodha_session_and_stream_watch"];
  return {
    available: true,
    routines: keys.map((routineKey, index) => ({
      routine_key: routineKey, routine_name: routineKey.replace(/_/g, " "), owner_agent: "Jarvis",
      current_version: 1, trigger_kind: index === 2 ? "event" : "schedule",
      control_state: index === 0 ? "paused" : "enabled", cost_budget_usd: 0, stale_data_policy: "fail_closed",
    })),
    history: [{ routine_key: "daily_system_health", status: "completed", finished_at: generatedAt }],
    broker_write_allowed: false,
  };
}

async function json(route: Route, body: unknown) {
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
}

export async function routePhase2Base(page: Page) {
  await page.route("**/api/office/snapshot", (route) => json(route, officeSnapshot()));
  await page.route("**/api/system-health/snapshot", (route) => json(route, systemHealthSnapshot()));
  await page.route("**/api/department-terminal/snapshot**", (route) => {
    const workspace = new URL(route.request().url()).searchParams.get("workspace") ?? "models";
    return json(route, departmentTerminalSnapshot(workspace));
  });
}

export async function routePhase2Controls(page: Page) {
  await page.route("**/api/v1/model-bindings**", (route) => json(route, modelFabricSnapshot()));
  await page.route("**/api/v1/model-fabric**", (route) => json(route, modelFabricSnapshot()));
  await page.route("**/api/v1/system/doctor**", (route) => json(route, doctorSnapshot()));
  await page.route("**/api/v1/doctor**", (route) => json(route, doctorSnapshot()));
  await page.route("**/api/v1/routines**", (route) => json(route, routinesSnapshot()));
}
