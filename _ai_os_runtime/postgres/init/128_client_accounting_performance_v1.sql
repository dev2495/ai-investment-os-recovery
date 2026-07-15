BEGIN;

CREATE TABLE IF NOT EXISTS portfolio.cash_ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    entry_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    entry_ts TIMESTAMPTZ NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN (
        'opening_balance','contribution','withdrawal','dividend','interest','fee',
        'tax','broker_charge','trade_settlement','cash_adjustment','transfer'
    )),
    flow_class TEXT NOT NULL CHECK (flow_class IN ('external','income','expense','internal','balance')),
    amount NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    description TEXT NOT NULL,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_ref TEXT,
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval','posted','rejected','reversed')),
    approval_id BIGINT REFERENCES agent.approvals(id),
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    decided_by TEXT,
    decision_notes TEXT,
    decided_at TIMESTAMPTZ,
    posted_at TIMESTAMPTZ,
    reversal_of_id BIGINT REFERENCES portfolio.cash_ledger_entries(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cash_entry_nonzero CHECK (amount <> 0),
    CONSTRAINT cash_entry_source_required CHECK (jsonb_array_length(source_evidence) > 0 OR source_ref IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_cash_ledger_account_ts ON portfolio.cash_ledger_entries(account_id, entry_ts DESC);
CREATE INDEX IF NOT EXISTS idx_cash_ledger_status ON portfolio.cash_ledger_entries(status, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.fee_ledger (
    id BIGSERIAL PRIMARY KEY,
    fee_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    fee_ts TIMESTAMPTZ NOT NULL,
    fee_type TEXT NOT NULL,
    amount NUMERIC NOT NULL CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    trade_id BIGINT REFERENCES portfolio.trades(id),
    cash_entry_id BIGINT REFERENCES portfolio.cash_ledger_entries(id),
    source_ref TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'posted' CHECK (status IN ('posted','estimated','reversed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fee_ledger_account_ts ON portfolio.fee_ledger(account_id, fee_ts DESC);

CREATE TABLE IF NOT EXISTS portfolio.tax_lot_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    method TEXT NOT NULL DEFAULT 'FIFO' CHECK (method IN ('FIFO')),
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','incomplete','failed')),
    trade_count INTEGER NOT NULL DEFAULT 0,
    open_lot_count INTEGER NOT NULL DEFAULT 0,
    match_count INTEGER NOT NULL DEFAULT 0,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    error_message TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Performance Attribution Agent'
);

ALTER TABLE portfolio.tax_lot_runs
    ADD COLUMN IF NOT EXISTS position_break_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS missing_inputs TEXT[] NOT NULL DEFAULT ARRAY[]::text[];

CREATE TABLE IF NOT EXISTS portfolio.tax_lots (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES portfolio.tax_lot_runs(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    opening_trade_id BIGINT NOT NULL REFERENCES portfolio.trades(id),
    symbol TEXT NOT NULL,
    contract_key TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT '',
    instrument_type TEXT NOT NULL DEFAULT 'equity',
    direction TEXT NOT NULL CHECK (direction IN ('long','short')),
    opened_at TIMESTAMPTZ NOT NULL,
    original_quantity NUMERIC NOT NULL CHECK (original_quantity > 0),
    remaining_quantity NUMERIC NOT NULL CHECK (remaining_quantity >= 0),
    unit_cost NUMERIC NOT NULL,
    cost_basis NUMERIC NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open','closed')),
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tax_lots_run_symbol ON portfolio.tax_lots(run_id, contract_key, opened_at);
CREATE INDEX IF NOT EXISTS idx_tax_lots_account_open ON portfolio.tax_lots(account_id, status, contract_key);

CREATE TABLE IF NOT EXISTS portfolio.tax_lot_matches (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES portfolio.tax_lot_runs(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    opening_trade_id BIGINT NOT NULL REFERENCES portfolio.trades(id),
    closing_trade_id BIGINT NOT NULL REFERENCES portfolio.trades(id),
    symbol TEXT NOT NULL,
    contract_key TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT '',
    instrument_type TEXT NOT NULL DEFAULT 'equity',
    direction TEXT NOT NULL CHECK (direction IN ('long','short')),
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL,
    matched_quantity NUMERIC NOT NULL CHECK (matched_quantity > 0),
    opening_price NUMERIC NOT NULL,
    closing_price NUMERIC NOT NULL,
    gross_realized_pnl NUMERIC NOT NULL,
    allocated_fees NUMERIC NOT NULL DEFAULT 0,
    net_realized_pnl NUMERIC NOT NULL,
    holding_days INTEGER NOT NULL,
    tax_term TEXT NOT NULL CHECK (tax_term IN ('intraday','short_term','long_term')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tax_lot_matches_account_closed ON portfolio.tax_lot_matches(account_id, closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_tax_lot_matches_symbol ON portfolio.tax_lot_matches(contract_key, closed_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.nav_snapshots (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    nav_date DATE NOT NULL,
    securities_market_value NUMERIC,
    cash_balance NUMERIC,
    accrued_income NUMERIC NOT NULL DEFAULT 0,
    liabilities NUMERIC NOT NULL DEFAULT 0,
    fees_payable NUMERIC NOT NULL DEFAULT 0,
    nav NUMERIC,
    external_flow NUMERIC NOT NULL DEFAULT 0,
    income_flow NUMERIC NOT NULL DEFAULT 0,
    expense_flow NUMERIC NOT NULL DEFAULT 0,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC,
    calculation_status TEXT NOT NULL CHECK (calculation_status IN ('complete','incomplete','source_snapshot')),
    missing_inputs TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
    source_snapshot_id TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, nav_date)
);

CREATE INDEX IF NOT EXISTS idx_nav_snapshots_client_date ON portfolio.nav_snapshots(client_id, nav_date DESC);

CREATE TABLE IF NOT EXISTS portfolio.benchmark_observations (
    id BIGSERIAL PRIMARY KEY,
    benchmark_key TEXT NOT NULL,
    observation_date DATE NOT NULL,
    close_value NUMERIC NOT NULL CHECK (close_value > 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_ref TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (benchmark_key, observation_date, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_observations_key_date ON portfolio.benchmark_observations(benchmark_key, observation_date DESC);

CREATE TABLE IF NOT EXISTS portfolio.performance_periods (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT REFERENCES portfolio.accounts(id),
    period_type TEXT NOT NULL CHECK (period_type IN ('day','month','quarter','year','since_inception','custom')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    opening_nav NUMERIC,
    closing_nav NUMERIC,
    external_flows NUMERIC NOT NULL DEFAULT 0,
    income NUMERIC NOT NULL DEFAULT 0,
    expenses NUMERIC NOT NULL DEFAULT 0,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl_change NUMERIC,
    twr_return_pct NUMERIC,
    money_weighted_return_pct NUMERIC,
    benchmark_key TEXT,
    benchmark_return_pct NUMERIC,
    active_return_pct NUMERIC,
    calculation_status TEXT NOT NULL CHECK (calculation_status IN ('complete','incomplete')),
    missing_inputs TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
    methodology TEXT NOT NULL DEFAULT 'Modified Dietz for period return; FIFO for realized P&L',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (client_id, account_id, period_type, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_performance_period_client ON portfolio.performance_periods(client_id, period_end DESC, period_type);

CREATE TABLE IF NOT EXISTS portfolio.performance_attribution (
    id BIGSERIAL PRIMARY KEY,
    performance_period_id BIGINT NOT NULL REFERENCES portfolio.performance_periods(id) ON DELETE CASCADE,
    attribution_type TEXT NOT NULL CHECK (attribution_type IN ('symbol','book','income','fees','cash')),
    attribution_key TEXT NOT NULL,
    opening_exposure NUMERIC,
    average_exposure NUMERIC,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl_change NUMERIC,
    income NUMERIC NOT NULL DEFAULT 0,
    fees NUMERIC NOT NULL DEFAULT 0,
    contribution_amount NUMERIC,
    contribution_pct NUMERIC,
    calculation_status TEXT NOT NULL CHECK (calculation_status IN ('complete','partial')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (performance_period_id, attribution_type, attribution_key)
);

CREATE TABLE IF NOT EXISTS ops.client_report_delivery_queue (
    id BIGSERIAL PRIMARY KEY,
    report_run_id BIGINT NOT NULL REFERENCES ops.report_runs(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    report_period DATE NOT NULL,
    output_note_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    delivery_channel TEXT NOT NULL DEFAULT 'manual_review',
    recipient_ref TEXT,
    status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval','approved','rejected','delivered','cancelled')),
    approval_id BIGINT NOT NULL REFERENCES agent.approvals(id),
    approved_by TEXT,
    decision_notes TEXT,
    decided_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (report_run_id, client_id)
);

CREATE OR REPLACE VIEW portfolio.v_cash_ledger_control AS
SELECT e.id,e.entry_key,c.client_code,c.display_name,a.account_code,e.entry_ts,
       e.entry_type,e.flow_class,e.amount,e.currency,e.description,e.source_ref,
       e.status,e.approval_id,approval.status approval_status,e.created_by,
       e.decided_by,e.decision_notes,e.decided_at,e.posted_at,e.source_evidence,e.created_at
FROM portfolio.cash_ledger_entries e
JOIN portfolio.clients c ON c.id=e.client_id
JOIN portfolio.accounts a ON a.id=e.account_id
LEFT JOIN agent.approvals approval ON approval.id=e.approval_id
ORDER BY e.entry_ts DESC,e.id DESC;

DROP VIEW IF EXISTS portfolio.v_tax_lot_summary;
CREATE VIEW portfolio.v_tax_lot_summary AS
SELECT r.id run_id,r.run_key,c.client_code,c.display_name,a.account_code,r.method,r.status,
       r.trade_count,r.open_lot_count,r.match_count,r.realized_pnl,r.position_break_count,
       r.missing_inputs,r.error_message,
       r.started_at,r.completed_at,
       coalesce((SELECT sum(l.cost_basis) FROM portfolio.tax_lots l WHERE l.run_id=r.id AND l.status='open'),0) open_cost_basis,
       coalesce((SELECT jsonb_agg(jsonb_build_object('symbol',x.symbol,'direction',x.direction,
           'remaining_quantity',x.remaining_quantity,'cost_basis',x.cost_basis,'oldest_opened_at',x.oldest_opened_at)
           ORDER BY x.cost_basis DESC) FROM (
               SELECT symbol,direction,sum(remaining_quantity) remaining_quantity,sum(cost_basis) cost_basis,min(opened_at) oldest_opened_at
               FROM portfolio.tax_lots WHERE run_id=r.id AND status='open' GROUP BY symbol,direction
           ) x),'[]'::jsonb) open_lots
FROM portfolio.tax_lot_runs r
JOIN portfolio.clients c ON c.id=r.client_id
JOIN portfolio.accounts a ON a.id=r.account_id
ORDER BY r.started_at DESC;

CREATE OR REPLACE VIEW portfolio.v_client_nav_control AS
SELECT n.id,c.client_code,c.display_name,a.account_code,n.nav_date,
       n.securities_market_value,n.cash_balance,n.accrued_income,n.liabilities,
       n.fees_payable,n.nav,n.external_flow,n.income_flow,n.expense_flow,
       n.realized_pnl,n.unrealized_pnl,n.calculation_status,n.missing_inputs,
       n.source_snapshot_id,n.evidence,n.calculated_at
FROM portfolio.nav_snapshots n
JOIN portfolio.clients c ON c.id=n.client_id
JOIN portfolio.accounts a ON a.id=n.account_id
ORDER BY n.nav_date DESC,c.display_name,a.account_code;

CREATE OR REPLACE VIEW portfolio.v_client_performance_control AS
SELECT p.id,c.client_code,c.display_name,a.account_code,p.period_type,
       p.period_start,p.period_end,p.opening_nav,p.closing_nav,p.external_flows,
       p.income,p.expenses,p.realized_pnl,p.unrealized_pnl_change,p.twr_return_pct,
       p.money_weighted_return_pct,p.benchmark_key,p.benchmark_return_pct,
       p.active_return_pct,p.calculation_status,p.missing_inputs,p.methodology,
       p.evidence,p.calculated_at
FROM portfolio.performance_periods p
JOIN portfolio.clients c ON c.id=p.client_id
LEFT JOIN portfolio.accounts a ON a.id=p.account_id
ORDER BY p.period_end DESC,c.display_name,a.account_code NULLS FIRST,p.period_type;

CREATE OR REPLACE VIEW portfolio.v_performance_attribution_control AS
SELECT pa.id,pp.client_id,c.client_code,c.display_name,a.account_code,
       pp.period_type,pp.period_start,pp.period_end,pa.attribution_type,
       pa.attribution_key,pa.opening_exposure,pa.average_exposure,
       pa.realized_pnl,pa.unrealized_pnl_change,pa.income,pa.fees,
       pa.contribution_amount,pa.contribution_pct,pa.calculation_status,pa.evidence
FROM portfolio.performance_attribution pa
JOIN portfolio.performance_periods pp ON pp.id=pa.performance_period_id
JOIN portfolio.clients c ON c.id=pp.client_id
LEFT JOIN portfolio.accounts a ON a.id=pp.account_id
ORDER BY pp.period_end DESC,abs(coalesce(pa.contribution_amount,0)) DESC;

CREATE OR REPLACE VIEW ops.v_client_report_delivery_control AS
SELECT q.id,q.report_run_id,r.run_key,c.client_code,c.display_name,q.report_period,
       q.output_note_path,q.content_hash,q.delivery_channel,q.recipient_ref,q.status,
       q.approval_id,a.status approval_status,q.approved_by,q.decision_notes,
       q.decided_at,q.delivered_at,q.evidence,q.created_at,q.updated_at
FROM ops.client_report_delivery_queue q
JOIN ops.report_runs r ON r.id=q.report_run_id
JOIN portfolio.clients c ON c.id=q.client_id
JOIN agent.approvals a ON a.id=q.approval_id
ORDER BY q.created_at DESC;

INSERT INTO agent.tool_registry(tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
 ('ai_os_client_cash_ledger_control','mcp_tool','Portfolio Manager','write_with_approval',true,
  'Stage and resolve source-backed client cash ledger entries. Manual cash cannot post without human approval.',
  '{"api_routes":["/api/client-office/cash/stage","/api/client-office/cash/resolve"],"broker_write":false}'::jsonb),
 ('ai_os_client_accounting_run','mcp_tool','Performance Attribution Agent','write_db_manual_only',true,
  'Rebuild FIFO tax lots, NAV evidence, performance periods, and attribution from warehouse facts.',
  '{"api_routes":["/api/client-office/accounting/run"],"deterministic":true,"broker_write":false}'::jsonb),
 ('ai_os_client_report_delivery_control','mcp_tool','Client Reporting Agent','write_with_approval',true,
  'Resolve the client report delivery gate. External sending remains disabled in v1.',
  '{"api_routes":["/api/client-office/report-delivery/resolve"],"external_send":false}'::jsonb)
ON CONFLICT(tool_name) DO UPDATE SET owning_agent=EXCLUDED.owning_agent,
 permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
 description=EXCLUDED.description,config=EXCLUDED.config;

INSERT INTO agent.skills(skill_key,skill_name,skill_family,skill_type,owner_department,status,
 execution_mode,permission_level,trigger_phrases,input_sources,output_targets,required_tools,
 risk_notes,prompt_template,config)
VALUES
 ('client_accounting_control','Client Accounting Control','client_office','deterministic','Client Office','active',
  'worker_deterministic','write_db_manual_only',ARRAY['calculate client nav','rebuild tax lots','client pnl'],
  ARRAY['portfolio.trades','portfolio.positions','portfolio.cash_ledger_entries','portfolio.snapshots'],
  ARRAY['portfolio.tax_lots','portfolio.tax_lot_matches','portfolio.nav_snapshots'],
  ARRAY['ai_os_client_accounting_run'],'Never infer cash, fees, benchmark values, or missing prices. Mark the result incomplete.',
  'Rebuild FIFO lots and account NAV only from linked warehouse facts. Preserve every missing input and evidence reference.',
  '{"tax_lot_method":"FIFO","allow_estimates":false}'::jsonb),
 ('client_performance_attribution','Client Performance And Attribution','client_office','deterministic','Client Office','active',
  'worker_deterministic','write_db_manual_only',ARRAY['client performance','portfolio attribution','benchmark comparison'],
  ARRAY['portfolio.nav_snapshots','portfolio.tax_lot_matches','portfolio.benchmark_observations','books.book_positions'],
  ARRAY['portfolio.performance_periods','portfolio.performance_attribution'],
  ARRAY['ai_os_client_accounting_run'],'Returns require opening and closing NAV. Benchmark comparison requires source observations.',
  'Calculate source-backed period performance and contribution. State incomplete status instead of filling evidence gaps.',
  '{"period_method":"modified_dietz","allow_estimates":false}'::jsonb),
 ('client_report_governance','Client Report Governance','client_office','operational','Client Office','active',
  'human_gated','write_with_approval',ARRAY['prepare client report','approve client report'],
  ARRAY['portfolio.v_client_nav_control','portfolio.v_client_performance_control','portfolio.v_performance_attribution_control'],
  ARRAY['ops.client_report_delivery_queue','agent.approvals','obsidian client report draft'],
  ARRAY['ai_os_client_report_delivery_control'],'A draft can be generated automatically. Delivery and recommendations require explicit human approval.',
  'Prepare one evidence-backed draft per client, disclose missing evidence, and keep delivery disabled until approved.',
  '{"external_send":false,"draft_only":true}'::jsonb)
ON CONFLICT(skill_key) DO UPDATE SET skill_name=EXCLUDED.skill_name,status=EXCLUDED.status,
 permission_level=EXCLUDED.permission_level,input_sources=EXCLUDED.input_sources,
 output_targets=EXCLUDED.output_targets,required_tools=EXCLUDED.required_tools,
 risk_notes=EXCLUDED.risk_notes,prompt_template=EXCLUDED.prompt_template,
 config=EXCLUDED.config,updated_at=now();

INSERT INTO agent.agent_skill_map(agent_name,skill_key,proficiency,is_primary,activation_rules)
VALUES
 ('Performance Attribution Agent','client_accounting_control','expert',true,'{"deterministic_owner":true}'::jsonb),
 ('Performance Attribution Agent','client_performance_attribution','expert',true,'{"deterministic_owner":true}'::jsonb),
 ('Portfolio Manager','client_accounting_control','advanced',false,'{"reviewer":true}'::jsonb),
 ('Client Reporting Agent','client_report_governance','expert',true,'{"draft_owner":true}'::jsonb),
 ('Charlie Munger','client_report_governance','advanced',false,'{"approval_router":true}'::jsonb)
ON CONFLICT(agent_name,skill_key) DO UPDATE SET proficiency=EXCLUDED.proficiency,
 is_primary=EXCLUDED.is_primary,activation_rules=EXCLUDED.activation_rules,updated_at=now();

UPDATE ops.report_schedules
SET source_views=ARRAY[
    'portfolio.v_client_nav_control','portfolio.v_client_performance_control',
    'portfolio.v_performance_attribution_control','portfolio.v_tax_lot_summary',
    'books.v_client_book_exposure'
],
description='One draft per client with NAV, cash, FIFO realized P&L, holdings, books, performance, benchmark state, attribution, and explicit evidence gaps. Delivery and recommendations require human approval.',
config=config || '{"per_client":true,"external_send":false,"requires_accounting_refresh":true}'::jsonb,
updated_at=now()
WHERE report_key='monthly_client_report';

COMMIT;
