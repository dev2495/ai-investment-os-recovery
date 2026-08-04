BEGIN;

CREATE TABLE IF NOT EXISTS research.companies (
    id BIGSERIAL PRIMARY KEY,
    company_key TEXT NOT NULL UNIQUE,
    legal_name TEXT NOT NULL,
    display_name TEXT,
    primary_symbol TEXT NOT NULL,
    primary_exchange TEXT NOT NULL,
    isin TEXT,
    cin TEXT,
    lei TEXT,
    fiscal_year_end_month SMALLINT NOT NULL DEFAULT 3,
    reporting_currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'active',
    real_company_verified_at TIMESTAMPTZ,
    real_company_verification_evidence_id BIGINT,
    identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_research_company_fye CHECK (fiscal_year_end_month BETWEEN 1 AND 12),
    CONSTRAINT chk_research_company_status CHECK (status IN ('active', 'inactive', 'merged', 'delisted')),
    UNIQUE (primary_exchange, primary_symbol)
);

CREATE TABLE IF NOT EXISTS research.fundamental_evidence (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    source_document_id BIGINT REFERENCES portfolio.long_term_source_documents(id) ON DELETE SET NULL,
    corporate_filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE SET NULL,
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    retrieved_at TIMESTAMPTZ NOT NULL,
    source_as_of_date DATE,
    page_start INTEGER,
    page_end INTEGER,
    section_reference TEXT,
    content_hash TEXT,
    extraction_method TEXT NOT NULL DEFAULT 'manual_verified',
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_fundamental_evidence_locator CHECK (
        num_nonnulls(source_document_id, corporate_filing_id, raw_artifact_id, nullif(source_url, '')) > 0
    ),
    CONSTRAINT chk_fundamental_evidence_pages CHECK (
        page_start IS NULL OR (page_start > 0 AND (page_end IS NULL OR page_end >= page_start))
    ),
    CONSTRAINT chk_fundamental_evidence_verification CHECK (
        verification_status IN ('unverified', 'machine_extracted', 'human_verified', 'superseded', 'rejected')
    ),
    CONSTRAINT chk_fundamental_evidence_verified_fields CHECK (
        verification_status <> 'human_verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)
    )
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_research_company_verification_evidence'
          AND conrelid = 'research.companies'::regclass
    ) THEN
        ALTER TABLE research.companies
            ADD CONSTRAINT fk_research_company_verification_evidence
            FOREIGN KEY (real_company_verification_evidence_id)
            REFERENCES research.fundamental_evidence(id) ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_fundamental_evidence_company
ON research.fundamental_evidence (company_id, published_at DESC, retrieved_at DESC);

CREATE INDEX IF NOT EXISTS idx_fundamental_evidence_source_document
ON research.fundamental_evidence (source_document_id) WHERE source_document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fundamental_evidence_filing
ON research.fundamental_evidence (corporate_filing_id) WHERE corporate_filing_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS research.statement_fact_definitions (
    id BIGSERIAL PRIMARY KEY,
    fact_key TEXT NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL,
    statement_type TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'monetary',
    default_unit TEXT,
    balance_type TEXT NOT NULL DEFAULT 'flow',
    description TEXT,
    taxonomy_mappings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_statement_definition_type CHECK (
        statement_type IN ('income_statement', 'balance_sheet', 'cash_flow', 'equity', 'notes', 'derived')
    ),
    CONSTRAINT chk_statement_definition_balance CHECK (balance_type IN ('instant', 'flow', 'ratio', 'count'))
);

