CREATE SCHEMA IF NOT EXISTS books;

CREATE TABLE IF NOT EXISTS books.capital_policy_proposals (
    id BIGSERIAL PRIMARY KEY,
    proposal_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id) ON DELETE RESTRICT,
    proposal_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_risk_review'
        CHECK (status IN ('draft','pending_risk_review','risk_blocked','committee_review','pending_human_approval','approved','rejected','superseded')),
    capital_basis_type TEXT NOT NULL DEFAULT 'gross_exposure_only'
        CHECK (capital_basis_type IN ('gross_exposure_only','net_liquidation_value','operator_supplied_total_capital')),
    total_capital_basis NUMERIC NOT NULL CHECK (total_capital_basis > 0),
    position_as_of TIMESTAMPTZ,
    risk_run_id BIGINT REFERENCES risk.portfolio_risk_runs(id) ON DELETE SET NULL,
    assumptions JSONB NOT NULL DEFAULT '{}'::JSONB,
    source_lineage JSONB NOT NULL DEFAULT '[]'::JSONB,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL DEFAULT 'Capital Allocation Agent',
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_capital_policy_no_direct_capital CHECK (capital_action_allowed = false),
    CONSTRAINT chk_capital_policy_no_execution CHECK (live_execution_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_capital_policy_client_status
    ON books.capital_policy_proposals (client_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS books.capital_policy_rules (
    id BIGSERIAL PRIMARY KEY,
    proposal_id BIGINT NOT NULL REFERENCES books.capital_policy_proposals(id) ON DELETE CASCADE,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE RESTRICT,
    target_pct NUMERIC NOT NULL CHECK (target_pct >= 0 AND target_pct <= 100),
    min_pct NUMERIC NOT NULL CHECK (min_pct >= 0 AND min_pct <= 100),
    max_pct NUMERIC NOT NULL CHECK (max_pct >= 0 AND max_pct <= 100),
    risk_budget_var_99_10d_pct NUMERIC CHECK (risk_budget_var_99_10d_pct >= 0),
    max_drawdown_budget_pct NUMERIC CHECK (max_drawdown_budget_pct >= 0),
    minimum_liquidity_coverage_pct NUMERIC CHECK (minimum_liquidity_coverage_pct >= 0 AND minimum_liquidity_coverage_pct <= 100),
    rationale TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (proposal_id, book_key),
    CONSTRAINT chk_capital_policy_range CHECK (min_pct <= target_pct AND target_pct <= max_pct)
);

CREATE TABLE IF NOT EXISTS books.capital_allocation_analysis_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    proposal_id BIGINT NOT NULL REFERENCES books.capital_policy_proposals(id) ON DELETE RESTRICT,
    risk_run_id BIGINT REFERENCES risk.portfolio_risk_runs(id) ON DELETE SET NULL,
    run_status TEXT NOT NULL DEFAULT 'running'
        CHECK (run_status IN ('running','completed','blocked','failed')),
    methodology TEXT NOT NULL DEFAULT 'policy_drift_and_risk_budget_v1',
    position_as_of TIMESTAMPTZ,
    risk_data_coverage_pct NUMERIC,
    minimum_required_coverage_pct NUMERIC NOT NULL DEFAULT 80,
    assumptions JSONB NOT NULL DEFAULT '{}'::JSONB,
    warnings JSONB NOT NULL DEFAULT '[]'::JSONB,
    summary JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_by TEXT NOT NULL DEFAULT 'Capital Allocation Agent',
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    CONSTRAINT chk_capital_analysis_no_direct_capital CHECK (capital_action_allowed = false),
    CONSTRAINT chk_capital_analysis_no_execution CHECK (live_execution_allowed = false)
);

CREATE TABLE IF NOT EXISTS books.capital_allocation_analysis_lines (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES books.capital_allocation_analysis_runs(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id) ON DELETE RESTRICT,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE RESTRICT,
    current_exposure NUMERIC NOT NULL DEFAULT 0,
    current_pct NUMERIC NOT NULL DEFAULT 0,
    target_pct NUMERIC NOT NULL,
    min_pct NUMERIC NOT NULL,
    max_pct NUMERIC NOT NULL,
    drift_pct NUMERIC NOT NULL,
    target_exposure NUMERIC NOT NULL,
    rebalance_preview_notional NUMERIC NOT NULL,
    risk_budget_var_99_10d_pct NUMERIC,
    observed_var_99_10d_pct NUMERIC,
    risk_budget_status TEXT NOT NULL,
    liquidity_status TEXT NOT NULL,
    gate_status TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    broker_order_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, book_key),
    CONSTRAINT chk_capital_line_no_direct_capital CHECK (capital_action_allowed = false),
    CONSTRAINT chk_capital_line_no_broker CHECK (broker_order_allowed = false),
    CONSTRAINT chk_capital_line_no_execution CHECK (live_execution_allowed = false)
);

