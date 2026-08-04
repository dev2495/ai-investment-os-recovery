BEGIN;

CREATE TABLE IF NOT EXISTS research.company_intake_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    requested_symbol TEXT,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','failed')),
    holding_candidates INTEGER NOT NULL DEFAULT 0,
    companies_upserted INTEGER NOT NULL DEFAULT 0,
    position_links_upserted INTEGER NOT NULL DEFAULT 0,
    filing_evidence_upserted INTEGER NOT NULL DEFAULT 0,
    identities_verified INTEGER NOT NULL DEFAULT 0,
    started_by TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false
        CHECK (capital_action_allowed=false),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false
        CHECK (broker_write_allowed=false)
);

CREATE TABLE IF NOT EXISTS research.company_position_links (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
    position_id BIGINT NOT NULL REFERENCES portfolio.positions(id) ON DELETE CASCADE,
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id) ON DELETE CASCADE,
    position_as_of TIMESTAMPTZ NOT NULL,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (position_id)
);

CREATE INDEX IF NOT EXISTS idx_company_position_links_company
ON research.company_position_links (company_id, position_as_of DESC);

CREATE OR REPLACE FUNCTION research.sync_real_company_intake(
    p_started_by TEXT DEFAULT 'Fundamental Research Factory',
    p_symbol TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id BIGINT;
    v_run_key TEXT;
    v_candidates INTEGER := 0;
    v_companies INTEGER := 0;
    v_links INTEGER := 0;
    v_evidence INTEGER := 0;
    v_verified INTEGER := 0;
    v_symbol TEXT := nullif(upper(trim(p_symbol)), '');
    v_result JSONB;
BEGIN
    IF v_symbol IS NOT NULL AND v_symbol !~ '^[A-Z0-9._&-]{1,40}$' THEN
        RAISE EXCEPTION 'unsupported symbol format';
    END IF;

    v_run_key := 'fundamental-intake-' || coalesce(lower(v_symbol), 'all') || '-' ||
        to_char(clock_timestamp(), 'YYYYMMDDHH24MISSUS');

    INSERT INTO research.company_intake_runs (run_key, requested_symbol, started_by)
    VALUES (v_run_key, v_symbol, p_started_by)
    RETURNING id INTO v_run_id;

    SELECT count(*) INTO v_candidates
    FROM (
        SELECT DISTINCT upper(position.symbol), upper(position.exchange)
        FROM portfolio.positions position
        WHERE position.quantity <> 0
          AND upper(position.exchange) IN ('NSE','BSE')
          AND (v_symbol IS NULL OR upper(position.symbol)=v_symbol)
    ) candidates;

    WITH holdings AS (
        SELECT upper(position.symbol) AS symbol, upper(position.exchange) AS exchange,
               max(nullif(trim(symbol.name), '')) AS symbol_name,
               max(position.as_of) AS latest_position_at,
               count(*) AS position_count
        FROM portfolio.positions position
        LEFT JOIN trading.symbols symbol
          ON upper(symbol.symbol)=upper(position.symbol)
         AND upper(symbol.exchange)=upper(position.exchange)
        WHERE position.quantity <> 0
          AND upper(position.exchange) IN ('NSE','BSE')
          AND (v_symbol IS NULL OR upper(position.symbol)=v_symbol)
        GROUP BY upper(position.symbol), upper(position.exchange)
    ), candidates AS (
        SELECT holding.*,
               filing.id AS official_filing_id,
               nullif(trim(filing.company_name), '') AS official_company_name,
               filing.source_url AS official_source_url,
               filing.filed_at AS official_filed_at
        FROM holdings holding
        LEFT JOIN LATERAL (
            SELECT item.*
            FROM research.corporate_filings item
            WHERE upper(item.symbol)=holding.symbol
              AND upper(item.exchange)=holding.exchange
              AND item.source_url IS NOT NULL
            ORDER BY item.filed_at DESC, item.id DESC
            LIMIT 1
        ) filing ON true
    )
    INSERT INTO research.companies (
        company_key, legal_name, display_name, primary_symbol, primary_exchange,
        reporting_currency, status, identifiers, metadata, updated_at
    )
    SELECT lower(exchange) || ':' || lower(regexp_replace(symbol, '[^A-Za-z0-9]+', '-', 'g')),
           coalesce(official_company_name, symbol_name, symbol),
           coalesce(official_company_name, symbol_name, symbol),
           symbol, exchange, 'INR', 'active',
           jsonb_build_object('exchange', exchange, 'symbol', symbol),
           jsonb_build_object(
               'intake_source', 'portfolio.positions',
               'identity_source', CASE WHEN official_filing_id IS NOT NULL
                   THEN 'official_exchange_filing' ELSE 'symbol_master_or_position' END,
               'identity_verified', official_filing_id IS NOT NULL,
               'official_filing_id', official_filing_id,
               'official_source_url', official_source_url,
               'latest_position_at', latest_position_at,
               'position_count', position_count,
               'financial_coverage_inferred', false
           ), now()
    FROM candidates
    ON CONFLICT (primary_exchange, primary_symbol) DO UPDATE SET
        legal_name=CASE
            WHEN EXCLUDED.metadata->>'identity_source'='official_exchange_filing'
                THEN EXCLUDED.legal_name
            ELSE research.companies.legal_name
        END,
        display_name=CASE
            WHEN EXCLUDED.metadata->>'identity_source'='official_exchange_filing'
                THEN EXCLUDED.display_name
            ELSE coalesce(research.companies.display_name, EXCLUDED.display_name)
        END,
        identifiers=research.companies.identifiers || EXCLUDED.identifiers,
        metadata=research.companies.metadata || EXCLUDED.metadata,
        updated_at=now();
    GET DIAGNOSTICS v_companies = ROW_COUNT;

    INSERT INTO research.fundamental_evidence (
        company_id, corporate_filing_id, source_type, source_name, source_url,
        source_title, published_at, retrieved_at, source_as_of_date,
        content_hash, extraction_method, verification_status,
        source_locator, metadata
    )
    SELECT company.id, filing.id, 'corporate_filing', filing.source_name,
           filing.source_url, filing.title, filing.filed_at, filing.created_at,
           filing.filed_at::date, filing.content_hash, 'official_exchange_collector',
           CASE WHEN nullif(trim(coalesce(filing.extracted_text,'')), '') IS NOT NULL
                THEN 'machine_extracted' ELSE 'unverified' END,
           jsonb_build_object(
               'exchange', filing.exchange, 'symbol', filing.symbol,
               'corporate_filing_id', filing.id,
               'attachment_url', filing.attachment_url
           ),
           jsonb_build_object(
               'event_type', filing.event_type,
               'filing_type', filing.filing_type,
               'official_exchange_source', true,
               'financial_facts_extracted', false
           )
    FROM research.companies company
    JOIN research.corporate_filings filing
      ON upper(filing.symbol)=company.primary_symbol
     AND upper(filing.exchange)=company.primary_exchange
    WHERE (v_symbol IS NULL OR company.primary_symbol=v_symbol)
      AND filing.source_url IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM research.fundamental_evidence existing
          WHERE existing.corporate_filing_id=filing.id
      );
    GET DIAGNOSTICS v_evidence = ROW_COUNT;

    INSERT INTO research.company_position_links (
        company_id, position_id, account_id, position_as_of, source_system_id
    )
    SELECT company.id, position.id, position.account_id, position.as_of,
           position.source_system_id
    FROM portfolio.positions position
    JOIN research.companies company
      ON company.primary_symbol=upper(position.symbol)
     AND company.primary_exchange=upper(position.exchange)
    WHERE position.quantity <> 0
      AND upper(position.exchange) IN ('NSE','BSE')
      AND (v_symbol IS NULL OR upper(position.symbol)=v_symbol)
    ON CONFLICT (position_id) DO UPDATE SET
        company_id=EXCLUDED.company_id,
        account_id=EXCLUDED.account_id,
        position_as_of=EXCLUDED.position_as_of,
        source_system_id=EXCLUDED.source_system_id,
        updated_at=now();
    GET DIAGNOSTICS v_links = ROW_COUNT;

    WITH official_identity AS (
        SELECT DISTINCT ON (evidence.company_id)
               evidence.company_id, evidence.id AS evidence_id,
               coalesce(evidence.published_at, evidence.retrieved_at) AS verified_at
        FROM research.fundamental_evidence evidence
        JOIN research.corporate_filings filing ON filing.id=evidence.corporate_filing_id
        WHERE filing.source_url IS NOT NULL
          AND upper(filing.exchange) IN ('NSE','BSE')
          AND (v_symbol IS NULL OR upper(filing.symbol)=v_symbol)
        ORDER BY evidence.company_id,
                 coalesce(evidence.published_at, evidence.retrieved_at) DESC,
                 evidence.id DESC
    )
    UPDATE research.companies company
    SET real_company_verified_at=coalesce(company.real_company_verified_at, identity.verified_at),
        real_company_verification_evidence_id=coalesce(
            company.real_company_verification_evidence_id, identity.evidence_id
        ),
        metadata=company.metadata || jsonb_build_object(
            'identity_verified', true,
            'identity_verification_method', 'official_exchange_filing',
            'financial_coverage_inferred', false
        ),
        updated_at=now()
    FROM official_identity identity
    WHERE company.id=identity.company_id
      AND company.real_company_verification_evidence_id IS NULL;
    GET DIAGNOSTICS v_verified = ROW_COUNT;

    v_result := jsonb_build_object(
        'run_id', v_run_id,
        'run_key', v_run_key,
        'status', 'completed',
        'requested_symbol', v_symbol,
        'holding_candidates', v_candidates,
        'companies_upserted', v_companies,
        'position_links_upserted', v_links,
        'filing_evidence_upserted', v_evidence,
        'identities_verified', v_verified,
        'capital_action_allowed', false,
        'broker_write_allowed', false,
        'financial_statements_inferred', false
    );

    UPDATE research.company_intake_runs
    SET status='completed', holding_candidates=v_candidates,
        companies_upserted=v_companies, position_links_upserted=v_links,
        filing_evidence_upserted=v_evidence, identities_verified=v_verified,
        finished_at=now(), summary=v_result
    WHERE id=v_run_id;

    RETURN v_result;