CREATE TABLE IF NOT EXISTS research.company_statement_facts (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    fact_definition_id BIGINT NOT NULL REFERENCES research.statement_fact_definitions(id),
    fiscal_year INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL,
    period_start DATE,
    period_end DATE NOT NULL,
    statement_scope TEXT NOT NULL,
    value_numeric NUMERIC,
    value_text TEXT,
    currency TEXT,
    unit TEXT,
    scale_power INTEGER NOT NULL DEFAULT 0,
    reported_value_text TEXT,
    source_as_of_date DATE NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    restatement_version INTEGER NOT NULL DEFAULT 1,
    restatement_status TEXT NOT NULL DEFAULT 'reported',
    supersedes_fact_id BIGINT REFERENCES research.company_statement_facts(id) ON DELETE SET NULL,
    is_current BOOLEAN NOT NULL DEFAULT true,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_statement_fact_value CHECK (num_nonnulls(value_numeric, value_text) = 1),
    CONSTRAINT chk_statement_fact_period CHECK (period_start IS NULL OR period_start <= period_end),
    CONSTRAINT chk_statement_fact_fiscal_period CHECK (
        fiscal_period IN ('FY', 'H1', 'H2', 'Q1', 'Q2', 'Q3', 'Q4', 'TTM')
    ),
    CONSTRAINT chk_statement_fact_scope CHECK (statement_scope IN ('consolidated', 'standalone')),
    CONSTRAINT chk_statement_fact_restatement CHECK (
        restatement_status IN ('reported', 'restated', 'reclassified', 'corrected') AND restatement_version > 0
    ),
    UNIQUE (
        company_id, fact_definition_id, fiscal_year, fiscal_period,
        period_end, statement_scope, restatement_version
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_company_statement_fact_current
ON research.company_statement_facts (
    company_id, fact_definition_id, fiscal_year, fiscal_period, period_end, statement_scope
)
WHERE is_current;

CREATE INDEX IF NOT EXISTS idx_company_statement_fact_series
ON research.company_statement_facts (
    company_id, fact_definition_id, statement_scope, period_end DESC, available_at DESC
);

CREATE TABLE IF NOT EXISTS research.company_segments (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    segment_key TEXT NOT NULL,
    segment_name TEXT NOT NULL,
    segment_type TEXT NOT NULL,
    parent_segment_id BIGINT REFERENCES research.company_segments(id) ON DELETE SET NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_company_segment_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (company_id, segment_key, valid_from)
);

CREATE TABLE IF NOT EXISTS research.company_segment_facts (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    segment_id BIGINT NOT NULL REFERENCES research.company_segments(id) ON DELETE CASCADE,
    fact_definition_id BIGINT NOT NULL REFERENCES research.statement_fact_definitions(id),
    fiscal_year INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL,
    period_start DATE,
    period_end DATE NOT NULL,
    value_numeric NUMERIC NOT NULL,
    currency TEXT,
    unit TEXT,
    scale_power INTEGER NOT NULL DEFAULT 0,
    source_as_of_date DATE NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_company_segment_fact_period CHECK (period_start IS NULL OR period_start <= period_end),
    CONSTRAINT chk_company_segment_fact_fiscal_period CHECK (
        fiscal_period IN ('FY', 'H1', 'H2', 'Q1', 'Q2', 'Q3', 'Q4', 'TTM')
    ),
    UNIQUE (segment_id, fact_definition_id, fiscal_year, fiscal_period, period_end, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_company_segment_fact_series
ON research.company_segment_facts (company_id, segment_id, fact_definition_id, period_end DESC);

CREATE TABLE IF NOT EXISTS research.operational_kpi_definitions (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    kpi_key TEXT NOT NULL,
    kpi_name TEXT NOT NULL,
    description TEXT NOT NULL,
    unit TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'numeric',
    frequency TEXT NOT NULL,
    aggregation_method TEXT,
    definition_valid_from DATE NOT NULL,
    definition_valid_to DATE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_operational_kpi_definition_dates CHECK (
        definition_valid_to IS NULL OR definition_valid_to >= definition_valid_from
    ),
    UNIQUE (company_id, kpi_key, definition_valid_from)
);

CREATE TABLE IF NOT EXISTS research.operational_kpi_observations (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    kpi_definition_id BIGINT NOT NULL REFERENCES research.operational_kpi_definitions(id) ON DELETE CASCADE,
    period_start DATE,
    period_end DATE NOT NULL,
    value_numeric NUMERIC,
    value_text TEXT,
    source_as_of_date DATE NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_operational_kpi_observation_value CHECK (num_nonnulls(value_numeric, value_text) = 1),
    CONSTRAINT chk_operational_kpi_observation_period CHECK (period_start IS NULL OR period_start <= period_end),
    UNIQUE (kpi_definition_id, period_end, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_operational_kpi_observation_series
ON research.operational_kpi_observations (company_id, kpi_definition_id, period_end DESC);

CREATE TABLE IF NOT EXISTS research.market_share_observations (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    market_key TEXT NOT NULL,
    market_name TEXT NOT NULL,
    product_or_service TEXT,
    geography TEXT NOT NULL,
    channel TEXT,
    period_start DATE,
    period_end DATE NOT NULL,
    share_pct NUMERIC NOT NULL,
    numerator_value NUMERIC,
    denominator_value NUMERIC,
    measurement_basis TEXT NOT NULL,
    methodology TEXT,
    source_as_of_date DATE NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_market_share_pct CHECK (share_pct BETWEEN 0 AND 100),
    CONSTRAINT chk_market_share_period CHECK (period_start IS NULL OR period_start <= period_end),
    UNIQUE (company_id, market_key, geography, period_end, measurement_basis, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_market_share_series
ON research.market_share_observations (company_id, market_key, geography, period_end DESC);

CREATE TABLE IF NOT EXISTS research.peer_sets (
    id BIGSERIAL PRIMARY KEY,
    peer_set_key TEXT NOT NULL UNIQUE,
    subject_company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    peer_set_name TEXT NOT NULL,
    methodology TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_peer_set_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS research.peer_set_memberships (
    id BIGSERIAL PRIMARY KEY,
    peer_set_id BIGINT NOT NULL REFERENCES research.peer_sets(id) ON DELETE CASCADE,
    peer_company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    membership_role TEXT NOT NULL DEFAULT 'operating_peer',
    inclusion_reason TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_peer_membership_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (peer_set_id, peer_company_id, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_peer_set_memberships_company
ON research.peer_set_memberships (peer_company_id, valid_from DESC);

CREATE TABLE IF NOT EXISTS research.management_communications (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    communication_key TEXT NOT NULL UNIQUE,
    communication_type TEXT NOT NULL,
    title TEXT NOT NULL,
    communication_date DATE NOT NULL,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    language_code TEXT NOT NULL DEFAULT 'en',
    body_text TEXT,
    transcript_status TEXT NOT NULL DEFAULT 'registered',
    speaker_map JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_management_communication_type CHECK (
        communication_type IN (
            'earnings_call', 'annual_letter', 'annual_report_message', 'investor_day',
            'conference', 'interview', 'exchange_communication', 'credit_rating_call'
        )
    ),
    CONSTRAINT chk_management_transcript_status CHECK (
        transcript_status IN ('registered', 'extracted', 'reviewed', 'superseded', 'rejected')
    )
);

CREATE TABLE IF NOT EXISTS research.management_claims (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    communication_id BIGINT NOT NULL REFERENCES research.management_communications(id) ON DELETE CASCADE,
    claim_key TEXT NOT NULL UNIQUE,
    claim_date DATE NOT NULL,
    speaker_name TEXT,
    speaker_role TEXT,
    claim_type TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    normalized_claim TEXT NOT NULL,
    metric_key TEXT,
    target_operator TEXT,
    target_value NUMERIC,
    target_unit TEXT,
    target_period_end DATE,
    assessment_due_at DATE,
    claim_status TEXT NOT NULL DEFAULT 'open',
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    source_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_management_claim_status CHECK (
        claim_status IN ('open', 'due', 'met', 'partially_met', 'missed', 'withdrawn', 'not_measurable')
    )
);

CREATE TABLE IF NOT EXISTS research.management_claim_outcomes (
    id BIGSERIAL PRIMARY KEY,
    claim_id BIGINT NOT NULL REFERENCES research.management_claims(id) ON DELETE CASCADE,
    outcome_date DATE NOT NULL,
    outcome_status TEXT NOT NULL,
    actual_value NUMERIC,
    actual_unit TEXT,
    assessment TEXT NOT NULL,
    attribution_notes TEXT,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    assessed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_management_claim_outcome_status CHECK (
        outcome_status IN ('met', 'partially_met', 'missed', 'withdrawn', 'not_measurable', 'pending')
    ),
    UNIQUE (claim_id, outcome_date, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_management_claims_due
ON research.management_claims (company_id, claim_status, assessment_due_at);

CREATE TABLE IF NOT EXISTS research.investment_dossiers (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    dossier_key TEXT NOT NULL UNIQUE,
    dossier_status TEXT NOT NULL DEFAULT 'draft',
    owner_agent TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    current_version_number INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_investment_dossier_status CHECK (
        dossier_status IN ('draft', 'in_review', 'committee_ready', 'approved', 'stale', 'archived')
    ),
    UNIQUE NULLS NOT DISTINCT (company_id, holding_thesis_id)
);

CREATE TABLE IF NOT EXISTS research.investment_dossier_versions (
    id BIGSERIAL PRIMARY KEY,
    dossier_id BIGINT NOT NULL REFERENCES research.investment_dossiers(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    version_status TEXT NOT NULL DEFAULT 'draft',
    research_as_of TIMESTAMPTZ NOT NULL,
    source_cutoff_at TIMESTAMPTZ NOT NULL,
    executive_conclusion TEXT,
    decision_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_coverage JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    supersedes_version_id BIGINT REFERENCES research.investment_dossier_versions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_dossier_version_status CHECK (
        version_status IN ('draft', 'specialist_review', 'committee_ready', 'approved', 'superseded', 'rejected')
    ),
    UNIQUE (dossier_id, version_number)
);

CREATE TABLE IF NOT EXISTS research.investment_dossier_sections (
    id BIGSERIAL PRIMARY KEY,
    dossier_version_id BIGINT NOT NULL REFERENCES research.investment_dossier_versions(id) ON DELETE CASCADE,
    section_key TEXT NOT NULL,
    section_order SMALLINT NOT NULL,
    section_title TEXT NOT NULL,
    section_status TEXT NOT NULL DEFAULT 'draft',
    content_markdown TEXT NOT NULL,
    primary_evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    evidence_as_of TIMESTAMPTZ NOT NULL,
    generated_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_dossier_section_key CHECK (section_key IN (
        'executive_conclusion', 'industry_value_chain', 'business_model_unit_economics',
        'segments_geography_customers', 'market_size_share_competition', 'moat_durability',
        'management_capital_allocation', 'ten_year_financial_teardown',
        'forensic_accounting_governance', 'peer_benchmarking', 'operating_scenarios',
        'valuation', 'catalysts_thesis_killers_monitoring', 'portfolio_fit_opportunity_cost',
        'specialist_opinions_committee_decision'
    )),
    CONSTRAINT chk_dossier_section_status CHECK (
        section_status IN ('draft', 'evidence_complete', 'reviewed', 'rejected', 'stale')
    ),
    UNIQUE (dossier_version_id, section_key),
    UNIQUE (dossier_version_id, section_order)
);

CREATE TABLE IF NOT EXISTS research.investment_dossier_section_evidence (
    dossier_section_id BIGINT NOT NULL REFERENCES research.investment_dossier_sections(id) ON DELETE CASCADE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    evidence_role TEXT NOT NULL DEFAULT 'supporting',
    citation_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier_section_id, evidence_id, evidence_role)
);

CREATE TABLE IF NOT EXISTS research.investment_dossier_refresh_triggers (
    id BIGSERIAL PRIMARY KEY,
    dossier_id BIGINT NOT NULL REFERENCES research.investment_dossiers(id) ON DELETE CASCADE,
    trigger_type TEXT NOT NULL,
    trigger_source_table TEXT NOT NULL,
    trigger_source_id TEXT NOT NULL,
    materiality TEXT NOT NULL DEFAULT 'review',
    event_at TIMESTAMPTZ NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    refresh_status TEXT NOT NULL DEFAULT 'pending',
    assigned_to TEXT,
    completed_version_id BIGINT REFERENCES research.investment_dossier_versions(id) ON DELETE SET NULL,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_dossier_refresh_trigger_type CHECK (trigger_type IN (
        'results', 'filing', 'earnings_call', 'annual_report', 'annual_letter',
        'investor_presentation', 'credit_rating_change', 'material_news',
        'governance_event', 'capital_allocation_event', 'scheduled_review'
    )),
    CONSTRAINT chk_dossier_refresh_status CHECK (
        refresh_status IN ('pending', 'assigned', 'in_progress', 'completed', 'dismissed')
    ),
    UNIQUE (dossier_id, trigger_source_table, trigger_source_id, trigger_type)
);

CREATE INDEX IF NOT EXISTS idx_dossier_refresh_queue
ON research.investment_dossier_refresh_triggers (refresh_status, materiality, event_at DESC);

CREATE TABLE IF NOT EXISTS research.fundamental_specialist_opinions (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    dossier_version_id BIGINT NOT NULL REFERENCES research.investment_dossier_versions(id) ON DELETE CASCADE,
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    specialist_key TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    opinion_status TEXT NOT NULL DEFAULT 'draft',
    conclusion TEXT NOT NULL,
    score_low NUMERIC,
    score_base NUMERIC,
    score_high NUMERIC,
    confidence_pct NUMERIC,
    disconfirming_evidence TEXT,
    required_followups JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    opinion_as_of TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_fundamental_specialist_key CHECK (specialist_key IN (
        'business_model', 'moat', 'industry', 'management', 'governance',
        'capital_allocation', 'financial_quality', 'forensic_accounting',
        'valuation', 'bear_case', 'risk', 'portfolio_fit'
    )),
    CONSTRAINT chk_fundamental_opinion_status CHECK (
        opinion_status IN ('draft', 'evidence_complete', 'reviewed', 'dissent', 'rejected', 'stale')
    ),
    CONSTRAINT chk_fundamental_opinion_confidence CHECK (
        confidence_pct IS NULL OR confidence_pct BETWEEN 0 AND 100
    ),
    UNIQUE (dossier_version_id, specialist_key, agent_name)
);

CREATE INDEX IF NOT EXISTS idx_fundamental_specialist_opinions_company
ON research.fundamental_specialist_opinions (company_id, opinion_as_of DESC);

CREATE TABLE IF NOT EXISTS research.fundamental_acceptance_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    dossier_version_id BIGINT REFERENCES research.investment_dossier_versions(id) ON DELETE SET NULL,
    acceptance_profile TEXT NOT NULL DEFAULT 'institutional_fundamental_v1',
    run_status TEXT NOT NULL DEFAULT 'opened',
    real_company_verified BOOLEAN NOT NULL,
    verification_evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    data_as_of TIMESTAMPTZ NOT NULL,
    started_by TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    notes TEXT,
    CONSTRAINT chk_fundamental_acceptance_run_status CHECK (
        run_status IN ('opened', 'running', 'passed', 'failed', 'blocked')
    ),
    CONSTRAINT chk_fundamental_acceptance_real_company CHECK (real_company_verified)
);

CREATE TABLE IF NOT EXISTS research.fundamental_acceptance_gates (
    id BIGSERIAL PRIMARY KEY,
    acceptance_run_id BIGINT NOT NULL REFERENCES research.fundamental_acceptance_runs(id) ON DELETE CASCADE,
    gate_key TEXT NOT NULL,
    gate_name TEXT NOT NULL,
    gate_status TEXT NOT NULL DEFAULT 'pending',
    observed_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    evaluated_by TEXT NOT NULL DEFAULT 'Fundamental Research Acceptance Worker',
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_fundamental_acceptance_gate_status CHECK (
        gate_status IN ('pending', 'passed', 'failed', 'blocked', 'waived')
    ),
    UNIQUE (acceptance_run_id, gate_key)
);

CREATE OR REPLACE FUNCTION research.record_company_statement_fact(
    p_company_id BIGINT,
    p_fact_definition_id BIGINT,
    p_fiscal_year INTEGER,
    p_fiscal_period TEXT,
    p_period_start DATE,
    p_period_end DATE,
    p_statement_scope TEXT,
    p_value_numeric NUMERIC,
    p_value_text TEXT,
    p_currency TEXT,
    p_unit TEXT,
    p_scale_power INTEGER,
    p_reported_value_text TEXT,
    p_source_as_of_date DATE,
    p_available_at TIMESTAMPTZ,
    p_restatement_status TEXT,
    p_evidence_id BIGINT,
    p_source_locator JSONB DEFAULT '{}'::jsonb,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_previous_id BIGINT;
    v_next_version INTEGER := 1;
    v_new_id BIGINT;
BEGIN
    SELECT id, restatement_version + 1
    INTO v_previous_id, v_next_version
    FROM research.company_statement_facts
    WHERE company_id = p_company_id
      AND fact_definition_id = p_fact_definition_id
      AND fiscal_year = p_fiscal_year
      AND fiscal_period = p_fiscal_period
      AND period_end = p_period_end
      AND statement_scope = p_statement_scope
      AND is_current
    FOR UPDATE;

    IF v_previous_id IS NOT NULL THEN
        UPDATE research.company_statement_facts
        SET is_current = false
        WHERE id = v_previous_id;
    END IF;

    INSERT INTO research.company_statement_facts (
        company_id, fact_definition_id, fiscal_year, fiscal_period, period_start, period_end,
        statement_scope, value_numeric, value_text, currency, unit, scale_power,
        reported_value_text, source_as_of_date, available_at, restatement_version,
        restatement_status, supersedes_fact_id, is_current, evidence_id, source_locator, metadata
    ) VALUES (
        p_company_id, p_fact_definition_id, p_fiscal_year, p_fiscal_period, p_period_start, p_period_end,
        p_statement_scope, p_value_numeric, p_value_text, p_currency, p_unit, coalesce(p_scale_power, 0),
        p_reported_value_text, p_source_as_of_date, p_available_at, v_next_version,
        p_restatement_status, v_previous_id, true, p_evidence_id,
        coalesce(p_source_locator, '{}'::jsonb), coalesce(p_metadata, '{}'::jsonb)
    )
    RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$;

CREATE OR REPLACE FUNCTION research.company_statement_series_as_of(
    p_company_id BIGINT,
    p_fact_key TEXT,
    p_as_of TIMESTAMPTZ DEFAULT now(),
    p_years INTEGER DEFAULT 15,
    p_statement_scope TEXT DEFAULT 'consolidated'
)
RETURNS TABLE (
    fact_id BIGINT,
    fact_key TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    period_end DATE,
    value_numeric NUMERIC,
    value_text TEXT,
    currency TEXT,
    unit TEXT,
    restatement_version INTEGER,
    restatement_status TEXT,
    source_as_of_date DATE,
    available_at TIMESTAMPTZ,
    evidence_id BIGINT
)
LANGUAGE sql
STABLE
AS $$
    WITH point_in_time AS (
        SELECT
            fact.*,
            definition.fact_key,
            row_number() OVER (
                PARTITION BY fact.company_id, fact.fact_definition_id, fact.fiscal_year,
                             fact.fiscal_period, fact.period_end, fact.statement_scope
                ORDER BY fact.restatement_version DESC, fact.recorded_at DESC
            ) AS version_rank
        FROM research.company_statement_facts fact
        JOIN research.statement_fact_definitions definition ON definition.id = fact.fact_definition_id
        WHERE fact.company_id = p_company_id
          AND definition.fact_key = p_fact_key
          AND fact.statement_scope = p_statement_scope
          AND fact.available_at <= p_as_of
          AND fact.recorded_at <= p_as_of
    )
    SELECT
        point_in_time.id,
        point_in_time.fact_key,
        point_in_time.fiscal_year,
        point_in_time.fiscal_period,
        point_in_time.period_end,
        point_in_time.value_numeric,
        point_in_time.value_text,
        point_in_time.currency,
        point_in_time.unit,
        point_in_time.restatement_version,
        point_in_time.restatement_status,
        point_in_time.source_as_of_date,
        point_in_time.available_at,
        point_in_time.evidence_id
    FROM point_in_time
    WHERE point_in_time.version_rank = 1
      AND point_in_time.fiscal_year >= extract(year FROM p_as_of)::INTEGER - greatest(1, least(p_years, 15))
    ORDER BY point_in_time.period_end, point_in_time.fiscal_period;
$$;

CREATE OR REPLACE FUNCTION research.open_real_company_acceptance_run(
    p_run_key TEXT,
    p_company_id BIGINT,
    p_holding_thesis_id BIGINT,
    p_dossier_version_id BIGINT,
    p_data_as_of TIMESTAMPTZ,
    p_started_by TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_verification_evidence_id BIGINT;
    v_run_id BIGINT;
BEGIN
    SELECT company.real_company_verification_evidence_id
    INTO v_verification_evidence_id
    FROM research.companies company
    JOIN research.fundamental_evidence evidence
      ON evidence.id = company.real_company_verification_evidence_id
     AND evidence.company_id = company.id
     AND evidence.verification_status = 'human_verified'
    WHERE company.id = p_company_id
      AND company.status = 'active'
      AND company.real_company_verified_at IS NOT NULL;

    IF v_verification_evidence_id IS NULL THEN
        RAISE EXCEPTION 'company % is not verified as a real company with human-verified evidence', p_company_id;
    END IF;

    INSERT INTO research.fundamental_acceptance_runs (
        run_key, company_id, holding_thesis_id, dossier_version_id, run_status,
        real_company_verified, verification_evidence_id, data_as_of, started_by
    ) VALUES (
        p_run_key, p_company_id, p_holding_thesis_id, p_dossier_version_id, 'opened',
        true, v_verification_evidence_id, p_data_as_of, p_started_by
    )
    RETURNING id INTO v_run_id;

    RETURN v_run_id;
END;
$$;

CREATE OR REPLACE VIEW research.v_company_statement_facts_current AS
SELECT
    company.id AS company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    company.primary_exchange,
    definition.fact_key,
    definition.canonical_name,
    definition.statement_type,
    fact.fiscal_year,
    fact.fiscal_period,
    fact.period_start,
    fact.period_end,
    fact.statement_scope,
    fact.value_numeric,
    fact.value_text,
    fact.currency,
    fact.unit,
    fact.scale_power,
    fact.source_as_of_date,
    fact.available_at,
    fact.restatement_version,
    fact.restatement_status,
    fact.evidence_id,
    evidence.source_type,
    evidence.source_name,
    evidence.source_url,
    evidence.verification_status,
    fact.source_locator
FROM research.company_statement_facts fact
JOIN research.companies company ON company.id = fact.company_id
JOIN research.statement_fact_definitions definition ON definition.id = fact.fact_definition_id
JOIN research.fundamental_evidence evidence ON evidence.id = fact.evidence_id
WHERE fact.is_current;

CREATE OR REPLACE VIEW research.v_management_claim_scorecard AS
SELECT
    company.id AS company_id,
    company.company_key,
    company.legal_name,
    claim.id AS claim_id,
    claim.claim_key,
    communication.communication_type,
    communication.title AS communication_title,
    claim.claim_date,
    claim.speaker_name,
    claim.speaker_role,
    claim.claim_type,
    claim.claim_text,
    claim.metric_key,
    claim.target_operator,
    claim.target_value,
    claim.target_unit,
    claim.target_period_end,
    claim.assessment_due_at,
    claim.claim_status,
    outcome.outcome_date,
    outcome.outcome_status,
    outcome.actual_value,
    outcome.actual_unit,
    outcome.assessment,
    claim.evidence_id AS claim_evidence_id,
    outcome.evidence_id AS outcome_evidence_id
FROM research.management_claims claim
JOIN research.companies company ON company.id = claim.company_id
JOIN research.management_communications communication ON communication.id = claim.communication_id
LEFT JOIN LATERAL (
    SELECT latest.*
    FROM research.management_claim_outcomes latest
    WHERE latest.claim_id = claim.id
    ORDER BY latest.outcome_date DESC, latest.id DESC
    LIMIT 1
) outcome ON true;

CREATE OR REPLACE VIEW research.v_latest_investment_dossiers AS
SELECT
    dossier.id AS dossier_id,
    dossier.dossier_key,
    dossier.company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    company.primary_exchange,
    dossier.holding_thesis_id,
    dossier.dossier_status,
    version.id AS dossier_version_id,
    version.version_number,
    version.version_status,
    version.research_as_of,
    version.source_cutoff_at,
    version.executive_conclusion,
    version.decision_summary,
    version.evidence_coverage,
    coalesce(section.section_count, 0) AS section_count,
    coalesce(section.reviewed_section_count, 0) AS reviewed_section_count,
    coalesce(opinion.specialist_count, 0) AS specialist_count,
    coalesce(opinion.has_portfolio_fit, false) AS has_portfolio_fit,
    dossier.updated_at
FROM research.investment_dossiers dossier
JOIN research.companies company ON company.id = dossier.company_id
LEFT JOIN LATERAL (
    SELECT candidate.*
    FROM research.investment_dossier_versions candidate
    WHERE candidate.dossier_id = dossier.id
    ORDER BY candidate.version_number DESC
    LIMIT 1
) version ON true
LEFT JOIN LATERAL (
    SELECT
        count(*) AS section_count,
        count(*) FILTER (WHERE section_status IN ('evidence_complete', 'reviewed')) AS reviewed_section_count
    FROM research.investment_dossier_sections candidate
    WHERE candidate.dossier_version_id = version.id
) section ON true
LEFT JOIN LATERAL (
    SELECT
        count(DISTINCT candidate.specialist_key) AS specialist_count,
        bool_or(candidate.specialist_key = 'portfolio_fit') AS has_portfolio_fit
    FROM research.fundamental_specialist_opinions candidate
    WHERE candidate.dossier_version_id = version.id
) opinion ON true;

CREATE OR REPLACE VIEW research.v_dossier_refresh_queue AS
SELECT
    trigger.id,
    trigger.dossier_id,
    dossier.dossier_key,
    dossier.company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    trigger.trigger_type,
    trigger.trigger_source_table,
    trigger.trigger_source_id,
    trigger.materiality,
    trigger.event_at,
    trigger.detected_at,
    trigger.refresh_status,
    trigger.assigned_to,
    trigger.evidence_id,
    trigger.metadata
FROM research.investment_dossier_refresh_triggers trigger
JOIN research.investment_dossiers dossier ON dossier.id = trigger.dossier_id
JOIN research.companies company ON company.id = dossier.company_id
WHERE trigger.refresh_status IN ('pending', 'assigned', 'in_progress')
ORDER BY
    CASE trigger.materiality WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'review' THEN 3 ELSE 4 END,
    trigger.event_at DESC;

CREATE OR REPLACE VIEW research.v_company_fundamental_coverage AS
SELECT
    company.id AS company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    company.primary_exchange,
    company.real_company_verified_at IS NOT NULL AS real_company_verified,
    count(DISTINCT fact.fiscal_year) FILTER (WHERE fact.is_current AND fact.fiscal_period = 'FY') AS annual_statement_years,
    min(fact.fiscal_year) FILTER (WHERE fact.is_current AND fact.fiscal_period = 'FY') AS first_statement_year,
    max(fact.fiscal_year) FILTER (WHERE fact.is_current AND fact.fiscal_period = 'FY') AS latest_statement_year,
    count(DISTINCT segment.id) AS segment_count,
    count(DISTINCT kpi.id) AS operational_kpi_count,
    count(DISTINCT market_share.market_key) AS market_share_series_count,
    count(DISTINCT peer_member.peer_company_id) AS peer_count,
    count(DISTINCT communication.id) AS management_communication_count,
    count(DISTINCT claim.id) AS management_claim_count,
    count(DISTINCT claim_outcome.claim_id) AS claims_with_outcomes,
    max(fact.available_at) AS latest_statement_available_at,
    max(evidence.retrieved_at) AS latest_evidence_retrieved_at
FROM research.companies company
LEFT JOIN research.company_statement_facts fact ON fact.company_id = company.id
LEFT JOIN research.fundamental_evidence evidence ON evidence.company_id = company.id
LEFT JOIN research.company_segments segment ON segment.company_id = company.id
LEFT JOIN research.operational_kpi_definitions kpi ON kpi.company_id = company.id
LEFT JOIN research.market_share_observations market_share ON market_share.company_id = company.id
LEFT JOIN research.peer_sets peer_set ON peer_set.subject_company_id = company.id
LEFT JOIN research.peer_set_memberships peer_member ON peer_member.peer_set_id = peer_set.id
LEFT JOIN research.management_communications communication ON communication.company_id = company.id
LEFT JOIN research.management_claims claim ON claim.company_id = company.id
LEFT JOIN research.management_claim_outcomes claim_outcome ON claim_outcome.claim_id = claim.id
GROUP BY company.id;

CREATE OR REPLACE VIEW research.v_real_company_acceptance_status AS
SELECT
    run.id AS acceptance_run_id,
    run.run_key,
    run.company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    company.primary_exchange,
    run.holding_thesis_id,
    run.dossier_version_id,
    run.acceptance_profile,
    run.run_status,
    run.real_company_verified,
    run.verification_evidence_id,
    run.data_as_of,
    count(gate.id) AS gate_count,
    count(gate.id) FILTER (WHERE gate.gate_status = 'passed') AS passed_gate_count,
    count(gate.id) FILTER (WHERE gate.gate_status = 'failed') AS failed_gate_count,
    count(gate.id) FILTER (WHERE gate.gate_status = 'blocked') AS blocked_gate_count,
    jsonb_object_agg(
        gate.gate_key,
        jsonb_build_object(
            'status', gate.gate_status,
            'observed', gate.observed_value,
            'required', gate.required_value,
            'failure_reason', gate.failure_reason,
            'evidence_id', gate.evidence_id
        )
    ) FILTER (WHERE gate.id IS NOT NULL) AS gates,
    run.started_by,
    run.started_at,
    run.completed_at,
    run.notes
FROM research.fundamental_acceptance_runs run
JOIN research.companies company ON company.id = run.company_id
LEFT JOIN research.fundamental_acceptance_gates gate ON gate.acceptance_run_id = run.id
GROUP BY run.id, company.id;

COMMIT;
