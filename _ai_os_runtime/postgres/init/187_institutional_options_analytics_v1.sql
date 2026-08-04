BEGIN;

-- Point-in-time source batches. A batch is immutable evidence for one underlying,
-- expiry, and source minute; analytics must reference it instead of current quotes.
CREATE TABLE IF NOT EXISTS trading.option_chain_snapshot_batches (
    id BIGSERIAL PRIMARY KEY,
    batch_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    source_connector_key TEXT NOT NULL,
    exchange TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry DATE NOT NULL,
    minute_ts TIMESTAMPTZ NOT NULL,
    source_timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    underlying_source_timestamp TIMESTAMPTZ,
    spot_price NUMERIC,
    contract_count INTEGER NOT NULL DEFAULT 0,
    expected_contract_count INTEGER,
    staleness_threshold_seconds INTEGER NOT NULL CHECK (staleness_threshold_seconds > 0),
    source_age_seconds INTEGER NOT NULL CHECK (source_age_seconds >= 0),
    freshness_status TEXT NOT NULL CHECK (freshness_status IN ('live','delayed','stale','unknown')),
    completeness_ratio NUMERIC CHECK (completeness_ratio BETWEEN 0 AND 1),
    quality_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (quality_status IN ('pending','passed','warning','failed','rejected')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    source_payload_hash TEXT NOT NULL,
    source_artifact_ref TEXT,
    lineage JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_chain_batch_minute_grain CHECK (minute_ts = date_trunc('minute', minute_ts)),
    CONSTRAINT option_chain_batch_time_order CHECK (source_timestamp <= received_at),
    CONSTRAINT option_chain_batch_spot_positive CHECK (spot_price IS NULL OR spot_price > 0),
    CONSTRAINT option_chain_batch_contract_counts CHECK (
        contract_count >= 0 AND (expected_contract_count IS NULL OR expected_contract_count >= 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_option_chain_batches_lookup
    ON trading.option_chain_snapshot_batches (exchange, underlying, expiry, minute_ts DESC);
CREATE INDEX IF NOT EXISTS idx_option_chain_batches_quality
    ON trading.option_chain_snapshot_batches (quality_status, freshness_status, minute_ts DESC);

CREATE TABLE IF NOT EXISTS trading.option_chain_contract_snapshots (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    instrument_token TEXT,
    trading_symbol TEXT NOT NULL,
    strike NUMERIC NOT NULL CHECK (strike > 0),
    option_type TEXT NOT NULL CHECK (option_type IN ('CE','PE')),
    contract_multiplier NUMERIC NOT NULL CHECK (contract_multiplier > 0),
    quote_source_timestamp TIMESTAMPTZ NOT NULL,
    last_trade_timestamp TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    last_price NUMERIC,
    bid_price NUMERIC,
    ask_price NUMERIC,
    bid_quantity NUMERIC,
    ask_quantity NUMERIC,
    volume NUMERIC,
    open_interest NUMERIC,
    previous_open_interest NUMERIC,
    source_age_seconds INTEGER NOT NULL CHECK (source_age_seconds >= 0),
    spread_absolute NUMERIC,
    spread_bps NUMERIC,
    liquidity_score NUMERIC CHECK (liquidity_score BETWEEN 0 AND 1),
    staleness_status TEXT NOT NULL CHECK (staleness_status IN ('live','delayed','stale','unknown')),
    liquidity_status TEXT NOT NULL CHECK (liquidity_status IN ('liquid','thin','illiquid','unknown')),
    liquidity_flags TEXT[] NOT NULL DEFAULT '{}',
    source_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_payload_hash TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, strike, option_type),
    CONSTRAINT option_contract_quote_time_order CHECK (quote_source_timestamp <= received_at),
    CONSTRAINT option_contract_prices_nonnegative CHECK (
        (last_price IS NULL OR last_price >= 0)
        AND (bid_price IS NULL OR bid_price >= 0)
        AND (ask_price IS NULL OR ask_price >= 0)
    ),
    CONSTRAINT option_contract_market_nonnegative CHECK (
        (volume IS NULL OR volume >= 0)
        AND (open_interest IS NULL OR open_interest >= 0)
        AND (previous_open_interest IS NULL OR previous_open_interest >= 0)
    ),
    CONSTRAINT option_contract_crossed_quote_flagged CHECK (
        bid_price IS NULL OR ask_price IS NULL OR bid_price <= ask_price
        OR 'crossed_quote' = ANY(liquidity_flags)
    )
);

CREATE INDEX IF NOT EXISTS idx_option_contract_snapshots_batch_strike
    ON trading.option_chain_contract_snapshots (batch_id, strike, option_type);
CREATE INDEX IF NOT EXISTS idx_option_contract_snapshots_symbol
    ON trading.option_chain_contract_snapshots (trading_symbol, quote_source_timestamp DESC);

-- Explicit point-in-time inputs used by deterministic pricing models.
CREATE TABLE IF NOT EXISTS trading.option_valuation_inputs (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    input_key TEXT NOT NULL,
    model_family TEXT NOT NULL CHECK (model_family IN ('black_scholes_merton','black_76')),
    valuation_timestamp TIMESTAMPTZ NOT NULL,
    spot_price NUMERIC,
    futures_price NUMERIC,
    forward_price NUMERIC,
    risk_free_rate NUMERIC NOT NULL,
    dividend_yield NUMERIC,
    borrow_rate NUMERIC,
    time_to_expiry_years NUMERIC NOT NULL CHECK (time_to_expiry_years > 0),
    day_count_convention TEXT NOT NULL,
    expiry_timestamp TIMESTAMPTZ NOT NULL,
    spot_source_timestamp TIMESTAMPTZ,
    futures_source_timestamp TIMESTAMPTZ,
    rate_source_timestamp TIMESTAMPTZ NOT NULL,
    dividend_source_timestamp TIMESTAMPTZ,
    forward_method TEXT NOT NULL,
    rate_source TEXT NOT NULL,
    dividend_source TEXT,
    input_quality_status TEXT NOT NULL CHECK (input_quality_status IN ('pending','passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_hash TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, input_key),
    CONSTRAINT option_valuation_price_input CHECK (
        coalesce(forward_price, futures_price, spot_price) IS NOT NULL
        AND (spot_price IS NULL OR spot_price > 0)
        AND (futures_price IS NULL OR futures_price > 0)
        AND (forward_price IS NULL OR forward_price > 0)
    ),
    CONSTRAINT option_valuation_time_order CHECK (valuation_timestamp < expiry_timestamp)
);

CREATE TABLE IF NOT EXISTS trading.option_iv_greeks_results (
    id BIGSERIAL PRIMARY KEY,
    contract_snapshot_id BIGINT NOT NULL REFERENCES trading.option_chain_contract_snapshots(id) ON DELETE CASCADE,
    valuation_input_id BIGINT NOT NULL REFERENCES trading.option_valuation_inputs(id) ON DELETE RESTRICT,
    price_field_used TEXT NOT NULL CHECK (price_field_used IN ('mid','last','bid','ask','mark')),
    option_price_used NUMERIC NOT NULL CHECK (option_price_used >= 0),
    model_name TEXT NOT NULL CHECK (model_name IN ('black_scholes_merton','black_76')),
    model_version TEXT NOT NULL,
    solver_name TEXT NOT NULL,
    solver_version TEXT NOT NULL,
    calculation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (calculation_status IN ('pending','not_computable','failed','validated')),
    converged BOOLEAN NOT NULL DEFAULT false,
    iteration_count INTEGER CHECK (iteration_count IS NULL OR iteration_count >= 0),
    residual NUMERIC,
    implied_volatility NUMERIC,
    delta NUMERIC,
    gamma NUMERIC,
    theta NUMERIC,
    vega NUMERIC,
    rho NUMERIC,
    intrinsic_value NUMERIC,
    time_value NUMERIC,
    no_arbitrage_lower_bound NUMERIC,
    no_arbitrage_upper_bound NUMERIC,
    quality_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (quality_status IN ('pending','passed','warning','failed','rejected')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    calculation_hash TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    validated_at TIMESTAMPTZ,
    validated_by TEXT,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (contract_snapshot_id, valuation_input_id, model_version, solver_version, price_field_used),
    CONSTRAINT option_iv_greeks_validated_only CHECK (
        (
            calculation_status = 'validated'
            AND converged
            AND quality_status IN ('passed','warning')
            AND implied_volatility IS NOT NULL AND implied_volatility > 0
            AND delta IS NOT NULL AND gamma IS NOT NULL AND theta IS NOT NULL
            AND vega IS NOT NULL AND rho IS NOT NULL
            AND intrinsic_value IS NOT NULL AND time_value IS NOT NULL
            AND no_arbitrage_lower_bound IS NOT NULL AND no_arbitrage_upper_bound IS NOT NULL
            AND validated_at IS NOT NULL AND validated_by IS NOT NULL
        ) OR (
            calculation_status <> 'validated'
            AND implied_volatility IS NULL AND delta IS NULL AND gamma IS NULL
            AND theta IS NULL AND vega IS NULL AND rho IS NULL
            AND intrinsic_value IS NULL AND time_value IS NULL
            AND no_arbitrage_lower_bound IS NULL AND no_arbitrage_upper_bound IS NULL
            AND validated_at IS NULL AND validated_by IS NULL
        )
    ),
    CONSTRAINT option_iv_greeks_residual_required CHECK (
        NOT converged OR (residual IS NOT NULL AND iteration_count IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_option_iv_greeks_contract
    ON trading.option_iv_greeks_results (contract_snapshot_id, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_option_iv_greeks_quality
    ON trading.option_iv_greeks_results (calculation_status, quality_status, computed_at DESC);

CREATE TABLE IF NOT EXISTS trading.option_premium_series (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    series_type TEXT NOT NULL CHECK (series_type IN ('atm_straddle','strangle')),
    call_contract_snapshot_id BIGINT NOT NULL REFERENCES trading.option_chain_contract_snapshots(id),
    put_contract_snapshot_id BIGINT NOT NULL REFERENCES trading.option_chain_contract_snapshots(id),
    reference_spot NUMERIC NOT NULL CHECK (reference_spot > 0),
    call_strike NUMERIC NOT NULL CHECK (call_strike > 0),
    put_strike NUMERIC NOT NULL CHECK (put_strike > 0),
    call_premium NUMERIC NOT NULL CHECK (call_premium >= 0),
    put_premium NUMERIC NOT NULL CHECK (put_premium >= 0),
    combined_premium NUMERIC NOT NULL CHECK (combined_premium >= 0),
    selection_method TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, series_type, call_strike, put_strike),
    CONSTRAINT option_premium_series_structure CHECK (
        (series_type='atm_straddle' AND call_strike=put_strike)
        OR (series_type='strangle' AND call_strike<>put_strike)
    )
);

CREATE TABLE IF NOT EXISTS trading.option_buildup_classifications (
    id BIGSERIAL PRIMARY KEY,
    contract_snapshot_id BIGINT NOT NULL REFERENCES trading.option_chain_contract_snapshots(id) ON DELETE CASCADE,
    comparison_contract_snapshot_id BIGINT NOT NULL REFERENCES trading.option_chain_contract_snapshots(id) ON DELETE RESTRICT,
    price_change NUMERIC NOT NULL,
    open_interest_change NUMERIC NOT NULL,
    open_interest_change_percent NUMERIC,
    classification TEXT NOT NULL CHECK (classification IN ('long_buildup','short_buildup','long_unwinding','short_covering','neutral','indeterminate')),
    classification_version TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (contract_snapshot_id, comparison_contract_snapshot_id, classification_version)
);

CREATE TABLE IF NOT EXISTS trading.option_strike_migrations (
    id BIGSERIAL PRIMARY KEY,
    from_batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    to_batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    option_type TEXT NOT NULL CHECK (option_type IN ('CE','PE','COMBINED')),
    metric_name TEXT NOT NULL CHECK (metric_name IN ('max_open_interest','max_oi_change','call_wall','put_wall','volume_peak')),
    from_strike NUMERIC,
    to_strike NUMERIC,
    migration_points NUMERIC,
    calculation_version TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (from_batch_id, to_batch_id, option_type, metric_name, calculation_version),
    CONSTRAINT option_strike_migration_distinct_batches CHECK (from_batch_id <> to_batch_id)
);

CREATE TABLE IF NOT EXISTS trading.option_oi_heatmap_cells (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    strike NUMERIC NOT NULL CHECK (strike > 0),
    option_type TEXT NOT NULL CHECK (option_type IN ('CE','PE')),
    open_interest NUMERIC,
    open_interest_change NUMERIC,
    volume NUMERIC,
    normalized_intensity NUMERIC CHECK (normalized_intensity BETWEEN 0 AND 1),
    calculation_version TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, strike, option_type, calculation_version)
);

-- One relation carries IV percentile, skew, and term-structure observations while
-- preserving the dimensional point and the exact validated Greek inputs used.
CREATE TABLE IF NOT EXISTS trading.option_volatility_metrics (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    metric_type TEXT NOT NULL CHECK (metric_type IN ('iv_percentile','iv_rank','skew','term_structure')),
    tenor_label TEXT,
    delta_bucket NUMERIC,
    strike_moneyness NUMERIC,
    lookback_days INTEGER CHECK (lookback_days IS NULL OR lookback_days > 0),
    metric_value NUMERIC NOT NULL,
    observation_count INTEGER NOT NULL CHECK (observation_count > 0),
    valid_from TIMESTAMPTZ NOT NULL,
    calculation_version TEXT NOT NULL,
    source_result_ids BIGINT[] NOT NULL DEFAULT '{}',
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_volatility_percent_range CHECK (
        metric_type NOT IN ('iv_percentile','iv_rank') OR metric_value BETWEEN 0 AND 100
    ),
    CONSTRAINT option_volatility_source_results_required CHECK (
        quality_status='failed' OR cardinality(source_result_ids) > 0
    )
);

CREATE INDEX IF NOT EXISTS idx_option_volatility_metrics_lookup
    ON trading.option_volatility_metrics (batch_id, metric_type, tenor_label, delta_bucket);

CREATE TABLE IF NOT EXISTS trading.option_expected_move_bands (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    horizon_timestamp TIMESTAMPTZ NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('atm_straddle','validated_iv_lognormal','historical_empirical')),
    model_version TEXT NOT NULL,
    confidence_level NUMERIC NOT NULL CHECK (confidence_level > 0 AND confidence_level < 1),
    reference_price NUMERIC NOT NULL CHECK (reference_price > 0),
    expected_move_absolute NUMERIC NOT NULL CHECK (expected_move_absolute >= 0),
    expected_move_percent NUMERIC NOT NULL CHECK (expected_move_percent >= 0),
    lower_band NUMERIC NOT NULL CHECK (lower_band >= 0),
    upper_band NUMERIC NOT NULL CHECK (upper_band >= 0),
    probability_method TEXT NOT NULL,
    source_result_ids BIGINT[] NOT NULL DEFAULT '{}',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, horizon_timestamp, method, model_version, confidence_level),
    CONSTRAINT option_expected_move_band_order CHECK (lower_band <= reference_price AND reference_price <= upper_band),
    CONSTRAINT option_expected_move_sources_required CHECK (
        quality_status='failed' OR cardinality(source_result_ids) > 0
    )
);

CREATE TABLE IF NOT EXISTS trading.option_exposure_estimates (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE CASCADE,
    exposure_scope TEXT NOT NULL CHECK (exposure_scope IN ('contract','strike','expiry','underlying')),
    contract_snapshot_id BIGINT REFERENCES trading.option_chain_contract_snapshots(id) ON DELETE CASCADE,
    strike NUMERIC,
    metric_name TEXT NOT NULL CHECK (metric_name IN ('gex','dex','vanna','charm','gamma_flip')),
    metric_value NUMERIC,
    unit TEXT NOT NULL,
    dealer_position_assumption TEXT NOT NULL,
    open_interest_sign_method TEXT NOT NULL,
    contract_multiplier NUMERIC NOT NULL CHECK (contract_multiplier > 0),
    shock_size NUMERIC,
    spot_grid JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_result_ids BIGINT[] NOT NULL DEFAULT '{}',
    coverage_ratio NUMERIC CHECK (coverage_ratio BETWEEN 0 AND 1),
    calculation_version TEXT NOT NULL,
    assumptions JSONB NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed','not_computable')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_exposure_scope_shape CHECK (
        (exposure_scope='contract' AND contract_snapshot_id IS NOT NULL)
        OR (exposure_scope='strike' AND strike IS NOT NULL)
        OR (exposure_scope IN ('expiry','underlying'))
    ),
    CONSTRAINT option_exposure_assumptions_required CHECK (assumptions <> '{}'::jsonb),
    CONSTRAINT option_exposure_value_evidence CHECK (
        (quality_status IN ('passed','warning') AND metric_value IS NOT NULL AND cardinality(source_result_ids) > 0)
        OR (quality_status IN ('failed','not_computable') AND metric_value IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS trading.option_participant_positions (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_timestamp TIMESTAMPTZ NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    trade_date DATE NOT NULL,
    participant_type TEXT NOT NULL,
    instrument_class TEXT NOT NULL CHECK (instrument_class IN ('index_futures','stock_futures','index_options','stock_options')),
    long_contracts NUMERIC,
    short_contracts NUMERIC,
    net_contracts NUMERIC,
    long_notional NUMERIC,
    short_notional NUMERIC,
    source_artifact_ref TEXT,
    source_payload_hash TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_name, trade_date, participant_type, instrument_class),
    CONSTRAINT option_participant_availability_order CHECK (source_timestamp <= available_at)
);

CREATE TABLE IF NOT EXISTS trading.option_futures_positions (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    exchange TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry DATE NOT NULL,
    source_timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    futures_price NUMERIC,
    spot_price NUMERIC,
    open_interest NUMERIC,
    open_interest_change NUMERIC,
    volume NUMERIC,
    basis_absolute NUMERIC,
    basis_annualized NUMERIC,
    rollover_percent NUMERIC,
    positioning_classification TEXT CHECK (positioning_classification IN ('long_buildup','short_buildup','long_unwinding','short_covering','neutral','indeterminate')),
    calculation_version TEXT NOT NULL,
    source_payload_hash TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, exchange, underlying, expiry, source_timestamp),
    CONSTRAINT option_futures_time_order CHECK (source_timestamp <= received_at)
);

CREATE TABLE IF NOT EXISTS trading.option_analytics_alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_key TEXT NOT NULL UNIQUE,
    batch_id BIGINT REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE SET NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info','low','medium','high','critical')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved','dismissed')),
    observed_at TIMESTAMPTZ NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT NOT NULL,
    evidence JSONB NOT NULL,
    threshold_definition JSONB NOT NULL,
    calculation_version TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','failed')),
    paper_only BOOLEAN NOT NULL DEFAULT true CHECK (paper_only=true),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_alert_evidence_required CHECK (evidence <> '{}'::jsonb),
    CONSTRAINT option_alert_threshold_required CHECK (threshold_definition <> '{}'::jsonb)
);

CREATE INDEX IF NOT EXISTS idx_option_analytics_alerts_open
    ON trading.option_analytics_alerts (severity, detected_at DESC) WHERE status='open';

CREATE TABLE IF NOT EXISTS trading.option_paper_trade_attributions (
    id BIGSERIAL PRIMARY KEY,
    trade_activity_id BIGINT NOT NULL REFERENCES trading.trade_activity_ledger(id) ON DELETE CASCADE,
    entry_batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE RESTRICT,
    exit_batch_id BIGINT REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE RESTRICT,
    strategy_key TEXT,
    attribution_version TEXT NOT NULL,
    entry_signal JSONB NOT NULL,
    exit_signal JSONB,
    pnl_total NUMERIC,
    pnl_delta NUMERIC,
    pnl_gamma NUMERIC,
    pnl_vega NUMERIC,
    pnl_theta NUMERIC,
    pnl_residual NUMERIC,
    fees_and_slippage NUMERIC,
    source_result_ids BIGINT[] NOT NULL DEFAULT '{}',
    quality_status TEXT NOT NULL CHECK (quality_status IN ('pending','passed','warning','failed')),
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    paper_only BOOLEAN NOT NULL DEFAULT true CHECK (paper_only=true),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trade_activity_id, attribution_version),
    CONSTRAINT option_paper_attribution_results_required CHECK (
        quality_status IN ('pending','failed') OR cardinality(source_result_ids) > 0
    )
);

CREATE TABLE IF NOT EXISTS trading.option_replay_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT NOT NULL UNIQUE,
    exchange TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry DATE NOT NULL,
    replay_start TIMESTAMPTZ NOT NULL,
    replay_end TIMESTAMPTZ NOT NULL,
    replay_clock TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','running','paused','completed','failed')),
    maximum_available_source_timestamp TIMESTAMPTZ NOT NULL,
    speed_multiplier NUMERIC NOT NULL DEFAULT 1 CHECK (speed_multiplier > 0),
    point_in_time_enforced BOOLEAN NOT NULL DEFAULT true CHECK (point_in_time_enforced=true),
    created_by TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    paper_only BOOLEAN NOT NULL DEFAULT true CHECK (paper_only=true),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_replay_range CHECK (
        replay_start <= replay_clock AND replay_clock <= replay_end
        AND maximum_available_source_timestamp <= replay_clock
    )
);

CREATE TABLE IF NOT EXISTS trading.option_replay_frames (
    id BIGSERIAL PRIMARY KEY,
    replay_session_id BIGINT NOT NULL REFERENCES trading.option_replay_sessions(id) ON DELETE CASCADE,
    batch_id BIGINT NOT NULL REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE RESTRICT,
    frame_number INTEGER NOT NULL CHECK (frame_number >= 0),
    replay_timestamp TIMESTAMPTZ NOT NULL,
    source_timestamp TIMESTAMPTZ NOT NULL,
    frame_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (replay_session_id, frame_number),
    UNIQUE (replay_session_id, batch_id),
    CONSTRAINT option_replay_no_lookahead CHECK (source_timestamp <= replay_timestamp)
);

CREATE TABLE IF NOT EXISTS trading.option_specialist_observations (
    id BIGSERIAL PRIMARY KEY,
    observation_key TEXT NOT NULL UNIQUE,
    batch_id BIGINT REFERENCES trading.option_chain_snapshot_batches(id) ON DELETE SET NULL,
    specialist_agent TEXT NOT NULL DEFAULT 'Options Analyst',
    observation_type TEXT NOT NULL,
    observation_status TEXT NOT NULL DEFAULT 'draft' CHECK (observation_status IN ('draft','published','superseded','rejected')),
    as_of TIMESTAMPTZ NOT NULL,
    headline TEXT NOT NULL,
    observation TEXT NOT NULL,
    confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('pending','passed','warning','failed')),
    human_review_required BOOLEAN NOT NULL DEFAULT true,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false CHECK (capital_action_allowed=false),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_specialist_published_evidence CHECK (
        observation_status <> 'published'
        OR (quality_status IN ('passed','warning') AND jsonb_array_length(evidence_refs) > 0)
    )
);

