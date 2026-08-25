BEGIN;

CREATE OR REPLACE VIEW research.v_company_fundamental_coverage AS
WITH statement_coverage AS (
    SELECT
        company_id,
        count(DISTINCT fiscal_year) FILTER (
            WHERE is_current AND fiscal_period = 'FY'
        ) AS annual_statement_years,
        min(fiscal_year) FILTER (
            WHERE is_current AND fiscal_period = 'FY'
        ) AS first_statement_year,
        max(fiscal_year) FILTER (
            WHERE is_current AND fiscal_period = 'FY'
        ) AS latest_statement_year,
        max(available_at) AS latest_statement_available_at
    FROM research.company_statement_facts
    GROUP BY company_id
), evidence_coverage AS (
    SELECT company_id, max(retrieved_at) AS latest_evidence_retrieved_at
    FROM research.fundamental_evidence
    GROUP BY company_id
), segment_coverage AS (
    SELECT company_id, count(*) AS segment_count
    FROM research.company_segments
    GROUP BY company_id
), kpi_coverage AS (
    SELECT company_id, count(*) AS operational_kpi_count
    FROM research.operational_kpi_definitions
    GROUP BY company_id
), market_share_coverage AS (
    SELECT company_id, count(DISTINCT market_key) AS market_share_series_count
    FROM research.market_share_observations
    GROUP BY company_id
), peer_coverage AS (
    SELECT peer_set.subject_company_id AS company_id,
           count(DISTINCT membership.peer_company_id) AS peer_count
    FROM research.peer_sets peer_set
    LEFT JOIN research.peer_set_memberships membership
      ON membership.peer_set_id = peer_set.id
    GROUP BY peer_set.subject_company_id
), communication_coverage AS (
    SELECT company_id, count(*) AS management_communication_count
    FROM research.management_communications
    GROUP BY company_id
), claim_coverage AS (
    SELECT claim.company_id,
           count(DISTINCT claim.id) AS management_claim_count,
           count(DISTINCT outcome.claim_id) AS claims_with_outcomes
    FROM research.management_claims claim
    LEFT JOIN research.management_claim_outcomes outcome
      ON outcome.claim_id = claim.id
    GROUP BY claim.company_id
)
SELECT
    company.id AS company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    company.primary_exchange,
    company.real_company_verified_at IS NOT NULL AS real_company_verified,
    coalesce(statement.annual_statement_years, 0) AS annual_statement_years,
    statement.first_statement_year,
    statement.latest_statement_year,
    coalesce(segment.segment_count, 0) AS segment_count,
    coalesce(kpi.operational_kpi_count, 0) AS operational_kpi_count,
    coalesce(market_share.market_share_series_count, 0) AS market_share_series_count,
    coalesce(peer.peer_count, 0) AS peer_count,
    coalesce(communication.management_communication_count, 0) AS management_communication_count,
    coalesce(claim.management_claim_count, 0) AS management_claim_count,
    coalesce(claim.claims_with_outcomes, 0) AS claims_with_outcomes,
    statement.latest_statement_available_at,
    evidence.latest_evidence_retrieved_at
FROM research.companies company
LEFT JOIN statement_coverage statement ON statement.company_id = company.id
LEFT JOIN evidence_coverage evidence ON evidence.company_id = company.id
LEFT JOIN segment_coverage segment ON segment.company_id = company.id
LEFT JOIN kpi_coverage kpi ON kpi.company_id = company.id
LEFT JOIN market_share_coverage market_share ON market_share.company_id = company.id
LEFT JOIN peer_coverage peer ON peer.company_id = company.id
LEFT JOIN communication_coverage communication ON communication.company_id = company.id
LEFT JOIN claim_coverage claim ON claim.company_id = company.id;

CREATE OR REPLACE VIEW research.v_company_intake_status AS
WITH position_coverage AS (
    SELECT
        link.company_id,
        count(DISTINCT link.position_id) AS linked_position_count,
        count(DISTINCT link.account_id) AS linked_account_count,
        coalesce(sum(abs(position.market_value)), 0) AS gross_market_value,
        max(link.position_as_of) AS latest_position_at
    FROM research.company_position_links link
    LEFT JOIN portfolio.positions position ON position.id = link.position_id
    GROUP BY link.company_id
), evidence_coverage AS (
    SELECT
        company_id,
        count(*) AS filing_evidence_count,
        max(retrieved_at) AS latest_evidence_at
    FROM research.fundamental_evidence
    GROUP BY company_id
)
SELECT
    company.id AS company_id,
    company.company_key,
    company.legal_name,
    company.primary_symbol,
    company.primary_exchange,
    company.real_company_verified_at IS NOT NULL AS identity_verified,
    coalesce(position.linked_position_count, 0) AS linked_position_count,
    coalesce(position.linked_account_count, 0) AS linked_account_count,
    coalesce(position.gross_market_value, 0) AS gross_market_value,
    position.latest_position_at,
    coalesce(evidence.filing_evidence_count, 0) AS filing_evidence_count,
    evidence.latest_evidence_at,
    coverage.annual_statement_years,
    coverage.segment_count,
    coverage.operational_kpi_count,
    coverage.market_share_series_count,
    coverage.peer_count,
    coverage.management_communication_count,
    CASE
        WHEN company.real_company_verified_at IS NULL THEN 'identity_evidence_required'
        WHEN coverage.annual_statement_years < 10 THEN 'financial_history_required'
        WHEN coverage.segment_count = 0 THEN 'segment_history_required'
        WHEN coverage.operational_kpi_count = 0 THEN 'operational_kpis_required'
        WHEN coverage.peer_count = 0 THEN 'peer_set_required'
        ELSE 'factory_ready'
    END AS next_required_action,
    false AS capital_action_allowed,
    false AS broker_write_allowed
FROM research.companies company
LEFT JOIN position_coverage position ON position.company_id = company.id
LEFT JOIN evidence_coverage evidence ON evidence.company_id = company.id
LEFT JOIN research.v_company_fundamental_coverage coverage
  ON coverage.company_id = company.id;

COMMENT ON VIEW research.v_company_fundamental_coverage IS
'Company-level institutional research coverage using independent aggregates to avoid cross-product inflation and dashboard timeouts.';

COMMENT ON VIEW research.v_company_intake_status IS
'Real-company research intake readiness with independently aggregated positions and evidence. Capital and broker actions remain disabled.';

COMMIT;
