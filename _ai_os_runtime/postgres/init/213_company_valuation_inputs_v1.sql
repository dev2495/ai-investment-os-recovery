BEGIN;

CREATE TABLE IF NOT EXISTS research.company_valuation_inputs (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    fiscal_year INTEGER NOT NULL,
    input_key TEXT NOT NULL,
    value_numeric NUMERIC NOT NULL,
    unit TEXT NOT NULL,
    statement_scope TEXT NOT NULL DEFAULT 'consolidated',
    source_page INTEGER NOT NULL,
    source_excerpt TEXT NOT NULL,
    extraction_method TEXT NOT NULL DEFAULT 'deterministic_pattern',
    verification_status TEXT NOT NULL DEFAULT 'machine_extracted',
    available_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_company_valuation_input_key CHECK (input_key IN (
        'diluted_weighted_average_shares', 'basic_weighted_average_shares',
        'diluted_eps_continuing', 'basic_eps_continuing', 'shares_outstanding'
    )),
    CONSTRAINT chk_company_valuation_input_value CHECK (value_numeric > 0),
    CONSTRAINT chk_company_valuation_input_page CHECK (source_page > 0),
    CONSTRAINT chk_company_valuation_input_verification CHECK (
        verification_status IN ('machine_extracted','human_verified','rejected','superseded')
    ),
    UNIQUE (company_id, evidence_id, fiscal_year, input_key, statement_scope)
);

CREATE INDEX IF NOT EXISTS idx_company_valuation_inputs_lookup
ON research.company_valuation_inputs (company_id, fiscal_year DESC, input_key, statement_scope);

COMMENT ON TABLE research.company_valuation_inputs IS
    'Page-cited inputs required by deterministic valuation engines. Machine extraction never constitutes operator review.';

COMMIT;
