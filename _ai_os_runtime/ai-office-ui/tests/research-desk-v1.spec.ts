import { expect, test } from "@playwright/test";

const generatedAt = "2026-08-24T10:00:00+05:30";
let apiRequests: string[];

function payload(pathname: string) {
  if (pathname === "/api/research/cases") return {
    generated_at: generatedAt,
    runtime_root: "/Volumes/Devarsh SSD/AI OS Data",
    storage_policy: {
      transaction_truth: "postgres",
      artifact_root: "/Volumes/Devarsh SSD/AI OS Data/artifacts",
      private_data_egress_allowed: false,
      broker_write_allowed: false,
      external_write_allowed: false
    },
    pagination: { page: 1, page_size: 8, total: 2, pages: 1 },
    cases: [
      { id: 12, exchange: "NSE", ticker: "WIPRO", company_name: "Wipro Limited", status: "review", next_action: "Review the decision pack", updated_at: generatedAt, report_id: 801, report_version: 2, report_html_path: "/Volumes/Devarsh SSD/AI OS Data/reports/wipro-v2.html", report_pdf_path: null, report_coverage_snapshot: { content_state: "evidence_debt", content_label: "Evidence-Debt Research Pack", delivery_state: "html_ready_pdf_retry" } },
      { id: 15, exchange: "NSE", ticker: "SBCL", company_name: "Shivalik Bimetal Controls", status: "blocked", next_action: "Repair filing extraction", preflight_id: 151, preflight_status: "draft", source_job_blocked: 1, source_count: 7, updated_at: generatedAt }
    ],
    selected_case_id: 0,
    agents: [], work_items: [], events: [], evidence: [], model_runs: [], source_jobs: [],
    blockers: [{ id: 91, status: "open", severity: "medium", title: "Official filing extraction stopped", detail: "{\"error_message\":\"RuntimeError: pypdf is required; source /Volumes/Devarsh SSD/AI OS Data/artifacts/filings/sbcl.pdf; api_key=super-secret\"}", system_action: "Retry only the filing extraction stage with the bundled local reader." }],
    sections: [], imported_research: []
  };
  if (pathname === "/api/research/monitoring") return {
    generated_at: generatedAt,
    pagination: { page: 1, page_size: 20, total: 1, pages: 1 },
    companies: [{ symbol: "WIPRO", company_name: "Wipro Limited", priority: "high", latest_update_title: "Annual report review completed", latest_update_materiality: "high", latest_update_decision_impact: "review decision", latest_update_at: generatedAt, new_update_count: 1, thesis_href: "/fundamental/theses?symbol=WIPRO", case_href: "/research/cases?case_id=12", latest_update_source_url: "https://www.wipro.com/investors/annual-reports/" }]
  };
  if (pathname === "/api/today/research-updates") return {
    generated_at: generatedAt,
    pagination: { page: 1, page_size: 20, total: 1, pages: 1 },
    items: [{ update_key: "wipro-ar", exchange: "NSE", symbol: "WIPRO", title: "Annual report review completed", summary: "A qualified company filing was linked to the decision record.", materiality: "high", decision_impact: "review", source_kind: "annual report", status: "new", effective_at: generatedAt, source_url: "https://www.wipro.com/investors/annual-reports/", thesis_href: "/fundamental/theses?symbol=WIPRO" }]
  };
  if (pathname === "/api/fundamental-scanners") return {
    items: [{ id: 701, name: "Quality compounders", description: "Persisted candidate awaiting a bounded research plan.", version: 1, version_status: "draft", scope_key: "workspace:default", run_count: 0 }],
    page: { next_cursor: null }, broker_write_allowed: false, external_write_allowed: false
  };
  if (pathname === "/api/research/knowledge") return {
    scope_key: "workspace:default", query: "", items: [],
    nodes: [{ id: 501, node_type: "company_research", label: "Wipro company research pack", source_schema: "research", source_table: "case_reports", source_pk: "501", authority: "governed", privacy_class: "private_local", available_at: generatedAt, updated_at: generatedAt }],
    edges: [{ id: 1, from_label: "Wipro annual report", to_label: "Wipro company research pack", edge_type: "supports", source_kind: "annual report", available_at: generatedAt }],
    notes: [], unresolved_links: [], page: { next_cursor: null }, privacy: "local_private", broker_write_allowed: false, external_write_allowed: false
  };
  if (pathname === "/api/research/daily") return {
    generated_at: generatedAt,
    runtime_root: "/Volumes/Devarsh SSD/AI OS Data",
    generated_ideas: [{ symbol: "SBCL", company_name: "Shivalik Bimetal Controls", idea_type: "coverage candidate", thesis: "Persisted candidate awaiting a bounded research plan.", status: "unreviewed", updated_at: generatedAt }],
    discovery_candidates: [],
    fundamental_intake: []
  };
  if (pathname === "/api/research/long-term-thesis") return {
    generated_at: generatedAt,
    workspace_profile: "long_term_thesis_dashboard_v1",
    runtime_root: "/Volumes/Devarsh SSD/AI OS Data",
    privacy: {
      private_data_egress_allowed: false,
      broker_write_allowed: false,
      external_write_allowed: false
    },
    pagination: { facts_total: 72, evidence_total: 11, filings_total: 11 },
    theses: [{ id: 12, exchange: "NSE", symbol: "WIPRO", company_name: "Wipro Limited", legal_name: "Wipro Limited" }],
    selected_thesis: {
      id: 12,
      exchange: "NSE",
      symbol: "WIPRO",
      company_name: "Wipro Limited",
      legal_name: "Wipro Limited",
      thesis_title: "WIPRO Long-Term Thesis",
      dossier_version_number: 2,
      latest_research_case_id: 12,
      latest_research_case_report_id: 801,
      latest_research_case_report_version: 2,
      latest_research_case_report_status: "generated",
      latest_research_case_report_delivery_state: "html_ready_pdf_retry",
      research_pack: {
        investment_conclusion: {
          title: "Hold while the valuation evidence is completed",
          narrative: "The operating recovery is supported, while the current valuation remains under review."
        }
      }
    },
    execution_control: [{
      global_execution_locked: true,
      lock_reason: "Research is read-only; broker and external writes remain disabled."
    }]
  };
  if (pathname === "/api/department-terminal/snapshot") return {
    generated_at: generatedAt,
    workspace: "models",
    data_mode: { seed_data_allowed: false, source: "test" },
    payload_profile: { query_count: 7, row_count: 2 },
    execution_control: [], widgets: [], summary: [],
    primary: [{ route_name: "openrouter_research_fast", default_provider: "openrouter", default_model: "deepseek/deepseek-v4-flash", runtime_status: "active" }],
    secondary: [], tertiary: [],
    canaries: [{ id: 52, canary_key: "prior-glm53", candidate_route: "openrouter_public_lead_glm53_flash_canary", candidate_model: "z-ai/glm-5.3-flash", status: "completed", structured_output_valid: true, selected_for_role: false, hard_max_cost_usd: 0.002, updated_at: generatedAt }]
  };
  if (pathname === "/api/research/model-runs/preflight") return {
    id: 900, request_kind: "canary", status: "awaiting_approval",
    estimated_cost_usd: 0.0010, hard_max_cost_usd: 0.0012, hard_max_cost_inr: 0.11,
    no_model_invocation: true
  };
  if (pathname === "/api/research/model-runs/preflight/approve") return {
    id: 900, request_kind: "canary", status: "approved", execution_enabled: false
  };
  if (pathname === "/api/research/model-runs/canary/configure") return {
    id: 901, status: "awaiting_approval", candidate_model: "z-ai/glm-5.3-flash", execution_enabled: false
  };
  if (pathname === "/api/research/model-runs/canary/run") return {
    id: 901, status: "completed", candidate_model: "z-ai/glm-5.3-flash",
    response_output: "{\"facts\":[{\"claim\":\"FY26 volume\",\"value\":\"207 KMT\",\"source\":\"official historical disclosure\"}],\"inferences\":[],\"missing\":[],\"disconfirmers\":[]}",
    receipt: { response_hash: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }
  };
  if (pathname === "/api/research/model-runs/canary/review-promote") return {
    canary_id: 901, daily_driver_route: "openrouter_research_fast",
    daily_driver_model: "z-ai/glm-5.3-flash",
    detail: "z-ai/glm-5.3-flash is selected for public Research Case specialist work."
  };
  if (pathname === "/api/reports/snapshot") return {
    generated_at: generatedAt,
    runtime_root: "/Volumes/Devarsh SSD/AI OS Data",
    artifacts: [{ id: 501, artifact_key: "wipro-pack-v1", title: "Wipro company research pack", summary: "Versioned company pack", artifact_family: "company_research", symbol: "WIPRO", source_system: "local registry", updated_at: generatedAt }],
    raw_artifacts: [],
    artifact_lineage: [{ id: 1, source_title: "Wipro annual report", target_title: "Wipro company research pack", relationship_type: "supports", symbol: "WIPRO" }],
    pagination: { page: 1, page_size: 40, total: 1, pages: 1 }
  };
  return { generated_at: generatedAt, runtime_root: "/Volumes/Devarsh SSD/AI OS Data" };
}