CREATE TABLE IF NOT EXISTS books.capital_committee_reviews (
    id BIGSERIAL PRIMARY KEY,
    review_key TEXT NOT NULL UNIQUE,
    proposal_id BIGINT NOT NULL REFERENCES books.capital_policy_proposals(id) ON DELETE RESTRICT,
    analysis_run_id BIGINT REFERENCES books.capital_allocation_analysis_runs(id) ON DELETE SET NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending','risk_blocked','needs_revision','pending_human_approval','approved','rejected')),
    risk_review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (risk_review_status IN ('pending','passed','blocked_data_quality','blocked_budget','rejected')),
    recommendation TEXT,
    decision TEXT CHECK (decision IS NULL OR decision IN ('approve','reject','revise','defer')),
    decision_notes TEXT,
    committee_members TEXT[] NOT NULL DEFAULT ARRAY[
        'Charlie Munger','Capital Allocation Agent','Portfolio Manager',
        'Portfolio Risk Analyst','Risk Agent','Devarsh'
    ]::TEXT[],
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_capital_committee_no_direct_capital CHECK (capital_action_allowed = false),
    CONSTRAINT chk_capital_committee_no_execution CHECK (live_execution_allowed = false)
);

CREATE OR REPLACE VIEW books.v_capital_policy_control_board AS
WITH current_exposure AS (
    SELECT bp.client_id, bp.book_key, sum(bp.gross_exposure) AS current_exposure,
           max(bp.as_of) AS position_as_of
    FROM books.book_positions bp
    WHERE bp.status = 'active'
    GROUP BY bp.client_id, bp.book_key
), client_totals AS (
    SELECT client_id, sum(current_exposure) AS total_exposure, max(position_as_of) AS position_as_of
    FROM current_exposure
    GROUP BY client_id
), latest_policy AS (
    SELECT proposal.*
    FROM books.capital_policy_proposals proposal
    JOIN (
        SELECT client_id, max(id) AS id
        FROM books.capital_policy_proposals
        WHERE status <> 'superseded'
        GROUP BY client_id
    ) latest ON latest.id = proposal.id
), legacy AS (
    SELECT DISTINCT ON (client_id, book_key)
           client_id, book_key, target_pct, min_pct, max_pct, effective_from, notes
    FROM books.book_capital_allocations
    WHERE status = 'active'
    ORDER BY client_id, book_key, effective_from DESC, id DESC
), latest_client_risk AS (
    SELECT metrics.*
    FROM risk.v_latest_portfolio_risk_metrics metrics
    WHERE metrics.scope_type = 'client'
)
SELECT
    c.id AS client_id,
    c.client_code,
    c.display_name AS client_name,
    b.book_key,
    b.book_name,
    b.owner_agent,
    p.id AS proposal_id,
    p.proposal_key,
    p.proposal_name,
    p.status AS proposal_status,
    p.capital_basis_type,
    p.total_capital_basis,
    p.approval_id,
    approval.status AS approval_status,
    coalesce(ex.current_exposure, 0) AS current_exposure,
    CASE WHEN coalesce(total.total_exposure, 0) = 0 THEN 0
         ELSE round(coalesce(ex.current_exposure, 0) / total.total_exposure * 100, 6) END AS current_pct,
    rule.target_pct,
    rule.min_pct,
    rule.max_pct,
    rule.risk_budget_var_99_10d_pct,
    rule.max_drawdown_budget_pct,
    rule.minimum_liquidity_coverage_pct,
    CASE WHEN rule.target_pct IS NULL THEN NULL
         ELSE round((coalesce(ex.current_exposure, 0) / nullif(total.total_exposure, 0) * 100) - rule.target_pct, 6) END AS drift_pct,
    legacy.target_pct AS legacy_unverified_target_pct,
    legacy.min_pct AS legacy_unverified_min_pct,
    legacy.max_pct AS legacy_unverified_max_pct,
    'legacy_unverified'::TEXT AS legacy_policy_status,
    risk.coverage_pct AS risk_data_coverage_pct,
    risk.bootstrap_var_99_10d_pct AS observed_var_99_10d_pct,
    risk.maximum_drawdown_pct AS observed_maximum_drawdown_pct,
    CASE
        WHEN p.id IS NULL THEN 'policy_required'
        WHEN p.status = 'risk_blocked' THEN 'risk_blocked'
        WHEN p.status = 'approved' AND approval.status = 'approved' THEN 'approved_policy'
        ELSE p.status
    END AS control_status,
    CASE
        WHEN p.id IS NULL THEN 'Create an operator-supplied client policy; legacy defaults are reference only.'
        WHEN coalesce(risk.coverage_pct, 0) < coalesce(rule.minimum_liquidity_coverage_pct, 80) THEN 'Improve market-history and liquidity coverage before policy approval.'
        WHEN p.status = 'pending_risk_review' THEN 'Run independent allocation and risk-budget analysis.'
        WHEN p.status = 'committee_review' THEN 'Open Capital Allocation Committee review.'
        WHEN p.status = 'pending_human_approval' THEN 'Devarsh must decide the linked approval.'
        ELSE 'Monitor drift and risk budget; no broker action is authorized.'
    END AS next_required_action,
    coalesce(ex.position_as_of, total.position_as_of) AS position_as_of,
    p.updated_at,
    false AS capital_action_allowed,
    false AS live_execution_allowed
