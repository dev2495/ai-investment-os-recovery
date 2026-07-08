CREATE TABLE IF NOT EXISTS strategy.strategy_templates (
    id BIGSERIAL PRIMARY KEY,
    template_key TEXT NOT NULL UNIQUE,
    template_name TEXT NOT NULL,
    template_family TEXT NOT NULL DEFAULT 'quant',
    asset_class TEXT NOT NULL DEFAULT 'equity',
    default_timeframe TEXT NOT NULL DEFAULT '5m',
    engine_template TEXT NOT NULL DEFAULT 'momentum',
    default_symbols TEXT[] NOT NULL DEFAULT '{}',
    default_universe TEXT,
    description TEXT NOT NULL,
    default_dsl TEXT NOT NULL,
    entry_rule TEXT NOT NULL,
    exit_rule TEXT NOT NULL,
    risk_rule TEXT NOT NULL,
    data_requirements TEXT[] NOT NULL DEFAULT '{}',
    required_gates TEXT[] NOT NULL DEFAULT ARRAY[
        'data_lineage',
        'baseline_backtest',
        'transaction_costs',
        'model_validation',
        'human_approval'
    ]::TEXT[],
    risk_controls JSONB NOT NULL DEFAULT '{}'::jsonb,
    supported_assets TEXT[] NOT NULL DEFAULT '{}',
    source_component TEXT NOT NULL DEFAULT 'ai_os_native',
    execution_readiness TEXT NOT NULL DEFAULT 'backtest_ready',
    owner_agent TEXT NOT NULL DEFAULT 'Strategy Intake Agent',
    status TEXT NOT NULL DEFAULT 'active',
    display_rank INT NOT NULL DEFAULT 100,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_templates_family ON strategy.strategy_templates (template_family, asset_class, status);
CREATE INDEX IF NOT EXISTS idx_strategy_templates_rank ON strategy.strategy_templates (display_rank, template_name);

CREATE TABLE IF NOT EXISTS strategy.strategy_template_applications (
    id BIGSERIAL PRIMARY KEY,
    application_key TEXT NOT NULL UNIQUE,
    template_id BIGINT NOT NULL REFERENCES strategy.strategy_templates(id) ON DELETE CASCADE,
    template_key TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    strategy_name TEXT NOT NULL,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    universe TEXT,
    timeframe TEXT NOT NULL,
    intake_id BIGINT REFERENCES strategy.strategy_intakes(id) ON DELETE SET NULL,
    idea_id BIGINT REFERENCES strategy.generated_ideas(id) ON DELETE SET NULL,
    candidate_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    task_id BIGINT,
    inbox_id BIGINT,
    status TEXT NOT NULL DEFAULT 'queued',
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_template_applications_template ON strategy.strategy_template_applications (template_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_template_applications_candidate ON strategy.strategy_template_applications (candidate_id);

INSERT INTO strategy.strategy_templates (
    template_key, template_name, template_family, asset_class, default_timeframe,
    engine_template, default_symbols, default_universe, description, default_dsl,
    entry_rule, exit_rule, risk_rule, data_requirements, required_gates,
    risk_controls, supported_assets, source_component, execution_readiness,
    owner_agent, status, display_rank, evidence
)
VALUES
    (
        'intraday_momentum_5m',
        'Intraday Momentum 5m',
        'intraday',
        'equity',
        '5m',
        'momentum',
        ARRAY['NSE:TATASTEEL','NSE:HINDALCO','NSE:NIFTY 50']::TEXT[],
        'NSE liquid equities and indices',
        'Long-only intraday continuation template for liquid NSE symbols using short-horizon moving-average confirmation.',
        'Name: Intraday Momentum 5m
Template: momentum
Timeframe: 5m
Entry: close > sma(close, 12)
Exit: close < sma(close, 12) or holding_days >= 1
Risk: stop_loss_pct <= 1.25 and target_pct >= 1.8',
        'close > sma(close, 12)',
        'close < sma(close, 12) or holding_days >= 1',
        'stop_loss_pct <= 1.25 and target_pct >= 1.8',
        ARRAY['5m_ohlcv','transaction_costs','slippage_model','symbol_liquidity']::TEXT[],
        ARRAY['dsl_parse','data_quality','baseline_backtest','transaction_costs','paper_monitor','human_approval']::TEXT[],
        '{"paper_first":true,"max_position_risk_pct":0.5,"no_live_execution":true}'::jsonb,
        ARRAY['equity','index']::TEXT[],
        'ai_os_native',
        'optimizer_ready',
        'Strategy Intake Agent',
        'active',
        10,
        '[{"source":"AI OS template library v1"}]'::jsonb
    ),
    (
        'intraday_mean_reversion_5m',
        'Intraday Mean Reversion 5m',
        'intraday',
        'equity',
        '5m',
        'mean_reversion',
        ARRAY['NSE:TATASTEEL','NSE:HINDALCO','NSE:NIFTY 50']::TEXT[],
        'NSE liquid equities and indices',
        'Oversold intraday reversal template using z-score against a rolling mean.',
        'Name: Intraday Mean Reversion 5m
Template: mean_reversion
Timeframe: 5m
Entry: zscore(close, 20) < -1.0
Exit: zscore(close, 20) > 0 or holding_days >= 1
Risk: stop_loss_pct <= 1.0 and target_pct >= 1.5',
        'zscore(close, 20) < -1.0',
        'zscore(close, 20) > 0 or holding_days >= 1',
        'stop_loss_pct <= 1.0 and target_pct >= 1.5',
        ARRAY['5m_ohlcv','transaction_costs','slippage_model','symbol_liquidity']::TEXT[],
        ARRAY['dsl_parse','data_quality','baseline_backtest','transaction_costs','paper_monitor','human_approval']::TEXT[],
        '{"paper_first":true,"max_position_risk_pct":0.4,"no_live_execution":true}'::jsonb,
        ARRAY['equity','index']::TEXT[],
        'ai_os_native',
        'optimizer_ready',
        'Strategy Intake Agent',
        'active',
        20,
        '[{"source":"AI OS template library v1"}]'::jsonb
    ),
    (
        'opening_range_breakout_5m',
        'Opening Range Breakout',
        'intraday',
        'equity',
        '5m',
        'breakout',
        ARRAY['NSE:NIFTY 50','NSE:NIFTY BANK','NSE:TATASTEEL']::TEXT[],
        'NSE liquid equities and indices',
        'Opening-range expansion template for high-liquidity instruments.',
        'Name: Opening Range Breakout
Template: breakout
Timeframe: 5m
Entry: close > sma(close, 12) * 1.002
Exit: close < sma(close, 12) or holding_days >= 1
Risk: stop_loss_pct <= 1.0 and target_pct >= 2.0',
        'close > sma(close, 12) * 1.002',
        'close < sma(close, 12) or holding_days >= 1',
        'stop_loss_pct <= 1.0 and target_pct >= 2.0',
        ARRAY['5m_ohlcv','opening_range_bars','volume','transaction_costs','slippage_model']::TEXT[],
        ARRAY['dsl_parse','data_quality','baseline_backtest','transaction_costs','paper_monitor','human_approval']::TEXT[],
        '{"paper_first":true,"max_position_risk_pct":0.5,"no_live_execution":true}'::jsonb,
        ARRAY['equity','index']::TEXT[],
        'ai_os_native',
        'optimizer_ready',
        'Backtest Engineer',
        'active',
        30,
        '[{"source":"AI OS template library v1"}]'::jsonb
    ),
    (
        'low_volatility_trend_filter',
        'Low Volatility Trend Filter',
        'quant',
        'equity',
        '5m',
        'low_volatility',
        ARRAY['NSE:TCS','NSE:TITAN','NSE:NTPC']::TEXT[],
        'NSE liquid equities',
        'Trend-following candidate that only participates when realized volatility is below recent median.',
        'Name: Low Volatility Trend Filter
Template: low_volatility
Timeframe: 5m
Entry: atr(14) < sma(atr(14), 20) and close > sma(close, 20)
Exit: close < sma(close, 20) or holding_days >= 5
Risk: stop_loss_pct <= 2 and target_pct >= 3',
        'atr(14) < sma(atr(14), 20) and close > sma(close, 20)',
        'close < sma(close, 20) or holding_days >= 5',
        'stop_loss_pct <= 2 and target_pct >= 3',
        ARRAY['5m_ohlcv','atr_features','transaction_costs','slippage_model']::TEXT[],
        ARRAY['dsl_parse','data_quality','baseline_backtest','transaction_costs','walk_forward','model_validation','human_approval']::TEXT[],
        '{"paper_first":true,"max_position_risk_pct":0.75,"no_live_execution":true}'::jsonb,
        ARRAY['equity']::TEXT[],
        'ai_os_native',
        'optimizer_ready',
        'Optimizer Agent',
        'active',
        40,
        '[{"source":"AI OS template library v1"}]'::jsonb
    ),
    (
        'options_event_long_straddle',
        'Event Long Straddle Research',
        'options',
        'options',
        'intraday_to_days',
        'breakout',
        ARRAY['NSE:NIFTY 50','NSE:NIFTY BANK']::TEXT[],
        'Index options',
        'Research-only template for pre-event long straddles that requires options chain, IV, OI, payoff, and event calendar data before backtest.',
        'Name: Event Long Straddle Research
Template: breakout
Timeframe: intraday_to_days
Entry: close > sma(close, 12) * 1.002
Exit: holding_days >= 2 or target_pct >= 25
Risk: premium_at_risk <= approved_budget and no_short_gamma',
        'event_with_implied_move_underpriced and liquidity_ok',
        'event_passed or target_pct >= 25 or premium_loss_pct >= 40',
        'premium_at_risk <= approved_budget and no_short_gamma',
        ARRAY['options_chain','iv_history','open_interest','event_calendar','payoff_curve','5m_ohlcv']::TEXT[],
        ARRAY['options_data_quality','payoff_model','scenario_table','human_approval']::TEXT[],
        '{"paper_first":true,"max_premium_loss_pct":100,"no_live_execution":true,"options_backtest_required":true}'::jsonb,
        ARRAY['options','index_options']::TEXT[],
        'ai_os_native_options_template',
        'research_only',
        'Options Analyst',
        'active',
        50,
        '[{"source":"AI OS template library v1"},{"limitation":"options chain ingestion is not complete"}]'::jsonb
    ),
    (
        'options_iv_mean_reversion_short_straddle',
        'IV Mean Reversion Short Straddle Research',
        'options',
        'options',
        'intraday_to_days',
        'mean_reversion',
        ARRAY['NSE:NIFTY 50','NSE:NIFTY BANK']::TEXT[],
        'Index options',
        'Research-only short-premium template that stays blocked until IV/OI, margin, gap-risk, and kill-switch controls are complete.',
        'Name: IV Mean Reversion Short Straddle Research
Template: mean_reversion
Timeframe: intraday_to_days
Entry: zscore(close, 20) > 1.0
Exit: zscore(close, 20) < 0 or holding_days >= 2
Risk: defined_loss_required and event_blackout_required',
        'iv_rank_high and realized_vol_falling and event_blackout_clear',
        'iv_normalized or stop_loss_hit or event_risk_appears',
        'defined_loss_required and event_blackout_required',
        ARRAY['options_chain','iv_history','open_interest','margin_model','event_calendar','gap_risk_model']::TEXT[],
        ARRAY['options_data_quality','margin_model','gap_risk_review','kill_switch','human_approval']::TEXT[],
        '{"paper_first":true,"defined_loss_required":true,"no_live_execution":true,"short_gamma_approval_required":true}'::jsonb,
        ARRAY['options','index_options']::TEXT[],
        'ai_os_native_options_template',
        'research_only',
        'Options Analyst',
        'active',
        60,
        '[{"source":"AI OS template library v1"},{"limitation":"options risk engine is not complete"}]'::jsonb
    ),
    (
        'tactical_event_breakout',
        'Tactical Event Breakout',
        'tactical',
        'equity',
        '5m',
        'breakout',
        ARRAY['NSE:TATASTEEL','NSE:HINDALCO','NSE:JSWSTEEL']::TEXT[],
        'Catalyst-driven NSE equities',
        'Catalyst/event breakout template for filings/news-driven tactical ideas.',
        'Name: Tactical Event Breakout
Template: breakout
Timeframe: 5m
Entry: close > sma(close, 12) * 1.002
Exit: close < sma(close, 12) or holding_days >= 5
Risk: catalyst_invalidated or stop_loss_pct <= 2',
        'material_catalyst and close > sma(close, 12) * 1.002',
        'catalyst_invalidated or close < sma(close, 12) or holding_days >= 5',
        'stop_loss_pct <= 2 and catalyst_review_required',
        ARRAY['5m_ohlcv','news_or_filing_catalyst','transaction_costs','slippage_model']::TEXT[],
        ARRAY['source_lineage','dsl_parse','data_quality','baseline_backtest','catalyst_review','human_approval']::TEXT[],
        '{"paper_first":true,"requires_catalyst_source":true,"no_live_execution":true}'::jsonb,
        ARRAY['equity']::TEXT[],
        'ai_os_native',
        'optimizer_ready',
        'Catalyst Analyst',
        'active',
        70,
        '[{"source":"AI OS template library v1"}]'::jsonb
    ),
    (
        'crypto_breakout_1h',
        'Crypto Breakout 1h',
        'crypto',
        'crypto',
        '1h',
        'breakout',
        ARRAY['BTC','ETH']::TEXT[],
        'Liquid crypto majors',
        'Crypto breakout template queued for connector readiness; backtest requires crypto OHLCV source before promotion.',
        'Name: Crypto Breakout 1h
Template: breakout
Timeframe: 1h
Entry: close > sma(close, 12) * 1.002
Exit: close < sma(close, 12) or holding_days >= 5
Risk: stop_loss_pct <= 2 and exchange_risk_ok',
        'close > sma(close, 12) * 1.002',
        'close < sma(close, 12) or holding_days >= 5',
        'stop_loss_pct <= 2 and exchange_risk_ok',
        ARRAY['crypto_ohlcv','exchange_connector','transaction_costs','slippage_model']::TEXT[],
        ARRAY['connector_health','data_quality','baseline_backtest','exchange_risk_review','human_approval']::TEXT[],
        '{"paper_first":true,"exchange_risk_review":true,"no_live_execution":true}'::jsonb,
        ARRAY['crypto']::TEXT[],
        'ai_os_native_crypto_template',
        'research_only',
        'Crypto Macro Agent',
        'active',
        80,
        '[{"source":"AI OS template library v1"},{"limitation":"crypto exchange connector is not complete"}]'::jsonb
    ),
    (
        'commodity_gold_trend',
        'Gold/Silver Trend Research',
        'commodity',
        'commodity',
        '1h',
        'momentum',
        ARRAY['GOLD','SILVER']::TEXT[],
        'Gold, silver, commodity proxies',
        'Commodity trend template queued for connector readiness and macro/risk review.',
        'Name: Gold/Silver Trend Research
Template: momentum
Timeframe: 1h
Entry: close > sma(close, 12)
Exit: close < sma(close, 12) or holding_days >= 10
Risk: stop_loss_pct <= 2 and macro_event_check',
        'close > sma(close, 12)',
        'close < sma(close, 12) or holding_days >= 10',
        'stop_loss_pct <= 2 and macro_event_check',
        ARRAY['commodity_ohlcv','macro_calendar','transaction_costs','slippage_model']::TEXT[],
        ARRAY['connector_health','data_quality','baseline_backtest','macro_review','human_approval']::TEXT[],
        '{"paper_first":true,"macro_event_check":true,"no_live_execution":true}'::jsonb,
        ARRAY['commodity','macro']::TEXT[],
        'ai_os_native_commodity_template',
        'research_only',
        'Macro Agent',
        'active',
        90,
        '[{"source":"AI OS template library v1"},{"limitation":"commodity connector is not complete"}]'::jsonb
    ),
    (
        'long_term_momentum_overlay',
        'Long-Term Holding Momentum Overlay',
        'long_term_overlay',
        'equity',
        '1d',
        'momentum',
        ARRAY[]::TEXT[],
        'Current client long-term holdings',
        'Overlay template to study temporary add/trim signals around core long-term holdings without confusing thesis ownership.',
        'Name: Long-Term Holding Momentum Overlay
Template: momentum
Timeframe: 1d
Entry: close > sma(close, 12)
Exit: close < sma(close, 12) or holding_days >= 20
Risk: never_invalidates_core_thesis and book_conflict_review_required',
        'close > sma(close, 12) and thesis_status_ok',
        'close < sma(close, 12) or holding_days >= 20',
        'never_invalidates_core_thesis and book_conflict_review_required',
        ARRAY['daily_ohlcv','current_holdings','book_exposure','transaction_costs']::TEXT[],
        ARRAY['book_conflict_review','data_quality','baseline_backtest','portfolio_fit','human_approval']::TEXT[],
        '{"paper_first":true,"must_preserve_book_purpose":true,"no_live_execution":true}'::jsonb,
        ARRAY['equity','portfolio_overlay']::TEXT[],
        'ai_os_native',
        'research_only',
        'Long-Term Portfolio Manager',
        'active',
        100,
        '[{"source":"AI OS template library v1"}]'::jsonb
    )
ON CONFLICT (template_key) DO UPDATE SET
    template_name = EXCLUDED.template_name,
    template_family = EXCLUDED.template_family,
    asset_class = EXCLUDED.asset_class,
    default_timeframe = EXCLUDED.default_timeframe,
    engine_template = EXCLUDED.engine_template,
    default_symbols = EXCLUDED.default_symbols,
    default_universe = EXCLUDED.default_universe,
    description = EXCLUDED.description,
    default_dsl = EXCLUDED.default_dsl,
    entry_rule = EXCLUDED.entry_rule,
    exit_rule = EXCLUDED.exit_rule,
    risk_rule = EXCLUDED.risk_rule,
    data_requirements = EXCLUDED.data_requirements,
    required_gates = EXCLUDED.required_gates,
    risk_controls = EXCLUDED.risk_controls,
    supported_assets = EXCLUDED.supported_assets,
    source_component = EXCLUDED.source_component,
    execution_readiness = EXCLUDED.execution_readiness,
    owner_agent = EXCLUDED.owner_agent,
    status = EXCLUDED.status,
    display_rank = EXCLUDED.display_rank,
    evidence = EXCLUDED.evidence,
    updated_at = now();

CREATE OR REPLACE FUNCTION strategy.create_strategy_from_template(
    p_template_key TEXT,
    p_created_by TEXT DEFAULT 'Devarsh',
    p_strategy_name TEXT DEFAULT NULL,
    p_symbols TEXT[] DEFAULT NULL,
    p_universe TEXT DEFAULT NULL,
    p_timeframe TEXT DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_template strategy.strategy_templates%ROWTYPE;
    v_result JSONB;
    v_application_id BIGINT;
    v_application_key TEXT := 'strategy-template-app-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');
    v_symbols TEXT[];
    v_timeframe TEXT;
    v_universe TEXT;
    v_strategy_name TEXT;
    v_intake_text TEXT;
BEGIN
    SELECT *
    INTO v_template
    FROM strategy.strategy_templates
    WHERE template_key = p_template_key
      AND status = 'active';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'active strategy template not found: %', p_template_key;
    END IF;

    v_symbols := coalesce(p_symbols, v_template.default_symbols, ARRAY[]::TEXT[]);
    v_timeframe := coalesce(nullif(trim(coalesce(p_timeframe, '')), ''), v_template.default_timeframe);
    v_universe := coalesce(nullif(trim(coalesce(p_universe, '')), ''), v_template.default_universe);
    v_strategy_name := coalesce(nullif(trim(coalesce(p_strategy_name, '')), ''), v_template.template_name || ' - template run');
    v_intake_text := concat_ws(E'\n\n',
        v_template.description,
        v_template.default_dsl,
        'Data requirements: ' || array_to_string(v_template.data_requirements, ', '),
        'Required gates: ' || array_to_string(v_template.required_gates, ', '),
        CASE WHEN nullif(trim(coalesce(p_notes, '')), '') IS NOT NULL THEN 'User notes: ' || trim(p_notes) END
    );

    v_result := strategy.create_strategy_arsenal_intake(
        coalesce(nullif(trim(coalesce(p_created_by, '')), ''), 'Devarsh'),
        v_intake_text,
        v_strategy_name,
        v_template.template_family,
        v_template.asset_class,
        v_symbols,
        v_universe,
        v_timeframe,
        ARRAY['template_library', v_template.template_family, v_template.engine_template]::TEXT[],
        'Queued from strategy template library. Paper-first only; live execution blocked until all gates and human approvals pass.',
        'Template risk controls: ' || v_template.risk_controls::TEXT,
        CASE
            WHEN v_template.execution_readiness = 'optimizer_ready'
                THEN ARRAY['parse_dsl','data_quality_gate','baseline_backtest','parameter_optimization','model_validation']::TEXT[]
            ELSE ARRAY['structured_spec','candidate','data_gap_review','validation_review']::TEXT[]
        END,
        'strategy_template_library',
        v_template.template_key
    );

    UPDATE strategy.strategy_candidates
    SET structured_spec = coalesce(structured_spec, '{}'::jsonb) || jsonb_build_object(
            'template_key', v_template.template_key,
            'template_name', v_template.template_name,
            'engine_template', v_template.engine_template,
            'default_dsl', v_template.default_dsl,
            'data_requirements', v_template.data_requirements,
            'required_gates', v_template.required_gates,
            'execution_readiness', v_template.execution_readiness
        ),
        activation_gate = CASE
            WHEN v_template.execution_readiness = 'optimizer_ready' THEN 'paper_first_backtest_required'
            ELSE 'data_connector_required_before_backtest'
        END,
        updated_at = now()
    WHERE id = (v_result->>'candidate_id')::BIGINT;

    INSERT INTO strategy.strategy_template_applications (
        application_key, template_id, template_key, created_by, strategy_name,
        symbols, universe, timeframe, intake_id, idea_id, candidate_id, task_id,
        inbox_id, status, notes, evidence
    )
    VALUES (
        v_application_key,
        v_template.id,
        v_template.template_key,
        coalesce(nullif(trim(coalesce(p_created_by, '')), ''), 'Devarsh'),
        v_strategy_name,
        v_symbols,
        v_universe,
        v_timeframe,
        (v_result->>'intake_id')::BIGINT,
        (v_result->>'idea_id')::BIGINT,
        (v_result->>'candidate_id')::BIGINT,
        (v_result->>'task_id')::BIGINT,
        (v_result->>'inbox_id')::BIGINT,
        'candidate_queued',
        nullif(trim(coalesce(p_notes, '')), ''),
        jsonb_build_array(
            jsonb_build_object('table', 'strategy.strategy_templates', 'template_key', v_template.template_key),
            jsonb_build_object('result', v_result)
        )
    )
    RETURNING id INTO v_application_id;

    RETURN v_result || jsonb_build_object(
        'application_id', v_application_id,
        'application_key', v_application_key,
        'template_key', v_template.template_key,
        'template_name', v_template.template_name,
        'execution_readiness', v_template.execution_readiness,
        'engine_template', v_template.engine_template
    );
END;
$$;

CREATE OR REPLACE VIEW strategy.v_strategy_template_library AS
SELECT
    template.id,
    template.template_key,
    template.template_name,
    template.template_family,
    template.asset_class,
    template.default_timeframe,
    template.engine_template,
    template.default_symbols,
    template.default_universe,
    template.description,
    template.entry_rule,
    template.exit_rule,
    template.risk_rule,
    template.data_requirements,
    template.required_gates,
    template.risk_controls,
    template.supported_assets,
    template.source_component,
    template.execution_readiness,
    template.owner_agent,
    template.status,
    template.display_rank,
    count(application.id) AS application_count,
    count(application.id) FILTER (WHERE application.created_at >= now() - interval '7 days') AS applications_7d,
    max(application.created_at) AS latest_application_at,
    template.updated_at
FROM strategy.strategy_templates template
LEFT JOIN strategy.strategy_template_applications application ON application.template_id = template.id
GROUP BY template.id
ORDER BY template.display_rank, template.template_name;

CREATE OR REPLACE VIEW strategy.v_strategy_template_summary AS
SELECT 'active_templates' AS metric, count(*)::TEXT AS value, 'Active strategy templates visible to Devarsh and agents.' AS interpretation
FROM strategy.strategy_templates
WHERE status = 'active'
UNION ALL
SELECT 'optimizer_ready_templates', count(*)::TEXT, 'Templates that can use the current deterministic backtest/optimizer path.'
FROM strategy.strategy_templates
WHERE status = 'active' AND execution_readiness = 'optimizer_ready'
UNION ALL
SELECT 'research_only_templates', count(*)::TEXT, 'Templates queued for research because a data connector or risk engine is still missing.'
FROM strategy.strategy_templates
WHERE status = 'active' AND execution_readiness = 'research_only'
UNION ALL
SELECT 'template_applications', count(*)::TEXT, 'Templates queued into the strategy arsenal.'
FROM strategy.strategy_template_applications
UNION ALL
SELECT 'options_templates', count(*)::TEXT, 'Options templates available for research-only queueing.'
FROM strategy.strategy_templates
WHERE status = 'active' AND asset_class = 'options'
UNION ALL
SELECT 'crypto_commodity_templates', count(*)::TEXT, 'Crypto/commodity templates available for connector-readiness research.'
FROM strategy.strategy_templates
WHERE status = 'active' AND asset_class IN ('crypto','commodity');

CREATE OR REPLACE VIEW strategy.v_strategy_template_applications AS
SELECT
    application.id,
    application.application_key,
    application.template_key,
    template.template_name,
    template.template_family,
    template.asset_class,
    template.engine_template,
    template.execution_readiness,
    application.created_by,
    application.strategy_name,
    application.symbols,
    application.universe,
    application.timeframe,
    application.intake_id,
    si.intake_key,
    application.idea_id,
    gi.idea_key,
    application.candidate_id,
    coalesce(sc.candidate_key, 'candidate_' || sc.id::TEXT) AS candidate_key,
    sc.status AS candidate_status,
    sc.activation_gate,
    application.task_id,
    application.inbox_id,
    application.status,
    application.notes,
    application.created_at,
    application.updated_at
FROM strategy.strategy_template_applications application
JOIN strategy.strategy_templates template ON template.id = application.template_id
LEFT JOIN strategy.strategy_intakes si ON si.id = application.intake_id
LEFT JOIN strategy.generated_ideas gi ON gi.id = application.idea_id
LEFT JOIN strategy.strategy_candidates sc ON sc.id = application.candidate_id
ORDER BY application.created_at DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_strategy_template_library', 'mcp_tool', 'Strategy Intake Agent', 'read_only', true, 'List available strategy templates, data requirements, gates, and readiness.', '{"reads":["strategy.v_strategy_template_library","strategy.v_strategy_template_summary"]}'::jsonb),
    ('ai_os_create_strategy_from_template', 'mcp_tool', 'Charlie Munger', 'write_with_approval', true, 'Queue a strategy candidate from an approved template. This does not execute trades.', '{"writes":["strategy.strategy_template_applications","strategy.strategy_intakes","strategy.strategy_candidates","agent.tasks"],"execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO core.control_plane_modules (
    module_key, module_name, category, status, priority, owner_agent,
    ui_workspace, description, warehouse_objects, mcp_tools, fincept_component,
    next_action, metadata
)
VALUES (
    'strategy-template-library',
    'Strategy Template Library',
    'quant',
    'active',
    'high',
    'Strategy Intake Agent',
    'quant',
    'Reusable strategy templates for user ideas, agent-discovered ideas, intraday setups, options research, crypto, commodities, and long-term overlays.',
    ARRAY['strategy.strategy_templates','strategy.strategy_template_applications','strategy.v_strategy_template_library']::TEXT[],
    ARRAY['ai_os_strategy_template_library','ai_os_create_strategy_from_template']::TEXT[],
    NULL,
    'Queue templates through the paper-first strategy arsenal, then run parse, data-quality, backtest, optimization, and validation gates where data is available.',
    '{"seed_data_allowed":false,"paper_first":true,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (module_key) DO UPDATE SET
    module_name = EXCLUDED.module_name,
    category = EXCLUDED.category,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    owner_agent = EXCLUDED.owner_agent,
    ui_workspace = EXCLUDED.ui_workspace,
    description = EXCLUDED.description,
    warehouse_objects = EXCLUDED.warehouse_objects,
    mcp_tools = EXCLUDED.mcp_tools,
    fincept_component = EXCLUDED.fincept_component,
    next_action = EXCLUDED.next_action,
    metadata = EXCLUDED.metadata,
    updated_at = now();
