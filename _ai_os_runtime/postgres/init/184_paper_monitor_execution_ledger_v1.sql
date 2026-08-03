BEGIN;

CREATE TABLE IF NOT EXISTS trading.paper_positions (
    id BIGSERIAL PRIMARY KEY,
    paper_monitor_session_id BIGINT NOT NULL REFERENCES strategy.paper_monitor_sessions(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    instance_id BIGINT NOT NULL REFERENCES strategy.strategy_instances(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    timeframe TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'long',
    quantity NUMERIC NOT NULL DEFAULT 1,
    state TEXT NOT NULL DEFAULT 'open',
    entry_signal_id BIGINT REFERENCES trading.signals(id) ON DELETE SET NULL,
    entry_ts TIMESTAMPTZ NOT NULL,
    entry_price NUMERIC NOT NULL,
    exit_signal_id BIGINT REFERENCES trading.signals(id) ON DELETE SET NULL,
    exit_ts TIMESTAMPTZ,
    exit_price NUMERIC,
    latest_mark_ts TIMESTAMPTZ NOT NULL,
    latest_mark_price NUMERIC NOT NULL,
    unrealized_pnl NUMERIC NOT NULL DEFAULT 0,
    realized_pnl NUMERIC,
    fees NUMERIC NOT NULL DEFAULT 0,
    close_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_paper_position_state CHECK (state IN ('open', 'closed')),
    CONSTRAINT chk_paper_position_side CHECK (side IN ('long', 'short')),
    CONSTRAINT chk_paper_position_quantity CHECK (quantity > 0),
    CONSTRAINT chk_paper_position_prices CHECK (entry_price > 0 AND latest_mark_price > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_positions_open_symbol
ON trading.paper_positions (paper_monitor_session_id, symbol, exchange)
WHERE state = 'open';

CREATE INDEX IF NOT EXISTS idx_paper_positions_session
ON trading.paper_positions (paper_monitor_session_id, state, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_paper_positions_strategy
ON trading.paper_positions (strategy_id, state, updated_at DESC);

CREATE OR REPLACE VIEW trading.v_paper_positions AS
SELECT
    position.id,
    position.paper_monitor_session_id,
    monitor.session_key,
    position.strategy_id,
    candidate.candidate_key,
    candidate.name AS strategy_name,
    position.instance_id,
    position.symbol,
    position.exchange,
    position.timeframe,
    position.side,
    position.quantity,
    position.state,
    position.entry_signal_id,
    position.entry_ts,
    position.entry_price,
    position.exit_signal_id,
    position.exit_ts,
    position.exit_price,
    position.latest_mark_ts,
    position.latest_mark_price,
    position.unrealized_pnl,
    position.realized_pnl,
    position.fees,
    position.close_reason,
    position.metadata,
    position.created_at,
    position.updated_at
FROM trading.paper_positions position
JOIN strategy.paper_monitor_sessions monitor ON monitor.id = position.paper_monitor_session_id
JOIN strategy.strategy_candidates candidate ON candidate.id = position.strategy_id;

CREATE OR REPLACE VIEW trading.v_paper_monitor_performance AS
SELECT
    monitor.id AS paper_monitor_session_id,
    monitor.session_key,
    monitor.strategy_id,
    candidate.candidate_key,
    candidate.name AS strategy_name,
    monitor.status AS monitor_status,
    count(position.id) AS positions_total,
    count(position.id) FILTER (WHERE position.state = 'open') AS positions_open,
    count(position.id) FILTER (WHERE position.state = 'closed') AS positions_closed,
    coalesce(sum(position.unrealized_pnl) FILTER (WHERE position.state = 'open'), 0) AS unrealized_pnl,
    coalesce(sum(position.realized_pnl) FILTER (WHERE position.state = 'closed'), 0) AS realized_pnl,
    coalesce(sum(position.fees), 0) AS fees,
    max(position.latest_mark_ts) AS latest_mark_ts,
    monitor.last_heartbeat_at,
    monitor.heartbeat_status,
    monitor.live_execution_allowed
FROM strategy.paper_monitor_sessions monitor
JOIN strategy.strategy_candidates candidate ON candidate.id = monitor.strategy_id
LEFT JOIN trading.paper_positions position ON position.paper_monitor_session_id = monitor.id
GROUP BY monitor.id, monitor.session_key, monitor.strategy_id, candidate.candidate_key,
         candidate.name, monitor.status, monitor.last_heartbeat_at,
         monitor.heartbeat_status, monitor.live_execution_allowed;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES (
    'ai_os_evaluate_paper_monitors',
    'deterministic_worker',
    'Trading Desk Agent',
    'write_db_scheduled',
    true,
    'Evaluate approved paper monitors against canonical stored OHLCV and maintain paper-only signals, positions, marks, exits, and P&L.',
    '{"script":"_ai_os_runtime/scripts/run_paper_monitors.py","reads":["trading.ohlcv","strategy.paper_monitor_sessions","strategy.strategy_rule_specs"],"writes":["trading.signals","trading.paper_positions","trading.trade_activity_ledger","strategy.paper_monitor_events"],"deterministic":true,"live_execution_allowed":false,"broker_order_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

COMMIT;