FROM portfolio.clients c
CROSS JOIN books.investment_books b
LEFT JOIN client_totals total ON total.client_id = c.id
LEFT JOIN current_exposure ex ON ex.client_id = c.id AND ex.book_key = b.book_key
LEFT JOIN latest_policy p ON p.client_id = c.id
LEFT JOIN books.capital_policy_rules rule ON rule.proposal_id = p.id AND rule.book_key = b.book_key
LEFT JOIN legacy ON legacy.client_id = c.id AND legacy.book_key = b.book_key
LEFT JOIN latest_client_risk risk ON risk.scope_ref = c.client_code
LEFT JOIN agent.approvals approval ON approval.id = p.approval_id
WHERE c.active = true AND b.status = 'active';

CREATE OR REPLACE VIEW books.v_capital_allocation_analysis AS
SELECT
    run.id AS run_id, run.run_key, run.run_status, run.proposal_id,
    proposal.proposal_key, proposal.proposal_name, proposal.client_id,
    client.client_code, client.display_name AS client_name,
    line.id AS line_id, line.book_key, book.book_name,
    line.current_exposure, line.current_pct, line.target_pct,
    line.min_pct, line.max_pct, line.drift_pct, line.target_exposure,
    line.rebalance_preview_notional, line.risk_budget_var_99_10d_pct,
    line.observed_var_99_10d_pct, line.risk_budget_status,
    line.liquidity_status, line.gate_status, line.recommended_action,
    line.evidence, line.capital_action_allowed, line.broker_order_allowed,
    line.live_execution_allowed, run.risk_data_coverage_pct,
    run.minimum_required_coverage_pct, run.warnings, run.summary,
    run.started_at, run.finished_at
FROM books.capital_allocation_analysis_runs run
JOIN books.capital_policy_proposals proposal ON proposal.id = run.proposal_id
JOIN portfolio.clients client ON client.id = proposal.client_id
JOIN books.capital_allocation_analysis_lines line ON line.run_id = run.id
JOIN books.investment_books book ON book.book_key = line.book_key;

CREATE OR REPLACE VIEW books.v_capital_committee_queue AS
SELECT
    review.id, review.review_key, review.proposal_id, proposal.proposal_key,
    proposal.proposal_name, proposal.client_id, client.client_code,
    client.display_name AS client_name, review.analysis_run_id,
    review.review_status, review.risk_review_status, review.recommendation,
    review.decision, review.decision_notes, review.committee_members,
    review.approval_id, approval.status AS approval_status,
    review.decided_by, review.decided_at, review.capital_action_allowed,
    review.live_execution_allowed, review.created_at, review.updated_at,
    CASE
        WHEN review.risk_review_status <> 'passed' THEN 'Close risk/data-quality blockers before approval.'
        WHEN review.review_status = 'pending' THEN 'Record committee recommendation.'
        WHEN review.review_status = 'pending_human_approval' THEN 'Devarsh must decide the linked capital-policy approval.'
        ELSE 'Monitor follow-up actions; no broker order is authorized.'
    END AS next_required_action
FROM books.capital_committee_reviews review
JOIN books.capital_policy_proposals proposal ON proposal.id = review.proposal_id
JOIN portfolio.clients client ON client.id = proposal.client_id
LEFT JOIN agent.approvals approval ON approval.id = review.approval_id;

