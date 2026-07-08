CREATE SCHEMA IF NOT EXISTS books;

CREATE TABLE IF NOT EXISTS books.investment_books (
    book_key TEXT PRIMARY KEY,
    book_name TEXT NOT NULL,
    book_type TEXT NOT NULL,
    mandate TEXT NOT NULL,
    default_horizon TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.book_mandates (
    book_key TEXT PRIMARY KEY REFERENCES books.investment_books(book_key) ON DELETE CASCADE,
    objective TEXT NOT NULL,
    allowed_instruments TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    max_gross_exposure_pct NUMERIC,
    max_net_exposure_pct NUMERIC,
    max_single_name_pct NUMERIC,
    max_leverage NUMERIC,
    review_cadence TEXT NOT NULL DEFAULT 'monthly',
    approval_required BOOLEAN NOT NULL DEFAULT true,
    constraints JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.book_capital_allocations (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES portfolio.clients(id) ON DELETE SET NULL,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE CASCADE,
    target_capital NUMERIC,
    target_pct NUMERIC,
    min_pct NUMERIC,
    max_pct NUMERIC,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, book_key, effective_from)
);

CREATE TABLE IF NOT EXISTS books.book_risk_limits (
    id BIGSERIAL PRIMARY KEY,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE CASCADE,
    limit_key TEXT NOT NULL,
    limit_name TEXT NOT NULL,
    limit_type TEXT NOT NULL,
    threshold_value NUMERIC,
    unit TEXT NOT NULL DEFAULT 'pct',
    severity TEXT NOT NULL DEFAULT 'medium',
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (book_key, limit_key)
);

CREATE TABLE IF NOT EXISTS books.position_purposes (
    purpose_key TEXT PRIMARY KEY,
    purpose_name TEXT NOT NULL,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE CASCADE,
    purpose_family TEXT NOT NULL,
    description TEXT NOT NULL,
    default_horizon TEXT NOT NULL,
    exit_rule_template TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.book_positions (
    id BIGSERIAL PRIMARY KEY,
    source_position_id BIGINT REFERENCES portfolio.positions(id) ON DELETE SET NULL,
    source_trade_id BIGINT REFERENCES trading.trade_activity_ledger(id) ON DELETE SET NULL,
    client_id BIGINT REFERENCES portfolio.clients(id) ON DELETE SET NULL,
    account_id BIGINT REFERENCES portfolio.accounts(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    instrument_type TEXT,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE RESTRICT,
    purpose_key TEXT REFERENCES books.position_purposes(purpose_key) ON DELETE SET NULL,
    owner_agent TEXT NOT NULL,
    strategy_key TEXT,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short', 'flat', 'watch')),
    quantity NUMERIC NOT NULL DEFAULT 0,
    average_price NUMERIC,
    market_price NUMERIC,
    market_value NUMERIC,
    notional_exposure NUMERIC NOT NULL DEFAULT 0,
    gross_exposure NUMERIC NOT NULL DEFAULT 0,
    net_exposure NUMERIC NOT NULL DEFAULT 0,
    time_horizon TEXT NOT NULL,
    thesis TEXT,
    exit_criteria TEXT,
    review_frequency TEXT NOT NULL DEFAULT 'quarterly',
    status TEXT NOT NULL DEFAULT 'active',
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    as_of TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_position_id),
    UNIQUE (source_trade_id)
);

CREATE TABLE IF NOT EXISTS books.position_theses (
    id BIGSERIAL PRIMARY KEY,
    book_position_id BIGINT NOT NULL REFERENCES books.book_positions(id) ON DELETE CASCADE,
    thesis_title TEXT NOT NULL,
    thesis_body TEXT NOT NULL,
    thesis_status TEXT NOT NULL DEFAULT 'needs_research',
    conviction TEXT NOT NULL DEFAULT 'unrated',
    review_due_at TIMESTAMPTZ,
    owner_agent TEXT NOT NULL DEFAULT 'Equity Research',
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.exit_criteria (
    id BIGSERIAL PRIMARY KEY,
    book_position_id BIGINT NOT NULL REFERENCES books.book_positions(id) ON DELETE CASCADE,
    exit_type TEXT NOT NULL,
    criteria_text TEXT NOT NULL,
    trigger_value NUMERIC,
    status TEXT NOT NULL DEFAULT 'needs_review',
    owner_agent TEXT NOT NULL DEFAULT 'Portfolio Manager',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.exposure_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_id BIGINT REFERENCES portfolio.clients(id) ON DELETE SET NULL,
    account_id BIGINT REFERENCES portfolio.accounts(id) ON DELETE SET NULL,
    book_key TEXT REFERENCES books.investment_books(book_key) ON DELETE SET NULL,
    symbol TEXT,
    gross_long NUMERIC NOT NULL DEFAULT 0,
    gross_short NUMERIC NOT NULL DEFAULT 0,
    gross_exposure NUMERIC NOT NULL DEFAULT 0,
    net_exposure NUMERIC NOT NULL DEFAULT 0,
    offset_ratio NUMERIC,
    payload JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS books.cross_book_exposure (
    id BIGSERIAL PRIMARY KEY,
    snapshot_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_id BIGINT REFERENCES portfolio.clients(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    long_books TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    short_books TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    gross_long NUMERIC NOT NULL DEFAULT 0,
    gross_short NUMERIC NOT NULL DEFAULT 0,
    net_exposure NUMERIC NOT NULL DEFAULT 0,
    offset_ratio NUMERIC,
    status TEXT NOT NULL DEFAULT 'observed',
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB
);

CREATE TABLE IF NOT EXISTS books.book_conflicts (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    client_id BIGINT REFERENCES portfolio.clients(id) ON DELETE SET NULL,
    conflict_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    long_exposure NUMERIC NOT NULL DEFAULT 0,
    short_exposure NUMERIC NOT NULL DEFAULT 0,
    net_exposure NUMERIC NOT NULL DEFAULT 0,
    affected_books TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    status TEXT NOT NULL DEFAULT 'open',
    owner_agent TEXT NOT NULL DEFAULT 'Risk Agent',
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.book_performance (
    id BIGSERIAL PRIMARY KEY,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    client_id BIGINT REFERENCES portfolio.clients(id) ON DELETE SET NULL,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE CASCADE,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC NOT NULL DEFAULT 0,
    fees NUMERIC NOT NULL DEFAULT 0,
    gross_exposure_avg NUMERIC,
    net_exposure_avg NUMERIC,
    return_pct NUMERIC,
    benchmark_return_pct NUMERIC,
    attribution JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (period_start, period_end, client_id, book_key)
);

CREATE TABLE IF NOT EXISTS books.book_assignment_staging (
    id BIGSERIAL PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    client_code TEXT,
    account_code TEXT,
    symbol TEXT NOT NULL,
    proposed_book_key TEXT REFERENCES books.investment_books(book_key) ON DELETE SET NULL,
    proposed_purpose_key TEXT REFERENCES books.position_purposes(purpose_key) ON DELETE SET NULL,
    proposed_thesis TEXT,
    proposed_exit_criteria TEXT,
    status TEXT NOT NULL DEFAULT 'staged',
    requested_by TEXT NOT NULL DEFAULT 'Charlie Munger',
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.book_assignment_audit (
    id BIGSERIAL PRIMARY KEY,
    book_position_id BIGINT REFERENCES books.book_positions(id) ON DELETE SET NULL,
    changed_by TEXT NOT NULL,
    change_type TEXT NOT NULL,
    previous_value JSONB NOT NULL DEFAULT '{}'::JSONB,
    new_value JSONB NOT NULL DEFAULT '{}'::JSONB,
    rationale TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_positions_client_book ON books.book_positions (client_id, book_key, status);
CREATE INDEX IF NOT EXISTS idx_book_positions_symbol_book ON books.book_positions (symbol, exchange, book_key);
CREATE INDEX IF NOT EXISTS idx_book_positions_account ON books.book_positions (account_id);
CREATE INDEX IF NOT EXISTS idx_book_positions_strategy ON books.book_positions (strategy_key);
CREATE INDEX IF NOT EXISTS idx_position_theses_position ON books.position_theses (book_position_id, thesis_status);
CREATE INDEX IF NOT EXISTS idx_exit_criteria_position ON books.exit_criteria (book_position_id, status);
CREATE INDEX IF NOT EXISTS idx_book_assignment_staging_status ON books.book_assignment_staging (status, created_at DESC);

INSERT INTO books.investment_books (
    book_key, book_name, book_type, mandate, default_horizon, owner_agent, status, priority
) VALUES
    ('long_term', 'Long-Term Investing', 'investment', 'Own durable compounding businesses and client core holdings with explicit thesis, review cadence, and sell discipline.', 'years', 'Long-Term Portfolio Manager', 'active', 'critical'),
    ('tactical', 'Tactical Investing', 'investment', 'Capture medium-term catalyst, event, sector-rotation, and swing opportunities without contaminating long-term thesis accounting.', 'days_to_months', 'Tactical Portfolio Manager', 'active', 'high'),
    ('quant', 'Quantitative Strategies', 'systematic_trading', 'Run rules-based and model-tested strategies with paper-first validation, risk budgets, and separate attribution.', 'days_to_weeks', 'Quant Agent', 'active', 'critical'),
    ('active_trading', 'Active Trading', 'discretionary_trading', 'Track discretionary intraday, options, futures, event, and short-horizon trades as independent decisions.', 'intraday_to_days', 'Trading Desk Agent', 'active', 'critical'),
    ('cash_treasury', 'Cash And Treasury', 'treasury', 'Track cash, liquid funds, margin, collateral, and dry powder by client and book.', 'daily_to_months', 'Portfolio Manager', 'active', 'high'),
    ('hedges', 'Hedges And Overlays', 'risk_overlay', 'Track explicit hedges, collars, index futures, protective options, and offsetting overlays with hedge purpose visible.', 'intraday_to_months', 'Risk Agent', 'active', 'high')
ON CONFLICT (book_key) DO UPDATE SET
    book_name = EXCLUDED.book_name,
    book_type = EXCLUDED.book_type,
    mandate = EXCLUDED.mandate,
    default_horizon = EXCLUDED.default_horizon,
    owner_agent = EXCLUDED.owner_agent,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    updated_at = now();

INSERT INTO books.book_mandates (
    book_key, objective, allowed_instruments, max_gross_exposure_pct, max_net_exposure_pct,
    max_single_name_pct, max_leverage, review_cadence, approval_required, constraints
) VALUES
    ('long_term', 'Compound client capital through researched ownership.', ARRAY['equity','mutual_fund','etf','bond','cash'], 100, 100, 25, 1, 'quarterly', true, '{"requires_thesis":true,"requires_exit_criteria":true,"committee":"Investment Committee"}'::JSONB),
    ('tactical', 'Exploit defined catalysts with explicit risk/reward and time exits.', ARRAY['equity','etf','options','futures'], 35, 25, 10, 1.2, 'weekly', true, '{"requires_catalyst":true,"requires_stop":true,"committee":"Strategy Review Committee"}'::JSONB),
    ('quant', 'Generate repeatable alpha only from validated rules and model evidence.', ARRAY['equity','futures','options','crypto','commodity'], 40, 25, 8, 1.5, 'daily', true, '{"paper_first":true,"requires_backtest":true,"committee":"Strategy Review Committee"}'::JSONB),
    ('active_trading', 'Record short-horizon discretionary trades separately from investment books.', ARRAY['equity','futures','options','crypto','commodity'], 25, 15, 6, 2, 'daily', true, '{"requires_journal":true,"requires_stop_or_time_exit":true,"committee":"Risk Desk"}'::JSONB),
    ('cash_treasury', 'Preserve liquidity and collateral visibility.', ARRAY['cash','liquid_fund','treasury_bill','fd','margin'], 100, 100, 100, 1, 'daily', false, '{"cash_source_of_truth":"broker_statement"}'::JSONB),
    ('hedges', 'Reduce intended risk without hiding economic offsets.', ARRAY['index_future','stock_future','options','inverse_etf','commodity','currency'], 30, 20, 20, 2, 'daily', true, '{"requires_hedge_objective":true,"must_link_exposure":true,"committee":"Risk Committee"}'::JSONB)
ON CONFLICT (book_key) DO UPDATE SET
    objective = EXCLUDED.objective,
    allowed_instruments = EXCLUDED.allowed_instruments,
    max_gross_exposure_pct = EXCLUDED.max_gross_exposure_pct,
    max_net_exposure_pct = EXCLUDED.max_net_exposure_pct,
    max_single_name_pct = EXCLUDED.max_single_name_pct,
    max_leverage = EXCLUDED.max_leverage,
    review_cadence = EXCLUDED.review_cadence,
    approval_required = EXCLUDED.approval_required,
    constraints = EXCLUDED.constraints,
    updated_at = now();

INSERT INTO books.position_purposes (
    purpose_key, purpose_name, book_key, purpose_family, description, default_horizon, exit_rule_template
) VALUES
    ('core_compounder', 'Core Compounder', 'long_term', 'ownership', 'High-conviction long-term business ownership.', 'years', 'Exit if moat, management, balance sheet, capital allocation, or opportunity-cost test breaks.'),
    ('quality_at_reasonable_price', 'Quality At Reasonable Price', 'long_term', 'ownership', 'Quality business bought at acceptable valuation.', 'years', 'Exit if valuation becomes extreme without earnings support or quality deteriorates.'),
    ('dividend_income', 'Dividend / Income', 'long_term', 'income', 'Income or yield-oriented holding.', 'months_to_years', 'Exit if payout safety, credit quality, or after-tax yield no longer clears hurdle.'),
    ('recovery_thesis', 'Recovery Thesis', 'long_term', 'turnaround', 'Long-term recovery or normalization case.', 'months_to_years', 'Exit if recovery milestones fail or downside risk rises.'),
    ('watchlist_starter', 'Watchlist Starter', 'long_term', 'starter', 'Small starter position to force research and monitoring.', 'months_to_years', 'Exit or size up after thesis completion deadline.'),
    ('special_situation_long_term', 'Special Situation Long-Term', 'long_term', 'special_situation', 'Demerger, merger, restructuring, or unlock with longer horizon.', 'months_to_years', 'Exit if event thesis changes or unlock is priced in.'),
    ('earnings_trade', 'Earnings Trade', 'tactical', 'event', 'Tactical trade around earnings event.', 'days_to_weeks', 'Exit after event, target, stop, or volatility crush.'),
    ('sector_rotation', 'Sector Rotation', 'tactical', 'macro', 'Medium-term sector allocation shift.', 'weeks_to_months', 'Exit when relative strength, macro catalyst, or valuation support fades.'),
    ('swing_trade', 'Swing Trade', 'tactical', 'technical', 'Multi-day to multi-week directional setup.', 'days_to_weeks', 'Exit at target, stop, or setup invalidation.'),
    ('event_driven', 'Event-Driven', 'tactical', 'event', 'Catalyst-driven medium-term position.', 'days_to_months', 'Exit when event resolves, delays, or risk/reward compresses.'),
    ('hedge_around_core', 'Hedge Around Core Position', 'tactical', 'hedge', 'Temporary hedge or trade around a long-term holding.', 'days_to_weeks', 'Exit when hedge objective is met or underlying risk passes.'),
    ('covered_call_overlay', 'Covered Call Overlay', 'tactical', 'options_overlay', 'Covered-call income or partial exit overlay.', 'weeks_to_months', 'Exit or roll by expiry, delta, or assignment plan.'),
    ('cash_secured_put', 'Cash-Secured Put', 'tactical', 'options_overlay', 'Put-writing entry or income strategy backed by cash.', 'weeks_to_months', 'Exit, roll, or accept assignment based on thesis and risk limit.'),
    ('momentum', 'Momentum', 'quant', 'trend', 'Rules-based momentum exposure.', 'days_to_weeks', 'Exit on signal reversal or model stop.'),
    ('mean_reversion', 'Mean Reversion', 'quant', 'reversion', 'Rules-based mean reversion exposure.', 'days', 'Exit on signal mean reversion, time stop, or risk stop.'),
    ('factor_exposure', 'Factor Exposure', 'quant', 'factor', 'Systematic factor tilt.', 'days_to_months', 'Exit on rebalance, factor decay, or risk limit.'),
    ('pairs_trade', 'Pairs Trade', 'quant', 'relative_value', 'Market-neutral pair or spread trade.', 'days_to_weeks', 'Exit on spread convergence, divergence stop, or model invalidation.'),
    ('market_neutral', 'Market Neutral', 'quant', 'relative_value', 'Beta-controlled systematic book.', 'days_to_weeks', 'Exit on rebalance, risk break, or model failure.'),
    ('volatility_signal', 'Volatility Signal', 'quant', 'volatility', 'Volatility-driven systematic exposure.', 'intraday_to_days', 'Exit on vol signal reversal, expiry rule, or risk cap.'),
    ('ml_signal', 'ML Signal', 'quant', 'machine_learning', 'Machine-learning generated signal with validation gate.', 'days_to_weeks', 'Exit by model threshold, drift monitor, or risk stop.'),
    ('regime_signal', 'Regime Signal', 'quant', 'regime', 'Market regime or macro state allocation.', 'days_to_months', 'Exit when regime score changes or drawdown cap hits.'),
    ('intraday_setup', 'Intraday Setup', 'active_trading', 'intraday', 'Discretionary intraday setup.', 'intraday', 'Exit by stop, target, or market close.'),
    ('breakout', 'Breakout', 'active_trading', 'technical', 'Breakout trade.', 'intraday_to_days', 'Exit if breakout fails, stop hits, or target hits.'),
    ('breakdown', 'Breakdown', 'active_trading', 'technical', 'Breakdown or short setup.', 'intraday_to_days', 'Exit if breakdown fails, stop hits, or target hits.'),
    ('scalping', 'Scalping', 'active_trading', 'intraday', 'Very short-term liquidity or momentum scalp.', 'minutes_to_hours', 'Exit on predefined ticks, stop, or liquidity change.'),
    ('volatility_trade', 'Volatility Trade', 'active_trading', 'options', 'Discretionary volatility trade.', 'intraday_to_days', 'Exit on IV target, stop, expiry, or event resolution.'),
    ('options_directional', 'Options Directional', 'active_trading', 'options', 'Directional option trade.', 'intraday_to_days', 'Exit on delta target, stop, premium loss cap, or time stop.'),
    ('futures_hedge', 'Futures Hedge', 'active_trading', 'futures', 'Short-horizon futures hedge or trade.', 'intraday_to_days', 'Exit when hedge/trade objective is met or stop hits.'),
    ('event_risk_trade', 'Event Risk Trade', 'active_trading', 'event', 'Discretionary event-risk trade.', 'intraday_to_days', 'Exit when event resolves or risk/reward changes.'),
    ('cash_buffer', 'Cash Buffer', 'cash_treasury', 'liquidity', 'Uninvested cash or near-cash liquidity.', 'daily', 'Reallocate when capital allocation decision is approved.'),
    ('collateral_margin', 'Collateral / Margin', 'cash_treasury', 'collateral', 'Broker collateral, margin, or pledge visibility.', 'daily', 'Release or adjust when exposure changes.'),
    ('protective_hedge', 'Protective Hedge', 'hedges', 'risk_reduction', 'Explicit hedge against portfolio or name risk.', 'days_to_months', 'Exit when hedge risk passes, cost breaches limit, or linked exposure changes.'),
    ('tail_risk_hedge', 'Tail Risk Hedge', 'hedges', 'risk_reduction', 'Low-probability high-impact risk hedge.', 'weeks_to_months', 'Exit or roll by cost budget, expiry, or risk regime.'),
    ('index_overlay', 'Index Overlay', 'hedges', 'risk_overlay', 'Index future/options overlay for beta management.', 'intraday_to_months', 'Exit or rebalance to target beta hedge ratio.')
ON CONFLICT (purpose_key) DO UPDATE SET
    purpose_name = EXCLUDED.purpose_name,
    book_key = EXCLUDED.book_key,
    purpose_family = EXCLUDED.purpose_family,
    description = EXCLUDED.description,
    default_horizon = EXCLUDED.default_horizon,
    exit_rule_template = EXCLUDED.exit_rule_template,
    status = 'active',
    updated_at = now();

INSERT INTO books.book_risk_limits (
    book_key, limit_key, limit_name, limit_type, threshold_value, unit, severity
) VALUES
    ('long_term', 'single_name_25pct', 'Single Name Max', 'single_name_pct', 25, 'pct', 'high'),
    ('long_term', 'missing_thesis_zero', 'No Active Thesis', 'quality_gate', 0, 'count', 'critical'),
    ('tactical', 'single_name_10pct', 'Single Tactical Name Max', 'single_name_pct', 10, 'pct', 'high'),
    ('quant', 'strategy_drawdown_10pct', 'Strategy Drawdown Limit', 'drawdown_pct', 10, 'pct', 'critical'),
    ('quant', 'paper_first_required', 'Paper First Required', 'approval_gate', 1, 'boolean', 'critical'),
    ('active_trading', 'daily_loss_stop', 'Daily Loss Stop', 'loss_pct', 3, 'pct', 'critical'),
    ('hedges', 'hedge_intent_required', 'Hedge Intent Required', 'quality_gate', 1, 'boolean', 'high')
ON CONFLICT (book_key, limit_key) DO UPDATE SET
    limit_name = EXCLUDED.limit_name,
    limit_type = EXCLUDED.limit_type,
    threshold_value = EXCLUDED.threshold_value,
    unit = EXCLUDED.unit,
    severity = EXCLUDED.severity,
    enabled = true,
    updated_at = now();

INSERT INTO books.book_capital_allocations (
    client_id, book_key, target_pct, min_pct, max_pct, notes
)
SELECT c.id, b.book_key,
       CASE b.book_key
           WHEN 'long_term' THEN 80
           WHEN 'tactical' THEN 10
           WHEN 'quant' THEN 5
           WHEN 'active_trading' THEN 3
           WHEN 'cash_treasury' THEN 2
           ELSE 0
       END AS target_pct,
       CASE b.book_key WHEN 'long_term' THEN 50 ELSE 0 END AS min_pct,
       CASE b.book_key
           WHEN 'long_term' THEN 100
           WHEN 'tactical' THEN 25
           WHEN 'quant' THEN 20
           WHEN 'active_trading' THEN 10
           WHEN 'cash_treasury' THEN 30
           ELSE 15
       END AS max_pct,
       'Default starting allocation; requires client-specific policy review.' AS notes
FROM portfolio.clients c
CROSS JOIN books.investment_books b
WHERE c.active = true
ON CONFLICT (client_id, book_key, effective_from) DO NOTHING;

INSERT INTO books.book_positions (
    source_position_id, client_id, account_id, symbol, exchange, instrument_type,
    book_key, purpose_key, owner_agent, direction, quantity, average_price,
    market_price, market_value, notional_exposure, gross_exposure, net_exposure,
    time_horizon, thesis, exit_criteria, review_frequency, status, evidence, as_of
)
SELECT
    p.id,
    a.client_id,
    p.account_id,
    upper(p.symbol),
    p.exchange,
    p.instrument_type,
    'long_term',
    CASE
        WHEN coalesce(p.instrument_type, '') ILIKE '%cash%' THEN 'cash_buffer'
        WHEN coalesce(p.instrument_type, '') ILIKE '%bond%' THEN 'dividend_income'
        ELSE 'core_compounder'
    END,
    'Long-Term Portfolio Manager',
    CASE
        WHEN coalesce(p.quantity, 0) < 0 OR coalesce(p.market_value, 0) < 0 THEN 'short'
        WHEN coalesce(p.quantity, 0) = 0 AND coalesce(p.market_value, 0) = 0 THEN 'flat'
        ELSE 'long'
    END,
    coalesce(p.quantity, 0),
    p.average_price,
    p.market_price,
    p.market_value,
    coalesce(p.market_value, coalesce(p.quantity, 0) * coalesce(p.market_price, 0), 0),
    abs(coalesce(p.market_value, coalesce(p.quantity, 0) * coalesce(p.market_price, 0), 0)),
    CASE
        WHEN coalesce(p.quantity, 0) < 0 OR coalesce(p.market_value, 0) < 0
            THEN -abs(coalesce(p.market_value, coalesce(p.quantity, 0) * coalesce(p.market_price, 0), 0))
        ELSE abs(coalesce(p.market_value, coalesce(p.quantity, 0) * coalesce(p.market_price, 0), 0))
    END,
    'years',
    'Migrated live holding. Requires explicit research thesis, purpose confirmation, and exit discipline before new decisions.',
    'Needs reviewed exit criteria.',
    'quarterly',
    'active',
    jsonb_build_array(
        jsonb_build_object('source', 'portfolio.v_latest_positions', 'position_id', p.id),
        jsonb_build_object('source', '032_multi_book_portfolio_brain.sql', 'assignment', 'default_long_term_backfill')
    ),
    p.as_of
FROM portfolio.v_latest_positions p
JOIN portfolio.accounts a ON a.id = p.account_id
WHERE a.client_id IS NOT NULL
ON CONFLICT (source_position_id) DO UPDATE SET
    client_id = EXCLUDED.client_id,
    account_id = EXCLUDED.account_id,
    symbol = EXCLUDED.symbol,
    exchange = EXCLUDED.exchange,
    instrument_type = EXCLUDED.instrument_type,
    quantity = EXCLUDED.quantity,
    average_price = EXCLUDED.average_price,
    market_price = EXCLUDED.market_price,
    market_value = EXCLUDED.market_value,
    notional_exposure = EXCLUDED.notional_exposure,
    gross_exposure = EXCLUDED.gross_exposure,
    net_exposure = EXCLUDED.net_exposure,
    as_of = EXCLUDED.as_of,
    updated_at = now();

INSERT INTO books.position_theses (
    book_position_id, thesis_title, thesis_body, thesis_status, conviction,
    review_due_at, owner_agent, evidence
)
SELECT bp.id,
       bp.symbol || ' migrated thesis placeholder',
       'This is a live migrated holding. Equity Research must replace this placeholder with a researched thesis, bear case, valuation, and exit discipline.',
       'needs_research',
       'unrated',
       now() + INTERVAL '30 days',
       'Equity Research',
       jsonb_build_array(jsonb_build_object('source', 'books.book_positions', 'id', bp.id))
FROM books.book_positions bp
LEFT JOIN books.position_theses t ON t.book_position_id = bp.id
WHERE t.id IS NULL;

INSERT INTO books.exit_criteria (
    book_position_id, exit_type, criteria_text, status, owner_agent
)
SELECT bp.id,
       'research_required',
       coalesce(pp.exit_rule_template, 'Define explicit stop, time exit, thesis killer, or sell discipline.'),
       'needs_review',
       bp.owner_agent
FROM books.book_positions bp
LEFT JOIN books.position_purposes pp ON pp.purpose_key = bp.purpose_key
LEFT JOIN books.exit_criteria ec ON ec.book_position_id = bp.id
WHERE ec.id IS NULL;

CREATE OR REPLACE VIEW books.v_book_positions AS
SELECT
    bp.id,
    bp.source_position_id,
    bp.source_trade_id,
    c.client_code,
    c.display_name AS client_name,
    bp.client_id,
    a.account_code,
    a.broker,
    bp.account_id,
    bp.symbol,
    bp.exchange,
    bp.instrument_type,
    bp.book_key,
    ib.book_name,
    ib.book_type,
    bp.purpose_key,
    pp.purpose_name,
    pp.purpose_family,
    bp.owner_agent,
    bp.strategy_key,
    bp.direction,
    bp.quantity,
    bp.average_price,
    bp.market_price,
    bp.market_value,
    bp.notional_exposure,
    bp.gross_exposure,
    bp.net_exposure,
    bp.time_horizon,
    bp.thesis,
    bp.exit_criteria,
    bp.review_frequency,
    bp.status,
    bp.evidence,
    bp.as_of,
    bp.updated_at
FROM books.book_positions bp
JOIN books.investment_books ib ON ib.book_key = bp.book_key
LEFT JOIN books.position_purposes pp ON pp.purpose_key = bp.purpose_key
LEFT JOIN portfolio.clients c ON c.id = bp.client_id
LEFT JOIN portfolio.accounts a ON a.id = bp.account_id;

CREATE OR REPLACE VIEW books.v_investment_books AS
WITH position_agg AS (
    SELECT
        book_key,
        count(*) AS position_count,
        coalesce(sum(gross_exposure), 0) AS gross_exposure,
        coalesce(sum(net_exposure), 0) AS net_exposure,
        count(DISTINCT client_id) FILTER (WHERE client_id IS NOT NULL) AS client_count
    FROM books.book_positions
    WHERE status = 'active'
    GROUP BY book_key
),
purpose_agg AS (
    SELECT book_key, count(*) AS active_purpose_count
    FROM books.position_purposes
    WHERE status = 'active'
    GROUP BY book_key
)
SELECT
    ib.book_key,
    ib.book_name,
    ib.book_type,
    ib.mandate,
    ib.default_horizon,
    ib.owner_agent,
    ib.status,
    ib.priority,
    bm.objective,
    bm.allowed_instruments,
    bm.max_gross_exposure_pct,
    bm.max_net_exposure_pct,
    bm.max_single_name_pct,
    bm.max_leverage,
    bm.review_cadence,
    bm.approval_required,
    coalesce(pa.position_count, 0) AS position_count,
    coalesce(pa.gross_exposure, 0) AS gross_exposure,
    coalesce(pa.net_exposure, 0) AS net_exposure,
    coalesce(pa.client_count, 0) AS client_count,
    coalesce(pua.active_purpose_count, 0) AS active_purpose_count,
    ib.updated_at
FROM books.investment_books ib
LEFT JOIN books.book_mandates bm ON bm.book_key = ib.book_key
LEFT JOIN position_agg pa ON pa.book_key = ib.book_key
LEFT JOIN purpose_agg pua ON pua.book_key = ib.book_key;

CREATE OR REPLACE VIEW books.v_symbol_book_exposure AS
WITH grouped AS (
    SELECT
        client_id,
        client_code,
        client_name,
        symbol,
        exchange,
        sum(net_exposure) FILTER (WHERE book_key = 'long_term') AS long_term_exposure,
        sum(net_exposure) FILTER (WHERE book_key = 'tactical') AS tactical_exposure,
        sum(net_exposure) FILTER (WHERE book_key = 'quant') AS quant_exposure,
        sum(net_exposure) FILTER (WHERE book_key = 'active_trading') AS active_trading_exposure,
        sum(net_exposure) FILTER (WHERE book_key = 'hedges') AS hedges_exposure,
        sum(net_exposure) FILTER (WHERE book_key = 'cash_treasury') AS cash_treasury_exposure,
        sum(greatest(net_exposure, 0)) AS gross_long,
        abs(sum(least(net_exposure, 0))) AS gross_short,
        sum(gross_exposure) AS gross_exposure,
        sum(net_exposure) AS net_exposure,
        count(DISTINCT book_key) AS book_count,
        array_agg(DISTINCT book_key ORDER BY book_key) AS active_books,
        array_agg(DISTINCT purpose_key ORDER BY purpose_key) FILTER (WHERE purpose_key IS NOT NULL) AS purposes,
        max(as_of) AS latest_as_of
    FROM books.v_book_positions
    WHERE status = 'active'
    GROUP BY client_id, client_code, client_name, symbol, exchange
)
SELECT
    *,
    CASE
        WHEN gross_long > 0 AND gross_short > 0 THEN round((gross_short / NULLIF(gross_long, 0))::NUMERIC, 4)
        ELSE 0
    END AS offset_ratio,
    CASE
        WHEN net_exposure > 0 THEN 'net_long'
        WHEN net_exposure < 0 THEN 'net_short'
        ELSE 'flat'
    END AS overall_bias
FROM grouped;

CREATE OR REPLACE VIEW books.v_client_book_exposure AS
SELECT
    client_id,
    client_code,
    client_name,
    book_key,
    book_name,
    count(*) AS position_count,
    count(DISTINCT symbol) AS symbol_count,
    coalesce(sum(greatest(net_exposure, 0)), 0) AS gross_long,
    abs(coalesce(sum(least(net_exposure, 0)), 0)) AS gross_short,
    coalesce(sum(gross_exposure), 0) AS gross_exposure,
    coalesce(sum(net_exposure), 0) AS net_exposure,
    CASE
        WHEN sum(net_exposure) > 0 THEN 'net_long'
        WHEN sum(net_exposure) < 0 THEN 'net_short'
        ELSE 'flat'
    END AS book_bias,
    max(as_of) AS latest_as_of
FROM books.v_book_positions
WHERE status = 'active'
GROUP BY client_id, client_code, client_name, book_key, book_name;

CREATE OR REPLACE VIEW books.v_account_book_exposure AS
SELECT
    client_id,
    client_code,
    client_name,
    account_id,
    account_code,
    broker,
    book_key,
    book_name,
    count(*) AS position_count,
    count(DISTINCT symbol) AS symbol_count,
    coalesce(sum(gross_exposure), 0) AS gross_exposure,
    coalesce(sum(net_exposure), 0) AS net_exposure,
    max(as_of) AS latest_as_of
FROM books.v_book_positions
WHERE status = 'active'
GROUP BY client_id, client_code, client_name, account_id, account_code, broker, book_key, book_name;

CREATE OR REPLACE VIEW books.v_strategy_book_exposure AS
SELECT
    coalesce(strategy_key, 'manual_or_unassigned') AS strategy_key,
    book_key,
    book_name,
    count(*) AS position_count,
    count(DISTINCT symbol) AS symbol_count,
    coalesce(sum(gross_exposure), 0) AS gross_exposure,
    coalesce(sum(net_exposure), 0) AS net_exposure,
    max(as_of) AS latest_as_of
FROM books.v_book_positions
WHERE status = 'active'
GROUP BY coalesce(strategy_key, 'manual_or_unassigned'), book_key, book_name;

CREATE OR REPLACE VIEW books.v_purpose_book_exposure AS
SELECT
    book_key,
    book_name,
    purpose_key,
    purpose_name,
    purpose_family,
    count(*) AS position_count,
    count(DISTINCT symbol) AS symbol_count,
    coalesce(sum(gross_exposure), 0) AS gross_exposure,
    coalesce(sum(net_exposure), 0) AS net_exposure,
    max(as_of) AS latest_as_of
FROM books.v_book_positions
WHERE status = 'active'
GROUP BY book_key, book_name, purpose_key, purpose_name, purpose_family;

CREATE OR REPLACE VIEW books.v_cross_book_conflicts AS
SELECT
    row_number() OVER (ORDER BY client_name, symbol) AS synthetic_id,
    client_id,
    client_code,
    client_name,
    symbol,
    exchange,
    'cross_book_offset' AS conflict_type,
    CASE
        WHEN offset_ratio >= 0.9 THEN 'critical'
        WHEN offset_ratio >= 0.5 THEN 'high'
        WHEN offset_ratio > 0 THEN 'medium'
        ELSE 'low'
    END AS severity,
    'Long and short exposure exist across independent books; Risk Office must verify whether this is intentional hedge or avoidable self-offset.' AS description,
    gross_long AS long_exposure,
    gross_short AS short_exposure,
    net_exposure,
    active_books AS affected_books,
    offset_ratio,
    latest_as_of
FROM books.v_symbol_book_exposure
WHERE gross_long > 0 AND gross_short > 0;

CREATE OR REPLACE VIEW books.v_unbooked_positions AS
SELECT
    p.id AS source_position_id,
    c.client_code,
    c.display_name AS client_name,
    a.account_code,
    p.symbol,
    p.exchange,
    p.instrument_type,
    p.quantity,
    p.market_value,
    p.as_of
FROM portfolio.v_latest_positions p
JOIN portfolio.accounts a ON a.id = p.account_id
LEFT JOIN portfolio.clients c ON c.id = a.client_id
LEFT JOIN books.book_positions bp ON bp.source_position_id = p.id
WHERE a.client_id IS NOT NULL
  AND bp.id IS NULL;

CREATE OR REPLACE VIEW books.v_book_assignment_gaps AS
SELECT
    NULL::BIGINT AS book_position_id,
    up.client_code,
    up.client_name,
    up.account_code,
    up.symbol,
    'unbooked' AS book_key,
    'Unbooked Position' AS book_name,
    'missing_book' AS gap_type,
    'Client-linked latest position has no book assignment.' AS gap_description,
    'critical' AS severity,
    'Portfolio Manager' AS owner_agent,
    up.as_of
FROM books.v_unbooked_positions up
UNION ALL
SELECT
    bp.id AS book_position_id,
    bp.client_code,
    bp.client_name,
    bp.account_code,
    bp.symbol,
    bp.book_key,
    bp.book_name,
    'missing_purpose' AS gap_type,
    'Position has no explicit purpose taxonomy.' AS gap_description,
    'high' AS severity,
    bp.owner_agent,
    bp.as_of
FROM books.v_book_positions bp
WHERE bp.purpose_key IS NULL
UNION ALL
SELECT
    bp.id,
    bp.client_code,
    bp.client_name,
    bp.account_code,
    bp.symbol,
    bp.book_key,
    bp.book_name,
    'exit_criteria_needs_review',
    'Position has no active reviewed exit criteria.',
    CASE WHEN bp.book_key IN ('active_trading', 'quant') THEN 'critical' ELSE 'high' END,
    bp.owner_agent,
    bp.as_of
FROM books.v_book_positions bp
WHERE NOT EXISTS (
    SELECT 1
    FROM books.exit_criteria ec
    WHERE ec.book_position_id = bp.id
      AND ec.status = 'active'
)
UNION ALL
SELECT
    bp.id,
    bp.client_code,
    bp.client_name,
    bp.account_code,
    bp.symbol,
    bp.book_key,
    bp.book_name,
    'thesis_needs_research',
    'Position needs a completed researched thesis before investment committee action.',
    CASE WHEN bp.book_key = 'long_term' THEN 'high' ELSE 'medium' END,
    bp.owner_agent,
    bp.as_of
FROM books.v_book_positions bp
WHERE NOT EXISTS (
    SELECT 1
    FROM books.position_theses t
    WHERE t.book_position_id = bp.id
      AND t.thesis_status IN ('approved', 'active')
)
UNION ALL
SELECT
    bp.id,
    bp.client_code,
    bp.client_name,
    bp.account_code,
    bp.symbol,
    bp.book_key,
    bp.book_name,
    'review_due_soon',
    'Position review is due within 30 days or already due.',
    'medium',
    bp.owner_agent,
    bp.as_of
FROM books.v_book_positions bp
JOIN books.position_theses t ON t.book_position_id = bp.id
WHERE t.review_due_at <= now() + INTERVAL '30 days';

CREATE OR REPLACE VIEW books.v_portfolio_intelligence_summary AS
SELECT 'investment_books' AS metric, count(*)::TEXT AS value, 'Configured portfolio books' AS interpretation
FROM books.investment_books
UNION ALL
SELECT 'book_positions', count(*)::TEXT, 'Live positions assigned to investment books'
FROM books.book_positions
UNION ALL
SELECT 'booked_clients', count(DISTINCT client_id)::TEXT, 'Clients with at least one book-assigned position'
FROM books.book_positions
WHERE client_id IS NOT NULL
UNION ALL
SELECT 'gross_book_exposure', round(coalesce(sum(gross_exposure), 0), 2)::TEXT, 'Gross exposure across all books'
FROM books.book_positions
WHERE status = 'active'
UNION ALL
SELECT 'net_book_exposure', round(coalesce(sum(net_exposure), 0), 2)::TEXT, 'Net exposure across all books'
FROM books.book_positions
WHERE status = 'active'
UNION ALL
SELECT 'cross_book_conflicts', count(*)::TEXT, 'Open live cross-book offset conflicts'
FROM books.v_cross_book_conflicts
UNION ALL
SELECT 'book_assignment_gaps', count(*)::TEXT, 'Positions or controls that still need purpose, thesis, exit, or review completion'
FROM books.v_book_assignment_gaps;

CREATE OR REPLACE VIEW portfolio.v_symbol_intelligence AS
SELECT
    e.client_id,
    e.client_code,
    e.client_name,
    e.symbol,
    e.exchange,
    e.long_term_exposure,
    e.tactical_exposure,
    e.quant_exposure,
    e.active_trading_exposure,
    e.hedges_exposure,
    e.cash_treasury_exposure,
    e.gross_long,
    e.gross_short,
    e.gross_exposure,
    e.net_exposure,
    e.offset_ratio,
    e.overall_bias,
    e.active_books,
    e.purposes,
    coalesce(conflict.conflict_count, 0) AS conflict_count,
    coalesce(gaps.gap_count, 0) AS gap_count,
    gaps.gap_types,
    e.latest_as_of
FROM books.v_symbol_book_exposure e
LEFT JOIN (
    SELECT client_id, symbol, count(*) AS conflict_count
    FROM books.v_cross_book_conflicts
    GROUP BY client_id, symbol
) conflict ON conflict.client_id IS NOT DISTINCT FROM e.client_id AND conflict.symbol = e.symbol
LEFT JOIN (
    SELECT client_code, symbol, count(*) AS gap_count, array_agg(DISTINCT gap_type ORDER BY gap_type) AS gap_types
    FROM books.v_book_assignment_gaps
    GROUP BY client_code, symbol
) gaps ON gaps.client_code IS NOT DISTINCT FROM e.client_code AND gaps.symbol = e.symbol;
