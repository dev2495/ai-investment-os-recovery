BEGIN;

ALTER TABLE portfolio.clients
    ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS communication_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS tax_residency TEXT,
    ADD COLUMN IF NOT EXISTS suitability_review_due_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE portfolio.accounts
    ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS external_account_ref TEXT,
    ADD COLUMN IF NOT EXISTS source_system_id BIGINT REFERENCES core.source_systems(id),
    ADD COLUMN IF NOT EXISTS last_reconciled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE portfolio.manual_holding_updates
    ADD COLUMN IF NOT EXISTS approval_id BIGINT REFERENCES agent.approvals(id),
    ADD COLUMN IF NOT EXISTS decision_notes TEXT,
    ADD COLUMN IF NOT EXISTS decided_by TEXT,
    ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS portfolio.client_onboarding_cases (
    id BIGSERIAL PRIMARY KEY,
    case_key TEXT NOT NULL UNIQUE,
    client_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    risk_profile TEXT NOT NULL,
    objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    investment_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    communication_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    tax_residency TEXT,
    investment_horizon TEXT,
    liquidity_needs TEXT,
    risk_tolerance TEXT,
    risk_capacity TEXT,
    suitability_status TEXT NOT NULL DEFAULT 'needs_review',
    suitability_notes TEXT,
    account_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    sensitivity TEXT NOT NULL DEFAULT 'client_private',
    status TEXT NOT NULL DEFAULT 'pending_approval',
    approval_id BIGINT REFERENCES agent.approvals(id),
    requested_by TEXT NOT NULL DEFAULT 'Devarsh',
    reviewed_by TEXT,
    decision_notes TEXT,
    decided_at TIMESTAMPTZ,
    applied_client_id BIGINT REFERENCES portfolio.clients(id),
    applied_account_id BIGINT REFERENCES portfolio.accounts(id),
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT client_onboarding_status_check CHECK (status IN ('pending_approval','approved','rejected','applied','cancelled')),
    CONSTRAINT client_onboarding_suitability_check CHECK (suitability_status IN ('needs_review','suitable','conditionally_suitable','unsuitable'))
);