test.beforeEach(async ({ page }) => {
  apiRequests = [];
  await page.addInitScript(() => {
    localStorage.setItem("aios-ui", JSON.stringify({ state: { theme: "light", density: "standard", assistantOpen: false }, version: 2 }));
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) apiRequests.push(url.pathname);
  });
  await page.route("**/api/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload(pathname)) });
  });
});

test("unified research desk is bounded and global drawers stay lazy", async ({ page }) => {
  await page.goto("/research/desk");
  await expect(page.getByRole("heading", { name: "One desk from question to decision-ready company pack." })).toBeVisible();
  const researchNav = page.getByRole("navigation", { name: "Company Research" });
  await expect(researchNav.getByRole("link", { name: "Desk" })).toBeVisible();
  await expect(researchNav.getByRole("link", { name: "Workstreams" })).toBeVisible();
  await expect(researchNav.getByRole("link", { name: "Following" })).toBeVisible();
  await expect(researchNav.getByRole("link", { name: "Fundamental scanners" })).toBeVisible();
  await expect(researchNav.getByRole("link", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByText("Wipro Limited", { exact: true })).toBeVisible();
  await page.waitForTimeout(400);
  expect(apiRequests).toContain("/api/research/cases");
  expect(apiRequests).toContain("/api/research/monitoring");
  expect(apiRequests).toContain("/api/today/research-updates");
  expect(apiRequests).not.toContain("/api/daily/command");
  expect(apiRequests).not.toContain("/api/department-terminal/snapshot");
  expect(apiRequests).not.toContain("/api/zerodha/auth/status");
  expect(apiRequests).not.toContain("/api/zerodha/market/status");
});

test("following, scanner and knowledge use real read models with independent states", async ({ page }) => {
  await page.goto("/research/following");
  await expect(page.getByRole("heading", { name: "Following" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Primary source" })).toHaveAttribute("href", "https://www.wipro.com/investors/annual-reports/");

  await page.goto("/research/scanners");
  await expect(page.getByRole("heading", { name: "Fundamental scanners" })).toBeVisible();
  await expect(page.getByText("Persisted candidate awaiting a bounded research plan.")).toBeVisible();

  await page.goto("/research/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByText("Wipro company research pack", { exact: true })).toBeVisible();
  await expect(page.getByText("Wipro annual report → Wipro company research pack")).toBeVisible();
});

test("research desk remains usable at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/research/desk");
  await expect(page.getByRole("heading", { name: "One desk from question to decision-ready company pack." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Review research plan" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("research failures are actionable and technical detail is redacted", async ({ page }) => {
  await page.goto("/research/cases?case_id=15");

  await expect(page.getByText("One or more filings could not be read.")).toBeVisible();
  await expect(page.getByText(/Retry extraction; if it fails again/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Review repair plan" })).toBeVisible();

  const technical = page.getByText("Technical detail", { exact: true });
  await expect(technical).toBeVisible();
  await technical.click();
  const diagnostic = page.locator(".rc-blockers code");
  await expect(diagnostic).toContainText("[local path hidden]");
  await expect(diagnostic).toContainText("[credential hidden]");
  await expect(diagnostic).not.toContainText("/Volumes/Devarsh SSD");
  await expect(diagnostic).not.toContainText("super-secret");
});

test("evidence-debt HTML stays usable while PDF rendering is pending", async ({ page }) => {
  await page.goto("/research/cases?case_id=12");

  await expect(page.getByRole("link", { name: "Open evidence-debt report v2" })).toBeVisible();
  await expect(page.getByText("PDF rendering / retry scheduled", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download PDF" })).toHaveCount(0);
});
test("completed Wipro research is visible from its exact company dashboard", async ({ page }) => {
  await page.goto("/fundamental/theses?symbol=WIPRO&exchange=NSE");

  await expect(page.getByRole("heading", { name: "Wipro Limited", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open latest research pack" })).toHaveAttribute(
    "href",
    /\/api\/research\/case-reports\/801\/view$/,
  );
  await expect(page.getByRole("link", { name: /PDF pending.*repair delivery/ })).toHaveAttribute(
    "href",
    "/research/cases?case_id=12",
  );
  await expect(page.getByRole("link", { name: "Download case PDF" })).toHaveCount(0);
  expect(apiRequests).toContain("/api/research/long-term-thesis");
});

test("GLM 5.3 daily-driver gate separates cost, spend and human promotion", async ({ page }) => {
  await page.goto("/firm/models");
  await expect(page.getByText("GLM 5.3 Flash public-research daily-driver gate")).toBeVisible();
  await expect(page.getByText("z-ai/glm-5.3-flash", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Prepare GLM 5.3 canary" }).click();
  await expect(page.getByText(/Estimate \$0\.0010.*hard max \$0\.0012/)).toBeVisible();
  expect(apiRequests).toContain("/api/research/model-runs/preflight");
  expect(apiRequests).not.toContain("/api/research/model-runs/canary/run");

  await page.getByRole("button", { name: "Approve and configure" }).click();
  await expect.poll(() => apiRequests.includes("/api/research/model-runs/canary/configure")).toBe(true);
  await expect(page.getByText("I confirm this bounded paid canary")).toBeVisible();
  expect(apiRequests).toContain("/api/research/model-runs/preflight/approve");
  expect(apiRequests).not.toContain("/api/research/model-runs/canary/run");

  await page.getByText("I confirm this bounded paid canary").click();
  await expect(page.getByRole("button", { name: "Run paid canary" })).toBeEnabled();
  await page.getByRole("button", { name: "Run paid canary" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText(/207 KMT/)).toBeVisible();
  expect(apiRequests).toContain("/api/research/model-runs/canary/run");

  await page.getByText("I checked every cited fact and numerical value against the fixed public packet.").click();
  await page.locator(".aios-drawer textarea").fill("Every cited fact and number matches the fixed public packet exactly.");
  await page.getByRole("button", { name: "Select public daily driver" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(apiRequests).toContain("/api/research/model-runs/canary/review-promote");
});
