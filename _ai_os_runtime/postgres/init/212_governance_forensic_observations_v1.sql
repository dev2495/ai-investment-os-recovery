BEGIN;

CREATE TABLE IF NOT EXISTS research.governance_forensic_observations (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    evidence_id BIGINT NOT NULL REFERENCES research.fundamental_evidence(id),
    observation_key TEXT NOT NULL,
    category TEXT NOT NULL,
    observation_status TEXT NOT NULL,
    severity TEXT NOT NULL,
    conclusion TEXT NOT NULL,
    disclosed_value NUMERIC,
    disclosed_unit TEXT,
    period_end DATE,
    source_page INTEGER NOT NULL,
    source_excerpt TEXT NOT NULL,
    extraction_method TEXT NOT NULL DEFAULT 'deterministic_pattern',
    verification_status TEXT NOT NULL DEFAULT 'machine_extracted',
    available_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_gf_category CHECK (category IN (
        'auditor', 'related_party', 'legal_regulatory', 'contingent_liability',
        'internal_control', 'remuneration', 'pledge', 'minority_treatment',
        'whistleblower', 'fraud'
    )),
    CONSTRAINT chk_gf_status CHECK (observation_status IN (
        'no_adverse_remark', 'no_material_issue_disclosed', 'emphasis_of_matter',
        'active_issue', 'qualified', 'exception', 'disclosure_only'
    )),
    CONSTRAINT chk_gf_severity CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_gf_verification CHECK (verification_status IN (
        'machine_extracted', 'human_verified', 'rejected', 'superseded'
    )),
    CONSTRAINT chk_gf_page_positive CHECK (source_page > 0),
    CONSTRAINT chk_gf_excerpt_present CHECK (length(btrim(source_excerpt)) > 0),
    UNIQUE (company_id, evidence_id, observation_key, period_end)
);

CREATE INDEX IF NOT EXISTS idx_gf_company_period
ON research.governance_forensic_observations (company_id, period_end DESC, category, severity);

CREATE INDEX IF NOT EXISTS idx_gf_active_issues
ON research.governance_forensic_observations (company_id, severity, available_at DESC)
WHERE observation_status IN ('active_issue', 'qualified', 'exception')
  AND verification_status NOT IN ('rejected', 'superseded');

COMMENT ON TABLE research.governance_forensic_observations IS
    'Point-in-time, page-cited governance and forensic disclosures. Evidence completeness does not imply a clean-company conclusion.';

COMMIT;
