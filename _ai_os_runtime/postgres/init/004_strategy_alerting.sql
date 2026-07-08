CREATE SCHEMA IF NOT EXISTS risk;

CREATE TABLE IF NOT EXISTS trading.ticks (
    ts TIMESTAMPTZ NOT NULL,
    symbol_id BIGINT REFERENCES trading.symbols(id),
    symbol TEXT NOT NULL,
    exchange TEXT,
    price NUMERIC,
    volume NUMERIC,
    bid NUMERIC,
    ask NUMERIC,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (ts, symbol, exchange)
);

SELECT create_hypertable('trading.ticks', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON trading.ticks (symbol, ts DESC);

CREATE TABLE IF NOT EXISTS strategy.strategy_versions (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    version_name TEXT NOT NULL,
    code_ref TEXT,
    rule_summary TEXT,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    entry_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    exit_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (strategy_id, version_name)
);

CREATE TABLE IF NOT EXISTS strategy.strategy_instances (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id),
    version_id BIGINT REFERENCES strategy.strategy_versions(id),
    source_component_id BIGINT REFERENCES core.source_components(id),
    instance_name TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL DEFAULT 'shadow',
    timeframe TEXT,
    universe TEXT,
    status TEXT NOT NULL DEFAULT 'stopped',
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_strategy_instances_status ON strategy.strategy_instances (status);
CREATE INDEX IF NOT EXISTS idx_strategy_instances_mode ON strategy.strategy_instances (mode);

CREATE TABLE IF NOT EXISTS strategy.alert_rules (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id),
    instance_id BIGINT REFERENCES strategy.strategy_instances(id),
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    enabled BOOLEAN NOT NULL DEFAULT true,
    cooldown_seconds INTEGER DEFAULT 0,
    condition JSONB NOT NULL DEFAULT '{}'::jsonb,
    route_to_agent TEXT NOT NULL DEFAULT 'Trading Desk Agent',
    requires_approval BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (instance_id, rule_name)
);

CREATE TABLE IF NOT EXISTS strategy.alert_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    alert_rule_id BIGINT REFERENCES strategy.alert_rules(id),
    instance_id BIGINT REFERENCES strategy.strategy_instances(id),
    source_signal_id BIGINT REFERENCES trading.signals(id),
    symbol TEXT,
    exchange TEXT,
    timeframe TEXT,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'new',
    title TEXT NOT NULL,
    message TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id)
);

CREATE INDEX IF NOT EXISTS idx_alert_events_ts ON strategy.alert_events (ts DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_status ON strategy.alert_events (status);
CREATE INDEX IF NOT EXISTS idx_alert_events_symbol ON strategy.alert_events (symbol);

CREATE TABLE IF NOT EXISTS strategy.performance_snapshots (
    ts TIMESTAMPTZ NOT NULL,
    instance_id BIGINT NOT NULL REFERENCES strategy.strategy_instances(id),
    trades_count INTEGER,
    win_rate NUMERIC,
    expectancy NUMERIC,
    pnl NUMERIC,
    max_drawdown NUMERIC,
    sharpe NUMERIC,
    exposure NUMERIC,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (ts, instance_id)
);

SELECT create_hypertable('strategy.performance_snapshots', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS risk.limits (
    id BIGSERIAL PRIMARY KEY,
    scope_type TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    limit_type TEXT NOT NULL,
    limit_value NUMERIC,
    unit TEXT,
    severity TEXT NOT NULL DEFAULT 'high',
    enabled BOOLEAN NOT NULL DEFAULT true,
    requires_approval BOOLEAN NOT NULL DEFAULT true,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope_type, scope_ref, limit_type)
);

CREATE TABLE IF NOT EXISTS risk.events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    limit_id BIGINT REFERENCES risk.limits(id),
    scope_type TEXT,
    scope_ref TEXT,
    severity TEXT NOT NULL DEFAULT 'high',
    status TEXT NOT NULL DEFAULT 'new',
    title TEXT NOT NULL,
    message TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    approval_id BIGINT REFERENCES agent.approvals(id)
);

CREATE INDEX IF NOT EXISTS idx_risk_events_ts ON risk.events (ts DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_status ON risk.events (status);

INSERT INTO risk.limits (scope_type, scope_ref, limit_type, limit_value, unit, severity, requires_approval, notes)
VALUES
    ('system', 'live_trading', 'live_execution_enabled', 0, 'boolean', 'critical', true, 'Live broker execution is disabled by default.'),
    ('strategy', 'all', 'paper_first_required', 1, 'boolean', 'critical', true, 'Every strategy must run in shadow/paper mode before live consideration.'),
    ('strategy', 'intraday', 'approval_required_for_trade_action', 1, 'boolean', 'critical', true, 'Intraday signals can alert and recommend, not auto-place orders.')
ON CONFLICT (scope_type, scope_ref, limit_type) DO NOTHING;

