CREATE TABLE IF NOT EXISTS core.source_components (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id),
    component_name TEXT NOT NULL,
    component_type TEXT NOT NULL,
    source_path TEXT,
    reuse_mode TEXT NOT NULL DEFAULT 'data_source',
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'mapped',
    description TEXT,
    target_schema TEXT,
    target_tables TEXT[] NOT NULL DEFAULT '{}',
    safety_notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system_id, component_name)
);

CREATE INDEX IF NOT EXISTS idx_source_components_type ON core.source_components (component_type);
CREATE INDEX IF NOT EXISTS idx_source_components_status ON core.source_components (status);
CREATE INDEX IF NOT EXISTS idx_source_components_target_schema ON core.source_components (target_schema);

INSERT INTO core.source_components (
    source_system_id,
    component_name,
    component_type,
    source_path,
    reuse_mode,
    priority,
    status,
    description,
    target_schema,
    target_tables,
    safety_notes,
    metadata
)
SELECT
    ss.id,
    components.component_name,
    components.component_type,
    components.source_path,
    components.reuse_mode,
    components.priority,
    components.status,
    components.description,
    components.target_schema,
    components.target_tables,
    components.safety_notes,
    components.metadata
FROM core.source_systems ss
JOIN (
    VALUES
    (
        'ps 2 cursor archive',
        'client portfolio data',
        'client_data',
        '/Volumes/Devarsh SSD/ps 2 cursor.zip',
        'extract_transform_import',
        'critical',
        'mapped',
        'Client folio, holdings, account, and reporting data from the old p2 cursor system.',
        'portfolio',
        ARRAY['portfolio.clients','portfolio.accounts','portfolio.positions','portfolio.snapshots','client_data.safe_dataset_registry'],
        'Client-private. Inspect metadata and schemas before extraction. Do not expose raw client identifiers to agents without safe views.',
        '{"import_phase":"phase_1","requires_quarantine":true}'::jsonb
    ),
    (
        'ps 2 cursor archive',
        'equity charts and portfolio UI patterns',
        'frontend_component',
        '/Volumes/Devarsh SSD/ps 2 cursor.zip',
        'reference_and_rebuild',
        'medium',
        'mapped',
        'Existing chart/dashboard UI patterns that can inform the new AI Office portfolio views.',
        'ops',
        ARRAY[]::text[],
        'Use as design/component reference. Do not run old app as production source of truth without review.',
        '{"import_phase":"phase_2"}'::jsonb
    ),
    (
        'algo trading terminal',
        'historical price data',
        'market_data',
        '/Volumes/Devarsh SSD/algo based trading software 2/data/storage/prices.db',
        'extract_transform_import',
        'critical',
        'mapped',
        'Historical and possibly intraday OHLCV/price data already collected by the old algo system.',
        'trading',
        ARRAY['trading.symbols','trading.ohlcv'],
        'Read-only source. Copy into quarantine/import staging before heavy reads if SQLite locking errors recur.',
        '{"import_phase":"phase_1","time_series":true}'::jsonb
    ),
    (
        'algo trading terminal',
        'trade history and journals',
        'trade_history',
        '/Volumes/Devarsh SSD/algo based trading software 2/data/trades.db',
        'extract_transform_import',
        'critical',
        'mapped',
        'Old trades, outcomes, journal fields, strategy labels, and execution history for learning and strategy generation.',
        'trading',
        ARRAY['portfolio.trades','trading.trade_journals','strategy.strategy_candidates'],
        'Private trading data. Use for learning and backtest ideas, not for live execution without approval.',
        '{"import_phase":"phase_1","learning_source":true}'::jsonb
    ),
    (
        'algo trading terminal',
        'strategy library and backtesting engine',
        'strategy_engine',
        '/Volumes/Devarsh SSD/algo based trading software 2',
        'reuse_and_improve',
        'high',
        'mapped',
        'Existing strategies, backtesting modules, options tools, quant modules, and analysis code.',
        'strategy',
        ARRAY['strategy.strategy_candidates','strategy.backtest_runs','trading.signals'],
        'Wrap as services/tools. Do not allow direct live execution until paper/shadow mode and approvals exist.',
        '{"import_phase":"phase_2","paper_first":true}'::jsonb
    ),
    (
        'algo trading terminal',
        'TradingView webhook bridge',
        'signal_bridge',
        '/Volumes/Devarsh SSD/algo based trading software 2/integrations/tradingview.py',
        'reuse_and_wrap',
        'high',
        'mapped',
        'Existing TradingView webhook receiver and signal persistence path for live/intraday alerts.',
        'trading',
        ARRAY['trading.signals','agent.inbox_items','agent.approvals'],
        'Read-only alert ingestion first. Live trade actions must go through Execution Safety and Approval Center.',
        '{"import_phase":"phase_1","intraday_alerts":true}'::jsonb
    ),
    (
        'algo trading terminal',
        'live strategy monitor and alerts',
        'alerting',
        '/Volumes/Devarsh SSD/algo based trading software 2',
        'reuse_and_improve',
        'high',
        'mapped',
        'Existing strategy monitoring and alerting primitives to feed the AI Office strategy monitor.',
        'agent',
        ARRAY['trading.signals','agent.inbox_items','ops.browser_runs'],
        'Agents may summarize and rank alerts. No automated broker actions without explicit approval.',
        '{"import_phase":"phase_2","alerting":true}'::jsonb
    )
) AS components (
    source_system_name,
    component_name,
    component_type,
    source_path,
    reuse_mode,
    priority,
    status,
    description,
    target_schema,
    target_tables,
    safety_notes,
    metadata
) ON ss.name = components.source_system_name
ON CONFLICT (source_system_id, component_name) DO UPDATE SET
    component_type = EXCLUDED.component_type,
    source_path = EXCLUDED.source_path,
    reuse_mode = EXCLUDED.reuse_mode,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    description = EXCLUDED.description,
    target_schema = EXCLUDED.target_schema,
    target_tables = EXCLUDED.target_tables,
    safety_notes = EXCLUDED.safety_notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();