CREATE TABLE IF NOT EXISTS trading.option_acceptance_gate_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    exchange TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry DATE NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed','blocked')),
    contracts_expected INTEGER,
    contracts_observed INTEGER NOT NULL DEFAULT 0,
    minute_batches_expected INTEGER,
    minute_batches_observed INTEGER NOT NULL DEFAULT 0,
    validated_greeks_ratio NUMERIC CHECK (validated_greeks_ratio BETWEEN 0 AND 1),
    liquid_contract_ratio NUMERIC CHECK (liquid_contract_ratio BETWEEN 0 AND 1),
    stale_contract_ratio NUMERIC CHECK (stale_contract_ratio BETWEEN 0 AND 1),
    replay_coverage_ratio NUMERIC CHECK (replay_coverage_ratio BETWEEN 0 AND 1),
    paper_attribution_coverage_ratio NUMERIC CHECK (paper_attribution_coverage_ratio BETWEEN 0 AND 1),
    gate_version TEXT NOT NULL,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    CONSTRAINT option_acceptance_window CHECK (window_start < window_end)
);

CREATE TABLE IF NOT EXISTS trading.option_acceptance_gate_results (
    id BIGSERIAL PRIMARY KEY,
    acceptance_run_id BIGINT NOT NULL REFERENCES trading.option_acceptance_gate_runs(id) ON DELETE CASCADE,
    gate_key TEXT NOT NULL,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('passed','failed','blocked','not_applicable')),
    observed_value NUMERIC,
    threshold_value NUMERIC,
    comparator TEXT CHECK (comparator IN ('gte','lte','eq','not_null','zero')),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_by TEXT NOT NULL DEFAULT 'Options Data Quality Agent',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    UNIQUE (acceptance_run_id, gate_key),
    CONSTRAINT option_acceptance_failure_reason CHECK (
        status NOT IN ('failed','blocked') OR failure_reason IS NOT NULL
    )
);

