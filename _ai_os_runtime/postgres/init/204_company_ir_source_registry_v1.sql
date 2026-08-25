BEGIN;

INSERT INTO core.data_source_registry (
    source_key, source_name, source_type, provider, connection_mode, status,
    freshness_target_minutes, owner_agent, sensitivity, notes, metadata
) VALUES (
    'company_ir_official', 'Official Company Investor Relations', 'research_filings',
    'Listed companies', 'https_primary_source', 'active', 1440,
    'Fundamental Data Steward', 'public',
    'Governed registry of official investor-relations pages and annual-report PDFs. Collection is evidence-only.',
    '{"primary_source_only":true,"financial_facts_require_separate_normalization":true,"broker_write_allowed":false}'::jsonb
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name=EXCLUDED.source_name,
    status='active',
    owner_agent=EXCLUDED.owner_agent,
    sensitivity='public',
    metadata=core.data_source_registry.metadata || EXCLUDED.metadata,
    updated_at=now();

CREATE TABLE IF NOT EXISTS research.company_ir_sources (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL REFERENCES core.data_source_registry(source_key) ON DELETE RESTRICT DEFAULT 'company_ir_official',
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    company_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_url TEXT NOT NULL,
    fiscal_year_end INTEGER,
    document_label TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    verified_at TIMESTAMPTZ NOT NULL,
    verified_by TEXT NOT NULL,
    verification_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_collected_at TIMESTAMPTZ,
    last_collection_run_id BIGINT REFERENCES research.company_ir_collection_runs(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_company_ir_source_exchange CHECK (exchange IN ('NSE','BSE')),
    CONSTRAINT chk_company_ir_source_kind CHECK (source_kind IN ('ir_page','annual_report_pdf')),
    CONSTRAINT chk_company_ir_source_status CHECK (status IN ('active','paused','rejected')),
    CONSTRAINT chk_company_ir_source_https CHECK (source_url ~ '^https://'),
    CONSTRAINT chk_company_ir_source_document_year CHECK (
        (source_kind='ir_page' AND fiscal_year_end IS NULL)
        OR (source_kind='annual_report_pdf' AND fiscal_year_end BETWEEN 2001 AND 2100)
    ),
    UNIQUE (exchange, symbol, source_url)
);

CREATE INDEX IF NOT EXISTS idx_company_ir_sources_active
ON research.company_ir_sources (exchange, symbol, source_kind, fiscal_year_end DESC)
WHERE status='active';

CREATE OR REPLACE VIEW research.v_company_ir_source_readiness AS
SELECT source.id, source.symbol, source.exchange, source.company_name,
       source.source_kind, source.source_url, source.fiscal_year_end,
       source.document_label, source.status, source.verified_at, source.verified_by,
       source.last_collected_at, source.last_collection_run_id,
       run.status AS last_collection_status,
       run.reports_upserted AS last_reports_upserted,
       run.error_message AS last_collection_error,
       false AS broker_write_allowed
FROM research.company_ir_sources source
LEFT JOIN research.company_ir_collection_runs run ON run.id=source.last_collection_run_id;

COMMENT ON TABLE research.company_ir_sources IS
    'Operator-verified primary-source IR endpoints. Registration and collection are auditable; sources never create capital actions or reviewed financial facts directly.';

COMMIT;