EXCEPTION WHEN OTHERS THEN
    IF v_run_id IS NOT NULL THEN
        UPDATE research.company_intake_runs
        SET status='failed', finished_at=now(), error_message=SQLERRM
        WHERE id=v_run_id;
    END IF;
    RAISE;
END;
$$;

CREATE OR REPLACE VIEW research.v_company_intake_status AS
SELECT company.id AS company_id, company.company_key, company.legal_name,
       company.primary_symbol, company.primary_exchange,
       company.real_company_verified_at IS NOT NULL AS identity_verified,
       count(DISTINCT link.position_id) AS linked_position_count,
       count(DISTINCT link.account_id) AS linked_account_count,
       coalesce(sum(abs(position.market_value)),0) AS gross_market_value,
       max(link.position_as_of) AS latest_position_at,
       count(DISTINCT evidence.id) AS filing_evidence_count,
       max(evidence.retrieved_at) AS latest_evidence_at,
       coverage.annual_statement_years,
       coverage.segment_count,
       coverage.operational_kpi_count,
       coverage.market_share_series_count,
       coverage.peer_count,
       coverage.management_communication_count,
       CASE
           WHEN company.real_company_verified_at IS NULL THEN 'identity_evidence_required'
           WHEN coverage.annual_statement_years < 10 THEN 'financial_history_required'
           WHEN coverage.segment_count=0 THEN 'segment_history_required'
           WHEN coverage.operational_kpi_count=0 THEN 'operational_kpis_required'
           WHEN coverage.peer_count=0 THEN 'peer_set_required'
           ELSE 'factory_ready'
       END AS next_required_action,
       false AS capital_action_allowed,
       false AS broker_write_allowed
FROM research.companies company
LEFT JOIN research.company_position_links link ON link.company_id=company.id
LEFT JOIN portfolio.positions position ON position.id=link.position_id
LEFT JOIN research.fundamental_evidence evidence ON evidence.company_id=company.id
LEFT JOIN research.v_company_fundamental_coverage coverage ON coverage.company_id=company.id
GROUP BY company.id, coverage.annual_statement_years, coverage.segment_count,
         coverage.operational_kpi_count, coverage.market_share_series_count,
         coverage.peer_count, coverage.management_communication_count;

COMMENT ON FUNCTION research.sync_real_company_intake IS
    'Idempotently links real portfolio positions to the institutional company master and official exchange filing evidence. It never invents financial facts, scores, recommendations, capital actions, or broker writes.';

COMMIT;