CREATE OR REPLACE VIEW trading.v_institutional_option_chain AS
SELECT
    batch.batch_key,
    batch.provider,
    batch.exchange,
    batch.underlying,
    batch.expiry,
    batch.minute_ts,
    batch.source_timestamp,
    batch.received_at,
    batch.spot_price,
    batch.freshness_status AS batch_freshness_status,
    batch.quality_status AS batch_quality_status,
    contract.id AS contract_snapshot_id,
    contract.trading_symbol,
    contract.strike,
    contract.option_type,
    contract.last_price,
    contract.bid_price,
    contract.ask_price,
    contract.volume,
    contract.open_interest,
    contract.previous_open_interest,
    contract.staleness_status,
    contract.liquidity_status,
    result.implied_volatility,
    result.delta,
    result.gamma,
    result.theta,
    result.vega,
    result.rho,
    result.model_name,
    result.model_version,
    result.solver_version,
    result.quality_status AS calculation_quality_status,
    (result.calculation_status='validated') AS greeks_validated,
    false AS broker_write_allowed
FROM trading.option_chain_snapshot_batches batch
JOIN trading.option_chain_contract_snapshots contract ON contract.batch_id=batch.id
LEFT JOIN LATERAL (
    SELECT calculated.*
    FROM trading.option_iv_greeks_results calculated
    WHERE calculated.contract_snapshot_id=contract.id
      AND calculated.calculation_status='validated'
    ORDER BY calculated.validated_at DESC, calculated.id DESC
    LIMIT 1
) result ON true;

