BEGIN;

CREATE SCHEMA IF NOT EXISTS sector_intelligence;

CREATE TABLE IF NOT EXISTS sector_intelligence.taxonomy_nodes (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_key TEXT NOT NULL UNIQUE,
    node_code TEXT NOT NULL,
    node_name TEXT NOT NULL,
    node_level TEXT NOT NULL,
    parent_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE RESTRICT,
    country_code TEXT NOT NULL DEFAULT 'IN',
    description TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    source_system_id BIGINT REFERENCES core.source_systems(id) ON DELETE SET NULL,
    source_reference TEXT,
    methodology JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_taxonomy_level CHECK (node_level IN ('sector', 'industry', 'sub_industry')),
    CONSTRAINT chk_sector_taxonomy_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (country_code, node_level, node_code, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_sector_taxonomy_parent
ON sector_intelligence.taxonomy_nodes (parent_id, node_level, valid_from DESC);

CREATE TABLE IF NOT EXISTS sector_intelligence.instrument_membership_history (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE CASCADE,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE RESTRICT,
    membership_role TEXT NOT NULL DEFAULT 'constituent',
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_primary BOOLEAN NOT NULL DEFAULT true,
    source_system_id BIGINT REFERENCES core.source_systems(id) ON DELETE SET NULL,
    source_reference TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_membership_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (symbol_id, taxonomy_node_id, membership_role, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_sector_membership_current
ON sector_intelligence.instrument_membership_history (taxonomy_node_id, symbol_id)
WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS sector_intelligence.metric_definitions (
    id BIGSERIAL PRIMARY KEY,
    metric_key TEXT NOT NULL UNIQUE,
    metric_name TEXT NOT NULL,
    metric_family TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'numeric',
    unit TEXT,
    frequency TEXT NOT NULL,
    aggregation_method TEXT NOT NULL,
    higher_is_better BOOLEAN,
    formula_expression TEXT,
    required_inputs JSONB NOT NULL DEFAULT '[]'::jsonb,
    methodology_version TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_metric_family CHECK (metric_family IN (
        'financial', 'valuation', 'operating', 'market_share', 'capacity',
        'price', 'volume', 'delivery', 'derivatives', 'ownership', 'flow',
        'relative_strength', 'breadth', 'macro'
    )),
    CONSTRAINT chk_sector_metric_aggregation CHECK (aggregation_method IN (
        'sum', 'mean', 'median', 'weighted_mean', 'ratio_of_sums', 'percentile',
        'count', 'breadth', 'last', 'custom'
    ))
);

CREATE TABLE IF NOT EXISTS sector_intelligence.metric_observations (
    id BIGSERIAL PRIMARY KEY,
    metric_definition_id BIGINT NOT NULL REFERENCES sector_intelligence.metric_definitions(id) ON DELETE RESTRICT,
    taxonomy_node_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    period_start DATE,
    period_end DATE,
    value_numeric NUMERIC,
    value_text TEXT,
    currency TEXT,
    source_system_id BIGINT REFERENCES core.source_systems(id) ON DELETE SET NULL,
    source_reference TEXT,
    calculation_version TEXT,
    input_fingerprint TEXT,
    quality_status TEXT NOT NULL DEFAULT 'observed',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_metric_subject CHECK (
        (taxonomy_node_id IS NOT NULL AND symbol_id IS NULL)
        OR (taxonomy_node_id IS NULL AND symbol_id IS NOT NULL)
    ),
    CONSTRAINT chk_sector_metric_value CHECK (
        (value_numeric IS NOT NULL AND value_text IS NULL)
        OR (value_numeric IS NULL AND value_text IS NOT NULL)
    ),
    CONSTRAINT chk_sector_metric_period CHECK (period_end IS NULL OR period_start IS NOT NULL),
    CONSTRAINT chk_sector_metric_quality CHECK (quality_status IN ('observed', 'validated', 'rejected', 'stale'))
);

CREATE INDEX IF NOT EXISTS idx_sector_metric_observations_node
ON sector_intelligence.metric_observations (taxonomy_node_id, metric_definition_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_sector_metric_observations_symbol
ON sector_intelligence.metric_observations (symbol_id, metric_definition_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS sector_intelligence.sector_aggregates (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    metric_definition_id BIGINT NOT NULL REFERENCES sector_intelligence.metric_definitions(id) ON DELETE RESTRICT,
    as_of_date DATE NOT NULL,
    horizon TEXT NOT NULL,
    value NUMERIC NOT NULL,
    constituent_count INTEGER NOT NULL,
    covered_count INTEGER NOT NULL,
    weighting_method TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    source_observation_ids BIGINT[] NOT NULL DEFAULT '{}',
    quality_status TEXT NOT NULL DEFAULT 'calculated',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_aggregate_counts CHECK (
        constituent_count >= 0 AND covered_count >= 0 AND covered_count <= constituent_count
    ),
    CONSTRAINT chk_sector_aggregate_weighting CHECK (weighting_method IN (
        'equal', 'market_cap', 'free_float_market_cap', 'quality', 'momentum', 'custom'
    )),
    UNIQUE (taxonomy_node_id, metric_definition_id, as_of_date, horizon, weighting_method, calculation_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.valuation_bands (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    metric_definition_id BIGINT NOT NULL REFERENCES sector_intelligence.metric_definitions(id) ON DELETE RESTRICT,
    as_of_date DATE NOT NULL,
    lookback_years INTEGER NOT NULL,
    current_value NUMERIC,
    percentile_rank NUMERIC,
    minimum_value NUMERIC,
    p10_value NUMERIC,
    p25_value NUMERIC,
    median_value NUMERIC,
    p75_value NUMERIC,
    p90_value NUMERIC,
    maximum_value NUMERIC,
    observation_count INTEGER NOT NULL,
    calculation_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_valuation_lookback CHECK (lookback_years > 0),
    CONSTRAINT chk_sector_valuation_percentile CHECK (percentile_rank IS NULL OR percentile_rank BETWEEN 0 AND 100),
    CONSTRAINT chk_sector_valuation_count CHECK (observation_count >= 0),
    UNIQUE (taxonomy_node_id, metric_definition_id, as_of_date, lookback_years, calculation_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.market_share_observations (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE CASCADE,
    participant_name TEXT NOT NULL,
    market_definition TEXT NOT NULL,
    period_end DATE NOT NULL,
    share_value NUMERIC NOT NULL,
    share_unit TEXT NOT NULL DEFAULT 'percent',
    market_size_value NUMERIC,
    market_size_unit TEXT,
    source_system_id BIGINT REFERENCES core.source_systems(id) ON DELETE SET NULL,
    source_reference TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality_status TEXT NOT NULL DEFAULT 'observed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_market_share_percent CHECK (share_unit <> 'percent' OR share_value BETWEEN 0 AND 100),
    UNIQUE (taxonomy_node_id, participant_name, market_definition, period_end, source_reference)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.capacity_observations (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE CASCADE,
    capacity_key TEXT NOT NULL,
    facility_or_region TEXT,
    period_end DATE NOT NULL,
    installed_capacity NUMERIC,
    production NUMERIC,
    utilization_percent NUMERIC,
    capacity_unit TEXT NOT NULL,
    announced_addition NUMERIC,
    expected_online_date DATE,
    source_system_id BIGINT REFERENCES core.source_systems(id) ON DELETE SET NULL,
    source_reference TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_capacity_nonnegative CHECK (
        coalesce(installed_capacity, 0) >= 0
        AND coalesce(production, 0) >= 0
        AND coalesce(announced_addition, 0) >= 0
    ),
    CONSTRAINT chk_capacity_utilization CHECK (utilization_percent IS NULL OR utilization_percent BETWEEN 0 AND 200),
    UNIQUE (taxonomy_node_id, symbol_id, capacity_key, facility_or_region, period_end, source_reference)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.custom_index_definitions (
    id BIGSERIAL PRIMARY KEY,
    index_key TEXT NOT NULL UNIQUE,
    index_name TEXT NOT NULL,
    taxonomy_node_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE SET NULL,
    base_date DATE NOT NULL,
    base_value NUMERIC NOT NULL DEFAULT 1000,
    currency TEXT NOT NULL DEFAULT 'INR',
    weighting_method TEXT NOT NULL,
    selection_rules JSONB NOT NULL,
    weighting_rules JSONB NOT NULL,
    rebalance_frequency TEXT NOT NULL,
    calculation_methodology TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_custom_index_base CHECK (base_value > 0),
    CONSTRAINT chk_custom_index_weighting CHECK (weighting_method IN (
        'equal', 'market_cap', 'free_float_market_cap', 'quality', 'momentum', 'custom'
    )),
    CONSTRAINT chk_custom_index_status CHECK (status IN ('draft', 'validated', 'active', 'retired'))
);

CREATE TABLE IF NOT EXISTS sector_intelligence.custom_index_constituents (
    id BIGSERIAL PRIMARY KEY,
    index_id BIGINT NOT NULL REFERENCES sector_intelligence.custom_index_definitions(id) ON DELETE CASCADE,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE RESTRICT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    inclusion_reason TEXT,
    source_membership_id BIGINT REFERENCES sector_intelligence.instrument_membership_history(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_custom_index_constituent_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (index_id, symbol_id, valid_from)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.custom_index_rebalances (
    id BIGSERIAL PRIMARY KEY,
    index_id BIGINT NOT NULL REFERENCES sector_intelligence.custom_index_definitions(id) ON DELETE CASCADE,
    effective_date DATE NOT NULL,
    announcement_date DATE,
    status TEXT NOT NULL DEFAULT 'calculated',
    methodology_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    constituent_count INTEGER NOT NULL,
    turnover_percent NUMERIC,
    calculation_run_reference TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_custom_index_rebalance_status CHECK (status IN ('calculated', 'validated', 'approved', 'applied', 'rejected')),
    CONSTRAINT chk_custom_index_rebalance_count CHECK (constituent_count >= 0),
    CONSTRAINT chk_custom_index_turnover CHECK (turnover_percent IS NULL OR turnover_percent BETWEEN 0 AND 200),
    UNIQUE (index_id, effective_date, methodology_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.custom_index_weights (
    id BIGSERIAL PRIMARY KEY,
    rebalance_id BIGINT NOT NULL REFERENCES sector_intelligence.custom_index_rebalances(id) ON DELETE CASCADE,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE RESTRICT,
    raw_score NUMERIC,
    target_weight NUMERIC NOT NULL,
    capped_weight NUMERIC,
    shares_per_unit NUMERIC,
    reference_price NUMERIC,
    calculation_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_custom_index_weight CHECK (target_weight BETWEEN 0 AND 1),
    CONSTRAINT chk_custom_index_capped_weight CHECK (capped_weight IS NULL OR capped_weight BETWEEN 0 AND 1),
    UNIQUE (rebalance_id, symbol_id)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.custom_index_history (
    index_id BIGINT NOT NULL REFERENCES sector_intelligence.custom_index_definitions(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    index_value NUMERIC NOT NULL,
    total_return_value NUMERIC,
    divisor NUMERIC,
    constituent_market_value NUMERIC,
    rebalance_id BIGINT REFERENCES sector_intelligence.custom_index_rebalances(id) ON DELETE SET NULL,
    input_fingerprint TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'calculated',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_custom_index_history_value CHECK (index_value > 0),
    PRIMARY KEY (index_id, ts)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.relative_strength_observations (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    benchmark_symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE SET NULL,
    as_of_date DATE NOT NULL,
    horizon TEXT NOT NULL,
    absolute_return NUMERIC,
    benchmark_return NUMERIC,
    relative_return NUMERIC NOT NULL,
    rank_value INTEGER,
    universe_size INTEGER,
    calculation_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_rs_horizon CHECK (horizon IN ('1D', '1W', '1M', '3M', '6M', '1Y', 'cycle')),
    CONSTRAINT chk_sector_rs_rank CHECK (rank_value IS NULL OR rank_value > 0),
    UNIQUE (taxonomy_node_id, benchmark_symbol_id, as_of_date, horizon, calculation_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.breadth_observations (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    as_of_date DATE NOT NULL,
    horizon TEXT NOT NULL,
    breadth_type TEXT NOT NULL,
    positive_count INTEGER NOT NULL,
    negative_count INTEGER NOT NULL,
    unchanged_count INTEGER NOT NULL DEFAULT 0,
    eligible_count INTEGER NOT NULL,
    breadth_value NUMERIC NOT NULL,
    calculation_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_breadth_horizon CHECK (horizon IN ('1D', '1W', '1M', '3M', '6M', '1Y', 'cycle')),
    CONSTRAINT chk_sector_breadth_counts CHECK (
        positive_count >= 0 AND negative_count >= 0 AND unchanged_count >= 0
        AND eligible_count >= positive_count + negative_count + unchanged_count
    ),
    UNIQUE (taxonomy_node_id, as_of_date, horizon, breadth_type, calculation_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.market_monitor_observations (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    market_segment TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    contract_expiry DATE,
    option_type TEXT,
    strike NUMERIC,
    value NUMERIC NOT NULL,
    unit TEXT,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id) ON DELETE RESTRICT,
    source_reference TEXT,
    quality_status TEXT NOT NULL DEFAULT 'observed',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_sector_market_segment CHECK (market_segment IN ('cash', 'futures', 'options')),
    CONSTRAINT chk_sector_option_contract CHECK (
        market_segment <> 'options'
        OR (contract_expiry IS NOT NULL AND option_type IN ('call', 'put') AND strike IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_sector_market_monitor
ON sector_intelligence.market_monitor_observations (taxonomy_node_id, market_segment, observed_at DESC);

CREATE TABLE IF NOT EXISTS sector_intelligence.flow_observations (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    flow_actor TEXT NOT NULL,
    flow_type TEXT NOT NULL,
    buy_value NUMERIC,
    sell_value NUMERIC,
    net_value NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id) ON DELETE RESTRICT,
    source_reference TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT chk_sector_flow_subject CHECK (taxonomy_node_id IS NOT NULL OR symbol_id IS NOT NULL),
    CONSTRAINT chk_sector_flow_actor CHECK (flow_actor IN (
        'FII', 'DII', 'mutual_fund', 'promoter', 'insider', 'institution', 'retail', 'other'
    )),
    CONSTRAINT chk_sector_flow_type CHECK (flow_type IN (
        'cash', 'futures', 'options', 'bulk_deal', 'block_deal', 'insider_trade', 'promoter_transaction'
    ))
);

CREATE INDEX IF NOT EXISTS idx_sector_flow_observations
ON sector_intelligence.flow_observations (taxonomy_node_id, flow_actor, observed_at DESC);

CREATE TABLE IF NOT EXISTS sector_intelligence.ownership_observations (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE CASCADE,
    taxonomy_node_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE SET NULL,
    period_end DATE NOT NULL,
    holder_category TEXT NOT NULL,
    holder_name TEXT,
    holding_percent NUMERIC,
    shares_held NUMERIC,
    pledged_percent NUMERIC,
    change_percent_points NUMERIC,
    observation_type TEXT NOT NULL,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id) ON DELETE RESTRICT,
    source_reference TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_ownership_percent CHECK (holding_percent IS NULL OR holding_percent BETWEEN 0 AND 100),
    CONSTRAINT chk_sector_pledge_percent CHECK (pledged_percent IS NULL OR pledged_percent BETWEEN 0 AND 100),
    CONSTRAINT chk_sector_holder_category CHECK (holder_category IN (
        'promoter', 'FII', 'DII', 'mutual_fund', 'insider', 'public', 'government', 'other'
    )),
    CONSTRAINT chk_sector_ownership_type CHECK (observation_type IN (
        'shareholding_pattern', 'bulk_deal', 'block_deal', 'insider_trade', 'promoter_transaction', 'pledge'
    )),
    UNIQUE (symbol_id, period_end, holder_category, holder_name, observation_type, source_reference)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.raw_material_sensitivities (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    symbol_id BIGINT REFERENCES trading.symbols(id) ON DELETE CASCADE,
    input_key TEXT NOT NULL,
    input_name TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    lag_period_days INTEGER,
    sensitivity_coefficient NUMERIC,
    coefficient_unit TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE,
    methodology_version TEXT,
    source_system_id BIGINT REFERENCES core.source_systems(id) ON DELETE SET NULL,
    source_reference TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT chk_raw_material_relationship CHECK (relationship_type IN (
        'cost_input', 'revenue_driver', 'substitute', 'complement', 'capacity_constraint'
    )),
    CONSTRAINT chk_raw_material_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (taxonomy_node_id, symbol_id, input_key, valid_from)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.macro_sensitivities (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    macro_factor_key TEXT NOT NULL,
    macro_factor_name TEXT NOT NULL,
    relationship_direction TEXT NOT NULL,
    lag_period_days INTEGER,
    beta_coefficient NUMERIC,
    correlation NUMERIC,
    sample_start DATE,
    sample_end DATE,
    regime TEXT,
    methodology_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_macro_direction CHECK (relationship_direction IN ('positive', 'negative', 'nonlinear', 'mixed')),
    CONSTRAINT chk_macro_correlation CHECK (correlation IS NULL OR correlation BETWEEN -1 AND 1),
    CONSTRAINT chk_macro_sample CHECK (sample_end IS NULL OR sample_start IS NOT NULL),
    UNIQUE (taxonomy_node_id, macro_factor_key, sample_end, regime, methodology_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.sector_classifications (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    as_of_date DATE NOT NULL,
    classification_type TEXT NOT NULL,
    classification_value TEXT NOT NULL,
    score NUMERIC,
    confidence NUMERIC,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    calculation_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_classification_confidence CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    UNIQUE (taxonomy_node_id, as_of_date, classification_type, calculation_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.sector_rankings (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    as_of_date DATE NOT NULL,
    ranking_universe TEXT NOT NULL,
    ranking_type TEXT NOT NULL,
    horizon TEXT NOT NULL,
    rank_value INTEGER NOT NULL,
    universe_size INTEGER NOT NULL,
    score NUMERIC NOT NULL,
    calculation_version TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_ranking CHECK (rank_value > 0 AND universe_size >= rank_value),
    CONSTRAINT chk_sector_ranking_type CHECK (ranking_type IN (
        'leader', 'challenger', 'improver', 'deteriorator', 'quality', 'momentum', 'valuation', 'composite'
    )),
    UNIQUE (taxonomy_node_id, as_of_date, ranking_universe, ranking_type, horizon, calculation_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.research_coverage (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    coverage_status TEXT NOT NULL DEFAULT 'queued',
    owner_agent TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    initiated_at TIMESTAMPTZ,
    last_reviewed_at TIMESTAMPTZ,
    next_review_due_at TIMESTAMPTZ,
    thesis_summary TEXT,
    evidence_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    data_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
    monitoring_indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_coverage_status CHECK (coverage_status IN (
        'queued', 'active', 'monitoring', 'review_due', 'suspended', 'closed'
    )),
    CONSTRAINT chk_sector_coverage_version CHECK (version > 0),
    UNIQUE (taxonomy_node_id, version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.sector_committee_packets (
    id BIGSERIAL PRIMARY KEY,
    packet_key TEXT NOT NULL UNIQUE,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE RESTRICT,
    committee_packet_id BIGINT REFERENCES agent.committee_packets(id) ON DELETE SET NULL,
    packet_type TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    decision_question TEXT NOT NULL,
    proposed_action TEXT,
    evidence_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    independent_positions JSONB NOT NULL DEFAULT '[]'::jsonb,
    dissent_summary TEXT,
    risk_challenges JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft',
    human_final_required BOOLEAN NOT NULL DEFAULT true,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_committee_status CHECK (status IN (
        'draft', 'collecting_positions', 'ready', 'decided', 'rejected', 'archived'
    )),
    CONSTRAINT chk_sector_committee_capital_guard CHECK (capital_action_allowed = false)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.portfolio_manager_mandates (
    id BIGSERIAL PRIMARY KEY,
    mandate_key TEXT NOT NULL UNIQUE,
    manager_agent TEXT NOT NULL,
    mandate_name TEXT NOT NULL,
    objective TEXT NOT NULL,
    eligible_taxonomy_node_ids BIGINT[] NOT NULL DEFAULT '{}',
    permitted_books TEXT[] NOT NULL DEFAULT '{}',
    benchmark_index_id BIGINT REFERENCES sector_intelligence.custom_index_definitions(id) ON DELETE SET NULL,
    risk_limits JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_rights JSONB NOT NULL DEFAULT '{}'::jsonb,
    escalation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft',
    human_approval_required BOOLEAN NOT NULL DEFAULT true,
    broker_order_allowed BOOLEAN NOT NULL DEFAULT false,
    valid_from DATE NOT NULL,
    valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_pm_mandate_status CHECK (status IN ('draft', 'active', 'suspended', 'retired')),
    CONSTRAINT chk_sector_pm_mandate_validity CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_sector_pm_broker_guard CHECK (broker_order_allowed = false)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.generated_chart_artifacts (
    id BIGSERIAL PRIMARY KEY,
    artifact_key TEXT NOT NULL UNIQUE,
    artifact_type TEXT NOT NULL,
    target_workspace TEXT NOT NULL DEFAULT 'tradingview_desktop',
    taxonomy_node_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE SET NULL,
    index_id BIGINT REFERENCES sector_intelligence.custom_index_definitions(id) ON DELETE SET NULL,
    generated_expression TEXT,
    pine_source TEXT,
    chart_layout JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_state_fingerprint TEXT NOT NULL,
    generation_version TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    CONSTRAINT chk_sector_chart_artifact_type CHECK (artifact_type IN (
        'formula', 'spread', 'pine_script', 'leader_laggard_pack', 'relative_strength_matrix', 'breadth_layout'
    )),
    CONSTRAINT chk_sector_chart_target CHECK (target_workspace = 'tradingview_desktop'),
    CONSTRAINT chk_sector_chart_payload CHECK (
        generated_expression IS NOT NULL OR pine_source IS NOT NULL OR chart_layout <> '{}'::jsonb
    )
);

CREATE OR REPLACE VIEW sector_intelligence.v_sector_hierarchy AS
SELECT
    sector.id AS sector_id,
    sector.taxonomy_key AS sector_key,
    sector.node_name AS sector_name,
    industry.id AS industry_id,
    industry.taxonomy_key AS industry_key,
    industry.node_name AS industry_name,
    sub_industry.id AS sub_industry_id,
    sub_industry.taxonomy_key AS sub_industry_key,
    sub_industry.node_name AS sub_industry_name,
    coalesce(sub_industry.valid_from, industry.valid_from, sector.valid_from) AS valid_from,
    coalesce(sub_industry.valid_to, industry.valid_to, sector.valid_to) AS valid_to
FROM sector_intelligence.taxonomy_nodes sector
LEFT JOIN sector_intelligence.taxonomy_nodes industry
    ON industry.parent_id = sector.id AND industry.node_level = 'industry'
LEFT JOIN sector_intelligence.taxonomy_nodes sub_industry
    ON sub_industry.parent_id = industry.id AND sub_industry.node_level = 'sub_industry'
WHERE sector.node_level = 'sector' AND sector.country_code = 'IN';

CREATE OR REPLACE VIEW sector_intelligence.v_custom_index_control AS
SELECT
    definition.id AS index_id,
    definition.index_key,
    definition.index_name,
    definition.status,
    definition.weighting_method,
    definition.rebalance_frequency,
    max(rebalance.effective_date) AS latest_rebalance_date,
    count(DISTINCT constituent.symbol_id) FILTER (WHERE constituent.valid_to IS NULL) AS current_constituent_count,
    max(history.ts) AS latest_calculated_at,
    max(history.index_value) FILTER (
        WHERE history.ts = (SELECT max(latest.ts) FROM sector_intelligence.custom_index_history latest WHERE latest.index_id = definition.id)
    ) AS latest_index_value
FROM sector_intelligence.custom_index_definitions definition
LEFT JOIN sector_intelligence.custom_index_rebalances rebalance ON rebalance.index_id = definition.id
LEFT JOIN sector_intelligence.custom_index_constituents constituent ON constituent.index_id = definition.id
LEFT JOIN sector_intelligence.custom_index_history history ON history.index_id = definition.id
GROUP BY definition.id;

CREATE OR REPLACE VIEW sector_intelligence.v_sector_committee_control AS
SELECT
    packet.id,
    packet.packet_key,
    packet.taxonomy_node_id,
    taxonomy.taxonomy_key,
    taxonomy.node_name AS sector_name,
    packet.packet_type,
    packet.as_of_date,
    packet.decision_question,
    packet.status,
    packet.human_final_required,
    packet.capital_action_allowed,
    packet.committee_packet_id,
    packet.updated_at
FROM sector_intelligence.sector_committee_packets packet
JOIN sector_intelligence.taxonomy_nodes taxonomy ON taxonomy.id = packet.taxonomy_node_id;

CREATE OR REPLACE VIEW sector_intelligence.v_sector_portfolio_manager_control AS
SELECT
    mandate.id,
    mandate.mandate_key,
    mandate.manager_agent,
    mandate.mandate_name,
    mandate.objective,
    mandate.status,
    mandate.human_approval_required,
    mandate.broker_order_allowed,
    mandate.valid_from,
    mandate.valid_to,
    mandate.benchmark_index_id,
    benchmark.index_key AS benchmark_index_key,
    count(packet.id) FILTER (WHERE packet.status IN ('collecting_positions', 'ready')) AS open_committee_packets,
    max(packet.updated_at) AS latest_committee_activity_at
FROM sector_intelligence.portfolio_manager_mandates mandate
LEFT JOIN sector_intelligence.custom_index_definitions benchmark ON benchmark.id = mandate.benchmark_index_id
LEFT JOIN sector_intelligence.sector_committee_packets packet
    ON packet.taxonomy_node_id = ANY(mandate.eligible_taxonomy_node_ids)
GROUP BY mandate.id, benchmark.index_key;

CREATE OR REPLACE VIEW sector_intelligence.v_sector_data_freshness AS
SELECT taxonomy.id AS taxonomy_node_id,
       taxonomy.taxonomy_key,
       taxonomy.node_name,
       max(metric.observed_at) AS latest_metric_at,
       max(monitor.observed_at) AS latest_market_monitor_at,
       max(flow.observed_at) AS latest_flow_at,
       max(ownership.period_end) AS latest_ownership_period_end,
       max(coverage.last_reviewed_at) AS latest_research_review_at
FROM sector_intelligence.taxonomy_nodes taxonomy
LEFT JOIN sector_intelligence.metric_observations metric ON metric.taxonomy_node_id = taxonomy.id
LEFT JOIN sector_intelligence.market_monitor_observations monitor ON monitor.taxonomy_node_id = taxonomy.id
LEFT JOIN sector_intelligence.flow_observations flow ON flow.taxonomy_node_id = taxonomy.id
LEFT JOIN sector_intelligence.ownership_observations ownership ON ownership.taxonomy_node_id = taxonomy.id
LEFT JOIN sector_intelligence.research_coverage coverage ON coverage.taxonomy_node_id = taxonomy.id
GROUP BY taxonomy.id;

COMMENT ON SCHEMA sector_intelligence IS
'Deterministic, source-backed Indian sector intelligence warehouse. This schema owns taxonomy, observations, calculations, indices, research controls, and history; TradingView Desktop is an artifact consumer only.';

COMMENT ON TABLE sector_intelligence.generated_chart_artifacts IS
'Generated formula, Pine, and layout artifacts for the logged-in TradingView Desktop workspace. This table does not delegate authoritative state, calculations, or execution to TradingView.';

COMMIT;