CREATE INDEX IF NOT EXISTS idx_client_onboarding_status ON portfolio.client_onboarding_cases(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_onboarding_client ON portfolio.client_onboarding_cases(client_code, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.client_suitability_reviews (
    id BIGSERIAL PRIMARY KEY,
    review_key TEXT NOT NULL UNIQUE,
    client_id BIGINT REFERENCES portfolio.clients(id),
    onboarding_case_id BIGINT REFERENCES portfolio.client_onboarding_cases(id),
    review_type TEXT NOT NULL DEFAULT 'initial',
    risk_tolerance TEXT,
    risk_capacity TEXT,
    investment_horizon TEXT,
    liquidity_needs TEXT,
    objectives JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    allowed_books JSONB NOT NULL DEFAULT '[]'::jsonb,
    restricted_assets JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'needs_review',
    findings TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    next_review_due_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT suitability_status_check CHECK (status IN ('needs_review','suitable','conditionally_suitable','unsuitable','expired'))
);

CREATE INDEX IF NOT EXISTS idx_suitability_client ON portfolio.client_suitability_reviews(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_suitability_status ON portfolio.client_suitability_reviews(status, next_review_due_at);

CREATE TABLE IF NOT EXISTS portfolio.account_change_requests (
    id BIGSERIAL PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT REFERENCES portfolio.accounts(id),
    change_type TEXT NOT NULL,
    requested_values JSONB NOT NULL,
    reason TEXT NOT NULL,
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending_approval',
    approval_id BIGINT REFERENCES agent.approvals(id),
    requested_by TEXT NOT NULL DEFAULT 'Devarsh',
    decided_by TEXT,
    decision_notes TEXT,
    decided_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT account_change_type_check CHECK (change_type IN ('create','update','deactivate','reactivate')),
    CONSTRAINT account_change_status_check CHECK (status IN ('pending_approval','approved','rejected','applied','cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_account_change_status ON portfolio.account_change_requests(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_change_client ON portfolio.account_change_requests(client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.holding_source_observations (
    id BIGSERIAL PRIMARY KEY,
    observation_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    source_label TEXT NOT NULL,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_record_ref TEXT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    instrument_type TEXT NOT NULL DEFAULT 'equity',
    quantity NUMERIC NOT NULL,
    average_price NUMERIC,
    market_price NUMERIC,
    market_value NUMERIC,
    as_of TIMESTAMPTZ NOT NULL,
    content_hash TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_by TEXT NOT NULL DEFAULT 'Data Steward',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_holding_observation_scope ON portfolio.holding_source_observations(account_id, source_label, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_holding_observation_symbol ON portfolio.holding_source_observations(symbol, exchange, as_of DESC);

CREATE TABLE IF NOT EXISTS portfolio.holding_reconciliation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    source_label TEXT NOT NULL,
    source_as_of TIMESTAMPTZ,
    warehouse_as_of TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    source_position_count INTEGER NOT NULL DEFAULT 0,
    warehouse_position_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    break_count INTEGER NOT NULL DEFAULT 0,
    material_break_count INTEGER NOT NULL DEFAULT 0,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Data Steward',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT holding_reconciliation_status_check CHECK (status IN ('running','matched','breaks_found','failed'))
);

CREATE TABLE IF NOT EXISTS portfolio.holding_reconciliation_breaks (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES portfolio.holding_reconciliation_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    break_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_quantity NUMERIC,
    warehouse_quantity NUMERIC,
    quantity_difference NUMERIC,
    source_average_price NUMERIC,
    warehouse_average_price NUMERIC,
    price_difference NUMERIC,
    status TEXT NOT NULL DEFAULT 'open',
    resolution_notes TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT holding_break_status_check CHECK (status IN ('open','acknowledged','resolved','accepted'))
);

CREATE INDEX IF NOT EXISTS idx_holding_break_run ON portfolio.holding_reconciliation_breaks(run_id, severity, status);

CREATE OR REPLACE VIEW portfolio.v_manual_holding_update_queue AS
SELECT mhu.id, mhu.client_code, mhu.account_code, mhu.symbol, mhu.exchange,
       mhu.instrument_type, mhu.quantity, mhu.average_price, mhu.market_price,
       coalesce(mhu.market_value, mhu.quantity * mhu.market_price) effective_market_value,
       mhu.as_of, mhu.update_reason, mhu.status, mhu.created_by, mhu.created_at,
       mhu.applied_at, mhu.approval_id, approval.status approval_status,
       mhu.decision_notes, mhu.decided_by, mhu.decided_at
FROM portfolio.manual_holding_updates mhu
LEFT JOIN agent.approvals approval ON approval.id=mhu.approval_id
ORDER BY CASE mhu.status WHEN 'pending_approval' THEN 1 WHEN 'staged' THEN 2 WHEN 'approved' THEN 3 WHEN 'applied' THEN 4 ELSE 5 END,
         mhu.created_at DESC;

CREATE OR REPLACE FUNCTION portfolio.run_holding_reconciliation(
    p_account_code TEXT,
    p_source_label TEXT,
    p_actor TEXT DEFAULT 'Data Steward'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_account_id BIGINT;
    v_client_id BIGINT;
    v_client_code TEXT;
    v_run_id BIGINT;
    v_run_key TEXT;
BEGIN
    SELECT a.id, a.client_id, c.client_code
      INTO v_account_id, v_client_id, v_client_code
    FROM portfolio.accounts a
    JOIN portfolio.clients c ON c.id = a.client_id
    WHERE a.account_code = p_account_code
    LIMIT 1;

    IF v_account_id IS NULL THEN
        RAISE EXCEPTION 'account not found: %', p_account_code;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM portfolio.holding_source_observations
        WHERE account_id = v_account_id AND source_label = p_source_label
    ) THEN
        RAISE EXCEPTION 'no source observations for account % and source %', p_account_code, p_source_label;
    END IF;

    v_run_key := 'recon-' || v_client_code || '-' || p_account_code || '-' || regexp_replace(lower(p_source_label), '[^a-z0-9]+', '-', 'g') || '-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

    INSERT INTO portfolio.holding_reconciliation_runs (
        run_key, client_id, account_id, source_label, source_as_of, warehouse_as_of,
        status, source_position_count, warehouse_position_count, evidence, created_by
    )
    SELECT v_run_key, v_client_id, v_account_id, p_source_label,
           (SELECT max(as_of) FROM portfolio.holding_source_observations WHERE account_id=v_account_id AND source_label=p_source_label),
           (SELECT max(as_of) FROM portfolio.positions WHERE account_id=v_account_id),
           'running',
           (SELECT count(*) FROM (
               SELECT DISTINCT ON (symbol, exchange, instrument_type) id
               FROM portfolio.holding_source_observations
               WHERE account_id=v_account_id AND source_label=p_source_label
               ORDER BY symbol, exchange, instrument_type, as_of DESC, observed_at DESC
           ) source_latest),
           (SELECT count(*) FROM (
               SELECT DISTINCT ON (symbol, exchange, instrument_type) id
               FROM portfolio.positions
               WHERE account_id=v_account_id
               ORDER BY symbol, exchange, instrument_type, as_of DESC
           ) warehouse_latest),
           jsonb_build_array(jsonb_build_object('table','portfolio.holding_source_observations','account_code',p_account_code,'source_label',p_source_label)),
           p_actor
    RETURNING id INTO v_run_id;

    WITH source_latest AS (
        SELECT DISTINCT ON (symbol, exchange, instrument_type)
               symbol, exchange, instrument_type, quantity, average_price, id, as_of
        FROM portfolio.holding_source_observations
        WHERE account_id=v_account_id AND source_label=p_source_label
        ORDER BY symbol, exchange, instrument_type, as_of DESC, observed_at DESC
    ), warehouse_latest AS (
        SELECT DISTINCT ON (symbol, exchange, instrument_type)
               symbol, exchange, instrument_type, quantity, average_price, id, as_of
        FROM portfolio.positions
        WHERE account_id=v_account_id
        ORDER BY symbol, exchange, instrument_type, as_of DESC
    ), compared AS (
        SELECT coalesce(s.symbol,w.symbol) symbol,
               coalesce(s.exchange,w.exchange) exchange,
               coalesce(s.instrument_type,w.instrument_type) instrument_type,
               s.quantity source_quantity, w.quantity warehouse_quantity,
               s.average_price source_average_price, w.average_price warehouse_average_price,
               s.id source_id, w.id warehouse_id,
               CASE WHEN s.id IS NULL THEN 'warehouse_only'
                    WHEN w.id IS NULL THEN 'source_only'
                    WHEN abs(coalesce(s.quantity,0)-coalesce(w.quantity,0)) > 0.000001 THEN 'quantity_mismatch'
                    WHEN s.average_price IS NOT NULL AND w.average_price IS NOT NULL
                         AND abs(s.average_price-w.average_price) > greatest(0.01, abs(w.average_price)*0.001) THEN 'average_price_mismatch'
                    ELSE NULL END break_type
        FROM source_latest s
        FULL OUTER JOIN warehouse_latest w USING (symbol,exchange,instrument_type)
    )
    INSERT INTO portfolio.holding_reconciliation_breaks (
        run_id, symbol, exchange, instrument_type, break_type, severity,
        source_quantity, warehouse_quantity, quantity_difference,
        source_average_price, warehouse_average_price, price_difference, evidence
    )
    SELECT v_run_id, symbol, exchange, instrument_type, break_type,
           CASE WHEN break_type IN ('source_only','warehouse_only') OR abs(coalesce(source_quantity,0)-coalesce(warehouse_quantity,0)) * coalesce(warehouse_average_price,source_average_price,0) >= 100000
                THEN 'high' ELSE 'medium' END,
           source_quantity, warehouse_quantity,
           coalesce(source_quantity,0)-coalesce(warehouse_quantity,0),
           source_average_price, warehouse_average_price,
           source_average_price-warehouse_average_price,
           jsonb_build_array(
               jsonb_build_object('table','portfolio.holding_source_observations','id',source_id),
               jsonb_build_object('table','portfolio.positions','id',warehouse_id)
           )
    FROM compared WHERE break_type IS NOT NULL;

    UPDATE portfolio.holding_reconciliation_runs r
    SET break_count=(SELECT count(*) FROM portfolio.holding_reconciliation_breaks WHERE run_id=v_run_id),
        material_break_count=(SELECT count(*) FROM portfolio.holding_reconciliation_breaks WHERE run_id=v_run_id AND severity IN ('high','critical')),
        matched_count=greatest(0, least(source_position_count,warehouse_position_count) - (SELECT count(*) FROM portfolio.holding_reconciliation_breaks WHERE run_id=v_run_id AND break_type IN ('quantity_mismatch','average_price_mismatch'))),
        status=CASE WHEN EXISTS (SELECT 1 FROM portfolio.holding_reconciliation_breaks WHERE run_id=v_run_id) THEN 'breaks_found' ELSE 'matched' END,
        completed_at=now()
    WHERE r.id=v_run_id;

    UPDATE portfolio.accounts SET last_reconciled_at=now(), updated_at=now() WHERE id=v_account_id;
    RETURN v_run_id;
END;
$$;

CREATE OR REPLACE VIEW portfolio.v_client_onboarding_queue AS
SELECT c.id, c.case_key, c.client_code, c.display_name, c.risk_profile,
       c.investment_horizon, c.liquidity_needs, c.risk_tolerance, c.risk_capacity,
       c.suitability_status, c.status, c.approval_id, a.status approval_status,
       c.requested_by, c.reviewed_by, c.decision_notes, c.created_at, c.updated_at,
       c.applied_client_id, c.applied_account_id, c.applied_at,
       c.objectives, c.constraints, c.account_payload, c.source_evidence
FROM portfolio.client_onboarding_cases c
LEFT JOIN agent.approvals a ON a.id=c.approval_id
ORDER BY CASE c.status WHEN 'pending_approval' THEN 1 WHEN 'approved' THEN 2 ELSE 3 END, c.created_at DESC;

CREATE OR REPLACE VIEW portfolio.v_client_suitability_control AS
SELECT c.client_code, c.display_name, c.lifecycle_status,
       s.id review_id, s.review_key, s.review_type, s.status suitability_status,
       s.risk_tolerance, s.risk_capacity, s.investment_horizon, s.liquidity_needs,
       s.allowed_books, s.restricted_assets, s.findings, s.reviewed_by,
       s.reviewed_at, s.next_review_due_at,
       CASE WHEN s.id IS NULL THEN 'missing'
            WHEN s.next_review_due_at < now() THEN 'overdue'
            WHEN s.status IN ('unsuitable','expired') THEN 'blocked'
            ELSE 'current' END review_health
FROM portfolio.clients c
LEFT JOIN LATERAL (
    SELECT * FROM portfolio.client_suitability_reviews sr
    WHERE sr.client_id=c.id ORDER BY sr.created_at DESC LIMIT 1
) s ON true
ORDER BY c.display_name;

CREATE OR REPLACE VIEW portfolio.v_holding_reconciliation_control AS
SELECT r.id, r.run_key, c.client_code, c.display_name, a.account_code, a.broker,
       r.source_label, r.source_as_of, r.warehouse_as_of, r.status,
       r.source_position_count, r.warehouse_position_count, r.matched_count,
       r.break_count, r.material_break_count, r.created_by, r.created_at, r.completed_at,
       coalesce((SELECT jsonb_agg(jsonb_build_object(
           'id',b.id,'symbol',b.symbol,'exchange',b.exchange,'break_type',b.break_type,
           'severity',b.severity,'source_quantity',b.source_quantity,
           'warehouse_quantity',b.warehouse_quantity,'status',b.status
       ) ORDER BY CASE b.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,b.symbol)
       FROM portfolio.holding_reconciliation_breaks b WHERE b.run_id=r.id), '[]'::jsonb) breaks
FROM portfolio.holding_reconciliation_runs r
JOIN portfolio.clients c ON c.id=r.client_id
JOIN portfolio.accounts a ON a.id=r.account_id
ORDER BY r.created_at DESC;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES
    ('ai_os_client_onboarding_control','mcp_tool','Charlie Munger','write_with_approval',true,
     'Stage and resolve client onboarding with suitability and evidence.',
     '{"api_routes":["/api/client-office/onboarding/stage","/api/client-office/onboarding/resolve"],"broker_write":false}'::jsonb),
    ('ai_os_client_account_change_control','mcp_tool','Portfolio Manager','write_with_approval',true,
     'Stage and resolve account lifecycle changes.',
     '{"api_routes":["/api/client-office/accounts/stage","/api/client-office/accounts/resolve"],"broker_write":false}'::jsonb),
    ('ai_os_holding_reconciliation_control','mcp_tool','Data Steward','write_db_manual_only',true,
     'Record source holding observations and reconcile them to the warehouse.',
     '{"api_routes":["/api/client-office/holding-observations","/api/client-office/reconciliation/run"],"broker_write":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent=EXCLUDED.owning_agent,permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,description=EXCLUDED.description,config=EXCLUDED.config;

UPDATE agent.tool_registry
SET permission_level='write_with_approval',
    description=CASE tool_name
        WHEN 'ai_os_upsert_client' THEN 'Compatibility tool that stages governed onboarding; it cannot directly activate a client.'
        WHEN 'ai_os_stage_holding_update' THEN 'Stages a holding proposal and dedicated approval; it cannot alter the position book.'
        WHEN 'ai_os_apply_holding_update' THEN 'Resolves an evidence-backed holding approval through the governed API; no broker write.'
    END,
    config=config || '{"governed_api":true,"direct_sql_disabled":true,"broker_write":false}'::jsonb
WHERE tool_name IN ('ai_os_upsert_client','ai_os_stage_holding_update','ai_os_apply_holding_update');

INSERT INTO agent.skills (
    skill_key,skill_name,skill_family,skill_type,owner_department,status,
    execution_mode,permission_level,trigger_phrases,input_sources,
    output_targets,required_tools,risk_notes,prompt_template,config
) VALUES
    ('client_onboarding_governance','Client Onboarding Governance','client_office','operational','Client Office','active',
     'human_gated','write_with_approval',ARRAY['add client','onboard client','new folio'],
     ARRAY['manual client instruction','source evidence'],ARRAY['portfolio.client_onboarding_cases','portfolio.clients','portfolio.accounts','agent.approvals'],
     ARRAY['ai_os_client_onboarding_control'],'Never activate a client without suitability and human approval.',
     'Validate objectives, horizon, risk tolerance, risk capacity, restrictions, account mapping, and evidence. Stage only; Charlie or Devarsh decides.',
     '{"broker_write":false,"sensitivity":"client_private"}'::jsonb),
    ('client_account_lifecycle','Client Account Lifecycle','client_office','operational','Client Office','active',
     'human_gated','write_with_approval',ARRAY['add account','update broker account','deactivate account'],
     ARRAY['portfolio.clients','manual client instruction'],ARRAY['portfolio.account_change_requests','portfolio.accounts','agent.approvals'],
     ARRAY['ai_os_client_account_change_control'],'Account changes alter reporting scope and require evidence plus approval.',
     'Stage account creation or maintenance, preserve source evidence, and never call a broker write API.',
     '{"broker_write":false,"sensitivity":"client_private"}'::jsonb),
    ('multi_source_holding_reconciliation','Multi-Source Holding Reconciliation','data_ops','deterministic','Data Engineering','active',
     'worker_deterministic','write_db_manual_only',ARRAY['reconcile holdings','compare broker holdings','position breaks'],
     ARRAY['broker statement','p2cursor','algo source','manual source'],ARRAY['portfolio.holding_source_observations','portfolio.holding_reconciliation_runs','portfolio.holding_reconciliation_breaks'],
     ARRAY['ai_os_holding_reconciliation_control'],'Observations are evidence, not authorization to change the position book.',
     'Normalize source rows, compare the latest source snapshot with the warehouse, classify breaks, and route material differences for review.',
     '{"auto_apply":false,"quantity_tolerance":0.000001}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name,owner_department=EXCLUDED.owner_department,
    status=EXCLUDED.status,permission_level=EXCLUDED.permission_level,
    required_tools=EXCLUDED.required_tools,risk_notes=EXCLUDED.risk_notes,
    prompt_template=EXCLUDED.prompt_template,config=EXCLUDED.config,updated_at=now();

INSERT INTO agent.agent_skill_map (agent_name,skill_key,proficiency,is_primary,activation_rules)
VALUES
    ('Charlie Munger','client_onboarding_governance','expert',true,'{"approval_owner":true}'::jsonb),
    ('Portfolio Manager','client_onboarding_governance','expert',false,'{"prepares_case":true}'::jsonb),
    ('Portfolio Manager','client_account_lifecycle','expert',true,'{"approval_owner":true}'::jsonb),
    ('Client Reporting Agent','client_account_lifecycle','working',false,'{"consumes_account_scope":true}'::jsonb),
    ('Data Steward','multi_source_holding_reconciliation','expert',true,'{"default_for":"holding reconciliation"}'::jsonb),
    ('Portfolio Risk Analyst','multi_source_holding_reconciliation','working',false,'{"reviews_material_breaks":true}'::jsonb)
ON CONFLICT (agent_name,skill_key) DO UPDATE SET
    proficiency=EXCLUDED.proficiency,is_primary=EXCLUDED.is_primary,
    activation_rules=EXCLUDED.activation_rules,updated_at=now();

INSERT INTO agent.workflow_registry (
    workflow_key,workflow_name,workflow_type,owner_agent,trigger_type,status,
    permission_level,input_sources,output_targets,approval_required,
    schedule_hint,notes,metadata
) VALUES
    ('governed_client_onboarding_v1','Governed Client Onboarding v1','client_office','Charlie Munger','manual','active','write_with_approval',
     ARRAY['manual client intake','source evidence'],ARRAY['portfolio.client_onboarding_cases','portfolio.client_suitability_reviews','portfolio.clients','portfolio.accounts','agent.approvals'],true,
     'on demand','Suitability first; activation only inside the dedicated approval transaction.',
     '{"ui_workspace":"clients","broker_write":false}'::jsonb),
    ('client_account_lifecycle_v1','Client Account Lifecycle v1','client_office','Portfolio Manager','manual','active','write_with_approval',
     ARRAY['manual client instruction'],ARRAY['portfolio.account_change_requests','portfolio.accounts','agent.approvals'],true,
     'on demand','Account create, update, deactivate, and reactivate are evidence-backed and approval-gated.',
     '{"ui_workspace":"clients","broker_write":false}'::jsonb),
    ('multi_source_holding_reconciliation_v1','Multi-Source Holding Reconciliation v1','data_ops','Data Steward','manual_or_connector','active','write_db_manual_only',
     ARRAY['broker holdings','p2cursor holdings','algo holdings','manual holdings'],ARRAY['portfolio.holding_source_observations','portfolio.holding_reconciliation_runs','portfolio.holding_reconciliation_breaks','agent.inbox_items'],false,
     'after every holdings import','Reconciliation creates evidence and breaks; it never auto-applies positions.',
     '{"ui_workspace":"clients","auto_apply":false}'::jsonb)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name=EXCLUDED.workflow_name,owner_agent=EXCLUDED.owner_agent,
    status=EXCLUDED.status,permission_level=EXCLUDED.permission_level,
    input_sources=EXCLUDED.input_sources,output_targets=EXCLUDED.output_targets,
    approval_required=EXCLUDED.approval_required,notes=EXCLUDED.notes,
    metadata=EXCLUDED.metadata,updated_at=now();

COMMIT;
