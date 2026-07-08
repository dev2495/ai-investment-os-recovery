CREATE TABLE IF NOT EXISTS research.special_situation_spread_checks (
    id BIGSERIAL PRIMARY KEY,
    special_memo_id BIGINT NOT NULL REFERENCES research.special_situation_memos(id) ON DELETE CASCADE,
    special_terms_id BIGINT NOT NULL REFERENCES research.special_situation_terms(id) ON DELETE CASCADE,
    filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE SET NULL,
    symbol TEXT,
    event_type TEXT NOT NULL,
    target_price NUMERIC,
    target_price_source TEXT,
    market_price NUMERIC,
    market_price_source TEXT,
    quote_id BIGINT REFERENCES market.price_quotes(id) ON DELETE SET NULL,
    quote_ts TIMESTAMPTZ,
    quote_staleness_minutes NUMERIC,
    gross_spread_abs NUMERIC,
    gross_spread_pct NUMERIC,
    annualized_spread_pct NUMERIC,
    days_to_close INTEGER,
    scenario_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    data_quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Special Situations Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_special_situation_spread_memo ON research.special_situation_spread_checks (special_memo_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_special_situation_spread_terms ON research.special_situation_spread_checks (special_terms_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_special_situation_spread_symbol ON research.special_situation_spread_checks (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_special_situation_spread_status ON research.special_situation_spread_checks (status);

CREATE TABLE IF NOT EXISTS research.special_situation_decisions (
    id BIGSERIAL PRIMARY KEY,
    special_memo_id BIGINT NOT NULL REFERENCES research.special_situation_memos(id) ON DELETE CASCADE,
    special_terms_id BIGINT NOT NULL REFERENCES research.special_situation_terms(id) ON DELETE CASCADE,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    decision TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'final',
    decision_notes TEXT,
    monitor_allowed BOOLEAN NOT NULL DEFAULT false,
    trade_allowed BOOLEAN NOT NULL DEFAULT false,
    client_recommendation_allowed BOOLEAN NOT NULL DEFAULT false,
    decided_by TEXT NOT NULL DEFAULT 'Devarsh',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_special_situation_decisions_memo ON research.special_situation_decisions (special_memo_id);
CREATE INDEX IF NOT EXISTS idx_special_situation_decisions_terms ON research.special_situation_decisions (special_terms_id);
CREATE INDEX IF NOT EXISTS idx_special_situation_decisions_decision ON research.special_situation_decisions (decision);

CREATE OR REPLACE VIEW research.v_special_situation_spread_checks AS
SELECT
    sc.id,
    sc.special_memo_id,
    sc.special_terms_id,
    sc.filing_id,
    sc.symbol,
    sc.event_type,
    memo.company_name,
    memo.memo_title,
    memo.note_path,
    sc.target_price,
    sc.target_price_source,
    sc.market_price,
    sc.market_price_source,
    sc.quote_id,
    sc.quote_ts,
    sc.quote_staleness_minutes,
    sc.gross_spread_abs,
    sc.gross_spread_pct,
    sc.annualized_spread_pct,
    sc.days_to_close,
    sc.scenario_payload,
    sc.status,
    sc.data_quality_flags,
    sc.created_by,
    sc.created_at
FROM research.special_situation_spread_checks sc
JOIN research.special_situation_memos memo ON memo.id = sc.special_memo_id
ORDER BY sc.created_at DESC, sc.id DESC;

CREATE OR REPLACE VIEW research.v_latest_special_situation_spread AS
SELECT DISTINCT ON (special_memo_id)
    *
FROM research.v_special_situation_spread_checks
ORDER BY special_memo_id, created_at DESC, id DESC;

CREATE OR REPLACE VIEW research.v_special_situation_decisions AS
SELECT
    decision.id,
    decision.special_memo_id,
    decision.special_terms_id,
    decision.approval_id,
    memo.symbol,
    memo.company_name,
    memo.event_type,
    memo.memo_title,
    memo.note_path,
    decision.decision,
    decision.decision_status,
    decision.decision_notes,
    decision.monitor_allowed,
    decision.trade_allowed,
    decision.client_recommendation_allowed,
    decision.decided_by,
    decision.evidence,
    decision.created_at
FROM research.special_situation_decisions decision
JOIN research.special_situation_memos memo ON memo.id = decision.special_memo_id
ORDER BY decision.created_at DESC, decision.id DESC;

CREATE OR REPLACE FUNCTION research.resolve_special_situation_decision(
    p_special_memo_id BIGINT,
    p_decision TEXT,
    p_actor TEXT DEFAULT 'Devarsh',
    p_decision_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_memo research.special_situation_memos%ROWTYPE;
    v_decision TEXT := lower(trim(coalesce(p_decision, '')));
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Devarsh');
    v_notes TEXT := nullif(trim(coalesce(p_decision_notes, '')), '');
    v_decision_id BIGINT;
    v_memo_status TEXT;
    v_approval_status TEXT;
    v_inbox_owner TEXT;
    v_inbox_action TEXT;
    v_priority TEXT;
    v_monitor_allowed BOOLEAN := false;
BEGIN
    IF v_decision NOT IN ('reject', 'monitor', 'research_more', 'committee_review') THEN
        RAISE EXCEPTION 'decision must be reject, monitor, research_more, or committee_review';
    END IF;

    SELECT * INTO v_memo
    FROM research.special_situation_memos
    WHERE id = p_special_memo_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'special_memo_id % not found', p_special_memo_id;
    END IF;

    IF coalesce(v_memo.memo_status, '') NOT IN ('routed_for_review', 'generated', 'monitoring', 'research_required', 'committee_review', 'rejected') THEN
        RAISE EXCEPTION 'special situation memo % is not in a decision-ready state: %', p_special_memo_id, v_memo.memo_status;
    END IF;

    IF v_decision = 'reject' THEN
        v_memo_status := 'rejected';
        v_approval_status := 'rejected';
        v_inbox_owner := 'Special Situations Agent';
        v_inbox_action := 'Archive this event unless new source evidence arrives. No trade or client action is authorized.';
        v_priority := 'medium';
    ELSIF v_decision = 'monitor' THEN
        v_memo_status := 'monitoring';
        v_approval_status := 'approved';
        v_inbox_owner := 'Event Arbitrage Analyst';
        v_inbox_action := 'Monitor spread, quote freshness, event calendar, liquidity, and acceptance scenarios. No trade is authorized.';
        v_priority := 'high';
        v_monitor_allowed := true;
    ELSIF v_decision = 'research_more' THEN
        v_memo_status := 'research_required';
        v_approval_status := 'approved';
        v_inbox_owner := 'Special Situations Agent';
        v_inbox_action := 'Gather more filing evidence, price/liquidity data, and risk checks before another Charlie review.';
        v_priority := 'high';
    ELSE
        v_memo_status := 'committee_review';
        v_approval_status := 'approved';
        v_inbox_owner := 'Investment Committee Secretary';
        v_inbox_action := 'Prepare Investment Committee packet. No trade, paper trade, or client recommendation is authorized.';
        v_priority := 'critical';
    END IF;

    INSERT INTO research.special_situation_decisions (
        special_memo_id,
        special_terms_id,
        approval_id,
        decision,
        decision_status,
        decision_notes,
        monitor_allowed,
        trade_allowed,
        client_recommendation_allowed,
        decided_by,
        evidence
    )
    VALUES (
        v_memo.id,
        v_memo.special_terms_id,
        v_memo.approval_id,
        v_decision,
        'final',
        v_notes,
        v_monitor_allowed,
        false,
        false,
        v_actor,
        jsonb_build_array(
            jsonb_build_object('special_memo_id', v_memo.id),
            jsonb_build_object('special_terms_id', v_memo.special_terms_id),
            jsonb_build_object('memo_note_path', v_memo.note_path),
            jsonb_build_object('trade_allowed', false),
            jsonb_build_object('client_recommendation_allowed', false)
        )
    )
    RETURNING id INTO v_decision_id;

    UPDATE research.special_situation_memos
    SET memo_status = v_memo_status,
        updated_at = now()
    WHERE id = v_memo.id;

    UPDATE agent.approvals
    SET status = v_approval_status,
        decided_by = v_actor,
        decided_at = now()
    WHERE id = v_memo.approval_id
      AND status = 'pending';

    UPDATE agent.tasks
    SET status = CASE WHEN v_decision = 'reject' THEN 'done' ELSE 'needs_review' END,
        updated_at = now()
    WHERE id = v_memo.task_id;

    INSERT INTO agent.inbox_items (
        task_id,
        title,
        owner_agent,
        status,
        priority,
        recommended_action,
        evidence,
        target_workspace
    )
    VALUES (
        v_memo.task_id,
        'Special situation decision: ' || coalesce(v_memo.symbol, v_memo.company_name, 'event') || ' -> ' || v_decision,
        v_inbox_owner,
        'needs_review',
        v_priority,
        v_inbox_action,
        jsonb_build_array(
            jsonb_build_object('special_memo_id', v_memo.id),
            jsonb_build_object('special_terms_id', v_memo.special_terms_id),
            jsonb_build_object('special_situation_decision_id', v_decision_id),
            jsonb_build_object('trade_allowed', false),
            jsonb_build_object('client_recommendation_allowed', false)
        ),
        'research'
    );

    RETURN jsonb_build_object(
        'special_memo_id', v_memo.id,
        'special_terms_id', v_memo.special_terms_id,
        'special_situation_decision_id', v_decision_id,
        'approval_id', v_memo.approval_id,
        'decision', v_decision,
        'memo_status', v_memo_status,
        'approval_status', v_approval_status,
        'monitor_allowed', v_monitor_allowed,
        'trade_allowed', false,
        'client_recommendation_allowed', false
    );
END;
$$;

DROP VIEW IF EXISTS research.v_special_situation_inbox;
DROP VIEW IF EXISTS research.v_special_situation_memos;

CREATE OR REPLACE VIEW research.v_special_situation_memos AS
SELECT
    memo.id,
    memo.special_terms_id,
    memo.filing_id,
    memo.filing_event_id,
    memo.event_type,
    memo.symbol,
    memo.company_name,
    cf.title AS filing_title,
    cf.source_name,
    cf.exchange,
    cf.source_url,
    cf.attachment_url,
    memo.memo_title,
    memo.memo_status,
    memo.note_path,
    memo.summary,
    memo.extracted_terms,
    memo.risk_flags,
    memo.required_followups,
    memo.task_id,
    task.status AS task_status,
    task.owner_agent AS task_owner_agent,
    memo.approval_id,
    approval.status AS approval_status,
    approval.owner_agent AS approval_owner_agent,
    approval.risk_level AS approval_risk_level,
    latest_spread.id AS latest_spread_check_id,
    latest_spread.status AS latest_spread_status,
    latest_spread.market_price AS latest_market_price,
    latest_spread.target_price AS latest_target_price,
    latest_spread.gross_spread_pct AS latest_gross_spread_pct,
    latest_spread.quote_ts AS latest_quote_ts,
    latest_decision.id AS latest_decision_id,
    latest_decision.decision AS latest_decision,
    latest_decision.created_at AS latest_decision_at,
    memo.created_by,
    memo.created_at,
    memo.updated_at
FROM research.special_situation_memos memo
JOIN research.corporate_filings cf ON cf.id = memo.filing_id
LEFT JOIN agent.tasks task ON task.id = memo.task_id
LEFT JOIN agent.approvals approval ON approval.id = memo.approval_id
LEFT JOIN LATERAL (
    SELECT *
    FROM research.v_latest_special_situation_spread spread
    WHERE spread.special_memo_id = memo.id
    LIMIT 1
) latest_spread ON true
LEFT JOIN LATERAL (
    SELECT decision.id, decision.decision, decision.created_at
    FROM research.special_situation_decisions decision
    WHERE decision.special_memo_id = memo.id
    ORDER BY decision.created_at DESC, decision.id DESC
    LIMIT 1
) latest_decision ON true
ORDER BY memo.updated_at DESC, memo.id DESC;

CREATE OR REPLACE VIEW research.v_special_situation_inbox AS
SELECT
    inbox.*,
    terms.id AS special_terms_id,
    terms.record_date,
    terms.offer_price,
    terms.issue_price,
    terms.swap_ratio,
    terms.entitlement_ratio,
    terms.buyback_size,
    terms.aggregate_amount,
    terms.confidence AS terms_confidence,
    terms.status AS terms_status,
    memo.id AS special_memo_id,
    memo.memo_status AS special_memo_status,
    memo.note_path AS special_memo_note_path,
    memo.approval_id AS special_memo_approval_id,
    memo.approval_status AS special_memo_approval_status,
    memo.latest_spread_status AS special_memo_spread_status,
    memo.latest_gross_spread_pct AS special_memo_gross_spread_pct,
    memo.latest_decision AS special_memo_latest_decision
FROM research.v_corporate_filing_inbox inbox
LEFT JOIN research.special_situation_terms terms
  ON terms.filing_id = inbox.filing_id
 AND terms.event_type = inbox.event_type
LEFT JOIN research.v_special_situation_memos memo
  ON memo.special_terms_id = terms.id
WHERE inbox.event_type IN (
    'demerger',
    'merger',
    'reverse_merger',
    'scheme_arrangement',
    'buyback',
    'open_offer',
    'delisting',
    'rights_issue',
    'preferential_allotment',
    'asset_sale',
    'pledge_change',
    'insolvency',
    'arbitrage_watch',
    'board_action'
)
AND coalesce(inbox.event_status, 'new') <> 'superseded'
ORDER BY inbox.filed_at DESC NULLS LAST, inbox.filing_id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_calculate_special_situation_spread', 'mcp_tool', 'Event Arbitrage Analyst', 'write_with_approval', true, 'Calculate special-situation spread from extracted event terms and latest stored market quotes. Does not fetch or invent prices.', '{"script":"_ai_os_runtime/scripts/calculate_special_situation_spread.py","writes":["research.special_situation_spread_checks"],"reads":["research.v_special_situation_memos","market.v_latest_price_quotes"],"seed_data_allowed":false}'::jsonb),
    ('ai_os_resolve_special_situation_decision', 'mcp_tool', 'Charlie Munger', 'write_with_approval', true, 'Record Charlie or committee decision for special-situation memo. Never authorizes trade/client recommendation.', '{"function":"research.resolve_special_situation_decision","writes":["research.special_situation_decisions","agent.approvals","agent.inbox_items"],"trade_allowed":false}'::jsonb)
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
            'research.special_situation_spread_checks',
            'research.v_special_situation_spread_checks',
            'research.v_latest_special_situation_spread',
            'research.special_situation_decisions',
            'research.v_special_situation_decisions'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_calculate_special_situation_spread',
            'ai_os_resolve_special_situation_decision'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Add quote ingestion freshness and event scenario analytics for monitored special situations.',
    updated_at = now()
WHERE module_key = 'research_inbox';