CREATE OR REPLACE VIEW trading.v_option_acceptance_gate_summary AS
SELECT
    run.id,
    run.run_key,
    run.exchange,
    run.underlying,
    run.expiry,
    run.window_start,
    run.window_end,
    run.status,
    count(result.id) AS gate_count,
    count(result.id) FILTER (WHERE result.status='passed') AS passed_count,
    count(result.id) FILTER (WHERE result.status='failed') AS failed_count,
    count(result.id) FILTER (WHERE result.status='blocked') AS blocked_count,
    run.validated_greeks_ratio,
    run.liquid_contract_ratio,
    run.stale_contract_ratio,
    run.replay_coverage_ratio,
    run.paper_attribution_coverage_ratio,
    run.gate_version,
    run.started_at,
    run.finished_at,
    false AS broker_write_allowed
FROM trading.option_acceptance_gate_runs run
LEFT JOIN trading.option_acceptance_gate_results result ON result.acceptance_run_id=run.id
GROUP BY run.id;

COMMENT ON TABLE trading.option_chain_snapshot_batches IS
    'Immutable minute-grain option-chain source batches with event time, receipt time, freshness, completeness, and lineage; analytics only.';
COMMENT ON TABLE trading.option_iv_greeks_results IS
    'Deterministic IV and Greeks outputs. Non-validated rows are constrained to contain no model values; no provider or fabricated values may masquerade as validated calculations.';
COMMENT ON TABLE trading.option_exposure_estimates IS
    'GEX, DEX, vanna, charm, and gamma-flip estimates with explicit dealer-position and OI-sign assumptions; never an execution instruction.';
COMMENT ON TABLE trading.option_replay_sessions IS
    'Point-in-time option-chain replay state with look-ahead prevention and paper-only operation.';

COMMIT;
