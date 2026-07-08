CREATE TABLE IF NOT EXISTS research.special_situation_memos (
    id BIGSERIAL PRIMARY KEY,
    special_terms_id BIGINT NOT NULL REFERENCES research.special_situation_terms(id) ON DELETE CASCADE,
    filing_id BIGINT NOT NULL REFERENCES research.corporate_filings(id) ON DELETE CASCADE,
    filing_event_id BIGINT REFERENCES research.filing_events(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    memo_title TEXT NOT NULL,
    memo_status TEXT NOT NULL DEFAULT 'draft',
    note_path TEXT,
    summary TEXT,
    extracted_terms JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_followups JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL DEFAULT 'Special Situations Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (special_terms_id)
);

CREATE INDEX IF NOT EXISTS idx_special_situation_memos_event ON research.special_situation_memos (event_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_special_situation_memos_symbol ON research.special_situation_memos (symbol);
CREATE INDEX IF NOT EXISTS idx_special_situation_memos_status ON research.special_situation_memos (memo_status);

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
    memo.created_by,
    memo.created_at,
    memo.updated_at
FROM research.special_situation_memos memo
JOIN research.corporate_filings cf ON cf.id = memo.filing_id
LEFT JOIN agent.tasks task ON task.id = memo.task_id
LEFT JOIN agent.approvals approval ON approval.id = memo.approval_id
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
    memo.approval_status AS special_memo_approval_status
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
    ('ai_os_generate_special_situation_memo', 'mcp_tool', 'Special Situations Agent', 'write_with_approval', true, 'Generate Obsidian special-situation memo and route it to Charlie or Investment Committee review.', '{"script":"_ai_os_runtime/scripts/generate_special_situation_memo.py","writes":["research.special_situation_memos","agent.tasks","agent.inbox_items","agent.approvals","knowledge.obsidian_notes","filesystem:ai memory"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_special_situation_memos', 'mcp_tool', 'Special Situations Agent', 'read_only', true, 'Read generated special-situation memos and review status.', '{"reads":["research.v_special_situation_memos","research.v_special_situation_inbox"]}'::jsonb)
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
            'research.special_situation_memos',
            'research.v_special_situation_memos'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_generate_special_situation_memo',
            'ai_os_special_situation_memos'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Generate special-situation memos, route them to committee review, then add arbitrage spread tracking.',
    updated_at = now()
WHERE module_key = 'research_inbox';

UPDATE agent.skills
SET output_targets = ARRAY(
        SELECT DISTINCT target
        FROM unnest(output_targets || ARRAY['research.special_situation_memos','research.v_special_situation_memos']::TEXT[]) AS target
    ),
    config = config || '{"special_situation_memo_status":"deterministic_v1"}'::jsonb,
    updated_at = now()
WHERE skill_key IN ('detect_special_situation', 'corporate_action_detector', 'analyze_corporate_filing');
