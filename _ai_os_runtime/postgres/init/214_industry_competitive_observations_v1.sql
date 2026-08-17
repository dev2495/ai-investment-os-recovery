BEGIN;

CREATE TABLE IF NOT EXISTS research.industry_competitive_observations (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    observation_key TEXT NOT NULL,
    category TEXT NOT NULL,
    conclusion TEXT NOT NULL,
    value_numeric NUMERIC,
    unit TEXT,
    metric_availability TEXT NOT NULL DEFAULT 'qualitative_only',
    period_end DATE NOT NULL,
    source_page INTEGER NOT NULL,
    source_excerpt TEXT NOT NULL,
    extraction_method TEXT NOT NULL DEFAULT 'deterministic_pattern',
    verification_status TEXT NOT NULL DEFAULT 'machine_extracted',
    available_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_industry_observation_category CHECK (category IN (
      'market_share','capacity','value_chain','end_market_demand','replacement_cycle','competitive_position'
    )),
    CONSTRAINT chk_industry_metric_availability CHECK (metric_availability IN (
      'quantified','qualitative_only','not_disclosed'
    )),
    CONSTRAINT chk_industry_observation_page CHECK (source_page > 0),
    CONSTRAINT chk_industry_observation_verification CHECK (
      verification_status IN ('machine_extracted','human_verified','rejected','superseded')
    ),
    UNIQUE (company_id,evidence_id,observation_key,period_end)
);

CREATE INDEX IF NOT EXISTS idx_industry_observations_company
ON research.industry_competitive_observations (company_id,period_end DESC,category);

COMMENT ON TABLE research.industry_competitive_observations IS
  'Primary-source industry and competitive disclosures, including explicit non-disclosure of numeric market share.';

COMMIT;
