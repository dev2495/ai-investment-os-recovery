CREATE TABLE IF NOT EXISTS strategy.strategy_discovery_triage_decisions (
    id BIGSERIAL PRIMARY KEY,
    discovery_candidate_id BIGINT NOT NULL REFERENCES strategy.strategy_discovery_candidates(id) ON DELETE CASCADE,
    generated_idea_id BIGINT REFERENCES strategy.generated_ideas(id) ON DELETE SET NULL,
    optimizer_run_id BIGINT REFERENCES strategy.user_defined_optimizer_runs(id) ON DELETE SET NULL,
    decision TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'final',
    routed_to_agent TEXT,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    committee_review_id BIGINT REFERENCES strategy.committee_reviews(id) ON DELETE SET NULL,
    decision_notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    decided_by TEXT NOT NULL DEFAULT 'Charlie Munger',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_triage_candidate
ON strategy.strategy_discovery_triage_decisions (discovery_candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_triage_decision
ON strategy.strategy_discovery_triage_decisions (decision);

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_triage_queue AS
WITH latest_decision AS (
    SELECT DISTINCT ON (decision.discovery_candidate_id)
        decision.*
    FROM strategy.strategy_discovery_triage_decisions decision
    ORDER BY decision.discovery_candidate_id, decision.created_at DESC, decision.id DESC
)
SELECT
    candidate.id,
    candidate.run_key,
    candidate.discovery_key,
    candidate.source_kind,
    candidate.source_ref,
    candidate.title,
    candidate.symbols,
    candidate.universe,
    candidate.timeframe,
    candidate.template,
    candidate.thesis,
    candidate.catalyst,
    candidate.priority_score,
    candidate.risk_score,
    candidate.route_to_optimizer,
    candidate.generated_idea_id,
    candidate.idea_key,
    candidate.generated_idea_status,
    candidate.optimizer_run_id,
    candidate.optimizer_run_key,
    candidate.optimizer_status,
    candidate.optimizer_candidate_id,
    candidate.backtest_run_id,
    candidate.optimization_run_id,
    candidate.research_gate,
    candidate.next_required_action,
    candidate.status AS discovery_status,
    coalesce(latest_decision.decision, 'unreviewed') AS triage_decision,
    coalesce(latest_decision.decision_status, 'pending') AS triage_status,
    latest_decision.routed_to_agent,
    latest_decision.inbox_item_id,
    latest_decision.approval_id,
    latest_decision.committee_review_id,
    latest_decision.decision_notes,
    latest_decision.decided_by,
    latest_decision.created_at AS triaged_at,
    CASE
        WHEN latest_decision.id IS NOT NULL THEN 'triaged'
        WHEN candidate.optimizer_status = 'completed' THEN 'committee_or_model_validation_review'
        WHEN candidate.research_gate = 'component_or_research_reference' THEN 'convert_reference_to_strategy'
        WHEN candidate.route_to_optimizer THEN 'route_or_repair_optimizer'
        ELSE 'request_more_evidence'
    END AS recommended_triage_action,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed,
    candidate.created_at
FROM strategy.v_strategy_discovery_candidates candidate
LEFT JOIN latest_decision ON latest_decision.discovery_candidate_id = candidate.id
ORDER BY
    CASE WHEN latest_decision.id IS NULL THEN 0 ELSE 1 END,
    candidate.priority_score DESC NULLS LAST,
    candidate.created_at DESC,
    candidate.id DESC;

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_triage_decisions AS
SELECT
    decision.id,
    decision.discovery_candidate_id,
    candidate.discovery_key,
    candidate.title,
    candidate.source_kind,
    candidate.symbols,
    decision.generated_idea_id,
    decision.optimizer_run_id,
    decision.decision,
    decision.decision_status,
    decision.routed_to_agent,
    decision.inbox_item_id,
    inbox.status AS inbox_status,
    decision.approval_id,
    approval.status AS approval_status,
    decision.committee_review_id,
    committee.review_status AS committee_review_status,
    committee.recommended_decision AS committee_recommended_decision,
    decision.decision_notes,
    decision.evidence,
    decision.decided_by,
    decision.created_at,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed
FROM strategy.strategy_discovery_triage_decisions decision
JOIN strategy.strategy_discovery_candidates raw_candidate ON raw_candidate.id = decision.discovery_candidate_id
JOIN strategy.v_strategy_discovery_candidates candidate ON candidate.id = raw_candidate.id
LEFT JOIN agent.inbox_items inbox ON inbox.id = decision.inbox_item_id
LEFT JOIN agent.approvals approval ON approval.id = decision.approval_id
LEFT JOIN strategy.committee_reviews committee ON committee.id = decision.committee_review_id
ORDER BY decision.created_at DESC, decision.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_resolve_strategy_discovery_triage', 'mcp_tool', 'Charlie Munger', 'write_with_approval', true,
     'Resolve a discovered strategy idea into reject, more evidence, Quant Lab, Special Situations, or committee-review routing. This never approves live execution.',
     '{"script":"_ai_os_runtime/scripts/resolve_strategy_discovery_triage.py","reads":["strategy.v_strategy_discovery_triage_queue"],"writes":["strategy.strategy_discovery_triage_decisions","agent.inbox_items","strategy.committee_reviews","agent.approvals"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_strategy_discovery_triage_queue', 'mcp_tool', 'Charlie Munger', 'read_only', true,
     'Read discovered strategy idea triage queue, latest decisions, routing, inbox, approval, and committee status.',
     '{"reads":["strategy.v_strategy_discovery_triage_queue","strategy.v_strategy_discovery_triage_decisions"],"live_execution_allowed":false}'::jsonb)
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
            'strategy.strategy_discovery_triage_decisions',
            'strategy.v_strategy_discovery_triage_queue',
            'strategy.v_strategy_discovery_triage_decisions'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_resolve_strategy_discovery_triage',
            'ai_os_strategy_discovery_triage_queue'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Charlie/Jarvis can triage discovered strategy ideas into reject, research-more, Quant Lab, Special Situations, or committee-review lanes.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'trading_desk', 'runtime');
