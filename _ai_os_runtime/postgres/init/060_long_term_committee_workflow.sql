CREATE TABLE IF NOT EXISTS portfolio.long_term_committee_reviews (
    id BIGSERIAL PRIMARY KEY,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    review_key TEXT NOT NULL UNIQUE,
    review_status TEXT NOT NULL DEFAULT 'opened',
    recommended_decision TEXT NOT NULL DEFAULT 'research_more',
    decision_status TEXT NOT NULL DEFAULT 'pending',
    memo_status TEXT NOT NULL DEFAULT 'not_generated',
    memo_note_path TEXT,
    memo_generated_at TIMESTAMPTZ,
    committee_members JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_followups JSONB NOT NULL DEFAULT '[]'::jsonb,
    proposed_action JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    final_decision TEXT,
    decision_notes TEXT,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_long_term_committee_reviews_thesis ON portfolio.long_term_committee_reviews (holding_thesis_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_long_term_committee_reviews_status ON portfolio.long_term_committee_reviews (decision_status, review_status, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.long_term_committee_decisions (
    id BIGSERIAL PRIMARY KEY,
    committee_review_id BIGINT NOT NULL REFERENCES portfolio.long_term_committee_reviews(id) ON DELETE CASCADE,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    decision TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'final',
    decision_notes TEXT,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    decided_by TEXT NOT NULL DEFAULT 'Devarsh',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_long_term_committee_decisions_review ON portfolio.long_term_committee_decisions (committee_review_id);
CREATE INDEX IF NOT EXISTS idx_long_term_committee_decisions_thesis ON portfolio.long_term_committee_decisions (holding_thesis_id);

CREATE OR REPLACE VIEW portfolio.v_long_term_committee_queue AS
SELECT
    review.id,
    review.review_key,
    review.holding_thesis_id,
    thesis.symbol,
    thesis.exchange,
    thesis.company_name,
    thesis.thesis_title,
    thesis.thesis_status,
    thesis.decision_status AS thesis_decision_status,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients,
    control.checklist_count,
    control.checklist_complete_count,
    control.valuation_model_count,
    control.valuation_complete_count,
    review.review_status,
    review.recommended_decision,
    review.decision_status,
    review.memo_status,
    review.memo_note_path,
    review.committee_members,
    review.evidence_summary,
    review.source_gaps,
    review.required_followups,
    review.proposed_action,
    review.approval_id,
    approval.status AS approval_status,
    approval.owner_agent AS approval_owner_agent,
    approval.risk_level AS approval_risk_level,
    review.task_id,
    task.status AS task_status,
    task.owner_agent AS task_owner_agent,
    review.final_decision,
    review.decision_notes,
    review.live_execution_allowed,
    review.capital_action_allowed,
    review.decided_by,
    review.decided_at,
    review.created_by,
    review.created_at,
    review.updated_at
FROM portfolio.long_term_committee_reviews review
JOIN portfolio.holding_theses thesis ON thesis.id = review.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = thesis.id
LEFT JOIN agent.approvals approval ON approval.id = review.approval_id
LEFT JOIN agent.tasks task ON task.id = review.task_id
ORDER BY review.created_at DESC, review.id DESC;

CREATE OR REPLACE FUNCTION portfolio.open_long_term_committee_review(
    p_holding_thesis_id BIGINT,
    p_actor TEXT DEFAULT 'Long-Term Portfolio Manager'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_thesis portfolio.holding_theses%ROWTYPE;
    v_control portfolio.v_long_term_thesis_control%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Long-Term Portfolio Manager');
    v_review_key TEXT;
    v_review_id BIGINT;
    v_task_id BIGINT;
    v_approval_id BIGINT;
    v_research_packets INTEGER := 0;
    v_latest_packet TEXT;
    v_latest_packet_sources JSONB := '{}'::jsonb;
    v_source_gaps JSONB := '[]'::jsonb;
    v_required_followups JSONB := '[]'::jsonb;
    v_recommended_decision TEXT := 'research_more';
    v_evidence_summary JSONB;
BEGIN
    SELECT * INTO v_thesis
    FROM portfolio.holding_theses
    WHERE id = p_holding_thesis_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'holding_thesis_id % not found', p_holding_thesis_id;
    END IF;

    SELECT * INTO v_control
    FROM portfolio.v_long_term_thesis_control
    WHERE id = p_holding_thesis_id;

    SELECT count(*), max(note_path)
    INTO v_research_packets, v_latest_packet
    FROM portfolio.holding_thesis_research_updates
    WHERE holding_thesis_id = p_holding_thesis_id
      AND update_kind = 'research_packet';

    SELECT source_summary INTO v_latest_packet_sources
    FROM portfolio.holding_thesis_research_updates
    WHERE holding_thesis_id = p_holding_thesis_id
      AND update_kind = 'research_packet'
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_research_packets = 0 THEN
        v_source_gaps := v_source_gaps || jsonb_build_array(jsonb_build_object('gap', 'research_packet_missing', 'required_action', 'Generate source-backed research packet before committee decision.'));
    END IF;

    IF coalesce(v_control.checklist_count, 0) = 0 OR coalesce(v_control.checklist_complete_count, 0) < coalesce(v_control.checklist_count, 0) THEN
        v_source_gaps := v_source_gaps || jsonb_build_array(jsonb_build_object('gap', 'checklists_incomplete', 'complete', coalesce(v_control.checklist_complete_count, 0), 'total', coalesce(v_control.checklist_count, 0)));
    END IF;

    IF coalesce(v_control.valuation_model_count, 0) = 0 OR coalesce(v_control.valuation_complete_count, 0) < coalesce(v_control.valuation_model_count, 0) THEN
        v_source_gaps := v_source_gaps || jsonb_build_array(jsonb_build_object('gap', 'valuation_models_incomplete', 'complete', coalesce(v_control.valuation_complete_count, 0), 'total', coalesce(v_control.valuation_model_count, 0)));
    END IF;

    IF coalesce((v_latest_packet_sources->>'filings')::INTEGER, 0) = 0 THEN
        v_source_gaps := v_source_gaps || jsonb_build_array(jsonb_build_object('gap', 'company_filing_evidence_missing', 'required_action', 'Attach filings, annual reports, or transcripts before full thesis approval.'));
    END IF;

    v_required_followups := jsonb_build_array(
        jsonb_build_object('owner_agent', 'Company Analyst', 'action', 'Complete business model and segment economics with cited evidence.'),
        jsonb_build_object('owner_agent', 'Industry Analyst', 'action', 'Complete industry structure and competitive position.'),
        jsonb_build_object('owner_agent', 'Management Analyst', 'action', 'Complete promoter, governance, incentives, and capital allocation checks.'),
        jsonb_build_object('owner_agent', 'Financial Statement Analyst', 'action', 'Complete financial quality and cash-flow checks.'),
        jsonb_build_object('owner_agent', 'Forensic Accounting Agent', 'action', 'Complete accounting red-flag review.'),
        jsonb_build_object('owner_agent', 'Valuation Agent', 'action', 'Complete valuation module with assumptions and evidence.'),
        jsonb_build_object('owner_agent', 'Bear Case Agent', 'action', 'Write disconfirming evidence and thesis-killer case.'),
        jsonb_build_object('owner_agent', 'Risk Agent', 'action', 'Review concentration, liquidity, client suitability, and cross-book risk.')
    );

    IF jsonb_array_length(v_source_gaps) = 0 THEN
        v_recommended_decision := 'monitor';
    END IF;

    v_evidence_summary := jsonb_build_object(
        'holding_thesis_id', v_thesis.id,
        'symbol', v_thesis.symbol,
        'exchange', v_thesis.exchange,
        'long_term_gross_exposure', coalesce(v_control.long_term_gross_exposure, 0),
        'client_count', coalesce(v_control.client_count, 0),
        'checklist_count', coalesce(v_control.checklist_count, 0),
        'checklist_complete_count', coalesce(v_control.checklist_complete_count, 0),
        'valuation_model_count', coalesce(v_control.valuation_model_count, 0),
        'valuation_complete_count', coalesce(v_control.valuation_complete_count, 0),
        'research_packet_count', v_research_packets,
        'latest_research_packet', v_latest_packet,
        'latest_packet_sources', coalesce(v_latest_packet_sources, '{}'::jsonb)
    );

    v_review_key := 'ltic-' || v_thesis.id::TEXT || '-' || to_char(now(), 'YYYYMMDDHH24MISS');

    INSERT INTO agent.tasks (
        title, objective, owner_agent, status, priority, approval_required,
        source_kind, source_ref, output_format, evidence
    )
    VALUES (
        'Long-Term Investment Committee review: ' || v_thesis.symbol,
        'Review thesis, research packet, checklist gaps, valuation gaps, bear case, and risk memo. No capital action is authorized by opening this review.',
        'Long-Term Portfolio Manager',
        'queued',
        'high',
        true,
        'portfolio.holding_theses',
        v_thesis.id::TEXT,
        'long_term_committee_memo',
        jsonb_build_array(v_evidence_summary)
    )
    RETURNING id INTO v_task_id;

    INSERT INTO agent.approvals (
        task_id, approval_type, title, owner_agent, risk_level,
        status, requested_action, rationale
    )
    VALUES (
        v_task_id,
        'long_term_committee_review',
        'Long-Term Investment Committee decision: ' || v_thesis.symbol,
        'Charlie Munger',
        CASE WHEN jsonb_array_length(v_source_gaps) > 0 THEN 'high' ELSE 'medium' END,
        'pending',
        jsonb_build_object(
            'holding_thesis_id', v_thesis.id,
            'symbol', v_thesis.symbol,
            'recommended_decision', v_recommended_decision,
            'human_decision_required', true,
            'capital_action_allowed', false,
            'live_execution_allowed', false
        ),
        'Committee review can decide research/monitor/watchlist/hold status only. Any buy/add/trim/sell action requires a separate future approval workflow.'
    )
    RETURNING id INTO v_approval_id;

    INSERT INTO portfolio.long_term_committee_reviews (
        holding_thesis_id, review_key, review_status, recommended_decision,
        committee_members, evidence_summary, source_gaps, required_followups,
        proposed_action, approval_id, task_id, created_by
    )
    VALUES (
        v_thesis.id,
        v_review_key,
        'opened',
        v_recommended_decision,
        jsonb_build_array(
            'Charlie Munger',
            'Long-Term Portfolio Manager',
            'Company Analyst',
            'Industry Analyst',
            'Management Analyst',
            'Financial Statement Analyst',
            'Forensic Accounting Agent',
            'Valuation Agent',
            'Bear Case Agent',
            'Risk Agent',
            'Capital Allocation Officer'
        ),
        v_evidence_summary,
        v_source_gaps,
        v_required_followups,
        jsonb_build_object(
            'recommended_decision', v_recommended_decision,
            'capital_action_allowed', false,
            'live_execution_allowed', false,
            'separate_trade_approval_required', true
        ),
        v_approval_id,
        v_task_id,
        v_actor
    )
    RETURNING id INTO v_review_id;

    INSERT INTO agent.inbox_items (
        task_id, title, owner_agent, status, priority, recommended_action,
        evidence, target_workspace
    )
    VALUES (
        v_task_id,
        'Long-Term committee review opened: ' || v_thesis.symbol,
        'Charlie Munger',
        'needs_review',
        'high',
        'Generate the committee memo, review evidence gaps, then decide research_more/monitor/watchlist/hold/reject. No buy/sell action is authorized.',
        jsonb_build_array(jsonb_build_object('long_term_committee_review_id', v_review_id), v_evidence_summary),
        'Long-Term Office'
    );

    UPDATE portfolio.holding_theses
    SET decision_status = 'committee_review_open',
        updated_by = v_actor,
        updated_at = now()
    WHERE id = v_thesis.id;

    RETURN jsonb_build_object(
        'long_term_committee_review_id', v_review_id,
        'holding_thesis_id', v_thesis.id,
        'approval_id', v_approval_id,
        'task_id', v_task_id,
        'review_status', 'opened',
        'recommended_decision', v_recommended_decision,
        'source_gap_count', jsonb_array_length(v_source_gaps),
        'capital_action_allowed', false,
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION portfolio.resolve_long_term_committee_decision(
    p_committee_review_id BIGINT,
    p_decision TEXT,
    p_actor TEXT DEFAULT 'Devarsh',
    p_decision_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_review portfolio.long_term_committee_reviews%ROWTYPE;
    v_decision TEXT := lower(trim(coalesce(p_decision, '')));
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Devarsh');
    v_notes TEXT := nullif(trim(coalesce(p_decision_notes, '')), '');
    v_decision_id BIGINT;
    v_review_status TEXT;
    v_thesis_status TEXT;
    v_thesis_decision_status TEXT;
    v_approval_status TEXT;
    v_inbox_owner TEXT;
    v_inbox_action TEXT;
BEGIN
    IF v_decision NOT IN ('reject', 'research_more', 'monitor', 'approve_watchlist', 'approve_hold') THEN
        RAISE EXCEPTION 'decision must be reject, research_more, monitor, approve_watchlist, or approve_hold';
    END IF;

    SELECT * INTO v_review
    FROM portfolio.long_term_committee_reviews
    WHERE id = p_committee_review_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'long_term_committee_review_id % not found', p_committee_review_id;
    END IF;

    IF v_review.decision_status = 'final' THEN
        RAISE EXCEPTION 'long_term_committee_review_id % already has final decision %', p_committee_review_id, v_review.final_decision;
    END IF;

    IF coalesce(v_review.memo_status, 'not_generated') <> 'generated' THEN
        RAISE EXCEPTION 'committee memo must be generated before a final decision';
    END IF;

    IF v_decision = 'reject' THEN
        v_review_status := 'rejected';
        v_thesis_status := 'rejected';
        v_thesis_decision_status := 'committee_rejected';
        v_approval_status := 'rejected';
        v_inbox_owner := 'Research Analyst';
        v_inbox_action := 'Archive or rewrite the thesis. Committee rejected the current evidence package.';
    ELSIF v_decision = 'research_more' THEN
        v_review_status := 'research_required';
        v_thesis_status := 'under_research';
        v_thesis_decision_status := 'committee_research_required';
        v_approval_status := 'rejected';
        v_inbox_owner := 'Long-Term Portfolio Manager';
        v_inbox_action := 'Assign specialist agents to close source gaps, checklist gaps, valuation gaps, bear case, and risk review.';
    ELSIF v_decision = 'monitor' THEN
        v_review_status := 'monitor_only';
        v_thesis_status := 'monitor_only';
        v_thesis_decision_status := 'committee_monitor';
        v_approval_status := 'approved';
        v_inbox_owner := 'Portfolio Manager';
        v_inbox_action := 'Monitor thesis and keep review cadence active. No capital action authorized.';
    ELSIF v_decision = 'approve_watchlist' THEN
        v_review_status := 'watchlist_approved';
        v_thesis_status := 'watchlist';
        v_thesis_decision_status := 'committee_watchlist_approved';
        v_approval_status := 'approved';
        v_inbox_owner := 'Portfolio Manager';
        v_inbox_action := 'Move to approved watchlist. Any buy/add action requires separate future approval.';
    ELSE
        v_review_status := 'hold_approved';
        v_thesis_status := 'approved_hold';
        v_thesis_decision_status := 'committee_hold_approved';
        v_approval_status := 'approved';
        v_inbox_owner := 'Portfolio Manager';
        v_inbox_action := 'Hold thesis approved. Any add/trim/sell action requires separate future approval.';
    END IF;

    INSERT INTO portfolio.long_term_committee_decisions (
        committee_review_id, holding_thesis_id, approval_id, decision,
        decision_status, decision_notes, live_execution_allowed,
        capital_action_allowed, decided_by, evidence
    )
    VALUES (
        v_review.id,
        v_review.holding_thesis_id,
        v_review.approval_id,
        v_decision,
        'final',
        v_notes,
        false,
        false,
        v_actor,
        jsonb_build_array(
            jsonb_build_object('long_term_committee_review_id', v_review.id),
            jsonb_build_object('memo_note_path', v_review.memo_note_path),
            jsonb_build_object('recommended_decision', v_review.recommended_decision),
            jsonb_build_object('capital_action_allowed', false),
            jsonb_build_object('live_execution_allowed', false)
        )
    )
    RETURNING id INTO v_decision_id;

    UPDATE portfolio.long_term_committee_reviews
    SET review_status = v_review_status,
        final_decision = v_decision,
        decision_status = 'final',
        decision_notes = v_notes,
        live_execution_allowed = false,
        capital_action_allowed = false,
        decided_by = v_actor,
        decided_at = now(),
        updated_at = now()
    WHERE id = v_review.id;

    UPDATE agent.approvals
    SET status = v_approval_status,
        decided_by = v_actor,
        decided_at = now()
    WHERE id = v_review.approval_id
      AND status = 'pending';

    UPDATE portfolio.holding_theses
    SET thesis_status = v_thesis_status,
        decision_status = v_thesis_decision_status,
        last_reviewed_at = now(),
        updated_by = v_actor,
        updated_at = now()
    WHERE id = v_review.holding_thesis_id;

    INSERT INTO agent.inbox_items (
        task_id, title, owner_agent, status, priority, recommended_action,
        evidence, target_workspace
    )
    VALUES (
        v_review.task_id,
        'Long-Term committee decision: thesis ' || v_review.holding_thesis_id::TEXT || ' -> ' || v_decision,
        v_inbox_owner,
        'needs_review',
        CASE WHEN v_decision IN ('approve_hold', 'approve_watchlist') THEN 'high' ELSE 'medium' END,
        v_inbox_action,
        jsonb_build_array(
            jsonb_build_object('long_term_committee_review_id', v_review.id),
            jsonb_build_object('long_term_committee_decision_id', v_decision_id),
            jsonb_build_object('holding_thesis_id', v_review.holding_thesis_id),
            jsonb_build_object('capital_action_allowed', false),
            jsonb_build_object('live_execution_allowed', false)
        ),
        'Long-Term Office'
    );

    RETURN jsonb_build_object(
        'long_term_committee_review_id', v_review.id,
        'long_term_committee_decision_id', v_decision_id,
        'holding_thesis_id', v_review.holding_thesis_id,
        'approval_id', v_review.approval_id,
        'decision', v_decision,
        'review_status', v_review_status,
        'thesis_status', v_thesis_status,
        'thesis_decision_status', v_thesis_decision_status,
        'approval_status', v_approval_status,
        'capital_action_allowed', false,
        'live_execution_allowed', false
    );
END;
$$;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_open_long_term_committee_review',
        'mcp_tool',
        'Long-Term Portfolio Manager',
        'write_with_approval',
        true,
        'Open a Long-Term Investment Committee review for a holding thesis. No capital action is authorized.',
        '{"function":"portfolio.open_long_term_committee_review","writes":["portfolio.long_term_committee_reviews","agent.tasks","agent.approvals","agent.inbox_items","portfolio.holding_theses"],"reads":["portfolio.v_long_term_thesis_control","portfolio.holding_thesis_research_updates"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_generate_long_term_committee_memo',
        'mcp_tool',
        'Long-Term Portfolio Manager',
        'write_with_approval',
        true,
        'Generate an Obsidian Long-Term Investment Committee memo from thesis evidence and source gaps.',
        '{"script":"_ai_os_runtime/scripts/generate_long_term_committee_memo.py","writes":["portfolio.long_term_committee_reviews","knowledge.obsidian_notes","agent.inbox_items"],"reads":["portfolio.v_long_term_committee_queue","portfolio.v_long_term_thesis_checklists","portfolio.v_long_term_valuation_models","portfolio.v_long_term_research_updates"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_resolve_long_term_committee_decision',
        'mcp_tool',
        'Charlie Munger',
        'write_with_approval',
        true,
        'Resolve a Long-Term Investment Committee decision without authorizing buy/sell/trim/add execution.',
        '{"function":"portfolio.resolve_long_term_committee_decision","writes":["portfolio.long_term_committee_decisions","portfolio.long_term_committee_reviews","portfolio.holding_theses","agent.approvals","agent.inbox_items"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    )
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
            'portfolio.long_term_committee_reviews',
            'portfolio.long_term_committee_decisions',
            'portfolio.v_long_term_committee_queue'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_open_long_term_committee_review',
            'ai_os_generate_long_term_committee_memo',
            'ai_os_resolve_long_term_committee_decision'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Long-Term committee workflow is registered; open reviews, generate memos, then resolve no-trade decisions.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox');