CREATE OR REPLACE VIEW books.v_capital_allocation_control_summary AS
SELECT 'active_clients'::TEXT AS metric, count(DISTINCT client_id)::TEXT AS value,
       'Clients requiring a governed capital policy.'::TEXT AS interpretation
FROM books.v_capital_policy_control_board
UNION ALL
SELECT 'clients_without_policy', count(DISTINCT client_id) FILTER (WHERE proposal_id IS NULL)::TEXT,
       'Clients with only legacy/unverified defaults and no operator-supplied policy.'
FROM books.v_capital_policy_control_board
UNION ALL
SELECT 'pending_risk_review', count(DISTINCT proposal_id) FILTER (WHERE proposal_status = 'pending_risk_review')::TEXT,
       'Policy proposals awaiting independent risk analysis.'
FROM books.v_capital_policy_control_board
UNION ALL
SELECT 'risk_blocked_policies', count(DISTINCT proposal_id) FILTER (WHERE proposal_status = 'risk_blocked')::TEXT,
       'Policies blocked by data coverage or risk budgets.'
FROM books.v_capital_policy_control_board
UNION ALL
SELECT 'pending_human_approval', count(DISTINCT proposal_id) FILTER (WHERE proposal_status = 'pending_human_approval')::TEXT,
       'Policies requiring a Devarsh approval decision.'
FROM books.v_capital_policy_control_board
UNION ALL
SELECT 'approved_policies', count(DISTINCT proposal_id) FILTER (WHERE proposal_status = 'approved' AND approval_status = 'approved')::TEXT,
       'Human-approved policy records; approval does not authorize broker orders.'
FROM books.v_capital_policy_control_board;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES
    ('ai_os_capital_allocation_control_board', 'mcp_tool', 'Capital Allocation Agent', 'read_only', true,
     'Read client/book capital policy readiness, actual allocation, drift, risk budgets, committee state, and explicit execution locks.',
     '{"reads":["books.v_capital_policy_control_board","books.v_capital_allocation_analysis","books.v_capital_committee_queue"],"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_propose_capital_policy', 'mcp_tool', 'Capital Allocation Agent', 'write_with_approval', true,
     'Create an operator-supplied client capital/risk policy proposal that totals 100 percent and routes independent risk review.',
     '{"writes":["books.capital_policy_proposals","books.capital_policy_rules","agent.tasks","agent.inbox_items"],"human_approval_required":true,"live_execution_allowed":false}'::jsonb),
    ('ai_os_run_capital_allocation_analysis', 'mcp_tool', 'Portfolio Risk Analyst', 'write_with_approval', true,
     'Calculate allocation drift and risk-budget gates from real positions and latest institutional risk evidence. Produces previews only.',
     '{"writes":["books.capital_allocation_analysis_runs","books.capital_allocation_analysis_lines","books.capital_committee_reviews"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_capital_committee_decision', 'mcp_tool', 'Charlie Munger', 'write_with_approval', true,
     'Record revise, defer, reject, or approval-routing decisions for a capital policy; Devarsh approval remains separate.',
     '{"writes":["books.capital_committee_reviews","agent.approvals"],"human_final_decision":true,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
) VALUES (
    'capital_allocation_policy_cycle',
    'Capital Allocation Policy And Committee Cycle',
    'capital_allocation',
    'Capital Allocation Agent',
    'manual_or_scheduled',
    'active',
    'write_with_approval',
    ARRAY[
        'books.book_positions', 'risk.v_latest_portfolio_risk_metrics',
        'books.capital_policy_proposals', 'books.capital_policy_rules'
    ]::TEXT[],
    ARRAY[
        'books.capital_allocation_analysis_runs', 'books.capital_committee_reviews',
        'agent.tasks', 'agent.inbox_items', 'agent.approvals'
    ]::TEXT[],
    true,
    'on policy change and weekly drift review',
    'Operator-supplied policy, independent risk analysis, Capital Allocation Committee review, Devarsh approval, and drift monitoring. Legacy defaults are reference only and no stage grants broker authority.',
    '{"legacy_defaults_trusted":false,"seed_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false,"human_final_decision":true}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name = EXCLUDED.workflow_name,
    workflow_type = EXCLUDED.workflow_type,
    owner_agent = EXCLUDED.owner_agent,
    trigger_type = EXCLUDED.trigger_type,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    approval_required = EXCLUDED.approval_required,
    schedule_hint = EXCLUDED.schedule_hint,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();
