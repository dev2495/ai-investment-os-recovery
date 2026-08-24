\set ON_ERROR_STOP on

BEGIN;

-- Research Desk v1 deliberately executes user-facing graph, Following and
-- scanner queries under a NOLOGIN, RLS-constrained runtime role. Those
-- services also need a small, explicit set of legacy facts as read-only
-- inputs. Keep this list closed: do not grant schema-wide table access.
GRANT USAGE ON SCHEMA agent, market, research, trading TO ai_os_research_runtime;

GRANT SELECT ON
    agent.approvals,
    market.universe_memberships,
    research.companies,
    research.company_statement_facts,
    research.corporate_filings,
    research.financial_formula_definitions,
    research.financial_ratio_inputs,
    research.financial_ratio_results,
    research.statement_fact_definitions,
    trading.symbols
TO ai_os_research_runtime;

-- The runtime remains research-only. These assertions fail the migration if
-- a future grant accidentally broadens it into a destructive or trading role.
DO $least_privilege_guard$
BEGIN
    IF has_table_privilege('ai_os_research_runtime', 'research.companies', 'INSERT')
       OR has_table_privilege('ai_os_research_runtime', 'research.companies', 'UPDATE')
       OR has_table_privilege('ai_os_research_runtime', 'research.companies', 'DELETE')
       OR has_table_privilege('ai_os_research_runtime', 'agent.approvals', 'INSERT')
       OR has_table_privilege('ai_os_research_runtime', 'agent.approvals', 'UPDATE')
       OR has_table_privilege('ai_os_research_runtime', 'trading.symbols', 'INSERT')
       OR has_table_privilege('ai_os_research_runtime', 'trading.symbols', 'UPDATE')
       OR has_table_privilege('ai_os_research_runtime', 'trading.symbols', 'DELETE')
    THEN
        RAISE EXCEPTION 'research runtime legacy contract is broader than read-only';
    END IF;

    IF has_schema_privilege('ai_os_research_runtime', 'portfolio', 'USAGE')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'SELECT')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'INSERT')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'UPDATE')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'DELETE')
    THEN
        RAISE EXCEPTION 'research runtime must not gain portfolio or order access';
    END IF;
END
$least_privilege_guard$;

INSERT INTO core.schema_migrations (
    migration_number, migration_key, definition_checksum_sha256, description, metadata
)
VALUES (
    248,
    '248_research_runtime_legacy_read_contract_v1',
    'b71ec43e4cb61120afbe12bfd13f30134dcac6aa0bb75a5e349af8613e282a12',
    'Minimal read-only legacy inputs for scoped Research Following and deterministic scanners',
    '{"read_only":true,"broker_write_allowed":false,"portfolio_access":false,"private_storage":"external_ssd"}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

DO $migration_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM core.schema_migrations
        WHERE migration_number = 248
          AND migration_key = '248_research_runtime_legacy_read_contract_v1'
          AND definition_checksum_sha256 = 'b71ec43e4cb61120afbe12bfd13f30134dcac6aa0bb75a5e349af8613e282a12'
    ) THEN
        RAISE EXCEPTION 'migration 248 ledger mismatch';
    END IF;
END
$migration_guard$;

COMMIT;
