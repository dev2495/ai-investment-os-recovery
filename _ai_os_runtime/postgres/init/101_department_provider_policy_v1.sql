CREATE TABLE IF NOT EXISTS core.department_provider_policies (
    id BIGSERIAL PRIMARY KEY,
    policy_key TEXT NOT NULL UNIQUE,
    department_key TEXT NOT NULL,
    provider_kind TEXT NOT NULL DEFAULT '*',
    provider_key_pattern TEXT NOT NULL DEFAULT '*',
    route_or_source_pattern TEXT NOT NULL DEFAULT '*',
    provider_pattern TEXT NOT NULL DEFAULT '*',
    policy_status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    reason TEXT NOT NULL,
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_department_provider_policy_status CHECK (policy_status IN ('allowed', 'approval_required', 'blocked'))
);

CREATE INDEX IF NOT EXISTS idx_department_provider_policies_department
ON core.department_provider_policies (department_key, status, priority);

ALTER TABLE core.provider_assignment_gate_checks
    ADD COLUMN IF NOT EXISTS department_key TEXT,
    ADD COLUMN IF NOT EXISTS policy_status TEXT,
    ADD COLUMN IF NOT EXISTS policy_rule_id BIGINT REFERENCES core.department_provider_policies(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS policy_reason TEXT;

CREATE OR REPLACE FUNCTION core.policy_like(p_value TEXT, p_pattern TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT coalesce(p_pattern, '*') = '*'
        OR coalesce(p_value, '') ILIKE replace(coalesce(p_pattern, '*'), '*', '%')
$$;

CREATE OR REPLACE FUNCTION core.apply_department_provider_policy_before_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_department_key TEXT;
    v_policy JSONB;
    v_policy_status TEXT;
    v_policy_reason TEXT;
BEGIN
    SELECT p.department
    INTO v_department_key
    FROM agent.profiles p
    WHERE p.agent_name = NEW.requesting_agent
    LIMIT 1;

    v_department_key := coalesce(
        nullif(NEW.department_key, ''),
        nullif(v_department_key, ''),
        CASE
            WHEN NEW.target_workspace IN ('executive','runtime','automation','data','knowledge','news','portfolio','quant','research','risk','trading')
            THEN NEW.target_workspace
            ELSE NULL
        END,
        'unknown'
    );

    v_policy := core.match_department_provider_policy(
        v_department_key,
        NEW.provider_kind,
        NEW.provider_key,
        NEW.route_or_source,
        NEW.provider
    );
    v_policy_status := coalesce(v_policy->>'policy_status', 'approval_required');
    v_policy_reason := coalesce(v_policy->>'reason', 'No department provider policy matched; route requires explicit review.');

    NEW.department_key := v_department_key;
    NEW.policy_status := v_policy_status;
    NEW.policy_rule_id := NULLIF(v_policy->>'policy_rule_id', '')::BIGINT;
    NEW.policy_reason := v_policy_reason;
    NEW.readiness_snapshot := coalesce(NEW.readiness_snapshot, '{}'::jsonb)
        || jsonb_build_object('department_policy', v_policy);

    IF v_policy_status = 'blocked' THEN
        NEW.assignment_status := 'blocked';
        NEW.assignment_allowed := false;
        NEW.block_reasons := ARRAY(
            SELECT DISTINCT reason
            FROM unnest(coalesce(NEW.block_reasons, ARRAY[]::TEXT[]) || ARRAY['policy_blocked']::TEXT[]) reason
        );
        NEW.next_action := v_policy_reason;
    ELSIF v_policy_status = 'approval_required' AND NEW.assignment_status = 'passed' THEN
        NEW.assignment_status := 'approval_required';
        NEW.assignment_allowed := false;
        NEW.block_reasons := ARRAY(
            SELECT DISTINCT reason
            FROM unnest(coalesce(NEW.block_reasons, ARRAY[]::TEXT[]) || ARRAY['policy_approval_required']::TEXT[]) reason
        );
        NEW.next_action := v_policy_reason;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_apply_department_provider_policy_before_insert
ON core.provider_assignment_gate_checks;

CREATE TRIGGER trg_apply_department_provider_policy_before_insert
BEFORE INSERT ON core.provider_assignment_gate_checks
FOR EACH ROW
EXECUTE FUNCTION core.apply_department_provider_policy_before_insert();

CREATE OR REPLACE FUNCTION core.ensure_policy_provider_inbox_after_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_inbox_id BIGINT;
BEGIN
    IF NEW.inbox_item_id IS NULL
       AND NEW.assignment_allowed = false
       AND NEW.assignment_status IN ('blocked', 'approval_required')
       AND array_length(NEW.block_reasons, 1) = 1
       AND NEW.block_reasons[1] IN ('policy_blocked', 'policy_approval_required')
    THEN
        INSERT INTO agent.inbox_items (
            title,
            owner_agent,
            status,
            priority,
            recommended_action,
            evidence,
            target_workspace
        )
        VALUES (
            CASE
                WHEN NEW.assignment_status = 'approval_required' THEN 'Provider assignment needs department approval: ' || NEW.provider_key
                ELSE 'Provider assignment blocked by department policy: ' || NEW.provider_key
            END,
            coalesce(NEW.requesting_agent, 'Jarvis'),
            CASE WHEN NEW.assignment_status = 'approval_required' THEN 'needs_review' ELSE 'blocked' END,
            CASE WHEN NEW.assignment_status = 'approval_required' THEN 'high' ELSE 'normal' END,
            coalesce(NEW.policy_reason, NEW.next_action, 'Review department provider policy before assignment.'),
            jsonb_build_array(
                jsonb_build_object('table', 'core.provider_assignment_gate_checks', 'id', NEW.id),
                jsonb_build_object('provider_key', NEW.provider_key, 'provider_kind', NEW.provider_kind, 'assignment_status', NEW.assignment_status),
                jsonb_build_object('department_key', NEW.department_key, 'policy_status', NEW.policy_status, 'policy_rule_id', NEW.policy_rule_id)
            ),
            NEW.target_workspace
        )
        RETURNING id INTO v_inbox_id;

        UPDATE core.provider_assignment_gate_checks
        SET inbox_item_id = v_inbox_id,
            updated_at = now()
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ensure_policy_provider_inbox_after_insert
ON core.provider_assignment_gate_checks;

CREATE TRIGGER trg_ensure_policy_provider_inbox_after_insert
AFTER INSERT ON core.provider_assignment_gate_checks
FOR EACH ROW
EXECUTE FUNCTION core.ensure_policy_provider_inbox_after_insert();

CREATE OR REPLACE VIEW core.v_department_provider_policy_board AS
SELECT
    policy.id,
    policy.policy_key,
    policy.department_key,
    coalesce(dept.department_name, CASE WHEN policy.department_key = '*' THEN 'All Departments' ELSE initcap(policy.department_key) END) AS department_name,
    policy.provider_kind,
    policy.provider_key_pattern,
    policy.route_or_source_pattern,
    policy.provider_pattern,
    policy.policy_status,
    policy.priority,
    policy.reason,
    policy.guardrails,
    policy.status,
    policy.updated_at
FROM core.department_provider_policies policy
LEFT JOIN agent.department_registry dept ON dept.department_key = policy.department_key
ORDER BY
    CASE policy.policy_status WHEN 'blocked' THEN 1 WHEN 'approval_required' THEN 2 ELSE 3 END,
    policy.department_key,
    policy.priority,
    policy.policy_key;

DROP VIEW IF EXISTS core.v_provider_assignment_gate_checks;

CREATE OR REPLACE VIEW core.v_provider_assignment_gate_checks AS
SELECT
    gate.id,
    gate.gate_key,
    gate.provider_kind,
    gate.provider_key,
    gate.provider_name,
    gate.provider,
    gate.subject_name,
    gate.route_or_source,
    gate.department_key,
    coalesce(dept.department_name, initcap(gate.department_key)) AS department_name,
    gate.policy_status,
    gate.policy_rule_id,
    policy.policy_key,
    gate.policy_reason,
    gate.requested_by,
    gate.requesting_agent,
    gate.requested_use,
    gate.source_kind,
    gate.source_ref,
    gate.target_workspace,
    gate.readiness_status,
    gate.provider_health_status,
    gate.assignment_status,
    gate.assignment_allowed,
    gate.assignable_snapshot,
    gate.block_reasons,
    gate.next_action,
    gate.inbox_item_id,
    inbox.status AS inbox_status,
    gate.readiness_snapshot,
    gate.evidence,
    gate.metadata,
    gate.created_at,
    gate.updated_at
FROM core.provider_assignment_gate_checks gate
LEFT JOIN agent.inbox_items inbox ON inbox.id = gate.inbox_item_id
LEFT JOIN core.department_provider_policies policy ON policy.id = gate.policy_rule_id
LEFT JOIN agent.department_registry dept ON dept.department_key = gate.department_key
ORDER BY gate.created_at DESC, gate.id DESC;

CREATE OR REPLACE VIEW agent.v_task_provider_gate_status AS
WITH latest_task_gates AS (
    SELECT DISTINCT ON (gate.source_ref, gate.provider_kind, gate.provider_key)
        gate.*
    FROM core.provider_assignment_gate_checks gate
    WHERE gate.source_kind = 'agent_task'
      AND gate.source_ref ~ '^[0-9]+$'
    ORDER BY gate.source_ref, gate.provider_kind, gate.provider_key, gate.created_at DESC, gate.id DESC
),
aggregated AS (
    SELECT
        source_ref::BIGINT AS task_id,
        count(*) AS provider_gate_count,
        count(*) FILTER (WHERE assignment_status = 'passed' AND assignment_allowed) AS passed_provider_gates,
        count(*) FILTER (WHERE assignment_status = 'approval_required') AS approval_required_provider_gates,
        count(*) FILTER (WHERE assignment_status = 'blocked') AS blocked_provider_gates,
        max(created_at) AS latest_provider_gate_at,
        jsonb_agg(
            jsonb_build_object(
                'id', id,
                'provider_kind', provider_kind,
                'provider_key', provider_key,
                'department_key', department_key,
                'policy_status', policy_status,
                'policy_rule_id', policy_rule_id,
                'policy_reason', policy_reason,
                'assignment_status', assignment_status,
                'assignment_allowed', assignment_allowed,
                'readiness_status', readiness_status,
                'inbox_item_id', inbox_item_id,
                'next_action', next_action
            )
            ORDER BY created_at DESC, id DESC
        ) AS provider_gate_evidence
    FROM latest_task_gates
    GROUP BY source_ref::BIGINT
)
SELECT
    task.id AS task_id,
    task.title,
    task.owner_agent,
    task.status AS task_status,
    coalesce(aggregated.provider_gate_count, 0) AS provider_gate_count,
    coalesce(aggregated.passed_provider_gates, 0) AS passed_provider_gates,
    coalesce(aggregated.approval_required_provider_gates, 0) AS approval_required_provider_gates,
    coalesce(aggregated.blocked_provider_gates, 0) AS blocked_provider_gates,
    CASE
        WHEN coalesce(aggregated.blocked_provider_gates, 0) > 0 THEN 'blocked'
        WHEN coalesce(aggregated.approval_required_provider_gates, 0) > 0 THEN 'approval_required'
        WHEN coalesce(aggregated.provider_gate_count, 0) > 0 THEN 'passed'
        ELSE 'not_checked'
    END AS provider_gate_status,
    aggregated.latest_provider_gate_at,
    coalesce(aggregated.provider_gate_evidence, '[]'::jsonb) AS provider_gate_evidence
FROM agent.tasks task
LEFT JOIN aggregated ON aggregated.task_id = task.id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_department_provider_policy_board', 'mcp_tool', 'Jarvis', 'read_only', true,
     'Read department-level provider policies that decide which model/data-source providers each office can use, require approval for, or block.',
     '{"reads":["core.v_department_provider_policy_board"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'core.department_provider_policies',
            'core.v_department_provider_policy_board',
            'core.apply_department_provider_policy_before_insert'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_department_provider_policy_board']::TEXT[]) AS tool
    ),
    next_action = 'Use department provider policies with readiness gates before assigning agents to model or data-source providers.',
    updated_at = now()
WHERE module_key IN ('runtime', 'automation', 'data_sources');

INSERT INTO core.department_provider_policies (
    policy_key, department_key, provider_kind, provider_key_pattern,
    route_or_source_pattern, provider_pattern, policy_status, priority, reason, guardrails
)
VALUES
    ('global-local-models-allowed', '*', 'model_endpoint', '*', '*', 'ollama', 'allowed', 900, 'Local Ollama models are allowed by default when readiness passes.', '{"cost_tier":"local"}'::jsonb),
    ('global-local-python-tools-allowed', '*', 'model_endpoint', '*', '*', 'local_python', 'allowed', 890, 'Deterministic local Python tools are allowed by default when readiness passes.', '{"deterministic":true}'::jsonb),
    ('global-codex-approval', '*', 'model_endpoint', '*', '*', 'codex', 'approval_required', 100, 'Codex/frontier coding route needs explicit approval and secret readiness.', '{"cloud_requires_approval":true}'::jsonb),
    ('global-cloud-approval', '*', 'model_endpoint', '*', '*', 'cloud_optional', 'approval_required', 100, 'Cloud/frontier investment route needs explicit approval and secret readiness.', '{"cloud_requires_approval":true}'::jsonb),
    ('global-local-archives-allowed', '*', 'source_connector', '*archive*', '*', '*', 'allowed', 850, 'Local archives are read-only evidence sources.', '{"read_only":true}'::jsonb),
    ('global-fincept-allowed', '*', 'source_connector', 'fincept_terminal_connector', '*', '*', 'allowed', 200, 'FinceptTerminal is allowed as an installed local analytics component.', '{"read_only":true}'::jsonb),
    ('global-tradingview-browser-block-until-ready', '*', 'source_connector', 'tradingview_mcp_connector', '*', '*', 'blocked', 50, 'TradingView desktop control is blocked until CDP/browser readiness is available.', '{"requires_cdp_port":9222}'::jsonb),

    ('executive-local-first', 'executive', 'model_endpoint', '*', '*', 'ollama', 'allowed', 100, 'Executive office can use local reasoning routes for decision memos and orchestration.', '{"human_final_decision":true}'::jsonb),
    ('runtime-local-first', 'runtime', 'model_endpoint', '*', '*', 'ollama', 'allowed', 100, 'Runtime operations can use local models for routing, summaries, and dashboard work.', '{"human_final_decision":true}'::jsonb),
    ('automation-local-tools', 'automation', 'model_endpoint', '*', '*', 'local_python', 'allowed', 100, 'Automation engineering can use deterministic local worker tools.', '{"no_destructive_browser_action_without_approval":true}'::jsonb),

    ('quant-strategy-models', 'quant', 'model_endpoint', '*', 'strategy_*', '*', 'allowed', 100, 'Quant Lab can use strategy generation/backtest/optimizer routes with paper-first guardrails.', '{"paper_first":true,"live_execution_allowed":false}'::jsonb),
    ('quant-market-data', 'quant', 'source_connector', 'tick_ohlcv_aggregation_connector', '*', '*', 'allowed', 100, 'Quant Lab can use aggregated OHLCV/tick data for research and backtests.', '{"paper_first":true}'::jsonb),
    ('quant-algo-archive', 'quant', 'source_connector', 'algo_trading_archive_connector', '*', '*', 'allowed', 100, 'Quant Lab can use legacy algo archive data as research input.', '{"read_only":true}'::jsonb),
    ('quant-tradingview-quotes', 'quant', 'source_connector', 'tradingview_scanner_quotes_connector', '*', '*', 'allowed', 150, 'Quant Lab can use ready TradingView scanner quotes as read-only market data.', '{"read_only":true}'::jsonb),

    ('trading-local-models', 'trading', 'model_endpoint', '*', '*', 'ollama', 'allowed', 100, 'Trading Desk can use local models for monitoring and trade journaling.', '{"no_live_execution_without_gate":true}'::jsonb),
    ('trading-view-quotes', 'trading', 'source_connector', 'tradingview_scanner_quotes_connector', '*', '*', 'allowed', 100, 'Trading Desk can use ready TradingView scanner quotes.', '{"read_only":true}'::jsonb),
    ('trading-crypto-candidates-approval', 'trading', 'source_connector', '*crypto*', '*', '*', 'approval_required', 110, 'Crypto/commodity gateways need explicit activation and risk approval.', '{"approval_required":true}'::jsonb),
    ('trading-binance-approval', 'trading', 'source_connector', 'binance*', '*', '*', 'approval_required', 110, 'Binance connector requires activation, credentials, and risk approval.', '{"approval_required":true}'::jsonb),
    ('trading-dhan-mcx-approval', 'trading', 'source_connector', 'dhan_mcx*', '*', '*', 'approval_required', 110, 'MCX commodity gateway requires activation, credentials, and risk approval.', '{"approval_required":true}'::jsonb),

    ('portfolio-client-data', 'portfolio', 'source_connector', '*3081282*', '*', '*', 'allowed', 100, 'Portfolio Office can use imported client broker statements and holdings.', '{"client_private":true}'::jsonb),
    ('portfolio-sanjana-data', 'portfolio', 'source_connector', 'sanjana*', '*', '*', 'allowed', 100, 'Portfolio Office can use Sanjana long-term report data.', '{"client_private":true}'::jsonb),
    ('portfolio-p2cursor-data', 'portfolio', 'source_connector', 'p2cursor_archive_connector', '*', '*', 'allowed', 100, 'Portfolio Office can use P2Cursor archive data.', '{"client_private":true}'::jsonb),
    ('portfolio-live-brokers-approval', 'portfolio', 'source_connector', '*live_connector', '*', '*', 'approval_required', 90, 'Live broker connectors require credential reference and human approval.', '{"broker_write_allowed":false}'::jsonb),

    ('research-filings', 'research', 'source_connector', '*filings*', '*', '*', 'allowed', 100, 'Research Desk can use NSE/BSE filings connectors.', '{"source_required":true}'::jsonb),
    ('research-company-models', 'research', 'model_endpoint', '*', 'research_*', '*', 'allowed', 100, 'Research Desk can use company-analysis routes for sourced research.', '{"source_required":true}'::jsonb),
    ('research-fincept', 'research', 'source_connector', 'fincept_terminal_connector', '*', '*', 'allowed', 100, 'Research Desk can use FinceptTerminal analytics read-only.', '{"read_only":true}'::jsonb),

    ('news-filings', 'news', 'source_connector', '*filings*', '*', '*', 'allowed', 100, 'News Intelligence can use exchange filing feeds.', '{"source_required":true}'::jsonb),
    ('news-local-rss', 'news', 'source_connector', 'global_news_connector', '*', '*', 'approval_required', 100, 'Global news basket needs activation before autonomous use.', '{"activation_required":true}'::jsonb),
    ('news-x-watchlist-blocked-browser', 'news', 'source_connector', 'x_watchlist_connector', '*', '*', 'blocked', 90, 'X watchlist needs authenticated browser/session evidence before use.', '{"browser_session_required":true}'::jsonb),

    ('risk-readiness-local', 'risk', 'model_endpoint', '*', '*', 'ollama', 'allowed', 100, 'Risk office can use local model routes for reviews and summaries.', '{"risk_review_required":true}'::jsonb),
    ('data-connectors', 'data', 'source_connector', '*', '*', '*', 'allowed', 700, 'Data Engineering can inspect registered connectors as read-only configuration and ingestion sources.', '{"read_only":true}'::jsonb),
    ('knowledge-local-memory', 'knowledge', 'model_endpoint', '*', 'obsidian_*', '*', 'allowed', 100, 'Knowledge division can use Obsidian retrieval and summary routes.', '{"memory_writeback":true}'::jsonb)
ON CONFLICT (policy_key) DO UPDATE SET
    department_key = EXCLUDED.department_key,
    provider_kind = EXCLUDED.provider_kind,
    provider_key_pattern = EXCLUDED.provider_key_pattern,
    route_or_source_pattern = EXCLUDED.route_or_source_pattern,
    provider_pattern = EXCLUDED.provider_pattern,
    policy_status = EXCLUDED.policy_status,
    priority = EXCLUDED.priority,
    reason = EXCLUDED.reason,
    guardrails = EXCLUDED.guardrails,
    status = EXCLUDED.status,
    updated_at = now();

CREATE OR REPLACE FUNCTION core.match_department_provider_policy(
    p_department_key TEXT,
    p_provider_kind TEXT,
    p_provider_key TEXT,
    p_route_or_source TEXT,
    p_provider TEXT
)
RETURNS JSONB
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(
        (
            SELECT jsonb_build_object(
                'policy_rule_id', policy.id,
                'policy_key', policy.policy_key,
                'department_key', policy.department_key,
                'policy_status', policy.policy_status,
                'reason', policy.reason,
                'priority', policy.priority,
                'guardrails', policy.guardrails
            )
            FROM core.department_provider_policies policy
            WHERE policy.status = 'active'
              AND policy.department_key IN (coalesce(nullif(p_department_key, ''), '*'), '*')
              AND (policy.provider_kind = '*' OR policy.provider_kind = coalesce(nullif(p_provider_kind, ''), '*'))
              AND core.policy_like(p_provider_key, policy.provider_key_pattern)
              AND core.policy_like(p_route_or_source, policy.route_or_source_pattern)
              AND core.policy_like(p_provider, policy.provider_pattern)
            ORDER BY
                CASE WHEN policy.department_key = coalesce(nullif(p_department_key, ''), '*') THEN 0 ELSE 1 END,
                policy.priority,
                length(replace(policy.provider_key_pattern, '*', '')) DESC,
                policy.id
            LIMIT 1
        ),
        jsonb_build_object(
            'policy_rule_id', NULL,
            'policy_key', 'implicit-no-policy',
            'department_key', coalesce(nullif(p_department_key, ''), 'unknown'),
            'policy_status', 'approval_required',
            'reason', 'No department provider policy matched; route requires explicit review.',
            'priority', 9999,
            'guardrails', jsonb_build_object('implicit_default', true)
        )
    )
$$;
